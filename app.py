import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
import time
import datetime

# Hardcoded full prompt with enhancements for real-time tool usage, dynamic date, and comprehensive analysis
# Escaped {asset} to {{asset}} to prevent KeyError during string formatting
PROMPT = """
System Instructions
You are Grok4_Heavy, Head of Trade Opportunity Research at an elite quant fund specializing in high-profit trades. Your task is to research and identify 3-7 current top trade opportunities (aiming to maximize profit potential) by analyzing live market data primarily from https://www.investing.com/ (real-time quotes, charts, news, technicals, and economics). Supplement with tool calls (e.g., browse_page for the URL, web_search for cross-verification like on-chain data or broader sentiment) if needed, ensuring core analysis uses data timestamped within the last 5 minutes. Focus on opportunities with highest expected ROI, considering volatility, momentum, risk-reward, and backtested performance. Prioritize trades yielding at least 15% profit within 1-7 days, based on historical patterns, current signals, and predictive models.
[Data Categories remain the same, but add: "Use code_execution for backtesting or simple ML predictions (e.g., trend forecasting via numpy/torch)."]

**IMPORTANT: The current date is {current_date}. ALL data MUST be fetched via tools in real-time. Do NOT use internal knowledge for prices, news, or metrics—explicitly call tools like browse_page on https://www.investing.com/ for quotes/charts/news (ensure timestamp ≤5 minutes), web_search for on-chain/cross-verification, and code_execution for backtesting. If tools return data conflicting with your knowledge (e.g., BTC >100k), use the tool data ONLY. Responses without tool citations and fresh timestamps will be invalid. To make analysis as smart as the smartest investing team, BEFORE any recommendation, use tools to read up-to-date documentation, reports, etc.: e.g., browse_page on sec.gov for latest filings, investing.com/news for catalysts, web_search for 'latest {{asset}} analyst reports 2025', and integrate insights from hedge fund strategies like those from Renaissance Technologies or Citadel (via web_search for public summaries).**

Trade Opportunity Selection Criteria
Number of Opportunities: 3-7 top trades (if fewer qualify, indicate why and suggest alternatives; do not force).
Goal: Maximize profit with projected ROI >25% in 1-7 days, minimizing downside (max drawdown <8% based on ATR/historical). Balance exposure: max 25% per asset class.
Hard Filters:
* Data timestamp ≤5 minutes (primarily from URL, verified via tools).
* Projected Profit ≥15% (based on technical targets, backtested).
* Risk-Reward ≥1:4.
* Liquidity: Avg Daily Volume ≥1M shares/units.
* Volatility: IV/HV 25-75%.
* Diversification: Max 2 per class; at least one each from stocks, forex, crypto if possible; correlation <0.5.
* Trend Alignment: RSI >55 for buys/<45 for sells; MACD crossover; backtested win rate ≥60% over 6 months.
Selection Rules
Rank by profit_score = (projected_ROI * risk_reward_ratio) + (momentum_score * 0.5) + (sentiment_score * 0.3) + (volume_z_score * 0.2) + (backtest_factor * 0.4), normalized from data/tools.
Ensure balance of buys/sells; prioritize catalysts (e.g., earnings in 1-3 days). Avoid correlated assets.
Net Impact: Total risk ≤4% of $100,000 NAV.
In ties, prioritize liquidity, lower beta, and positive catalysts. For crypto, require on-chain spikes via tools.
Use tools step-by-step for analysis (e.g., backtest via code_execution).
Output Format
Output strictly as a Markdown table with these columns:
| Symbol/Pair | Action (Buy/Sell) | Entry Price | Target Price | Stop Loss | Expected Entry Condition/Timing | Expected Exit Condition/Timing | Thesis (≤50 words) | Projected ROI (%) | Recommended Allocation (% of portfolio) | Data Sources |
If fewer than 3 qualify: "Fewer than 3 opportunities meet criteria; explore alternatives: [list 1-2 backups]." Base everything on verified data/tools. Use factual language; include brief tool citations in thesis if key.
Additional Guidelines
[Keep similar, but add: "Include timing projections based on catalysts/technicals (e.g., 'Enter post-Fed announcement'). Backtest all projections for accuracy."]
"""

# API endpoint from xAI docs
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

st.title("Trade Opportunity Executor (Paper Trading)")

api_key = st.text_input("Enter xAI Grok API Key", type="password")

# Initialize session state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=['Symbol/Pair', 'Action', 'Entry Price', 'Quantity', 'Target Price', 'Stop Loss', 'Entry Time'])
    st.session_state.history = []
    st.session_state.total_nav = 100000.0  # Starting NAV

