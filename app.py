import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
import time
import datetime
import warnings

# Suppress FutureWarnings from yfinance
warnings.filterwarnings("ignore", category=FutureWarning)

# Hardcoded full prompt with enhancements: added likelihood column, summary paragraph, and ensured escaping
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
| Symbol/Pair | Action (Buy/Sell) | Entry Price | Target Price | Stop Loss | Expected Entry Condition/Timing | Expected Exit Condition/Timing | Thesis (≤50 words) | Projected ROI (%) | Likelihood of Profit (%) | Recommended Allocation (% of portfolio) | Data Sources |
Followed immediately by a paragraph summary (≤100 words) of the overall market outlook, key opportunities, and risks. If fewer than 3 qualify: "Fewer than 3 opportunities meet criteria; explore alternatives: [list 1-2 backups]." Base everything on verified data/tools. Use factual language; include brief tool citations in thesis if key.
Additional Guidelines
[Keep similar, but add: "Include timing projections based on catalysts/technicals (e.g., 'Enter post-Fed announcement'). Backtest all projections for accuracy. Calculate Likelihood of Profit as backtested win rate or ML-predicted probability."]
"""

# API endpoint (confirmed from official docs)
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

st.title("Professional Trade Opportunity Predictor")

with st.sidebar:
    api_key = st.text_input("Enter xAI Grok API Key", type="password")
    st.info("Enter your API key to generate predictions. This app simulates paper trading. If 404 error persists, verify your API key and model access in xAI console.")

# Initialize session state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=['Symbol/Pair', 'Action', 'Entry Price', 'Quantity', 'Target Price', 'Stop Loss', 'Entry Time'])
    st.session_state.history = []
    st.session_state.total_nav = 100000.0  # Starting NAV
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None
if 'summary' not in st.session_state:
    st.session_state.summary = ""

if st.button("AI Predictions"):
    if api_key:
        with st.spinner("Generating AI Predictions..."):
            try:
                # Dynamic current date
                current_date = datetime.date.today().strftime("%B %d, %Y")
                formatted_prompt = PROMPT.format(current_date=current_date)

                # Pre-fetch real-time data for key assets (updated tickers)
                key_assets = ['BTC-USD', 'ETH-USD', 'NVDA', 'TSLA', 'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AAPL', 'MSFT', 'GC=F']  # Changed 'GOLD' to 'GC=F'
                current_data = {}
                for asset in key_assets:
                    try:
                        data = yf.download(asset, period='1d', interval='1m', progress=False, auto_adjust=True)  # Explicit auto_adjust=True to avoid warning
                        current_price = data['Close'][-1]
                        current_data[asset] = {
                            'price': float(current_price),
                            'timestamp': data.index[-1].strftime("%Y-%m-%d %H:%M:%S")
                        }
                    except:
                        pass  # Skip if fetch fails

                # Append pre-fetched data to prompt
                prompt_with_data = formatted_prompt + f"\n\nPre-Fetched Real-Time Data (use and validate against this): {current_data}. Integrate this with tool calls for full analysis."

                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"model": "grok-4",  # Changed to 'grok-4' based on docs (assuming Heavy is a variant; adjust if needed)
                           "messages": [{"role": "user", "content": prompt_with_data}]}
                response = requests.post(XAI_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]

                # Parse content: table + summary
                if '|' in content:
                    table_end = content.rfind('|') + 1
                    table_content = content[:table_end].strip()
                    summary_content = content[table_end:].strip()

                    # Parse table
                    lines = table_content.split('\n')
                    if len(lines) > 2:
                        data_lines = [line for line in lines[2:] if line.strip()]  # Filter empty lines
                        csv_str = '\n'.join(data_lines)
                        df = pd.read_csv(StringIO(csv_str), sep='|', header=None, skipinitialspace=True, engine='python')
                        df.columns = ['empty1'] + ['Symbol/Pair', 'Action (Buy/Sell)', 'Entry Price', 'Target Price', 'Stop Loss', 
                                                   'Expected Entry Condition/Timing', 'Expected Exit Condition/Timing', 'Thesis (≤50 words)', 
                                                   'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)', 
                                                   'Data Sources'] + ['empty2']
                        df = df.drop(['empty1', 'empty2'], axis=1, errors='ignore')
                        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

                        # Convert numeric columns to float to avoid formatting errors
                        numeric_cols = ['Entry Price', 'Target Price', 'Stop Loss', 'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)']
                        for col in numeric_cols:
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                        # Validate and override prices if needed
                        for index, row in df.iterrows():
                            symbol = row['Symbol/Pair'].replace('/', '-')
                            try:
                                data = yf.download(symbol, period='1d', interval='1m', progress=False, auto_adjust=True)
                                current_price = data['Close'][-1]
                                suggested_entry = row['Entry Price']
                                if abs(current_price - suggested_entry) > 0.05 * suggested_entry:
                                    df.at[index, 'Entry Price'] = current_price  # Override with live price
                            except:
                                pass

                        st.session_state.recommendations = df
                        st.session_state.summary = summary_content
                    else:
                        st.error("No valid table found in response.")
                else:
                    st.error("Invalid response format.")
            except Exception as e:
                st.error(f"Error generating predictions: {e}")
                st.info("If you see a 404 error, double-check your API key and ensure you have access to the Grok API. The endpoint is correct per official docs.")
    else:
        st.error("Please enter your xAI API key in the sidebar.")

# Display recommendations if available
if st.session_state.recommendations is not None:
    st.markdown("### AI-Generated Trade Predictions")

    df = st.session_state.recommendations

    for index, row in df.iterrows():
        with st.container(border=True):  # Card-like container
            st.markdown(f"**{row['Symbol/Pair']}** - {row['Action (Buy/Sell)']}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Entry Price**")
                st.write(f"${row['Entry Price']:.2f}")
                st.markdown("**Target Price**")
                st.write(f"${row['Target Price']:.2f}")
                st.markdown("**Stop Loss**")
                st.write(f"${row['Stop Loss']:.2f}")
            
            with col2:
                st.markdown("**Projected ROI**")
                st.write(f"{row['Projected ROI (%)']:.2f}%")
                st.markdown("**Likelihood of Profit**")
                st.write(f"{row['Likelihood of Profit (%)']:.2f}%")
                st.markdown("**Recommended Allocation**")
                st.write(f"{row['Recommended Allocation (% of portfolio)']:.2f}%")
            
            with col3:
                st.markdown("**Entry Timing**")
                st.write(row['Expected Entry Condition/Timing'][:50] + '...' if len(row['Expected Entry Condition/Timing']) > 50 else row['Expected Entry Condition/Timing'])
                st.markdown("**Exit Timing**")
                st.write(row['Expected Exit Condition/Timing'][:50] + '...' if len(row['Expected Exit Condition/Timing']) > 50 else row['Expected Exit Condition/Timing'])
                st.markdown("**Data Sources**")
                st.write(row['Data Sources'][:50] + '...' if pd.notna(row['Data Sources']) and len(row['Data Sources']) > 50 else row['Data Sources'])
            
            st.markdown("**Thesis**")
            st.write(row['Thesis (≤50 words)'])
            
            # Buy/Sell button
            action = row['Action (Buy/Sell)']
            if st.button(f"{action} {row['Symbol/Pair']}"):
                entry_price = row['Entry Price']
                allocation_pct = row['Recommended Allocation (% of portfolio)'] / 100
                quantity = (st.session_state.total_nav * allocation_pct) / entry_price
                new_position = {
                    'Symbol/Pair': row['Symbol/Pair'],
                    'Action': action,
                    'Entry Price': entry_price,
                    'Quantity': quantity,
                    'Target Price': row['Target Price'],
                    'Stop Loss': row['Stop Loss'],
                    'Entry Time': time.strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.portfolio = pd.concat([st.session_state.portfolio, pd.DataFrame([new_position])], ignore_index=True)
                st.success(f"Paper trade placed: {action} {row['Symbol/Pair']}!")

    # Display summary paragraph
    st.markdown("### Market Summary")
    st.write(st.session_state.summary)

# Portfolio section (collapsed for simplicity)
with st.expander("View Portfolio and Performance"):
    st.subheader("Current Portfolio")
    st.dataframe(st.session_state.portfolio)

    if st.button("Update Portfolio Values"):
        with st.spinner("Updating portfolio..."):
            if not st.session_state.portfolio.empty:
                current_values = []
                total_value = 0
                for _, row in st.session_state.portfolio.iterrows():
                    symbol = row['Symbol/Pair'].replace('/', '-')
                    try:
                        data = yf.download(symbol, period='1d', interval='1m', progress=False, auto_adjust=True)
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
                    except:
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
                    st.line_chart(history_df.set_index('time')['total_value'])

st.markdown("---")
st.info("This is a simulated paper trading app for educational purposes. Not financial advice. Always consult professionals.")
```
