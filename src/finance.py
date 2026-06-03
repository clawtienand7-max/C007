"""
TFNK™ 財經模組（Finance Module）— G8
整合 Longbridge 長橋 / Yahoo Finance / Alpha Vantage / Finnhub
行情 / 統計 / 大量圖表數據
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from src.config import get_settings


class FinanceClient:
    """免費財經 API 整合客戶端"""

    def __init__(self):
        self.settings = get_settings()
        self._yf_base = "https://query1.finance.yahoo.com/v8/finance"
        self._av_base = "https://www.alphavantage.co/query"
        self._fh_base = "https://finnhub.io/api/v1"

    # ── Yahoo Finance（無需 Key）─────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> dict:
        """取得股票實時報價"""
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{self._yf_base}/chart/{symbol}",
                params={"interval": "1m", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
            data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        return {
            "symbol":        meta.get("symbol"),
            "price":         meta.get("regularMarketPrice"),
            "prev_close":    meta.get("chartPreviousClose"),
            "change":        round((meta.get("regularMarketPrice", 0) - meta.get("chartPreviousClose", 0)), 4),
            "change_pct":    round(((meta.get("regularMarketPrice", 0) / meta.get("chartPreviousClose", 1)) - 1) * 100, 2),
            "volume":        meta.get("regularMarketVolume"),
            "currency":      meta.get("currency"),
            "exchange":      meta.get("exchangeName"),
            "market_state":  meta.get("marketState"),
            "timestamp":     meta.get("regularMarketTime"),
        }

    async def get_historical(self, symbol: str, period: str = "1mo", interval: str = "1d") -> list[dict]:
        """取得歷史行情（OHLCV）"""
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{self._yf_base}/chart/{symbol}",
                params={"interval": interval, "range": period},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
            data = r.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        rows = []
        for i, ts in enumerate(timestamps):
            rows.append({
                "date":   datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
                "open":   round(ohlcv["open"][i] or 0, 4),
                "high":   round(ohlcv["high"][i] or 0, 4),
                "low":    round(ohlcv["low"][i] or 0, 4),
                "close":  round(ohlcv["close"][i] or 0, 4),
                "volume": ohlcv["volume"][i] or 0,
            })
        return rows

    async def get_multiple_quotes(self, symbols: list[str]) -> list[dict]:
        """批量取得報價"""
        tasks = [self.get_quote(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def search_symbol(self, query: str) -> list[dict]:
        """搜尋股票代碼"""
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://query2.finance.yahoo.com/v1/finance/search",
                params={"q": query, "lang": "zh-TW", "region": "HK", "quotesCount": 10},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
            data = r.json()
        return [
            {
                "symbol": item.get("symbol"),
                "name":   item.get("longname") or item.get("shortname"),
                "type":   item.get("typeDisp"),
                "exchange": item.get("exchDisp"),
            }
            for item in data.get("quotes", [])
        ]

    # ── Alpha Vantage ────────────────────────────────────────────────────────

    async def get_intraday(self, symbol: str, interval: str = "5min") -> list[dict]:
        """Alpha Vantage 日內分鐘行情"""
        key = self.settings.alpha_vantage_api_key
        if not key:
            raise ValueError("缺少 ALPHA_VANTAGE_API_KEY")
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(self._av_base, params={
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol, "interval": interval,
                "apikey": key, "outputsize": "compact",
            })
            r.raise_for_status()
            data = r.json()
        ts_key = f"Time Series ({interval})"
        series = data.get(ts_key, {})
        return [
            {
                "time":   t,
                "open":   float(v["1. open"]),
                "high":   float(v["2. high"]),
                "low":    float(v["3. low"]),
                "close":  float(v["4. close"]),
                "volume": int(v["5. volume"]),
            }
            for t, v in sorted(series.items(), reverse=True)[:100]
        ]

    async def get_fundamentals(self, symbol: str) -> dict:
        """取得公司基本面數據"""
        key = self.settings.alpha_vantage_api_key
        if not key:
            raise ValueError("缺少 ALPHA_VANTAGE_API_KEY")
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(self._av_base, params={
                "function": "OVERVIEW", "symbol": symbol, "apikey": key,
            })
            r.raise_for_status()
            data = r.json()
        return {
            "name":          data.get("Name"),
            "sector":        data.get("Sector"),
            "industry":      data.get("Industry"),
            "market_cap":    data.get("MarketCapitalization"),
            "pe_ratio":      data.get("PERatio"),
            "eps":           data.get("EPS"),
            "dividend_yield":data.get("DividendYield"),
            "52w_high":      data.get("52WeekHigh"),
            "52w_low":       data.get("52WeekLow"),
            "beta":          data.get("Beta"),
            "description":   data.get("Description", "")[:500],
        }

    # ── Finnhub ──────────────────────────────────────────────────────────────

    async def get_company_news(self, symbol: str, days: int = 7) -> list[dict]:
        """取得公司相關新聞"""
        key = self.settings.finnhub_api_key
        if not key:
            raise ValueError("缺少 FINNHUB_API_KEY")
        now = datetime.now()
        frm = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        to_ = now.strftime("%Y-%m-%d")
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._fh_base}/company-news", params={
                "symbol": symbol, "from": frm, "to": to_, "token": key,
            })
            r.raise_for_status()
            items = r.json()
        return [
            {
                "headline": item.get("headline"),
                "source":   item.get("source"),
                "datetime": item.get("datetime"),
                "summary":  (item.get("summary") or "")[:300],
                "url":      item.get("url"),
            }
            for item in items[:20]
        ]

    async def get_earnings(self, symbol: str) -> list[dict]:
        """取得財報日期"""
        key = self.settings.finnhub_api_key
        if not key:
            raise ValueError("缺少 FINNHUB_API_KEY")
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._fh_base}/calendar/earnings", params={
                "symbol": symbol, "token": key,
            })
            r.raise_for_status()
            data = r.json()
        return data.get("earningsCalendar", [])[:10]

    async def get_sentiment(self, symbol: str) -> dict:
        """取得社交媒體情緒分析"""
        key = self.settings.finnhub_api_key
        if not key:
            raise ValueError("缺少 FINNHUB_API_KEY")
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._fh_base}/news-sentiment", params={
                "symbol": symbol, "token": key,
            })
            r.raise_for_status()
            data = r.json()
        return {
            "bullish_pct":  data.get("sentiment", {}).get("bullishPercent"),
            "bearish_pct":  data.get("sentiment", {}).get("bearishPercent"),
            "score":        data.get("sentimentScore"),
            "articles":     data.get("buzz", {}).get("articlesInLastWeek"),
        }

    # ── 投資組合分析 ────────────────────────────────────────────────────────

    async def portfolio_summary(self, holdings: list[dict]) -> dict:
        """
        計算投資組合摘要
        holdings: [{"symbol": "AAPL", "shares": 10, "cost": 150.0}, ...]
        """
        quotes = await self.get_multiple_quotes([h["symbol"] for h in holdings])
        price_map = {q["symbol"]: q["price"] for q in quotes if q.get("symbol")}
        total_cost = 0
        total_value = 0
        positions = []
        for h in holdings:
            cost = h["cost"] * h["shares"]
            price = price_map.get(h["symbol"], h["cost"])
            value = price * h["shares"]
            total_cost  += cost
            total_value += value
            positions.append({
                "symbol":  h["symbol"],
                "shares":  h["shares"],
                "cost":    h["cost"],
                "price":   price,
                "value":   round(value, 2),
                "gain":    round(value - cost, 2),
                "gain_pct": round((value / cost - 1) * 100, 2) if cost else 0,
                "weight":  0,  # filled below
            })
        for p in positions:
            p["weight"] = round(p["value"] / total_value * 100, 1) if total_value else 0
        return {
            "total_cost":    round(total_cost, 2),
            "total_value":   round(total_value, 2),
            "total_gain":    round(total_value - total_cost, 2),
            "total_gain_pct":round((total_value / total_cost - 1) * 100, 2) if total_cost else 0,
            "positions":     sorted(positions, key=lambda x: x["value"], reverse=True),
        }


_client: Optional[FinanceClient] = None


def get_finance_client() -> FinanceClient:
    global _client
    if _client is None:
        _client = FinanceClient()
    return _client
