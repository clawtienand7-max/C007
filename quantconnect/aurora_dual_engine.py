# -*- coding: utf-8 -*-
"""
雙向極光防禦策略 (Aurora Dual-Engine Strategy) — QuantConnect LEAN 交叉驗證

趨勢跟隨 + 波動率克制；ATR 風險配倉 + 非對稱多空追蹤止損 + 單日熔斷 + 週五減倉。
參數對齊 docs/aurora-dual-engine-blueprint.md 第七節。
驗收：回測報告 Profit Factor > 1.5 且 Max Drawdown <= 8%。

直接貼上 QuantConnect 雲端 IDE（演算法名沿用 class 名）即可回測。
"""

from AlgorithmImports import *


class AuroraDualEngineStrategy(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100000)

        # ---- 統一參數 ----
        self.ema_fast_len = 50
        self.ema_slow_len = 200
        self.bb_len = 20
        self.bb_mult = 2.0
        self.atr_len = 14
        self.risk_per_trade = 1000.0
        self.long_atr_mult = 2.0      # 改進#1：好倉止損系數
        self.short_atr_mult = 1.5     # 改進#1：淡倉止損系數（收緊）
        self.daily_dd_pct = 0.02      # 單日熔斷 -2%
        self.friday_trim_ratio = 0.50 # 改進#2

        # 標的（換成港股可改用對應 symbol；此處用 SPY 作通用驗證）
        self.symbol = self.add_equity("SPY", Resolution.HOUR).symbol

        # ---- 指標 ----
        self.ema_fast = self.ema(self.symbol, self.ema_fast_len, Resolution.HOUR)
        self.ema_slow = self.ema(self.symbol, self.ema_slow_len, Resolution.HOUR)
        self.bb_ind = self.bb(self.symbol, self.bb_len, self.bb_mult, Resolution.HOUR)
        self.atr_ind = self.atr(self.symbol, self.atr_len, MovingAverageType.WILDERS,
                                Resolution.HOUR)
        self.set_warm_up(self.ema_slow_len, Resolution.HOUR)

        # ---- 全局變量「記憶盒」----
        self.position_state = 0       # 0 空 / 1 好 / -1 淡
        self.dynamic_high = 0.0
        self.dynamic_low = 99999.0
        self.daily_dd_line = 0.0
        self.halted_today = False

        # 路徑一：每日 09:15（美股換成開市後）對賬
        self.schedule.on(self.date_rules.every_day(self.symbol),
                         self.time_rules.after_market_open(self.symbol, 1),
                         self.daily_init)
        # 改進#2：週五尾盤減倉
        self.schedule.on(self.date_rules.every_day(self.symbol),
                         self.time_rules.before_market_close(self.symbol, 10),
                         self.friday_trim)

    # ---- 路徑三：ATR 風險配倉 ----
    def position_size(self, price):
        atr = self.atr_ind.current.value
        if atr <= 0 or price <= 0:
            return 0
        cash_for_risk = self.risk_per_trade / (atr * 2.0)  # 以 ATR 反推可承受股數
        shares = int(cash_for_risk)
        # 用組合可用資金做上限保護，避免槓桿爆倉
        max_shares = int(self.portfolio.cash / price)
        return max(0, min(shares, max_shares))

    # ---- 路徑一：開市對賬，鎖定當日熔斷線 ----
    def daily_init(self):
        self.daily_dd_line = self.portfolio.total_portfolio_value * (1.0 - self.daily_dd_pct)
        self.halted_today = False

    # ---- 改進#2：週五尾盤強制減倉 50% ----
    def friday_trim(self):
        if self.time.weekday() != 4:  # 4 = Friday
            return
        holding = self.portfolio[self.symbol]
        if not holding.invested:
            return
        target = holding.quantity * (1.0 - self.friday_trim_ratio)
        self.market_order(self.symbol, int(target - holding.quantity))

    # ---- 平倉 + 變量重置 ----
    def flatten(self, reason):
        if self.portfolio[self.symbol].invested:
            self.liquidate(self.symbol, tag=reason)
        self.position_state = 0
        self.dynamic_high = 0.0
        self.dynamic_low = 99999.0

    def on_data(self, data):
        if self.is_warming_up or not data.contains_key(self.symbol):
            return
        if not (self.ema_fast.is_ready and self.ema_slow.is_ready
                and self.bb_ind.is_ready and self.atr_ind.is_ready):
            return

        bar = data[self.symbol]
        if bar is None:
            return
        price = bar.close
        atr = self.atr_ind.current.value

        # 路徑一：盤中熔斷監控
        if not self.halted_today and \
                self.portfolio.total_portfolio_value < self.daily_dd_line:
            self.flatten("單日熔斷")
            self.halted_today = True
        if self.halted_today:
            return

        # 路徑四：雙向動態追蹤止損（非對稱）
        if self.position_state == 1:
            self.dynamic_high = max(self.dynamic_high, bar.high)
            if price < self.dynamic_high - self.long_atr_mult * atr:
                self.flatten("好倉移動止損")
                return
        elif self.position_state == -1:
            self.dynamic_low = min(self.dynamic_low, bar.low)
            if price > self.dynamic_low + self.short_atr_mult * atr:
                self.flatten("淡倉移動止損")
                return

        # 信號
        long_signal = price > self.bb_ind.upper_band.current.value and \
            self.ema_fast.current.value > self.ema_slow.current.value
        short_signal = price < self.bb_ind.lower_band.current.value and \
            self.ema_fast.current.value < self.ema_slow.current.value

        # 路徑二：開倉與自動切換（先平反向，再開新倉）
        if long_signal and self.position_state != 1:
            self.flatten("切換前先平倉")
            qty = self.position_size(price)
            if qty > 0:
                self.market_order(self.symbol, qty, tag="開好倉")
                self.position_state = 1
                self.dynamic_high = price
        elif short_signal and self.position_state != -1:
            self.flatten("切換前先平倉")
            qty = self.position_size(price)
            if qty > 0:
                self.market_order(self.symbol, -qty, tag="開淡倉")
                self.position_state = -1
                self.dynamic_low = price
