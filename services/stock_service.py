"""
Stock Service
Fetches stock data from Yahoo Finance and manages price updates
"""

import yfinance as yf
from typing import Optional, Dict
from datetime import datetime, timedelta
from utils.logger import get_logger

class StockService:
    """Handles stock data fetching and price updates"""
    
    def __init__(self):
        """Init.

        Args:
            None.

        Returns:
            Any: Method output for caller use.
        """
        self.logger = get_logger(__name__)
        self._stock_info_cache = {}
        self._price_cache = {}
        self._stock_info_ttl = timedelta(minutes=10)
        self._price_ttl = timedelta(minutes=1)
    
    def _get_cached(self, cache: Dict, key: str, ttl: timedelta):
        """Return cached value if within TTL."""
        if key not in cache:
            return None
        
        cached_at, value = cache[key]
        if datetime.now() - cached_at <= ttl:
            return value
        return None
    
    def _set_cached(self, cache: Dict, key: str, value):
        """Set cache value with current timestamp."""
        cache[key] = (datetime.now(), value)
    
    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """
        Get stock information
        Returns: Dict with stock data or None if not found
        """
        symbol = symbol.strip().upper()
        if not symbol:
            return None

        cached = self._get_cached(self._stock_info_cache, symbol, self._stock_info_ttl)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info or 'symbol' not in info:
                return None
            
            stock_info = {
                'symbol': symbol,
                'company_name': info.get('longName', info.get('shortName', symbol)),
                'current_price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                'previous_close': info.get('previousClose', 0),
                'market_cap': info.get('marketCap', 0),
                'currency': info.get('currency', 'INR'),
                'exchange': info.get('exchange', 'NSE')
            }
            self._set_cached(self._stock_info_cache, symbol, stock_info)
            return stock_info
        
        except Exception as e:
            self.logger.error("Error fetching stock %s: %s", symbol, e)
            return None

    def to_quote_symbol(self, symbol: str, exchange: str = None, override_yahoo_symbol: str = None) -> str:
        """Resolve canonical symbol to quote symbol used by Yahoo Finance."""
        if override_yahoo_symbol:
            return override_yahoo_symbol.strip().upper()

        raw = (symbol or "").strip().upper()
        if not raw:
            return raw

        # Already quote-formatted.
        if "." in raw:
            return raw

        ex = (exchange or "").strip().upper()
        if ex == "NSE":
            return f"{raw}.NS"
        if ex == "BSE":
            return f"{raw}.BO"
        return raw
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current stock price
        Returns: Current price or None if not found
        """
        symbol = symbol.strip().upper()
        if not symbol:
            return None

        cached = self._get_cached(self._price_cache, symbol, self._price_ttl)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            
            # Try to get from fast_info first (faster)
            try:
                price = ticker.fast_info.last_price
                if price:
                    price = float(price)
                    self._set_cached(self._price_cache, symbol, price)
                    return price
            except:
                pass
            
            # Fallback to regular info
            info = ticker.info
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if price:
                price = float(price)
                self._set_cached(self._price_cache, symbol, price)
                return price
            return None
        
        except Exception as e:
            self.logger.error("Error fetching price for %s: %s", symbol, e)
            return None
    
    def get_historical_prices(self, symbol: str, period: str = '1mo') -> Optional[Dict]:
        """
        Get historical prices
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                return None
            
            return {
                'dates': hist.index.tolist(),
                'prices': hist['Close'].tolist(),
                'volumes': hist['Volume'].tolist()
            }
        
        except Exception as e:
            self.logger.error("Error fetching historical data for %s: %s", symbol, e)
            return None
    
    def calculate_pnl(self, avg_price: float, current_price: float, quantity: int) -> Dict:
        """
        Calculate P&L for a position
        Returns: Dict with P&L details
        """
        total_invested = avg_price * quantity
        current_value = current_price * quantity
        
        pnl = current_value - total_invested
        pnl_percentage = (pnl / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'total_invested': total_invested,
            'current_value': current_value,
            'pnl': pnl,
            'pnl_percentage': pnl_percentage
        }
    
    def validate_symbol(self, symbol: str) -> bool:
        """Check if a stock symbol is valid"""
        stock_info = self.get_stock_info(symbol)
        return stock_info is not None
    
    def search_stocks(self, query: str) -> list:
        """
        Search for stocks by name or symbol
        Note: This is a basic implementation. For production, use a dedicated search API
        """
        # Common Indian stocks for demo
        common_stocks = {
            'RELIANCE': 'RELIANCE.NS',
            'TCS': 'TCS.NS',
            'INFY': 'INFY.NS',
            'HDFC': 'HDFCBANK.NS',
            'ICICI': 'ICICIBANK.NS',
            'WIPRO': 'WIPRO.NS',
            'ITC': 'ITC.NS',
            'BHARTI': 'BHARTIARTL.NS',
            'AAPL': 'AAPL',
            'MSFT': 'MSFT',
            'GOOGL': 'GOOGL',
            'AMZN': 'AMZN',
            'TSLA': 'TSLA'
        }
        
        query_upper = query.upper()
        matches = []
        
        for name, symbol in common_stocks.items():
            if query_upper in name or query_upper in symbol:
                matches.append({'name': name, 'symbol': symbol})
        
        return matches
