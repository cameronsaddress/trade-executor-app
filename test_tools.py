#!/usr/bin/env python3
"""
Test script for trade analysis tools.
Run this script to verify all tools are working correctly.
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

def test_all_tools():
    """Test all tool functions."""
    print("=" * 60)
    print("TESTING TRADE ANALYSIS TOOLS")
    print("=" * 60)
    
    # Test 1: fetch_current_price
    print("\n1. Testing fetch_current_price...")
    print("-" * 40)
    symbols = ["AAPL", "BTC-USD", "TSLA"]
    for symbol in symbols:
        result = fetch_current_price(symbol)
        print(f"{symbol}: ${result.get('price', 'N/A')} (Valid: {result.get('is_valid', False)})")
        if result.get('error'):
            print(f"  Error: {result['error']}")
    
    # Test 2: search_web_for_news
    print("\n2. Testing search_web_for_news...")
    print("-" * 40)
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    news = search_web_for_news("AAPL", yesterday, today)
    print(f"Found {len(news)} news items for AAPL")
    if news:
        print(f"Latest: {news[0]['title'][:80]}...")
    
    # Test 3: browse_page_for_data
    print("\n3. Testing browse_page_for_data...")
    print("-" * 40)
    try:
        result = browse_page_for_data("https://httpbin.org/html", "Extract the title and any links")
        print(f"Status: {result.get('status', 'unknown')}")
        if result.get('data'):
            print(f"Title found: {bool(result['data'].get('title'))}")
            print(f"Links found: {len(result['data'].get('links', []))}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: validate_data
    print("\n4. Testing validate_data...")
    print("-" * 40)
    from datetime import timezone
    
    # Fresh data
    fresh_data = {"timestamp": datetime.now(timezone.utc).isoformat()}
    print(f"Fresh data valid: {validate_data(fresh_data)}")
    
    # Old data (13 hours ago)
    old_data = {"timestamp": (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()}
    print(f"13-hour old data valid: {validate_data(old_data)}")
    
    # Test 5: code_execution_for_backtest
    print("\n5. Testing code_execution_for_backtest...")
    print("-" * 40)
    test_code = """
import numpy as np
import pandas as pd

# Simple backtest calculation
prices = [100, 102, 101, 103, 105, 104, 106, 108]
returns = pd.Series(prices).pct_change().dropna()

total_return = ((prices[-1] / prices[0]) - 1) * 100
avg_return = returns.mean() * 100
volatility = returns.std() * 100
sharpe = returns.mean() / returns.std()

print('Total Return:', round(total_return, 2), '%')
print('Average Daily Return:', round(avg_return, 4), '%')
print('Volatility:', round(volatility, 4), '%')
print('Sharpe Ratio:', round(sharpe, 4))
"""
    result = code_execution_for_backtest(test_code)
    print("Backtest Result:")
    print(result)
    
    # Test 6: get_onchain_metrics
    print("\n6. Testing get_onchain_metrics...")
    print("-" * 40)
    metrics_to_test = [
        ("BTC", "market_cap"),
        ("ETH", "volume"),
        ("bitcoin", "price")
    ]
    
    for asset, metric in metrics_to_test:
        result = get_onchain_metrics(asset, metric)
        if result.get('value') is not None:
            print(f"{asset} {metric}: {result['value']:,.2f}" if isinstance(result['value'], (int, float)) else f"{asset} {metric}: {result['value']}")
        else:
            print(f"{asset} {metric}: Error - {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_all_tools()