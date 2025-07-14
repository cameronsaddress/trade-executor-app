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

# Improved prompt: Enforce fetching ONLY today's real-time data from 5 top sites, cross-verification, and comprehensive report before recommendations
PROMPT = """
System Instructions
You are Grok4_Heavy, Head of Trade Opportunity Research at an elite quant fund specializing in high-profit trades. Your task is to research and identify 3-7 current top trade opportunities (aiming to maximize profit potential) by analyzing live market data STRICTLY from today ({current_date}) from the top 5 highest-ranked sites for real-time financial data: https://www.investing.com/, https://finance.yahoo.com/, https://www.google.com/finance/, https://www.bloomberg.com/markets, https://www.cnbc.com/quotes. For each asset, explicitly browse_page on relevant URLs from ALL 5 sites (e.g., for BTC/USD: https://www.investing.com/crypto/bitcoin, https://finance.yahoo.com/quote/BTC-USD, https://www.google.com/finance/quote/BTC-USD, https://www.bloomberg.com/quote/BTCUSD:CUR, https://www.cnbc.com/quotes/BTC.CB=) to fetch and cross-verify real-time quotes, charts, news, technicals, and economics. Ensure ALL data is strictly from today ({current_date}) and timestamped within the last 5 minutes—discard ANY data not explicitly from today. Cross-verify consistency across sites (e.g., if prices differ by >1%, flag and use the average from sites with today's timestamps; reject if inconsistency can't be resolved with today's data). Supplement with tool calls (e.g., web_search restricted to 'after:{current_date} before:{next_day}' for on-chain/cross-verification like 'bitcoin on-chain data {current_date} site:glassnode.com'). Focus on opportunities with highest expected ROI, considering volatility, momentum, risk-reward, and backtested performance. Prioritize trades yielding at least 15% profit within 1-7 days, based on historical patterns, current signals, and predictive models.
[Data Categories remain the same, but add: "Use code_execution for backtesting or simple ML predictions (e.g., trend forecasting via numpy/torch)."]

**IMPORTANT: The current date is {current_date} (next day is {next_day}). ALL data MUST be fetched via tools in real-time STRICTLY FROM TODAY ONLY. Do NOT use internal knowledge or any data not explicitly fetched and timestamped from {current_date}—explicitly call browse_page on each of the 5 sites for every asset analyzed (ensure timestamp ≤5 minutes from {current_date}), web_search with date filters for on-chain/cross-verification, and code_execution for backtesting using only historical data up to yesterday but projections based on today's fetches. If tools return data conflicting with your knowledge (e.g., BTC >100k), use the tool data ONLY. Responses without tool citations, fresh timestamps from today, and cross-verification from all 5 sites will be invalid. BEFORE any recommendation, compile a comprehensive report: Gather data from the 5 sites (quotes, news, technicals from {current_date} only), combine into an extremely advanced analysis (e.g., compare RSI/MACD/volumes across sources, sentiment from today's news, on-chain metrics from today), analyze discrepancies/trends/implications like a top-tier hedge fund team, and provide an expert synthesis (≤500 words) that integrates all sources for holistic insights.**

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
First, a Comprehensive Report section (≤500 words) synthesizing data from the 5 sites and tools into an advanced expert analysis, combining all sources, analyzing trends/discrepancies, and providing insights.
Then, strictly as a Markdown table with these columns:
| Symbol/Pair | Action (Buy/Sell) | Entry Price | Target Price | Stop Loss | Expected Entry Condition/Timing | Expected Exit Condition/Timing | Thesis (≤50 words) | Projected ROI (%) | Likelihood of Profit (%) | Recommended Allocation (% of portfolio) | Plain English Summary (1 sentence) | Data Sources |
Where 'Plain English Summary' is a simple 1-sentence explanation for non-traders summarizing what the analysis means (e.g., 'This suggests the stock price will rise due to strong company news, making it a good time to buy.').
Followed immediately by a paragraph summary (≤100 words) of the overall market outlook, key opportunities, and risks. If fewer than 3 qualify: "Fewer than 3 opportunities meet criteria; explore alternatives: [list 1-2 backups]." Base everything on verified data/tools. Use factual language; include brief tool citations in thesis if key.
Additional Guidelines
[Keep similar, but add: "Include timing projections based on catalysts/technicals (e.g., 'Enter post-Fed announcement'). Backtest all projections for accuracy. Calculate Likelihood of Profit as backtested win rate or ML-predicted probability."]
"""

