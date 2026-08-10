import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import yfinance as yf
from newsapi import NewsApiClient
from .config import get_newsapi_key, ConfigurationError

logger = logging.getLogger("stocksense.data_collectors")


def get_news_articles(ticker: str, days: int = 7) -> List[Dict[str, Any]]:
    """Fetch recent news articles with source metadata and clickable URLs."""
    try:
        api_key = get_newsapi_key()
        newsapi = NewsApiClient(api_key=api_key)

        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        articles = newsapi.get_everything(
            q=ticker,
            language='en',
            sort_by='publishedAt',
            from_param=from_date.strftime('%Y-%m-%d'),
            to=to_date.strftime('%Y-%m-%d'),
            page_size=20
        )

        if articles.get('status') != 'ok':
            return []

        results = []
        for article in articles.get('articles', []):
            title = article.get('title')
            if not title or title == '[Removed]':
                continue

            source = article.get('source') or {}
            results.append({
                "title": title,
                "source": source.get('name') or 'Unknown source',
                "url": article.get('url') or '',
                "published_at": article.get('publishedAt') or '',
            })

        return results

    except ConfigurationError as e:
        logger.warning(f"NewsAPI key error for {ticker}: {e}")
        return []
    except Exception as e:
        logger.warning(f"Failed to fetch news for {ticker}: {e}")
        return []


def get_news(ticker: str, days: int = 7) -> List[str]:
    """Fetch recent news headlines related to a stock ticker."""
    return [
        article["title"]
        for article in get_news_articles(ticker, days)
        if article.get("title")
    ]


def get_price_history(ticker: str, period: str = "1mo") -> Optional[object]:
    """Fetch historical price data for a stock ticker."""
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)

        if history.empty:
            return None

        return history

    except Exception as e:
        logger.warning(f"Failed to fetch price history for {ticker}: {e}")
        return None


def get_fundamental_data(ticker: str) -> Optional[dict]:
    """
    Fetch fundamental financial data (Income Statement, Balance Sheet, Cash Flow) 
    and key statistics.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Helper to convert DataFrame to dict safely
        def safe_to_dict(df):
            if df is None or df.empty:
                return {}
            # Convert timestamp keys to strings
            return {k.strftime('%Y-%m-%d') if isinstance(k, datetime) else str(k): v 
                    for k, v in df.to_dict().items()}

        info = stock.info
        
        # Get last 4 years of data
        income_stmt = stock.income_stmt
        balance_sheet = stock.balance_sheet
        cash_flow = stock.cashflow
        
        result = {
            "info": {
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "profit_margins": info.get("profitMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "debt_to_equity": info.get("debtToEquity"),
                "free_cashflow": info.get("freeCashflow"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "recommendation_mean": info.get("recommendationMean"), # 1 is Strong Buy, 5 is Sell
            },
            "income_statement": safe_to_dict(income_stmt),
            "balance_sheet": safe_to_dict(balance_sheet),
            "cash_flow": safe_to_dict(cash_flow)
        }
        
        return result
    except Exception as e:
        logger.error(f"Error fetching fundamentals for {ticker}: {e}")
        return None


if __name__ == '__main__':
    test_ticker = "AAPL"
    headlines = get_news(test_ticker, days=7)
    price_data = get_price_history(test_ticker, period="1mo")