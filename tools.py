"""
Trade Analysis Tool Functions

This module provides various utility functions for fetching financial data,
analyzing news, web scraping, and backtesting.
"""

import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time
import warnings
import io
import sys
import ast
import contextlib

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")


def fetch_current_price(symbol: str) -> Dict[str, Any]:
    """
    Fetch current price for a given symbol using yfinance.
    
    Args:
        symbol: Stock/crypto symbol (e.g., 'AAPL', 'BTC-USD')
        
    Returns:
        Dict containing price, timestamp, and validation status
    """
    try:
        # Download recent data
        ticker = yf.Ticker(symbol)
        
        # Try to get intraday data first
        try:
            data = ticker.history(period="1d", interval="1m")
            if data.empty:
                # Fallback to daily data if intraday is not available
                data = ticker.history(period="5d", interval="1d")
        except:
            # Fallback to daily data
            data = ticker.history(period="5d", interval="1d")
        
        if data.empty:
            return {
                "price": None,
                "timestamp": None,
                "is_valid": False,
                "error": f"No data available for symbol {symbol}"
            }
        
        # Get the latest price and timestamp
        latest_price = float(data['Close'].iloc[-1])
        latest_timestamp = data.index[-1]
        
        # Convert to timezone-aware datetime if needed
        if latest_timestamp.tzinfo is None:
            latest_timestamp = latest_timestamp.tz_localize('UTC')
        
        # Check if data is less than 5 minutes old
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - latest_timestamp
        is_valid = time_diff < timedelta(minutes=5)
        
        return {
            "symbol": symbol,
            "price": latest_price,
            "timestamp": latest_timestamp.isoformat(),
            "is_valid": is_valid,
            "age_minutes": time_diff.total_seconds() / 60,
            "currency": ticker.info.get('currency', 'USD') if hasattr(ticker, 'info') else 'USD'
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "price": None,
            "timestamp": None,
            "is_valid": False,
            "error": str(e)
        }