# API endpoint (confirmed from official docs)
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

# Custom CSS for TradingView-like style: dark theme, cards with shadows, gradients, animations
st.markdown("""
    <style>
    /* Global dark theme like TradingView */
    body, .stApp {
        background-color: #0E1117 !important;
        color: #FAFAFA !important;
        font-family: 'Arial', sans-serif;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #D4D4D4 !important;
    }
    .stButton > button {
        background-color: #2962FF;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: #0039CB;
    }
    /* Card style */
    div[data-testid="column"] > div > div > div > div > div.block-container {
        background-color: #1E212A !important;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        margin-bottom: 1rem;
    }
    /* Header with gradient */
    .card-header {
        background: linear-gradient(90deg, #1E212A, #2A2D38);
        padding: 0.5rem;
        border-radius: 4px 4px 0 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .card-header h4 {
        margin: 0;
        color: #4CAF50; /* Green for buy, can dynamic */
    }
    /* Animated ticker placeholder */
    .ticker {
        font-size: 1.2rem;
        color: #00E676;
        animation: pulse 1s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    /* Section dividers */
    hr {
        border-color: #2A2D38;
    }
    /* Info box */
    .stAlert {
        background-color: #1E212A !important;
        color: #FAFAFA !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Trade Opportunity Analysis: Grok 4 Heavy")

with st.sidebar:
    api_key = st.text_input("xAI API Key", type="password")
    st.info("Enter your API key.")

# Initialize session state
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=['Symbol/Pair', 'Action', 'Entry Price', 'Quantity', 'Target Price', 'Stop Loss', 'Entry Time'])
    st.session_state.history = []
    st.session_state.total_nav = 100000.0  # Starting NAV
if 'recommendations' not in st.session_state:
    st.session_state.recommendations = None
if 'summary' not in st.session_state:
    st.session_state.summary = ""
if 'report' not in st.session_state:
    st.session_state.report = ""

if st.button("AI Predictions"):
    if api_key:
        with st.spinner("Generating AI Predictions..."):
            try:
                # Dynamic current date and next day for date filtering
                current_date_obj = datetime.date.today()
                current_date = current_date_obj.strftime("%B %d, %Y")
                next_day_obj = current_date_obj + datetime.timedelta(days=1)
                next_day = next_day_obj.strftime("%B %d, %Y")
                formatted_prompt = PROMPT.format(current_date=current_date, next_day=next_day)

                # Pre-fetch real-time data for key assets (updated tickers) from yfinance as initial validation (today's data only)
                key_assets = ['BTC-USD', 'ETH-USD', 'NVDA', 'TSLA', 'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AAPL', 'MSFT', 'GC=F']  # Changed 'GOLD' to 'GC=F'
                current_data = {}
                for asset in key_assets:
                    try:
                        data = yf.download(asset, period='1d', interval='1m', progress=False, auto_adjust=True)  # Fetches today's data only
                        if not data.empty and data.index[-1].date() == current_date_obj:
                            current_price = data['Close'][-1]
                            current_data[asset] = {
                                'price': float(current_price),
                                'timestamp': data.index[-1].strftime("%Y-%m-%d %H:%M:%S")
                            }
                        else:
                            current_data[asset] = {'error': 'No data from today'}
                    except:
                        current_data[asset] = {'error': 'Fetch failed'}

                # Append pre-fetched data to prompt (enforce use of this for validation)
                prompt_with_data = formatted_prompt + f"\n\nPre-Fetched Real-Time Data from Today Only (use and validate against this; reject if conflicts with tool fetches): {current_data}. Integrate this with tool calls for full analysis, ensuring all final prices match today's fetches."

                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"model": "grok-4",  # Changed to 'grok-4' based on docs (assuming Heavy is a variant; adjust if needed)
                           "messages": [{"role": "user", "content": prompt_with_data}]}
                response = requests.post(XAI_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]

                # Parse content: report + table + summary
                # Assume report ends with a marker, e.g., '--- End of Report ---', but since not, use heuristics: find start of table
                table_start = content.find('|')
                if table_start != -1:
                    report_content = content[:table_start].strip() if table_start > 0 else ''
                    table_end = content.rfind('|') + 1
                    table_content = content[table_start:table_end].strip()
                    summary_content = content[table_end:].strip()
                else:
                    report_content = ''
                    table_content = ''
                    summary_content = content.strip()

                # Parse table if present
                if table_content:
                    lines = table_content.split('\n')
                    if len(lines) > 2:
                        data_lines = [line for line in lines[2:] if line.strip()]  # Filter empty lines
                        csv_str = '\n'.join(data_lines)
                        df = pd.read_csv(StringIO(csv_str), sep='|', header=None, skipinitialspace=True, engine='python')
                        df.columns = ['empty1'] + ['Symbol/Pair', 'Action (Buy/Sell)', 'Entry Price', 'Target Price', 'Stop Loss', 
                                                   'Expected Entry Condition/Timing', 'Expected Exit Condition/Timing', 'Thesis (≤50 words)', 
                                                   'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)', 
                                                   'Plain English Summary (1 sentence)', 'Data Sources'] + ['empty2']
                        df = df.drop(['empty1', 'empty2'], axis=1, errors='ignore')
                        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

                        # Convert numeric columns to float, handling errors
                        numeric_cols = ['Entry Price', 'Target Price', 'Stop Loss', 'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)']
                        for col in numeric_cols:
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                        # Strict validation: Override or reject if entry_price doesn't match today's live fetch (e.g., for BTC ensure ~120k)
                        for index, row in df.iterrows():
                            symbol = row['Symbol/Pair'].replace('/', '-')
                            try:
                                data = yf.download(symbol, period='1d', interval='1m', progress=False, auto_adjust=True)
                                if not data.empty and data.index[-1].date() == current_date_obj:
                                    current_price = data['Close'][-1]
                                    if pd.isna(row['Entry Price']) or abs(current_price - row['Entry Price']) > 0.01 * current_price:  # 1% tolerance for volatility
                                        df.at[index, 'Entry Price'] = current_price  # Override with live today's price
                                else:
                                    df.drop(index, inplace=True)  # Drop if no today's data
                            except:
                                df.drop(index, inplace=True)  # Drop if fetch fails

                        # Drop rows with too many NaNs (e.g., if >50% NaN)
                        df = df.dropna(thresh=len(df.columns) * 0.5)

                        st.session_state.recommendations = df
                    else:
                        st.error("No valid table found in response.")
                else:
                    st.error("No table found in response.")

                st.session_state.report = report_content
                st.session_state.summary = summary_content

            except Exception as e:
                st.error(f"Error generating predictions: {e}")
                st.info("If you see a 404 error, double-check your API key and ensure you have access to the Grok API. The endpoint is correct per official docs.")
    else:
        st.error("Please enter your xAI API key in the sidebar.")

# Display report if available
if 'report' in st.session_state and st.session_state.report:
    st.markdown("### Comprehensive Market Report")
    st.markdown(f'<p style="color: #FAFAFA;">{st.session_state.report}</p>', unsafe_allow_html=True)

# Display recommendations if available
if st.session_state.recommendations is not None:
    st.markdown("### AI-Generated Trade Analysis")

    df = st.session_state.recommendations

    for index, row in df.iterrows():
        with st.container():  # Card-like container with custom class
            # Card header with symbol, action, and embedded TradingView ticker widget
            symbol = row['Symbol/Pair']
            action = row['Action (Buy/Sell)']
            color = "#4CAF50" if action == "Buy" else "#F44336"  # Green for buy, red for sell
            st.markdown(f"""
                <div class="card-header" style="background: linear-gradient(90deg, #1E212A, #2A2D38);">
                    <h4 style="color: {color};">{symbol} - {action}</h4>
                    <div style="margin-left: auto;">
                        <!-- TradingView Widget BEGIN -->
                        <div class="tradingview-widget-container">
                          <div class="tradingview-widget-container__widget"></div>
                          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>
                          {{
                          "symbol": "{symbol}",
                          "width": "200",
                          "height": "100",
                          "locale": "en",
                          "dateRange": "1D",
                          "colorTheme": "dark",
                          "isTransparent": true,
                          "autosize": false,
                          "largeChartUrl": ""
                          }}
                          </script>
                        </div>
                        <!-- TradingView Widget END -->
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Prices & Metrics</p>', unsafe_allow_html=True)
                entry_price = row['Entry Price'] if pd.notna(row['Entry Price']) else 'N/A'
                target_price = row['Target Price'] if pd.notna(row['Target Price']) else 'N/A'
                stop_loss = row['Stop Loss'] if pd.notna(row['Stop Loss']) else 'N/A'
                st.markdown(f'<p style="color: #FAFAFA;">Entry Price: ${entry_price:.2f}</p>' if isinstance(entry_price, (int, float)) else f'<p style="color: #FAFAFA;">Entry Price: {entry_price}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Target Price: ${target_price:.2f}</p>' if isinstance(target_price, (int, float)) else f'<p style="color: #FAFAFA;">Target Price: {target_price}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Stop Loss: ${stop_loss:.2f}</p>' if isinstance(stop_loss, (int, float)) else f'<p style="color: #FAFAFA;">Stop Loss: {stop_loss}</p>', unsafe_allow_html=True)
                roi = row['Projected ROI (%)'] if pd.notna(row['Projected ROI (%)']) else 'N/A'
                likelihood = row['Likelihood of Profit (%)'] if pd.notna(row['Likelihood of Profit (%)']) else 'N/A'
                allocation = row['Recommended Allocation (% of portfolio)'] if pd.notna(row['Recommended Allocation (% of portfolio)']) else 'N/A'
                st.markdown(f'<p style="color: #FAFAFA;">Projected ROI: {roi:.2f}%</p>' if isinstance(roi, (int, float)) else f'<p style="color: #FAFAFA;">Projected ROI: {roi}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Likelihood of Profit: {likelihood:.2f}%</p>' if isinstance(likelihood, (int, float)) else f'<p style="color: #FAFAFA;">Likelihood of Profit: {likelihood}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Recommended Allocation: {allocation:.2f}%</p>' if isinstance(allocation, (int, float)) else f'<p style="color: #FAFAFA;">Recommended Allocation: {allocation}</p>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Timing & Sources</p>', unsafe_allow_html=True)
                entry_timing = row['Expected Entry Condition/Timing'] if pd.notna(row['Expected Entry Condition/Timing']) else 'N/A'
                exit_timing = row['Expected Exit Condition/Timing'] if pd.notna(row['Expected Exit Condition/Timing']) else 'N/A'
                data_sources = row['Data Sources'] if pd.notna(row['Data Sources']) else 'N/A'
                st.markdown(f'<p style="color: #FAFAFA;">Entry Timing: {entry_timing[:100] + "..." if isinstance(entry_timing, str) and len(entry_timing) > 100 else entry_timing}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Exit Timing: {exit_timing[:100] + "..." if isinstance(exit_timing, str) and len(exit_timing) > 100 else exit_timing}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Data Sources: {data_sources[:100] + "..." if isinstance(data_sources, str) and len(data_sources) > 100 else data_sources}</p>', unsafe_allow_html=True)
            
            st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Technical Thesis</p>', unsafe_allow_html=True)
            thesis = row['Thesis (≤50 words)'] if pd.notna(row['Thesis (≤50 words)']) else 'N/A'
            st.markdown(f'<p style="color: #FAFAFA;">{thesis}</p>', unsafe_allow_html=True)
            
            st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Plain English Summary</p>', unsafe_allow_html=True)
            plain_summary = row['Plain English Summary (1 sentence)'] if pd.notna(row['Plain English Summary (1 sentence)']) else 'N/A'
            st.markdown(f'<p style="color: #FAFAFA;">{plain_summary}</p>', unsafe_allow_html=True)
            
            # Action button as hyperlink to Interactive Brokers (top-rated, supports advanced orders; pre-pop via their TWS but link to trade page)
            # Note: Full pre-pop not supported publicly; linking to IBKR trade page for symbol
            ibkr_symbol = symbol.replace('-USD', '').replace('=X', '')  # Format for IBKR
            trade_url = f"https://www.interactivebrokers.com/en/trading/trade.php?symbol={ibkr_symbol}"
            st.markdown(f"""
                <a href="{trade_url}" target="_blank" style="background-color: #2962FF; color: white; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none; display: inline-block; transition: background-color 0.3s;">
                    {action} {symbol} on Interactive Brokers
                </a>
                <p style="font-size: 0.8rem; color: #9E9E9E;">(Pre-populated order details may require manual entry; IBKR is top-rated for execution.)</p>
            """, unsafe_allow_html=True)

    # Display summary paragraph
    st.markdown("### Market Summary")
    st.markdown(f'<p style="color: #FAFAFA;">{st.session_state.summary}</p>', unsafe_allow_html=True)

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
st.info("This is not financial advice. Always consult professionals.")
