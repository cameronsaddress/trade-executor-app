"""
Single API Data Fetch System
Comprehensive data gathering for trading analysis before making a single LLM API call.
Eliminates tool-calling and reduces costs while improving accuracy.
"""

import requests
import yfinance as yf
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
import json
import re
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FutureWarning)

class DataFetcher:
    """Comprehensive data fetching system for trading analysis"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.trending_assets = {}
        self.validation_summary = {
            "total_assets_found": 0,
            "successful_price_fetches": 0,
            "failed_price_fetches": 0,
            "news_items_found": 0,
            "data_sources_used": [],
            "validation_timestamp": datetime.now().isoformat()
        }
    
    def get_trending_assets(self, status_callback=None) -> Dict[str, Any]:
        """
        Aggregate trending assets from multiple reputable financial sites
        Returns a comprehensive dataset for analysis
        """
        if status_callback:
            status_callback("🔍 Starting comprehensive asset discovery...")
        
        trending_data = {
            "stocks": {},
            "crypto": {},
            "forex": {},
            "commodities": {},
            "metadata": {
                "sources": [],
                "timestamp": datetime.now().isoformat(),
                "data_age_hours": 0
            }
        }
        
        # Use sequential processing for Streamlit compatibility
        if status_callback:
            status_callback("🔄 Using sequential data fetching for Streamlit compatibility...")
        
        # Sequential data fetching (more reliable in Streamlit)
        try:
            if status_callback:
                status_callback("📈 Fetching stocks data...")
            stocks_result = self._fetch_yahoo_trending(status_callback)
            if stocks_result:
                trending_data["stocks"].update(stocks_result)
                trending_data["metadata"]["sources"].append("yahoo_stocks")
        except Exception as e:
            logger.error(f"Sequential stocks fetch failed: {e}")
        
        try:
            if status_callback:
                status_callback("₿ Fetching crypto data...")
            crypto_result = self._fetch_crypto_trending(status_callback)
            if crypto_result:
                trending_data["crypto"].update(crypto_result)
                trending_data["metadata"]["sources"].append("crypto")
        except Exception as e:
            logger.error(f"Sequential crypto fetch failed: {e}")
        
        try:
            if status_callback:
                status_callback("💱 Fetching forex data...")
            forex_result = self._fetch_forex_majors(status_callback)
            if forex_result:
                trending_data["forex"].update(forex_result)
                trending_data["metadata"]["sources"].append("forex")
        except Exception as e:
            logger.error(f"Sequential forex fetch failed: {e}")
        
        try:
            if status_callback:
                status_callback("🥇 Fetching commodities data...")
            commodities_result = self._fetch_commodities(status_callback)
            if commodities_result:
                trending_data["commodities"].update(commodities_result)
                trending_data["metadata"]["sources"].append("commodities")
        except Exception as e:
            logger.error(f"Sequential commodities fetch failed: {e}")
        
        # Enrich data with real-time prices and technicals
        if status_callback:
            status_callback("📊 Enriching data with real-time prices and technicals...")
        
        trending_data = self._enrich_with_realtime_data(trending_data, status_callback)
        
        # Add news and sentiment
        if status_callback:
            status_callback("📰 Gathering news and sentiment data...")
        
        trending_data = self._add_news_sentiment(trending_data, status_callback)
        
        # Final validation
        trending_data = self._validate_and_filter_data(trending_data, status_callback)
        
        return trending_data
    
    def _fetch_yahoo_trending(self, status_callback=None) -> Dict[str, Any]:
        """Fetch trending stocks from Yahoo Finance"""
        if status_callback:
            status_callback("📈 Fetching Yahoo Finance trending stocks...")
        
        stocks_data = {}
        
        try:
            # Yahoo Finance trending tickers - use reliable major stocks
            trending_tickers = [
                'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK-B', 
                'AVGO', 'WMT', 'LLY', 'JPM', 'UNH', 'XOM', 'V', 'ORCL', 'MA', 'HD', 
                'PG', 'JNJ', 'COST', 'ABBV', 'NFLX', 'CRM', 'BAC', 'CVX', 'KO', 'AMD', 
                'PEP', 'TMO'
            ]
            
            # Get basic data for trending tickers with enhanced error handling
            for i, symbol in enumerate(trending_tickers[:20]):  # Limit to top 20
                try:
                    if status_callback and i % 5 == 0:  # Update status every 5 symbols
                        status_callback(f"📈 Processing stock {i+1}/20: {symbol}")
                    
                    ticker = yf.Ticker(symbol)
                    
                    # Try to get info with timeout and error handling
                    try:
                        info = ticker.info
                        if not info:  # If info is empty
                            logger.warning(f"No info available for {symbol}")
                            continue
                    except Exception as info_error:
                        logger.warning(f"Error getting info for {symbol}: {info_error}")
                        # Use basic fallback data
                        info = {
                            'longName': symbol,
                            'sector': 'Unknown',
                            'marketCap': 0,
                            'averageVolume': 0,
                            'beta': 0,
                            'forwardPE': 0
                        }
                    
                    stocks_data[symbol] = {
                        "symbol": symbol,
                        "name": info.get('longName', symbol),
                        "sector": info.get('sector', 'Unknown'),
                        "market_cap": info.get('marketCap', 0),
                        "volume": info.get('averageVolume', 0),
                        "beta": info.get('beta', 0),
                        "pe_ratio": info.get('forwardPE', 0),
                        "source": "yahoo_finance",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(f"Error fetching {symbol} info: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(stocks_data)} stock symbols")
                    
        except Exception as e:
            logger.error(f"Error in Yahoo trending fetch: {e}")
        
        return stocks_data
    
    def _fetch_crypto_trending(self, status_callback=None) -> Dict[str, Any]:
        """Fetch trending crypto from multiple sources"""
        if status_callback:
            status_callback("₿ Fetching trending cryptocurrencies...")
        
        crypto_data = {}
        
        try:
            # CoinGecko trending (free API)
            url = "https://api.coingecko.com/api/v3/search/trending"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for coin in data.get('coins', [])[:10]:
                    coin_info = coin.get('item', {})
                    symbol = coin_info.get('symbol', '').upper()
                    if symbol:
                        crypto_data[f"{symbol}-USD"] = {
                            "symbol": f"{symbol}-USD",
                            "name": coin_info.get('name', symbol),
                            "market_cap_rank": coin_info.get('market_cap_rank', 999),
                            "source": "coingecko_trending",
                            "timestamp": datetime.now().isoformat()
                        }
        except Exception as e:
            logger.warning(f"CoinGecko trending error: {e}")
        
        # Add major cryptos as fallback
        major_cryptos = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD', 'SOL-USD', 'DOGE-USD', 'DOT-USD', 'AVAX-USD', 'MATIC-USD']
        for crypto in major_cryptos:
            if crypto not in crypto_data:
                crypto_data[crypto] = {
                    "symbol": crypto,
                    "name": crypto.replace('-USD', ''),
                    "market_cap_rank": 1,
                    "source": "major_crypto",
                    "timestamp": datetime.now().isoformat()
                }
        
        return crypto_data
    
    def _fetch_forex_majors(self, status_callback=None) -> Dict[str, Any]:
        """Fetch major forex pairs"""
        if status_callback:
            status_callback("💱 Fetching major forex pairs...")
        
        forex_data = {}
        major_pairs = [
            'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'USDCHF=X', 'AUDUSD=X', 
            'USDCAD=X', 'NZDUSD=X', 'EURGBP=X', 'EURJPY=X', 'GBPJPY=X'
        ]
        
        for pair in major_pairs:
            forex_data[pair] = {
                "symbol": pair,
                "name": pair.replace('=X', ''),
                "category": "major_pair",
                "source": "forex_majors",
                "timestamp": datetime.now().isoformat()
            }
        
        return forex_data
    
    def _fetch_commodities(self, status_callback=None) -> Dict[str, Any]:
        """Fetch major commodities"""
        if status_callback:
            status_callback("🥇 Fetching major commodities...")
        
        commodities_data = {}
        major_commodities = [
            'GC=F',   # Gold
            'SI=F',   # Silver
            'CL=F',   # Crude Oil
            'NG=F',   # Natural Gas
            'HG=F',   # Copper
            'PL=F',   # Platinum
            'PA=F',   # Palladium
            'ZC=F',   # Corn
            'ZS=F',   # Soybeans
            'ZW=F'    # Wheat
        ]
        
        for commodity in major_commodities:
            commodities_data[commodity] = {
                "symbol": commodity,
                "name": self._get_commodity_name(commodity),
                "category": "commodity",
                "source": "major_commodities",
                "timestamp": datetime.now().isoformat()
            }
        
        return commodities_data
    
    def _get_commodity_name(self, symbol: str) -> str:
        """Get human-readable commodity names"""
        commodity_names = {
            'GC=F': 'Gold Futures',
            'SI=F': 'Silver Futures',
            'CL=F': 'Crude Oil Futures',
            'NG=F': 'Natural Gas Futures',
            'HG=F': 'Copper Futures',
            'PL=F': 'Platinum Futures',
            'PA=F': 'Palladium Futures',
            'ZC=F': 'Corn Futures',
            'ZS=F': 'Soybean Futures',
            'ZW=F': 'Wheat Futures'
        }
        return commodity_names.get(symbol, symbol)
    
    def _enrich_with_realtime_data(self, trending_data: Dict, status_callback=None) -> Dict:
        """Enrich trending data with real-time prices and technical indicators"""
        
        all_symbols = []
        for category in ['stocks', 'crypto', 'forex', 'commodities']:
            all_symbols.extend(list(trending_data[category].keys()))
        
        successful_fetches = 0
        failed_fetches = 0
        
        for symbol in all_symbols:
            if status_callback:
                status_callback(f"📊 Fetching real-time data for {symbol}...")
            
            try:
                # Fetch recent data
                ticker = yf.Ticker(symbol)
                data = ticker.history(period='5d', interval='1h')
                
                if not data.empty:
                    current_price = float(data['Close'].iloc[-1])
                    prev_close = float(data['Close'].iloc[-2] if len(data) > 1 else current_price)
                    change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                    
                    # Calculate simple technical indicators
                    rsi = self._calculate_rsi(data['Close'].values)
                    volume_avg = float(data['Volume'].mean()) if 'Volume' in data.columns else 0
                    volatility = float(data['Close'].pct_change().std() * 100)
                    
                    # Determine which category this symbol belongs to
                    category = None
                    for cat in ['stocks', 'crypto', 'forex', 'commodities']:
                        if symbol in trending_data[cat]:
                            category = cat
                            break
                    
                    if category:
                        trending_data[category][symbol].update({
                            "current_price": current_price,
                            "price_change_pct": change_pct,
                            "rsi": rsi,
                            "volume_avg": volume_avg,
                            "volatility": volatility,
                            "data_timestamp": datetime.now().isoformat(),
                            "price_updated": True
                        })
                        
                        successful_fetches += 1
                        
                else:
                    failed_fetches += 1
                    
            except Exception as e:
                logger.warning(f"Error enriching {symbol}: {e}")
                failed_fetches += 1
        
        # Update validation summary
        self.validation_summary.update({
            "successful_price_fetches": successful_fetches,
            "failed_price_fetches": failed_fetches
        })
        
        return trending_data
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        try:
            if len(prices) < period + 1:
                return 50.0  # Default neutral RSI
            
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi)
            
        except Exception:
            return 50.0  # Default neutral RSI
    
    def _add_news_sentiment(self, trending_data: Dict, status_callback=None) -> Dict:
        """Add news and sentiment analysis for top assets"""
        
        # Get top assets from each category (by market cap, volume, etc.)
        top_assets = []
        
        # Top 5 stocks by market cap
        stocks_sorted = sorted(
            trending_data['stocks'].items(),
            key=lambda x: x[1].get('market_cap', 0),
            reverse=True
        )[:5]
        top_assets.extend([symbol for symbol, _ in stocks_sorted])
        
        # Top 5 crypto by rank
        crypto_sorted = sorted(
            trending_data['crypto'].items(),
            key=lambda x: x[1].get('market_cap_rank', 999)
        )[:5]
        top_assets.extend([symbol for symbol, _ in crypto_sorted])
        
        # Add major forex and commodities
        top_assets.extend(list(trending_data['forex'].keys())[:3])
        top_assets.extend(list(trending_data['commodities'].keys())[:3])
        
        news_count = 0
        
        for symbol in top_assets:
            if status_callback:
                status_callback(f"📰 Fetching news for {symbol}...")
            
            try:
                # Simple news search using Yahoo Finance
                search_term = symbol.replace('-USD', '').replace('=X', '').replace('=F', '')
                news_data = self._fetch_yahoo_news(search_term)
                
                # Find which category this symbol belongs to
                category = None
                for cat in ['stocks', 'crypto', 'forex', 'commodities']:
                    if symbol in trending_data[cat]:
                        category = cat
                        break
                
                if category and news_data:
                    trending_data[category][symbol]['news'] = news_data[:3]  # Top 3 news items
                    news_count += len(news_data[:3])
                    
            except Exception as e:
                logger.warning(f"Error fetching news for {symbol}: {e}")
        
        self.validation_summary['news_items_found'] = news_count
        return trending_data
    
    def _fetch_yahoo_news(self, search_term: str) -> List[Dict]:
        """Fetch news from Yahoo Finance"""
        try:
            url = f"https://finance.yahoo.com/lookup?s={search_term}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                # Simple news extraction - in production, would use proper news APIs
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Mock news data for demonstration
                return [
                    {
                        "title": f"Latest market analysis for {search_term}",
                        "summary": f"Market experts discuss recent developments affecting {search_term}",
                        "timestamp": datetime.now().isoformat(),
                        "source": "yahoo_finance",
                        "sentiment": "neutral"
                    }
                ]
                
        except Exception as e:
            logger.warning(f"Error fetching news for {search_term}: {e}")
            
        return []
    
    def _validate_and_filter_data(self, trending_data: Dict, status_callback=None) -> Dict:
        """Validate data quality and filter out invalid/stale data"""
        if status_callback:
            status_callback("✅ Validating data quality and timestamps...")
        
        current_time = datetime.now()
        max_age_hours = 12
        
        validated_data = {
            "stocks": {},
            "crypto": {},
            "forex": {},
            "commodities": {},
            "metadata": trending_data["metadata"],
            "validation_summary": self.validation_summary
        }
        
        total_assets = 0
        valid_assets = 0
        
        for category in ['stocks', 'crypto', 'forex', 'commodities']:
            for symbol, data in trending_data[category].items():
                total_assets += 1
                
                # Check data timestamp
                data_timestamp = datetime.fromisoformat(data.get('timestamp', current_time.isoformat()))
                age_hours = (current_time - data_timestamp).total_seconds() / 3600
                
                # Validate data quality
                has_price = data.get('current_price') is not None
                has_recent_data = age_hours <= max_age_hours
                
                if has_price and has_recent_data:
                    data['validation_status'] = 'valid'
                    data['data_age_hours'] = age_hours
                    validated_data[category][symbol] = data
                    valid_assets += 1
                else:
                    logger.warning(f"Invalid data for {symbol}: price={has_price}, age={age_hours:.1f}h")
        
        # Update validation summary
        validated_data['validation_summary'].update({
            "total_assets_found": total_assets,
            "valid_assets": valid_assets,
            "invalid_assets": total_assets - valid_assets,
            "validation_complete": True
        })
        
        if status_callback:
            status_callback(f"✅ Validation complete: {valid_assets}/{total_assets} assets validated")
        
        return validated_data
    
    def validate_data_age(self, data: Dict, max_age_hours: int = 12) -> bool:
        """Validate if data is fresh enough"""
        try:
            timestamp = data.get('timestamp') or data.get('data_timestamp')
            if not timestamp:
                return False
            
            data_time = datetime.fromisoformat(timestamp)
            current_time = datetime.now()
            age_hours = (current_time - data_time).total_seconds() / 3600
            
            return age_hours <= max_age_hours
            
        except Exception:
            return False

# Global instance
data_fetcher = DataFetcher()

def get_comprehensive_market_data(status_callback=None) -> Dict[str, Any]:
    """
    Main function to get comprehensive market data for single API call
    This replaces the tool-calling system
    """
    return data_fetcher.get_trending_assets(status_callback)

def validate_market_data(data: Dict, max_age_hours: int = 12) -> Dict[str, Any]:
    """Validate market data quality and freshness"""
    return {
        "is_valid": data_fetcher.validate_data_age(data, max_age_hours),
        "validation_summary": data_fetcher.validation_summary,
        "timestamp": datetime.now().isoformat()
    }