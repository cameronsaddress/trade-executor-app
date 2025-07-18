# Trade Analysis Tools

This document describes the comprehensive set of Python tool functions implemented for the trade analysis app. These tools provide real-time data fetching, news analysis, web scraping, backtesting, and on-chain metrics capabilities.

## Overview

The `tools.py` module contains six main functions designed to enhance your trade analysis workflow:

1. **fetch_current_price** - Real-time price data with validation
2. **search_web_for_news** - Financial news search with date filtering
3. **browse_page_for_data** - Web scraping for structured data extraction
4. **validate_data** - Data freshness validation
5. **code_execution_for_backtest** - Safe Python code execution for backtesting
6. **get_onchain_metrics** - Cryptocurrency on-chain metrics

## Installation

```bash
pip install -r requirements.txt
```

Required dependencies:
- yfinance
- requests
- pandas
- beautifulsoup4
- lxml
- numpy
- streamlit

## Function Documentation

### 1. fetch_current_price(symbol: str) -> dict

Fetches current price data for any financial instrument using yfinance.

**Parameters:**
- `symbol` (str): Stock/crypto symbol (e.g., 'AAPL', 'BTC-USD', 'TSLA')

**Returns:**
- `dict` containing:
  - `price` (float): Current price
  - `timestamp` (str): ISO format timestamp
  - `is_valid` (bool): True if data is <5 minutes old
  - `age_minutes` (float): Age of data in minutes
  - `currency` (str): Currency denomination
  - `error` (str): Error message if applicable

**Example:**
```python
from tools import fetch_current_price

result = fetch_current_price("AAPL")
print(f"AAPL Price: ${result['price']:.2f}")
print(f"Data is valid: {result['is_valid']}")
```

### 2. search_web_for_news(query: str, after_date: str, before_date: str) -> list[dict]

Searches for financial news with date filtering using multiple news sources.

**Parameters:**
- `query` (str): Search query
- `after_date` (str): Start date in YYYY-MM-DD format
- `before_date` (str): End date in YYYY-MM-DD format

**Returns:**
- `list[dict]` containing news items with:
  - `title` (str): News headline
  - `snippet` (str): News summary
  - `url` (str): Article URL
  - `timestamp` (str): Publication timestamp
  - `source` (str): News source

**Example:**
```python
from tools import search_web_for_news
from datetime import datetime, timedelta

today = datetime.now().strftime("%Y-%m-%d")
week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

news = search_web_for_news("AAPL earnings", week_ago, today)
for item in news:
    print(f"{item['title']} - {item['source']}")
```

### 3. browse_page_for_data(url: str, instructions: str) -> dict

Fetches and extracts structured data from web pages based on instructions.

**Parameters:**
- `url` (str): URL to fetch
- `instructions` (str): Instructions for data extraction

**Returns:**
- `dict` containing:
  - `data` (dict): Extracted data based on instructions
  - `timestamp` (str): Extraction timestamp
  - `status` (str): Success/error status
  - `error` (str): Error message if applicable

**Supported extraction patterns:**
- `title` - Page title
- `description` - Meta description
- `text` - Full text content
- `price` - Price information
- `table` - HTML tables
- `links` - All links
- `images` - All images

**Example:**
```python
from tools import browse_page_for_data

result = browse_page_for_data(
    "https://finance.yahoo.com/quote/AAPL",
    "Extract price, title, and any financial metrics"
)
print(result['data'])
```

### 4. validate_data(data: dict, max_age_hours: int = 12) -> bool

Validates if data is fresh enough based on timestamp.

**Parameters:**
- `data` (dict): Data dictionary containing 'timestamp' field
- `max_age_hours` (int): Maximum age in hours (default: 12)

**Returns:**
- `bool`: True if data is fresh enough, False otherwise

**Example:**
```python
from tools import validate_data
from datetime import datetime, timezone

data = {"timestamp": datetime.now(timezone.utc).isoformat()}
is_fresh = validate_data(data, max_age_hours=6)
print(f"Data is fresh: {is_fresh}")
```

### 5. code_execution_for_backtest(code: str) -> str

Safely executes Python code for backtesting with security restrictions.

**Parameters:**
- `code` (str): Python code to execute

**Returns:**
- `str`: Execution result or error message

**Allowed libraries:**
- numpy (as np)
- pandas (as pd)
- datetime
- math
- statistics
- json
- re
- yfinance (as yf)

**Security features:**
- Sandboxed execution environment
- Restricted built-in functions
- No file system access
- No network access (except through allowed libraries)

**Example:**
```python
from tools import code_execution_for_backtest

backtest_code = """
import numpy as np
import pandas as pd

# Simple moving average strategy
prices = [100, 102, 101, 103, 105, 104, 106, 108]
returns = pd.Series(prices).pct_change().dropna()

total_return = (prices[-1] / prices[0] - 1) * 100
print('Total Return:', round(total_return, 2), '%')
"""

result = code_execution_for_backtest(backtest_code)
print(result)
```