def search_web_for_news(query: str, after_date: str, before_date: str) -> List[Dict[str, Any]]:
    """
    Search for financial news with date filtering.
    Uses free news APIs with fallback options.
    
    Args:
        query: Search query string
        after_date: Start date in YYYY-MM-DD format
        before_date: End date in YYYY-MM-DD format
        
    Returns:
        List of news items with title, snippet, url, and timestamp
    """
    news_items = []
    
    try:
        # Parse dates
        after_dt = datetime.strptime(after_date, "%Y-%m-%d")
        before_dt = datetime.strptime(before_date, "%Y-%m-%d")
        
        # Try multiple news sources
        # 1. Try NewsAPI (requires free API key - using demo endpoint)
        try:
            # Note: In production, you would use a real API key
            newsapi_url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "from": after_date,
                "to": before_date,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": "demo"  # Replace with actual API key
            }
            
            response = requests.get(newsapi_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", [])[:10]:  # Limit to 10 articles
                    published_at = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
                    
                    # Validate article is within 12 hours
                    if validate_data({"timestamp": published_at.isoformat()}, max_age_hours=12):
                        news_items.append({
                            "title": article.get("title", ""),
                            "snippet": article.get("description", ""),
                            "url": article.get("url", ""),
                            "timestamp": published_at.isoformat(),
                            "source": article.get("source", {}).get("name", "Unknown")
                        })
        except:
            pass
        
        # 2. Fallback: Use Yahoo Finance news for the query
        if not news_items:
            try:
                # Extract ticker from query if possible
                ticker_match = re.search(r'\b[A-Z]{1,5}\b', query)
                if ticker_match:
                    ticker = ticker_match.group()
                    yf_ticker = yf.Ticker(ticker)
                    news = yf_ticker.news
                    
                    for item in news[:10]:  # Limit to 10 items
                        # Yahoo Finance provides Unix timestamp
                        published_at = datetime.fromtimestamp(item.get("providerPublishTime", 0), tz=timezone.utc)
                        
                        # Check if within date range and validate
                        if after_dt <= published_at.replace(tzinfo=None) <= before_dt:
                            if validate_data({"timestamp": published_at.isoformat()}, max_age_hours=12):
                                news_items.append({
                                    "title": item.get("title", ""),
                                    "snippet": item.get("summary", "")[:200] + "..." if len(item.get("summary", "")) > 200 else item.get("summary", ""),
                                    "url": item.get("link", ""),
                                    "timestamp": published_at.isoformat(),
                                    "source": item.get("publisher", "Unknown")
                                })
            except:
                pass
        
        # 3. If still no items, create a mock response with current data
        if not news_items:
            current_time = datetime.now(timezone.utc)
            news_items.append({
                "title": f"Latest update on {query}",
                "snippet": f"No recent news found for {query} in the specified date range. Consider checking broader sources or adjusting date parameters.",
                "url": f"https://finance.yahoo.com/quote/{query}",
                "timestamp": current_time.isoformat(),
                "source": "System Notice"
            })
        
    except Exception as e:
        # Return error as a news item
        current_time = datetime.now(timezone.utc)
        news_items.append({
            "title": "Error fetching news",
            "snippet": f"Error occurred while fetching news: {str(e)}",
            "url": "",
            "timestamp": current_time.isoformat(),
            "source": "Error"
        })
    
    return news_items


def browse_page_for_data(url: str, instructions: str) -> Dict[str, Any]:
    """
    Fetch webpage content and extract data based on instructions.
    
    Args:
        url: URL to fetch
        instructions: Instructions for what data to extract
        
    Returns:
        Dict containing extracted data and timestamp
    """
    try:
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {
                "error": "Invalid URL format",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": None
            }
        
        # Fetch the webpage
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract data based on instructions
        extracted_data = {}
        
        # Common extraction patterns based on instructions
        instructions_lower = instructions.lower()
        
        # Extract title
        if "title" in instructions_lower:
            title = soup.find('title')
            extracted_data["title"] = title.text.strip() if title else ""
        
        # Extract meta description
        if "description" in instructions_lower or "meta" in instructions_lower:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                extracted_data["description"] = meta_desc.get('content', '')
        
        # Extract all text
        if "text" in instructions_lower or "content" in instructions_lower:
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            extracted_data["text_content"] = text[:5000]  # Limit to 5000 chars
        
        # Extract specific elements if mentioned
        if "price" in instructions_lower:
            # Common price patterns
            price_patterns = [
                r'\$[\d,]+\.?\d*',
                r'[\d,]+\.?\d*\s*(?:USD|EUR|GBP)',
                r'Price:\s*[\d,]+\.?\d*'
            ]
            for pattern in price_patterns:
                matches = re.findall(pattern, str(soup))
                if matches:
                    extracted_data["prices_found"] = matches[:10]  # First 10 matches
                    break
        
        # Extract tables if mentioned
        if "table" in instructions_lower:
            tables = soup.find_all('table')
            if tables:
                # Convert first table to list of dicts
                table_data = []
                for table in tables[:3]:  # First 3 tables
                    rows = table.find_all('tr')
                    if rows:
                        headers = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
                        for row in rows[1:]:
                            cols = [td.text.strip() for td in row.find_all('td')]
                            if len(cols) == len(headers):
                                table_data.append(dict(zip(headers, cols)))
                extracted_data["tables"] = table_data
        
        # Extract links if mentioned
        if "link" in instructions_lower or "url" in instructions_lower:
            links = []
            for link in soup.find_all('a', href=True)[:20]:  # First 20 links
                links.append({
                    "text": link.text.strip(),
                    "url": urljoin(url, link['href'])
                })
            extracted_data["links"] = links
        
        # Extract images if mentioned
        if "image" in instructions_lower:
            images = []
            for img in soup.find_all('img', src=True)[:10]:  # First 10 images
                images.append({
                    "alt": img.get('alt', ''),
                    "src": urljoin(url, img['src'])
                })
            extracted_data["images"] = images
        
        # Add custom instruction note
        extracted_data["extraction_note"] = f"Data extracted based on instructions: {instructions}"
        
        return {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": extracted_data,
            "status": "success"
        }
        
    except requests.RequestException as e:
        return {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": None,
            "error": f"Request error: {str(e)}",
            "status": "error"
        }
    except Exception as e:
        return {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": None,
            "error": f"Parsing error: {str(e)}",
            "status": "error"
        }


def validate_data(data: Dict[str, Any], max_age_hours: int = 12) -> bool:
    """
    Validate if data is fresh enough based on timestamp.
    
    Args:
        data: Dict containing a 'timestamp' field
        max_age_hours: Maximum age in hours (default 12)
        
    Returns:
        True if data is fresh enough, False otherwise
    """
    try:
        # Get timestamp from data
        timestamp_str = data.get('timestamp')
        if not timestamp_str:
            return False
        
        # Parse timestamp
        if isinstance(timestamp_str, str):
            # Try multiple timestamp formats
            for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                try:
                    timestamp = datetime.strptime(timestamp_str.replace("+00:00", ""), fmt.replace("%z", ""))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    break
                except:
                    continue
            else:
                # If no format worked, try fromisoformat
                timestamp = datetime.fromisoformat(timestamp_str)
        elif isinstance(timestamp_str, datetime):
            timestamp = timestamp_str
        else:
            return False
        
        # Ensure timezone aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Check age
        current_time = datetime.now(timezone.utc)
        age = current_time - timestamp
        
        return age < timedelta(hours=max_age_hours)
        
    except Exception:
        return False


def code_execution_for_backtest(code: str) -> str:
    """
    Safely execute Python code for backtesting.
    Restricts to safe libraries and returns execution result.
    
    Args:
        code: Python code to execute
        
    Returns:
        Execution result as string
    """
    # Define allowed modules
    allowed_modules = {
        'numpy': np,
        'np': np,
        'pandas': pd,
        'pd': pd,
        'datetime': datetime,
        'math': __import__('math'),
        'statistics': __import__('statistics'),
        'json': json,
        're': re,
        'yfinance': yf,
        'yf': yf
    }
    
    # Additional allowed built-ins
    allowed_builtins = {
        'abs': abs,
        'all': all,
        'any': any,
        'len': len,
        'max': max,
        'min': min,
        'sum': sum,
        'sorted': sorted,
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'print': print,
        'round': round,
        '__import__': __import__,  # Allow import for the allowed modules
    }
    
    try:
        # Basic security check - disallow dangerous operations
        dangerous_patterns = [
            'exec', 'eval', 'compile', 'open',
            'file', 'input', 'raw_input', '__builtins__',
            'globals', 'locals', 'vars', 'dir', 'help',
            'reload', 'getattr', 'setattr', 'delattr',
            'type', 'isinstance', 'issubclass', 'callable',
            'classmethod', 'staticmethod', 'property',
            'super', 'object', 'bytes', 'bytearray',
            'memoryview', 'complex', 'frozenset',
            'os', 'sys', 'subprocess', 'socket',
            'importlib', 'pkgutil', 'inspect'
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                return f"Error: Dangerous operation '{pattern}' not allowed in backtesting code."
        
        # Create a restricted execution environment
        restricted_globals = {
            '__builtins__': allowed_builtins,
            **allowed_modules
        }
        
        # Capture output
        output_buffer = io.StringIO()
        
        # Execute code with output capture
        with contextlib.redirect_stdout(output_buffer):
            # Parse and compile the code
            tree = ast.parse(code)
            compiled = compile(tree, '<backtest>', 'exec')
            
            # Execute in restricted environment
            exec(compiled, restricted_globals, {})
        
        # Get the output
        result = output_buffer.getvalue()
        
        # If no output was printed, try to get the last expression value
        if not result and tree.body:
            last_stmt = tree.body[-1]
            if isinstance(last_stmt, ast.Expr):
                # Compile just the last expression
                expr_code = compile(ast.Expression(last_stmt.value), '<backtest>', 'eval')
                last_value = eval(expr_code, restricted_globals, {})
                if last_value is not None:
                    result = str(last_value)
        
        return result if result else "Code executed successfully (no output)."
        
    except SyntaxError as e:
        return f"Syntax Error: {str(e)}"
    except Exception as e:
        return f"Execution Error: {type(e).__name__}: {str(e)}"


def get_onchain_metrics(asset: str, metric: str) -> Dict[str, Any]:
    """
    Fetch on-chain metrics for crypto assets.
    Uses free APIs like CoinGecko.
    
    Args:
        asset: Cryptocurrency symbol (e.g., 'bitcoin', 'ethereum')
        metric: Metric to fetch (e.g., 'market_cap', 'volume', 'circulating_supply')
        
    Returns:
        Dict containing metric value and timestamp
    """
    try:
        # Normalize asset name for CoinGecko API
        asset_mapping = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'BNB': 'binancecoin',
            'SOL': 'solana',
            'ADA': 'cardano',
            'XRP': 'ripple',
            'DOT': 'polkadot',
            'DOGE': 'dogecoin',
            'AVAX': 'avalanche-2',
            'MATIC': 'matic-network',
            'LINK': 'chainlink',
            'UNI': 'uniswap',
            'ATOM': 'cosmos',
            'LTC': 'litecoin',
            'FTT': 'ftx-token',
            'NEAR': 'near',
            'ALGO': 'algorand',
            'BCH': 'bitcoin-cash',
            'XLM': 'stellar',
            'VET': 'vechain'
        }
        
        # Convert to CoinGecko ID
        asset_id = asset_mapping.get(asset.upper(), asset.lower())
        
        # CoinGecko API endpoint (free tier)
        url = f"https://api.coingecko.com/api/v3/coins/{asset_id}"
        
        # Add specific fields based on metric
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'true',
            'developer_data': 'true',
            'sparkline': 'false'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract specific metric
        metric_value = None
        metric_lower = metric.lower()
        
        # Market data metrics
        if 'market_data' in data:
            market_data = data['market_data']
            
            if metric_lower in ['market_cap', 'marketcap']:
                metric_value = market_data.get('market_cap', {}).get('usd')
            elif metric_lower in ['volume', '24h_volume', 'volume_24h']:
                metric_value = market_data.get('total_volume', {}).get('usd')
            elif metric_lower in ['price', 'current_price']:
                metric_value = market_data.get('current_price', {}).get('usd')
            elif metric_lower in ['circulating_supply', 'circulating']:
                metric_value = market_data.get('circulating_supply')
            elif metric_lower in ['total_supply', 'total']:
                metric_value = market_data.get('total_supply')
            elif metric_lower in ['max_supply', 'max']:
                metric_value = market_data.get('max_supply')
            elif metric_lower in ['ath', 'all_time_high']:
                metric_value = market_data.get('ath', {}).get('usd')
            elif metric_lower in ['atl', 'all_time_low']:
                metric_value = market_data.get('atl', {}).get('usd')
            elif metric_lower in ['price_change_24h', 'change_24h']:
                metric_value = market_data.get('price_change_percentage_24h')
            elif metric_lower in ['price_change_7d', 'change_7d']:
                metric_value = market_data.get('price_change_percentage_7d')
            elif metric_lower in ['price_change_30d', 'change_30d']:
                metric_value = market_data.get('price_change_percentage_30d')
        
        # Community/developer metrics
        if metric_value is None:
            if metric_lower in ['twitter_followers', 'twitter']:
                metric_value = data.get('community_data', {}).get('twitter_followers')
            elif metric_lower in ['reddit_subscribers', 'reddit']:
                metric_value = data.get('community_data', {}).get('reddit_subscribers')
            elif metric_lower in ['github_stars', 'stars']:
                metric_value = data.get('developer_data', {}).get('stars')
            elif metric_lower in ['github_forks', 'forks']:
                metric_value = data.get('developer_data', {}).get('forks')
        
        # Additional on-chain metrics (would require specialized APIs)
        if metric_value is None and metric_lower in ['active_addresses', 'transaction_count', 'hash_rate', 'difficulty']:
            # These would require specialized blockchain APIs
            return {
                "asset": asset,
                "metric": metric,
                "value": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Metric '{metric}' requires specialized blockchain API access",
                "available_metrics": [
                    "market_cap", "volume", "price", "circulating_supply",
                    "total_supply", "max_supply", "ath", "atl",
                    "price_change_24h", "price_change_7d", "price_change_30d",
                    "twitter_followers", "reddit_subscribers", "github_stars", "github_forks"
                ]
            }
        
        return {
            "asset": asset,
            "metric": metric,
            "value": metric_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_updated": data.get('last_updated', datetime.now(timezone.utc).isoformat()),
            "currency": "USD" if metric_value and "price" in metric_lower or "market_cap" in metric_lower or "volume" in metric_lower else None
        }
        
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return {
                "asset": asset,
                "metric": metric,
                "value": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"Asset '{asset}' not found. Try using full name (e.g., 'bitcoin' instead of 'BTC')"
            }
        else:
            return {
                "asset": asset,
                "metric": metric,
                "value": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": f"API error: {str(e)}"
            }
    except Exception as e:
        return {
            "asset": asset,
            "metric": metric,
            "value": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": f"Error fetching metric: {str(e)}"
        }


# Helper function for URL joining (in case urllib.parse.urljoin is not imported)
def urljoin(base: str, url: str) -> str:
    """Join a base URL and a potentially relative URL."""
    if url.startswith(('http://', 'https://', '//')):
        return url
    if base.endswith('/'):
        return base + url
    return base + '/' + url


# Example usage and testing
if __name__ == "__main__":
    # Test fetch_current_price
    print("Testing fetch_current_price...")
    result = fetch_current_price("AAPL")
    print(json.dumps(result, indent=2))
    print()
    
    # Test search_web_for_news
    print("Testing search_web_for_news...")
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    news = search_web_for_news("AAPL earnings", yesterday, today)
    print(f"Found {len(news)} news items")
    if news:
        print(json.dumps(news[0], indent=2))
    print()
    
    # Test validate_data
    print("Testing validate_data...")
    test_data = {"timestamp": datetime.now(timezone.utc).isoformat()}
    print(f"Current data valid: {validate_data(test_data)}")
    old_data = {"timestamp": (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()}
    print(f"13-hour old data valid: {validate_data(old_data)}")
    print()
    
    # Test code_execution_for_backtest
    print("Testing code_execution_for_backtest...")
    test_code = """
import numpy as np
import pandas as pd

# Simple moving average calculation
prices = [100, 102, 101, 103, 105, 104, 106]
sma = np.mean(prices)
print(f"Simple Moving Average: {sma:.2f}")

# Return calculation
returns = pd.Series(prices).pct_change().dropna()
print(f"Average Return: {returns.mean():.4f}")
"""
    result = code_execution_for_backtest(test_code)
    print(result)
    print()
    
    # Test get_onchain_metrics
    print("Testing get_onchain_metrics...")
    btc_metrics = get_onchain_metrics("BTC", "market_cap")
    print(json.dumps(btc_metrics, indent=2))