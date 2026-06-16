# -*- coding: utf-8 -*-
"""
雙向極光防禦策略 (Aurora Dual-Engine Strategy)
富途 OpenAPI (futu-api) 參考實作。

呢個檔案將藍圖嘅四條卡片路徑落地成可執行程式：
  路徑一：開市初始化與每日對賬 + 週五減倉 + 盤中熔斷
  路徑二：多空信號開倉與自動切換引擎（含三步走防鎖倉閉環）
  路徑三：ATR 風險配倉引擎
  路徑四：雙向動態追蹤止損防線

使用前提：本機已開 FutuOpenD，並登入相應賬戶。
預設行喺 TrdEnv.SIMULATE（模擬倉），確認穩定後先改 REAL。

依賴：pip install futu-api pandas
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, time as dtime

import pandas as pd

try:
    from futu import (
        OpenQuoteContext, OpenSecTradeContext,
        TrdMarket, SecurityFirm, TrdEnv, TrdSide, OrderType,
        SubType, KLType, RET_OK,
    )
except ImportError:  # 允許喺未安裝 futu-api 嘅環境睇 / 跑單元測試
    OpenQuoteContext = OpenSecTradeContext = None
    RET_OK = 0


# =============================================================================
# 策略參數（三平台統一，對齊 docs/aurora-dual-engine-blueprint.md 第七節）
# =============================================================================
@dataclass
class Params:
    code: str = "HK.00700"          # 標的
    ema_fast: int = 50
    ema_slow: int = 200
    bb_period: int = 20
    bb_mult: float = 2.0
    atr_period: int = 14
    risk_per_trade: float = 1000.0  # 每筆風險金額 (HKD)
    long_atr_mult: float = 2.0      # 改進#1：好倉止損系數
    short_atr_mult: float = 1.5     # 改進#1：淡倉止損系數（收緊）
    daily_dd_pct: float = 0.02      # 單日最大容忍虧損 2%
    reversal_delay_ms: int = 200    # 反向切換訂單隊列清空延時
    friday_cut_time: dtime = dtime(15, 50)  # 改進#2：週五尾盤減倉時間
    friday_cut_ratio: float = 0.50          # 砍 50%
    lot_size: int = 100             # 港股一手股數
    trd_env: str = "SIMULATE"       # SIMULATE / REAL


# =============================================================================
# 全局變量「記憶盒」（藍圖第二節）
# =============================================================================
@dataclass
class GlobalState:
    position_state: int = 0          # 0 空倉 / 1 好倉 / -1 淡倉
    dynamic_high: float = 0.0        # 好倉移動止損追蹤高位
    dynamic_low: float = 99999.0     # 淡倉移動止損追蹤低位
    daily_dd_line: float = 0.0       # 今日回撤警戒線
    risk_per_trade: float = 1000.0   # 每筆風險金額
    halted_today: bool = False       # 全日熔斷罷工旗標
    qty: int = 0                     # 當前持倉股數

    def reset_position(self):
        """任何平倉動作完成後必須重置（藍圖第二節重置規範）。"""
        self.position_state = 0
        self.dynamic_high = 0.0
        self.dynamic_low = 99999.0
        self.qty = 0


# =============================================================================
# 技術指標計算（由 K 線 DataFrame 計出 EMA / 布林 / ATR）
# =============================================================================
def compute_indicators(df: pd.DataFrame, p: Params) -> dict:
    close = df["close"]
    high, low = df["high"], df["low"]

    ema_fast = close.ewm(span=p.ema_fast, adjust=False).mean().iloc[-1]
    ema_slow = close.ewm(span=p.ema_slow, adjust=False).mean().iloc[-1]

    basis = close.rolling(p.bb_period).mean().iloc[-1]
    dev = close.rolling(p.bb_period).std(ddof=0).iloc[-1] * p.bb_mult
    bb_upper, bb_lower = basis + dev, basis - dev

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / p.atr_period, adjust=False).mean().iloc[-1]

    return {
        "close": close.iloc[-1],
        "ema_fast": ema_fast, "ema_slow": ema_slow,
        "bb_upper": bb_upper, "bb_lower": bb_lower,
        "atr": float(atr),
    }


def position_size(risk_per_trade: float, atr: float, p: Params) -> int:
    """路徑三：ATR 風險配倉。下單股數 = 風險金額 / (ATR × 2)，向下取整到一手。"""
    if atr <= 0:
        return 0
    raw = risk_per_trade / (atr * 2.0)
    lots = int(raw // p.lot_size)
    return lots * p.lot_size


# =============================================================================
# 策略主體
# =============================================================================
class AuroraStrategy:
    def __init__(self, params: Params | None = None,
                 host: str = "127.0.0.1", port: int = 11111):
        self.p = params or Params()
        self.s = GlobalState(risk_per_trade=self.p.risk_per_trade)
        self.host, self.port = host, port
        self.quote_ctx = None
        self.trd_ctx = None
        self._env = TrdEnv.SIMULATE if self.p.trd_env == "SIMULATE" else TrdEnv.REAL

    # ---- 連線管理（異常自癒：斷線可重複調用） ----
    def connect(self):
        self.quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
        self.trd_ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.HK, host=self.host, port=self.port,
            security_firm=SecurityFirm.FUTUSECURITIES,
        )
        self.quote_ctx.subscribe([self.p.code],
                                 [SubType.K_DAY, SubType.K_1M, SubType.QUOTE])

    def close(self):
        if self.quote_ctx:
            self.quote_ctx.close()
        if self.trd_ctx:
            self.trd_ctx.close()

    # ---- 賬戶輔助 ----
    def _equity(self) -> float:
        ret, data = self.trd_ctx.accinfo_query(trd_env=self._env)
        return float(data["total_assets"][0]) if ret == RET_OK else 0.0

    def _position_qty(self) -> int:
        ret, data = self.trd_ctx.position_list_query(
            code=self.p.code, trd_env=self._env)
        if ret != RET_OK or data.empty:
            return 0
        return int(data["qty"][0])

    def _market_order(self, side, qty: int) -> bool:
        if qty <= 0:
            return True
        ret, _ = self.trd_ctx.place_order(
            price=0, qty=qty, code=self.p.code, trd_side=side,
            order_type=OrderType.MARKET, trd_env=self._env,
        )
        return ret == RET_OK

    def _klines(self, ktype, num: int = 250) -> pd.DataFrame:
        ret, df = self.quote_ctx.get_cur_kline(self.p.code, num, ktype)
        return df if ret == RET_OK else pd.DataFrame()

    # =========================================================================
    # 路徑一：開市初始化與每日對賬（每日 09:15）
    # =========================================================================
    def path1_daily_init(self, now: datetime | None = None):
        now = now or datetime.now()
        equity = self._equity()
        self.s.daily_dd_line = equity * (1.0 - self.p.daily_dd_pct)
        self.s.halted_today = False
        print(f"[路徑一] 開市對賬 資產={equity:.0f} 熔斷線={self.s.daily_dd_line:.0f}")

        # 改進#2：週五尾盤強制減倉 50%
        if now.weekday() == 4 and now.time() >= self.p.friday_cut_time:
            self._friday_trim()

    def _friday_trim(self):
        held = self._position_qty()
        if held == 0:
            return
        cut = int(abs(held) // self.p.lot_size * self.p.friday_cut_ratio)
        cut *= self.p.lot_size
        if cut <= 0:
            return
        side = TrdSide.SELL if self.s.position_state == 1 else TrdSide.BUY
        if self._market_order(side, cut):
            self.s.qty = abs(held) - cut
            print(f"[路徑一/改進#2] 週五尾盤強制減倉 {cut} 股，餘 {self.s.qty}")

    def check_circuit_breaker(self) -> bool:
        """盤中監控：跌穿熔斷線 → 全線清倉並全日罷工。"""
        if self.s.halted_today:
            return True
        if self._equity() < self.s.daily_dd_line:
            self._flatten()
            self.s.halted_today = True
            print("[路徑一] ⚠️ 觸發單日熔斷，全線清倉並罷工至明日 09:15")
            return True
        return False

    # =========================================================================
    # 路徑二：多空信號開倉與自動切換引擎（每根 K 線收盤）
    # =========================================================================
    def path2_on_bar_close(self):
        if self.check_circuit_breaker():
            return

        df = self._klines(KLType.K_1M, max(self.p.ema_slow + 5, 250))
        if len(df) < self.p.ema_slow:
            return
        ind = compute_indicators(df, self.p)

        long_signal = ind["close"] > ind["bb_upper"] and ind["ema_fast"] > ind["ema_slow"]
        short_signal = ind["close"] < ind["bb_lower"] and ind["ema_fast"] < ind["ema_slow"]

        if long_signal:
            self._enter(direction=1, atr=ind["atr"], price=ind["close"])
        elif short_signal:
            self._enter(direction=-1, atr=ind["atr"], price=ind["close"])

    def _enter(self, direction: int, atr: float, price: float):
        # 已持同向倉 → 唔重複開
        if self.s.position_state == direction:
            return

        # 三步走防鎖倉閉環：先平反向 → 確認 0 倉 → 再開新倉（藍圖第五節）
        if self.s.position_state != 0:
            if not self._flatten():
                print("[路徑二] 平倉失敗，放棄本次切換（自癒：等下一根 K 線重試）")
                return
            time.sleep(self.p.reversal_delay_ms / 1000.0)
            if self._position_qty() != 0:
                print("[路徑二] 確認倉位非 0，中止開倉避免鎖倉")
                return

        # 路徑三：ATR 配倉
        qty = position_size(self.s.risk_per_trade, atr, self.p)
        if qty <= 0:
            print("[路徑三] 計算股數為 0（ATR 過大），本次不開倉")
            return

        side = TrdSide.BUY if direction == 1 else TrdSide.SELL
        if self._market_order(side, qty):
            self.s.position_state = direction
            self.s.qty = qty
            self.s.dynamic_high = price if direction == 1 else 0.0
            self.s.dynamic_low = price if direction == -1 else 99999.0
            tag = "好倉 Long" if direction == 1 else "淡倉 Short"
            print(f"[路徑二/三] 開{tag} {qty} 股 @≈{price:.2f} (ATR={atr:.3f})")

    # =========================================================================
    # 路徑四：雙向動態追蹤止損防線（Tick 級刷新）
    # =========================================================================
    def path4_on_tick(self, price: float, atr: float):
        if self.s.position_state == 1:                       # 好倉防線 2.0×ATR
            if price > self.s.dynamic_high:
                self.s.dynamic_high = price
            if price < self.s.dynamic_high - self.p.long_atr_mult * atr:
                self._flatten()
                print(f"[路徑四] 好倉移動止損觸發 @{price:.2f}")
        elif self.s.position_state == -1:                    # 淡倉防線 1.5×ATR
            if price < self.s.dynamic_low:
                self.s.dynamic_low = price
            if price > self.s.dynamic_low + self.p.short_atr_mult * atr:
                self._flatten()
                print(f"[路徑四] 淡倉移動止損觸發（買入補回）@{price:.2f}")

    # ---- 平倉（市價全平 + 變量重置） ----
    def _flatten(self) -> bool:
        held = self._position_qty()
        if held == 0:
            self.s.reset_position()
            return True
        side = TrdSide.SELL if self.s.position_state == 1 else TrdSide.BUY
        ok = self._market_order(side, abs(held))
        if ok:
            self.s.reset_position()
        return ok


if __name__ == "__main__":
    # 參考主迴圈骨架。實盤請接 FutuOpenD 嘅實時回調（K 線收盤 / 報價推送）。
    strat = AuroraStrategy()
    print("Aurora Dual-Engine Strategy — 參考骨架。"
          "請先開 FutuOpenD，再接實時推送觸發 path1/path2/path4。")