### 6. get_onchain_metrics(asset: str, metric: str) -> dict

Fetches on-chain metrics for cryptocurrency assets using CoinGecko API.

**Parameters:**
- `asset` (str): Cryptocurrency symbol or ID
- `metric` (str): Metric to fetch

**Returns:**
- `dict` containing:
  - `value` (float/int): Metric value
  - `timestamp` (str): Fetch timestamp
  - `currency` (str): Currency if applicable
  - `error` (str): Error message if applicable

**Supported assets:**
- BTC, ETH, BNB, SOL, ADA, XRP, DOT, DOGE, AVAX, MATIC, LINK, UNI, ATOM, LTC, NEAR, ALGO, BCH, XLM, VET
- Or use full names: bitcoin, ethereum, etc.

**Supported metrics:**
- `market_cap` - Market capitalization
- `volume` - 24h trading volume
- `price` - Current price
- `circulating_supply` - Circulating supply
- `total_supply` - Total supply
- `max_supply` - Maximum supply
- `price_change_24h` - 24h price change %
- `price_change_7d` - 7-day price change %
- `twitter_followers` - Twitter followers
- `github_stars` - GitHub stars

**Example:**
```python
from tools import get_onchain_metrics

btc_market_cap = get_onchain_metrics("BTC", "market_cap")
print(f"BTC Market Cap: ${btc_market_cap['value']:,.2f}")

eth_volume = get_onchain_metrics("ethereum", "volume")
print(f"ETH 24h Volume: ${eth_volume['value']:,.2f}")
```

## Integration Examples

### Basic Usage in Streamlit App

```python
import streamlit as st
from tools import fetch_current_price, search_web_for_news

# Get current price
symbol = st.text_input("Enter Symbol", "AAPL")
if st.button("Get Price"):
    price_data = fetch_current_price(symbol)
    if price_data['is_valid']:
        st.success(f"${price_data['price']:.2f}")
    else:
        st.warning("Data may be stale")

# Search news
if st.button("Get News"):
    news = search_web_for_news(symbol, "2024-01-01", "2024-01-31")
    for item in news:
        st.write(f"**{item['title']}** - {item['source']}")
```

### Comprehensive Analysis Function

```python
from tools import *
from datetime import datetime, timedelta

def comprehensive_analysis(symbol):
    """Perform comprehensive analysis using multiple tools."""
    results = {}
    
    # Get current price
    results['price'] = fetch_current_price(symbol)
    
    # Get recent news
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    results['news'] = search_web_for_news(f"{symbol} stock", week_ago, today)
    
    # Get on-chain metrics for crypto
    if symbol.endswith('-USD'):
        crypto_symbol = symbol.replace('-USD', '')
        results['onchain'] = get_onchain_metrics(crypto_symbol, 'market_cap')
    
    # Validate all data
    for key, data in results.items():
        if isinstance(data, dict) and 'timestamp' in data:
            results[f'{key}_valid'] = validate_data(data)
    
    return results

# Usage
analysis = comprehensive_analysis("BTC-USD")
print(f"Price: ${analysis['price']['price']:.2f}")
print(f"Market Cap: ${analysis['onchain']['value']:,.2f}")
```

## Testing

Run the test suite to verify all functions work correctly:

```bash
python test_tools.py
```

The test suite validates:
- Price fetching for multiple symbols
- News search functionality
- Web browsing and data extraction
- Data validation logic
- Code execution safety
- On-chain metrics retrieval

## Error Handling

All functions implement comprehensive error handling:

- **Network errors**: Graceful degradation with error messages
- **Data validation**: Timestamp and freshness checks
- **Security**: Sandboxed execution for code
- **Rate limiting**: Respectful API usage
- **Fallbacks**: Alternative data sources when primary fails

## Performance Considerations

- **Caching**: 15-minute cache for web requests
- **Timeouts**: 10-15 second timeouts for all requests
- **Batch processing**: Efficient handling of multiple requests
- **Memory management**: Proper cleanup of resources

## Security Features

- **Code execution**: Sandboxed environment with restricted imports
- **Web scraping**: User-agent rotation and respectful crawling
- **API access**: No hardcoded credentials (use environment variables)
- **Input validation**: Comprehensive validation of all inputs

## Future Enhancements

Potential improvements for the tool suite:

1. **Advanced news sentiment analysis** using NLP libraries
2. **Real-time WebSocket connections** for live data feeds
3. **Machine learning backtesting** with sklearn integration
4. **Advanced on-chain metrics** from specialized blockchain APIs
5. **Multi-exchange price aggregation** for better accuracy
6. **Technical indicators** calculation library
7. **Portfolio optimization** tools using modern portfolio theory

## Support

For issues or questions:
1. Check the test suite output for debugging
2. Review error messages for specific failure reasons
3. Ensure all dependencies are installed correctly
4. Verify internet connectivity for API calls

---

*This tool suite provides a solid foundation for comprehensive financial analysis and can be extended based on specific trading strategy requirements.*