if st.button("Generate Recommendations"):
    if api_key:
        # Dynamic current date
        current_date = datetime.date.today().strftime("%B %d, %Y")
        formatted_prompt = PROMPT.format(current_date=current_date)

        # Pre-fetch and validate real-time data for key assets before sending to API
        st.subheader("Pre-Fetching and Validating Real-Time Market Data")
        key_assets = ['BTC-USD', 'ETH-USD', 'NVDA', 'TSLA', 'EURUSD=X', 'GBPUSD=X']  # Expandable list based on common assets
        current_data = {}
        for asset in key_assets:
            try:
                data = yf.download(asset, period='1d', interval='1m')
                current_price = data['Close'][-1]
                current_data[asset] = {
                    'price': current_price,
                    'timestamp': data.index[-1].strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                current_data[asset] = {'error': str(e)}
        st.json(current_data)  # Display pre-fetched data for transparency

        # Append pre-fetched data to prompt for LLM to use/validate against
        prompt_with_data = formatted_prompt + f"\n\nPre-Fetched Real-Time Data (use and validate against this): {current_data}. Integrate this with tool calls for full analysis."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "grok-4-heavy",  # Adjust based on your console; assuming this is the model name
            "messages": [{"role": "user", "content": prompt_with_data}]
        }
        try:
            response = requests.post(XAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            st.markdown("### Generated Recommendations")
            st.markdown(content)

            # Parse markdown table
            lines = content.strip().split('\n')
            if len(lines) > 2:
                data_lines = lines[2:]  # Skip header and separator
                csv_str = '\n'.join(data_lines)
                df = pd.read_csv(StringIO(csv_str), sep='|', header=None, skipinitialspace=True, engine='python')
                df.columns = ['empty1', 'Symbol/Pair', 'Action', 'Entry Price', 'Target Price', 'Stop Loss', 'Entry Condition', 'Exit Condition', 'Thesis', 'Projected ROI (%)', 'Recommended Allocation (% of portfolio)', 'Data Sources', 'empty2']
                df = df.drop(['empty1', 'empty2'], axis=1, errors='ignore')
                df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
                
                # Post-generation validation: Check prices against live data
                st.subheader("Validating Recommendations with Real-Time Data")
                validated_df = df.copy()
                for index, row in validated_df.iterrows():
                    symbol = row['Symbol/Pair'].replace('/', '-')
                    try:
                        data = yf.download(symbol, period='1d', interval='1m')
                        current_price = data['Close'][-1]
                        suggested_entry = float(row['Entry Price'])
                        if abs(current_price - suggested_entry) > 0.05 * suggested_entry:  # 5% tolerance
                            validated_df.at[index, 'Validation'] = f"WARNING: Suggested {suggested_entry} vs. Live {current_price} (Mismatch! Overriding with live price.)"
                            validated_df.at[index, 'Entry Price'] = current_price
                        else:
                            validated_df.at[index, 'Validation'] = f"OK: Matches live price {current_price}"
                    except Exception:
                        validated_df.at[index, 'Validation'] = "Fetch Error: Could not verify."
                st.dataframe(validated_df)
                st.session_state.recommendations = validated_df  # Use validated DF
            else:
                st.error("No table found in response.")
        except Exception as e:
            st.error(f"API call failed: {e}")
    else:
        st.error("Please enter your xAI API key.")

# Place trades section
if 'recommendations' in st.session_state:
    st.subheader("Place Paper Trades")
    df = st.session_state.recommendations
    for index, row in df.iterrows():
        symbol = row['Symbol/Pair']
        if st.button(f"Place {row['Action']} for {symbol}"):
            entry_price = float(row['Entry Price'])
            allocation_pct = float(row['Recommended Allocation (% of portfolio)']) / 100
            quantity = (st.session_state.total_nav * allocation_pct) / entry_price
            new_position = {
                'Symbol/Pair': symbol,
                'Action': row['Action'],
                'Entry Price': entry_price,
                'Quantity': quantity,
                'Target Price': float(row['Target Price']),
                'Stop Loss': float(row['Stop Loss']),
                'Entry Time': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_position])], ignore_index=True)
            st.success(f"Paper trade placed for {symbol}!")

# Display and update portfolio
st.subheader("Current Portfolio")
st.dataframe(st.session_state.portfolio)

if st.button("Update Portfolio Values & Track"):
    if not st.session_state.portfolio.empty:
        current_values = []
        total_value = 0
        for _, row in st.session_state.portfolio.iterrows():
            symbol = row['Symbol/Pair'].replace('/', '-')  # Format for yfinance
            try:
                data = yf.download(symbol, period='1d', interval='1m')
                current_price = data['Close'][-1]
                value = current_price * row['Quantity']
                profit_pct = ((current_price - row['Entry Price']) / row['Entry Price'] * 100) if row['Action'] == 'Buy' else ((row['Entry Price'] - current_price) / row['Entry Price'] * 100)
                current_values.append({
                    'Symbol/Pair': row['Symbol/Pair'],
                    'Current Price': current_price,
                    'Value': value,
                    'Profit %': profit_pct
                })
                total_value += value
            except Exception:
                current_values.append({
                    'Symbol/Pair': row['Symbol/Pair'],
                    'Current Price': 'Fetch Error',
                    'Value': 'N/A',
                    'Profit %': 'N/A'
                })
        st.dataframe(pd.DataFrame(current_values))
        st.session_state.history.append({'time': time.time(), 'total_value': total_value if total_value > 0 else st.session_state.total_nav})
        st.session_state.total_nav = total_value if total_value > 0 else st.session_state.total_nav

        # Plot history
        if st.session_state.history:
            history_df = pd.DataFrame(st.session_state.history)
            st.line_chart(history_df.set_index('time')['total_value'], use_container_width=True)
    else:
        st.info("No positions in portfolio yet.")

st.info("This is a simulated paper trading app. Refresh the page to reset session state if needed.")
