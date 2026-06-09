import hashlib
import logging
from datetime import datetime

from elephant.framework import Harvester, HarvesterResult, Store


def _row_id(ticker: str, date: str) -> str:
    return hashlib.md5(f"{ticker}|{date}".encode()).hexdigest()


class PriceHarvester(Harvester):
    def __init__(self, store: Store, ticker: str):
        super().__init__(store)
        from elephant.ticker_registry import normalize_ticker
        self.ticker = normalize_ticker(ticker)

    def get_url(self, params: dict) -> str:
        return f"yfinance://{self.ticker}"

    async def scrape(self, url: str, params: dict) -> dict[str, HarvesterResult]:
        import asyncio
        return await asyncio.to_thread(self._fetch, params.get("period", "2y"))

    def _fetch(self, period: str = "max") -> dict[str, HarvesterResult]:
        try:
            import yfinance as yf
        except ImportError:
            logging.error("yfinance not installed")
            return {}

        try:
            t = yf.Ticker(self.ticker)
            hist = t.history(period=period, interval="1d", auto_adjust=True)
            if hist.empty:
                logging.warning(f"[Price] No data for {self.ticker}")
                return {}

            rows = []
            for date, row in hist.iterrows():
                date_str = date.strftime("%Y-%m-%d")
                rows.append({
                    "id": _row_id(self.ticker, date_str),
                    "ticker": self.ticker,
                    "date": date_str,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                    "scraped_at": datetime.now().isoformat(),
                })

            logging.info(f"[Price] {self.ticker}: {len(rows)} daily bars")
            return {
                "daily_prices": HarvesterResult(
                    tags={"ticker": self.ticker},
                    data=rows,
                )
            }
        except Exception:
            logging.exception(f"[Price] Failed to fetch {self.ticker}")
            return {}
