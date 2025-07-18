#!/usr/bin/env python3
"""
Example usage of the trade analysis tools.
This script demonstrates how to use each tool function effectively.
"""

import json
from datetime import datetime, timedelta
from tools import (
    fetch_current_price,
    search_web_for_news,
    browse_page_for_data,
    validate_data,
    code_execution_for_backtest,
    get_onchain_metrics
)

def example_price_analysis():
    """Example: Fetch and analyze current prices."""
    print("=== Price Analysis Example ===")
    
    symbols = ["AAPL", "TSLA", "BTC-USD", "ETH-USD"]
    
    for symbol in symbols:
        result = fetch_current_price(symbol)
        
        if result.get('is_valid'):
            print(f"✅ {symbol}: ${result['price']:.2f} ({result['currency']})")
            print(f"   Age: {result['age_minutes']:.1f} minutes")
        else:
            print(f"❌ {symbol}: Data unavailable or stale")
            if result.get('error'):
                print(f"   Error: {result['error']}")
    print()

def example_news_analysis():
    """Example: Search and analyze news."""
    print("=== News Analysis Example ===")
    
    # Search for recent news
    query = "Apple quarterly earnings"
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    news = search_web_for_news(query, week_ago, today)
    
    print(f"Found {len(news)} news items for '{query}':")
    for i, item in enumerate(news[:3], 1):  # Show first 3 items
        print(f"{i}. {item['title'][:60]}...")
        print(f"   Source: {item['source']}")
        print(f"   Published: {item['timestamp']}")
        print(f"   Valid: {validate_data(item)}")
        print()

def example_web_scraping():
    """Example: Extract data from web pages."""
    print("=== Web Scraping Example ===")
    
    # Example with a test URL
    url = "https://httpbin.org/html"
    instructions = "Extract title, any text content, and links"
    
    result = browse_page_for_data(url, instructions)
    
    if result.get('status') == 'success':
        print(f"✅ Successfully scraped {url}")
        print(f"Extracted data keys: {list(result['data'].keys())}")
        
        # Show some extracted data
        if 'text_content' in result['data']:
            content = result['data']['text_content']
            print(f"Text content (first 200 chars): {content[:200]}...")
    else:
        print(f"❌ Failed to scrape {url}")
        print(f"Error: {result.get('error', 'Unknown error')}")
    print()

def example_backtesting():
    """Example: Run backtesting code."""
    print("=== Backtesting Example ===")
    
    # Example of a simple momentum strategy
    backtest_code = """
import numpy as np
import pandas as pd

# Sample price data
prices = [100, 102, 98, 105, 108, 103, 110, 115, 112, 118]
returns = pd.Series(prices).pct_change().dropna()

# Calculate strategy metrics
total_return = (prices[-1] / prices[0] - 1) * 100
volatility = returns.std() * 100
sharpe_ratio = returns.mean() / returns.std()

# Simple moving average calculation
short_ma_values = []
long_ma_values = []

for i in range(len(prices)):
    if i >= 2:  # 3-period MA
        short_ma = sum(prices[i-2:i+1]) / 3
        short_ma_values.append(short_ma)
    else:
        short_ma_values.append(prices[i])
    
    if i >= 4:  # 5-period MA
        long_ma = sum(prices[i-4:i+1]) / 5
        long_ma_values.append(long_ma)
    else:
        long_ma_values.append(prices[i])

print('=== Backtest Results ===')
print('Total Return:', round(total_return, 2), '%')
print('Volatility:', round(volatility, 2), '%')
print('Sharpe Ratio:', round(sharpe_ratio, 3))
print('Final Price:', prices[-1])
print('Short MA (latest):', round(short_ma_values[-1], 2))
print('Long MA (latest):', round(long_ma_values[-1], 2))

# Generate signal
if short_ma_values[-1] > long_ma_values[-1]:
    print('Signal: BUY (Short MA > Long MA)')
else:
    print('Signal: SELL (Short MA < Long MA)')
"""
    
    result = code_execution_for_backtest(backtest_code)
    print("Backtest execution result:")
    print(result)
    print()

def example_onchain_metrics():
    """Example: Fetch on-chain metrics for crypto."""
    print("=== On-Chain Metrics Example ===")
    
    # Test different cryptocurrencies and metrics
    test_cases = [
        ("BTC", "market_cap"),
        ("ETH", "volume"),
        ("bitcoin", "price"),
        ("ethereum", "circulating_supply"),
        ("BTC", "price_change_24h")
    ]
    
    for asset, metric in test_cases:
        result = get_onchain_metrics(asset, metric)
        
        if result.get('value') is not None:
            value = result['value']
            if isinstance(value, (int, float)):
                # Format large numbers
                if value > 1e9:
                    formatted = f"{value/1e9:.2f}B"
                elif value > 1e6:
                    formatted = f"{value/1e6:.2f}M"
                elif value > 1e3:
                    formatted = f"{value/1e3:.2f}K"
                else:
                    formatted = f"{value:.2f}"
            else:
                formatted = str(value)
            
            print(f"✅ {asset.upper()} {metric}: {formatted}")
        else:
            print(f"❌ {asset.upper()} {metric}: {result.get('error', 'No data')}")
    print()

def example_comprehensive_analysis():
    """Example: Comprehensive analysis combining multiple tools."""
    print("=== Comprehensive Analysis Example ===")
    
    symbol = "AAPL"
    print(f"Analyzing {symbol}...")
    
    # 1. Get current price
    price_data = fetch_current_price(symbol)
    print(f"Current Price: ${price_data.get('price', 'N/A'):.2f}")
    
    # 2. Search for recent news
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    news = search_web_for_news(f"{symbol} stock", week_ago, today)
    print(f"Recent News Items: {len(news)}")
    
    # 3. Run a simple analysis
    current_price = price_data.get('price', 100)
    analysis_code = f"""
import pandas as pd
import numpy as np

# Use the current price in analysis
current_price = {current_price}
print('Current Price:', current_price)

# Simple technical analysis
# Simulate some historical data
base_prices = [95, 97, 99, 101, 103, 105, 107, 109, 111, 113, 
               115, 117, 119, 121, 123, 125, 127, 129, 131, current_price]

# Calculate moving averages
ma_5 = sum(base_prices[-5:]) / 5
ma_10 = sum(base_prices[-10:]) / 10

print('5-day MA:', round(ma_5, 2))
print('10-day MA:', round(ma_10, 2))

if ma_5 > ma_10:
    print('Technical Signal: BULLISH (5-day MA > 10-day MA)')
else:
    print('Technical Signal: BEARISH (5-day MA < 10-day MA)')
"""
    
    analysis_result = code_execution_for_backtest(analysis_code)
    print("Technical Analysis:")
    print(analysis_result)
    
    # 4. Validate data freshness
    all_valid = True
    if not validate_data(price_data):
        print("⚠️  Price data is stale")
        all_valid = False
    
    for item in news:
        if not validate_data(item):
            print("⚠️  Some news data is stale")
            all_valid = False
            break
    
    if all_valid:
        print("✅ All data is fresh and valid")
    
    print()

def main():
    """Run all examples."""
    print("TRADE ANALYSIS TOOLS - USAGE EXAMPLES")
    print("=" * 50)
    
    try:
        example_price_analysis()
        example_news_analysis()
        example_web_scraping()
        example_backtesting()
        example_onchain_metrics()
        example_comprehensive_analysis()
        
        print("=" * 50)
        print("All examples completed successfully!")
        print("You can now integrate these tools into your trading app.")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        print("Please check your internet connection and try again.")

if __name__ == "__main__":
    main()