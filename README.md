# 雙向極光防禦策略 (Aurora Dual-Engine Strategy)

趨勢跟隨 (Trend Following) + 波動率克制 (Volatility Control) 嘅全自動雙向切換量化策略。
核心目標：**長線穩定營利**、**極致壓低回撤 (Max Drawdown < 8%)**、**無需人為參與**、**異常自癒**。

壓回撤嘅靈魂唔係開倉指標有幾準，而係 **ATR 動態資金管理** + **動態風險截斷**。

## 內容

| 路徑 | 說明 |
| --- | --- |
| [`docs/aurora-dual-engine-blueprint.md`](docs/aurora-dual-engine-blueprint.md) | 富途牛牛「策略卡片」畫布完整藍圖：5 個全局變量 + 4 大卡片路徑 + 防鎖倉規範 + 3 項改進 |
| [`futu/aurora_strategy.py`](futu/aurora_strategy.py) | 富途 OpenAPI (futu-api) Python 執行實作 |
| [`tradingview/aurora_dual_engine.pine`](tradingview/aurora_dual_engine.pine) | TradingView Pine Script v5 回測（交叉驗證）|
| [`quantconnect/aurora_dual_engine.py`](quantconnect/aurora_dual_engine.py) | QuantConnect LEAN Python 回測（交叉驗證）|

## 策略骨架

- **路徑一** — 09:15 開市對賬，鎖定單日熔斷線（資產 × 0.98）；週五尾盤 (≥15:50) 強制減倉 50%；盤中跌穿熔斷線即全線清倉、全日罷工。
- **路徑二** — 每根 K 線收盤：`收盤價 > 布林上軌 AND EMA50 > EMA200` 開好倉；`收盤價 < 布林下軌 AND EMA50 < EMA200` 開淡倉。反向切換走「先平倉 → 確認 0 倉 → 再開新倉」三步閉環，避免鎖倉陷阱。
- **路徑三** — ATR 風險配倉：`下單股數 = 每筆風險金額 / (ATR × 2)`，將每筆潛在虧損鎖死喺 $1000 內。
- **路徑四** — 雙向動態追蹤止損（非對稱系數）：好倉 `高位 - 2.0×ATR`，淡倉 `低位 + 1.5×ATR`。

## 上線標準（三平台交叉認證）

參數對齊後，富途 / TradingView / QuantConnect 三邊跑同一段歷史數據，須全部達到
`Profit Factor > 1.5` 且 `Max Drawdown ≤ 8%`，方可投入實盤無需人為參與運行。

## 使用富途實作

```bash
pip install futu-api pandas
# 先開 FutuOpenD 並登入，預設 TrdEnv.SIMULATE（模擬倉），穩定後再改 REAL
python futu/aurora_strategy.py
```

> ⚠️ 風險提示：本倉庫為策略藍圖與參考實作，並非投資建議。實盤前務必完成三平台回測與小資金模擬驗證。
