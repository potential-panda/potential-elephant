import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

class YahooFinanceIngestor:
    """
    Ingestor for price and basic fundamental data from Yahoo Finance.
    Handles both JP (e.g., 7203.T) and US tickers.
    """
    
    def __init__(self):
        pass

    def get_price_history(self, ticker, period="1y", interval="1d"):
        """
        Fetch historical price data for a ticker.
        ticker: str (e.g., 'AAPL' or '7203.T')
        period: str (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: str (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        """
        print(f"Fetching price history for: {ticker} (Period: {period})")
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            return df
        except Exception as e:
            print(f"Error fetching prices for {ticker}: {e}")
            return None

    def get_basic_info(self, ticker):
        """
        Fetch basic company info and key metrics.
        """
        print(f"Fetching info for: {ticker}")
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            # Select a subset of useful fields for the LLM
            useful_fields = [
                'longName', 'sector', 'industry', 'longBusinessSummary',
                'marketCap', 'forwardPE', 'dividendYield', 'beta',
                'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'averageVolume'
            ]
            return {k: info.get(k) for k in useful_fields if k in info}
        except Exception as e:
            print(f"Error fetching info for {ticker}: {e}")
            return None

if __name__ == "__main__":
    ingestor = YahooFinanceIngestor()
    
    # Test with a JP stock (Toyota)
    print("\n--- Testing Toyota (7203.T) ---")
    toyota_prices = ingestor.get_price_history("7203.T", period="1mo")
    if toyota_prices is not None:
        print(toyota_prices.tail())
        
    toyota_info = ingestor.get_basic_info("7203.T")
    if toyota_info:
        print(f"Company: {toyota_info.get('longName')}")
        print(f"Market Cap: {toyota_info.get('marketCap')}")

    # Test with a US stock (Apple)
    print("\n--- Testing Apple (AAPL) ---")
    apple_prices = ingestor.get_price_history("AAPL", period="1mo")
    if apple_prices is not None:
        print(apple_prices.tail())
