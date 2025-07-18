"""
Integration example showing how to use the trade analysis tools
within the existing Streamlit app.
"""

import streamlit as st
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

def add_tools_to_app():
    """Add tool functionality to the existing Streamlit app."""
    
    # Add a section for manual tool testing
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Tool Testing")
    
    # Tool selection
    tool_option = st.sidebar.selectbox(
        "Select Tool to Test",
        ["None", "Current Price", "News Search", "Web Browse", "Backtest Code", "On-Chain Metrics"]
    )
    
    if tool_option == "Current Price":
        st.subheader("Current Price Tool")
        symbol = st.text_input("Enter Symbol (e.g., AAPL, BTC-USD)", value="AAPL")
        
        if st.button("Get Current Price"):
            with st.spinner("Fetching current price..."):
                result = fetch_current_price(symbol)
                
                if result.get('is_valid'):
                    st.success(f"✅ Fresh data (< 5 min old)")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Price", f"${result['price']:.2f}")
                    with col2:
                        st.metric("Currency", result.get('currency', 'USD'))
                    with col3:
                        st.metric("Age (min)", f"{result.get('age_minutes', 0):.1f}")
                else:
                    st.warning("⚠️ Data may be stale or unavailable")
                    if result.get('error'):
                        st.error(f"Error: {result['error']}")
                
                st.json(result)
    
    elif tool_option == "News Search":
        st.subheader("News Search Tool")
        query = st.text_input("Search Query", value="AAPL earnings")
        
        col1, col2 = st.columns(2)
        with col1:
            after_date = st.date_input("After Date", datetime.now() - timedelta(days=7))
        with col2:
            before_date = st.date_input("Before Date", datetime.now())
        
        if st.button("Search News"):
            with st.spinner("Searching for news..."):
                news = search_web_for_news(
                    query, 
                    after_date.strftime("%Y-%m-%d"),
                    before_date.strftime("%Y-%m-%d")
                )
                
                st.write(f"Found {len(news)} news items:")
                for i, item in enumerate(news):
                    with st.expander(f"📰 {item['title'][:80]}..."):
                        st.write(f"**Source:** {item['source']}")
                        st.write(f"**Published:** {item['timestamp']}")
                        st.write(f"**Summary:** {item['snippet']}")
                        if item['url']:
                            st.write(f"**URL:** {item['url']}")
    
    elif tool_option == "Web Browse":
        st.subheader("Web Browse Tool")
        url = st.text_input("URL to Browse", value="https://httpbin.org/html")
        instructions = st.text_area(
            "Extraction Instructions",
            value="Extract the title, description, and any price information"
        )
        
        if st.button("Browse Page"):
            with st.spinner("Browsing page..."):
                result = browse_page_for_data(url, instructions)
                
                if result.get('status') == 'success':
                    st.success("✅ Page browsed successfully")
                    st.json(result['data'])
                else:
                    st.error(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    elif tool_option == "Backtest Code":
        st.subheader("Backtest Code Execution")
        
        default_code = """
import numpy as np
import pandas as pd

# Simple momentum strategy backtest
prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 110]
returns = pd.Series(prices).pct_change().dropna()

# Calculate metrics
total_return = (prices[-1] / prices[0] - 1) * 100
avg_return = returns.mean() * 100
volatility = returns.std() * 100
sharpe = returns.mean() / returns.std() if returns.std() != 0 else 0

print(f"Total Return: {total_return:.2f}%")
print(f"Average Return: {avg_return:.4f}%")
print(f"Volatility: {volatility:.4f}%")
print(f"Sharpe Ratio: {sharpe:.4f}")

# Simple moving average crossover
sma_short = pd.Series(prices).rolling(3).mean()
sma_long = pd.Series(prices).rolling(5).mean()
print(f"\\nLatest SMA(3): {sma_short.iloc[-1]:.2f}")
print(f"Latest SMA(5): {sma_long.iloc[-1]:.2f}")
"""
        
        code = st.text_area("Python Code", value=default_code, height=300)
        
        if st.button("Execute Backtest"):
            with st.spinner("Executing code..."):
                result = code_execution_for_backtest(code)
                
                if "Error:" in result:
                    st.error(result)
                else:
                    st.success("✅ Code executed successfully")
                    st.code(result, language='text')
    
    elif tool_option == "On-Chain Metrics":
        st.subheader("On-Chain Metrics Tool")
        
        col1, col2 = st.columns(2)
        with col1:
            asset = st.selectbox(
                "Select Asset",
                ["BTC", "ETH", "BNB", "SOL", "ADA", "bitcoin", "ethereum"]
            )
        with col2:
            metric = st.selectbox(
                "Select Metric",
                ["market_cap", "volume", "price", "circulating_supply", 
                 "price_change_24h", "twitter_followers", "github_stars"]
            )
        
        if st.button("Get Metric"):
            with st.spinner("Fetching on-chain data..."):
                result = get_onchain_metrics(asset, metric)
                
                if result.get('value') is not None:
                    st.success("✅ Metric retrieved successfully")
                    
                    # Format the value nicely
                    value = result['value']
                    if isinstance(value, (int, float)):
                        if value > 1000000000:
                            formatted_value = f"{value/1000000000:.2f}B"
                        elif value > 1000000:
                            formatted_value = f"{value/1000000:.2f}M"
                        elif value > 1000:
                            formatted_value = f"{value/1000:.2f}K"
                        else:
                            formatted_value = f"{value:.2f}"
                    else:
                        formatted_value = str(value)
                    
                    st.metric(f"{asset.upper()} {metric.title()}", formatted_value)
                else:
                    st.error(f"❌ Error: {result.get('error', 'Unknown error')}")
                
                st.json(result)


def create_comprehensive_analysis_function():
    """Create a function that combines multiple tools for comprehensive analysis."""
    
    def comprehensive_analysis(symbol: str, include_news: bool = True, include_onchain: bool = True):
        """
        Perform comprehensive analysis using multiple tools.
        
        Args:
            symbol: Symbol to analyze
            include_news: Whether to include news analysis
            include_onchain: Whether to include on-chain metrics (for crypto)
        """
        analysis_results = {}
        
        # 1. Get current price
        price_data = fetch_current_price(symbol)
        analysis_results['price'] = price_data
        
        # 2. Get news if requested
        if include_news:
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            news_data = search_web_for_news(f"{symbol} stock", week_ago, today)
            analysis_results['news'] = news_data
        
        # 3. Get on-chain metrics if it's a crypto and requested
        if include_onchain and symbol.endswith('-USD'):
            crypto_symbol = symbol.replace('-USD', '')
            if crypto_symbol in ['BTC', 'ETH', 'BNB', 'SOL', 'ADA']:
                onchain_data = get_onchain_metrics(crypto_symbol, 'market_cap')
                analysis_results['onchain'] = onchain_data
        
        # 4. Validate all data
        for key, data in analysis_results.items():
            if isinstance(data, dict) and 'timestamp' in data:
                analysis_results[f'{key}_valid'] = validate_data(data)
        
        return analysis_results
    
    return comprehensive_analysis


# Example usage in the main app
def integrate_tools_into_main_app():
    """Show how to integrate these tools into the main app workflow."""
    
    st.markdown("### Enhanced Analysis Tools")
    st.info("These tools can be integrated into your AI prediction workflow for real-time data validation and analysis.")
    
    # Example: Real-time price validation
    st.markdown("#### Real-time Price Validation")
    st.code("""
# In your AI prediction workflow, validate prices:
def validate_ai_predictions(predictions_df):
    for idx, row in predictions_df.iterrows():
        symbol = row['Symbol/Pair']
        ai_price = row['Entry Price']
        
        # Get current price
        current_data = fetch_current_price(symbol)
        
        if current_data.get('is_valid') and current_data.get('price'):
            current_price = current_data['price']
            price_diff = abs(current_price - ai_price) / current_price * 100
            
            if price_diff > 5:  # If >5% difference
                st.warning(f"⚠️ {symbol}: AI price {ai_price} vs Current {current_price} ({price_diff:.1f}% diff)")
            else:
                st.success(f"✅ {symbol}: Price validated ({price_diff:.1f}% diff)")
    """)
    
    # Example: News sentiment integration
    st.markdown("#### News Sentiment Integration")
    st.code("""
# Add news analysis to your trading decisions:
def enhance_with_news_analysis(symbol):
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    news = search_web_for_news(f"{symbol} earnings guidance", week_ago, today)
    
    # Simple sentiment analysis (could be enhanced with NLP)
    positive_words = ['beat', 'exceed', 'growth', 'strong', 'buy', 'bullish']
    negative_words = ['miss', 'decline', 'weak', 'sell', 'bearish', 'concerns']
    
    sentiment_score = 0
    for item in news:
        text = (item['title'] + ' ' + item['snippet']).lower()
        sentiment_score += sum(1 for word in positive_words if word in text)
        sentiment_score -= sum(1 for word in negative_words if word in text)
    
    return sentiment_score, news
    """)
    
    # Example: Backtest validation
    st.markdown("#### Strategy Backtesting")
    st.code("""
# Test your trading strategy with backtesting:
def backtest_strategy(prices, buy_signals, sell_signals):
    backtest_code = f'''
import numpy as np
import pandas as pd

prices = {prices}
buy_signals = {buy_signals}
sell_signals = {sell_signals}

# Calculate returns
returns = []
position = 0
entry_price = 0

for i, (price, buy, sell) in enumerate(zip(prices, buy_signals, sell_signals)):
    if buy and position == 0:
        position = 1
        entry_price = price
    elif sell and position == 1:
        returns.append((price - entry_price) / entry_price)
        position = 0

if returns:
    total_return = (1 + np.mean(returns)) ** len(returns) - 1
    win_rate = sum(1 for r in returns if r > 0) / len(returns)
    print(f"Total Return: {{total_return:.2%}}")
    print(f"Win Rate: {{win_rate:.2%}}")
    print(f"Average Return per Trade: {{np.mean(returns):.2%}}")
else:
    print("No trades executed")
'''
    
    return code_execution_for_backtest(backtest_code)
    """)


if __name__ == "__main__":
    st.title("Trade Analysis Tools - Integration Example")
    add_tools_to_app()
    st.markdown("---")
    integrate_tools_into_main_app()