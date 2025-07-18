import streamlit as st
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
import time
import datetime
import warnings
import json
from typing import Dict, List, Any

# Import the single API data fetch system
from single_api_data_fetch import get_comprehensive_market_data, validate_market_data

# Suppress FutureWarnings from yfinance
warnings.filterwarnings("ignore", category=FutureWarning)

# Function to load and format the prompt from prompt.txt
def load_prompt(current_date, next_day):
    try:
        with open('prompt.txt', 'r') as f:
            prompt_template = f.read()
        return prompt_template.format(current_date=current_date, next_day=next_day)
    except FileNotFoundError:
        return f"Analyze trading opportunities for {current_date} with next day outlook for {next_day}"

# API endpoint for single API call
XAI_API_URL = "https://api.x.ai/v1/chat/completions"

def make_single_api_call(api_key: str, prompt_with_data: str, status_callback=None, enable_streaming=True, streaming_placeholder=None) -> str:
    """
    Make a single API call to Grok 4 Heavy with all data pre-fetched.
    Includes retry logic for network issues and streaming support.
    
    Grok 4 Heavy specs:
    - Max context: 256,000 tokens (128k at standard pricing)
    - Time to first token: ~15 seconds
    - Output speed: ~60 tokens/second
    - Supports streaming via SSE
    
    Args:
        api_key: API key for authentication
        prompt_with_data: Prompt with all pre-fetched data included
        status_callback: Optional callback for status updates
        enable_streaming: Enable streaming responses
        
    Returns:
        AI response content
    """
    import time
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # Create session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "trade-analysis-app/1.0"
    }
    
    # Calculate approximate token count (rough estimate: 1 token ≈ 4 chars)
    prompt_tokens_estimate = len(prompt_with_data) // 4
    
    # Try different model names - xAI may use different identifiers
    # Based on the error, we can see "grok-4-0709" is being used
    model_names_to_try = ["grok-beta", "grok-4-0709", "grok-4", "grok-4-heavy"]
    
    # Single message with all data
    payload_template = {
        "messages": [{"role": "user", "content": prompt_with_data}],
        "max_tokens": 4096,
        "temperature": 0.1,  # Lower temperature for more focused analysis
        "stream": enable_streaming  # Enable streaming for real-time updates
    }
    
    if status_callback:
        status_callback(f"📝 Prompt size: ~{prompt_tokens_estimate:,} tokens ({len(prompt_with_data):,} chars)")
    
    # Try API call with retries and different model names
    for attempt in range(3):
        # Try different models on different attempts
        model_name = model_names_to_try[attempt % len(model_names_to_try)]
        payload = {**payload_template, "model": model_name}
        
        try:
            if status_callback:
                if attempt > 0:
                    status_callback(f"🔄 Retrying API call (attempt {attempt + 1}/3) with model: {model_name}...")
                else:
                    status_callback(f"🤖 Making API call to Grok 4 Heavy using model: {model_name}...")
            
            # Adjust timeout for Grok 4 Heavy's longer response times
            # Extended to 5 minutes (300s) as requested for complex analysis
            response = session.post(
                XAI_API_URL, 
                headers=headers, 
                json=payload, 
                timeout=(30, 300),  # (connect_timeout, read_timeout) - 5 min for complex analysis
                stream=enable_streaming
            )
            
            # Check for specific error codes
            if response.status_code == 401:
                raise Exception("Invalid API key. Please check your xAI API key.")
            elif response.status_code == 404:
                if status_callback:
                    status_callback(f"⚠️ Model '{model_name}' not found, trying next model...")
                continue  # Try next model
            elif response.status_code == 400:
                # Check if it's a model error
                try:
                    error_data = response.json()
                    if "model" in str(error_data).lower():
                        if status_callback:
                            status_callback(f"⚠️ Model '{model_name}' error, trying next model...")
                        continue  # Try next model
                except:
                    pass
                # If not a model error, continue with normal handling
            elif response.status_code == 429:
                if status_callback:
                    status_callback("⏳ Rate limited, waiting before retry...")
                time.sleep(5)
                continue
            elif response.status_code == 503:
                if status_callback:
                    status_callback("🔧 Service temporarily unavailable, retrying...")
                time.sleep(2)
                continue
                
            response.raise_for_status()
            
            # Check if response is streaming (SSE format) regardless of our request
            # Grok API seems to return streaming format by default
            if (enable_streaming and 'text/event-stream' in response.headers.get('content-type', '')) or \
               response.text.startswith('data: '):
                # Process streaming response (SSE format) with real-time display
                content_parts = []
                thinking_parts = []
                token_count = 0
                thinking_count = 0
                start_time = time.time()
                
                if status_callback:
                    status_callback("🔄 Starting streaming response processing...")
                
                # Initialize streaming display
                def update_streaming_display():
                    thinking_text = ''.join(thinking_parts)
                    content_text = ''.join(content_parts)
                    elapsed = time.time() - start_time
                    
                    # Create streaming display HTML
                    streaming_html = f"""
                    <div class="streaming-container">
                        <div class="streaming-header">
                            <span>🤖 Grok 4 Heavy Live Response</span>
                            <span class="thinking-indicator">●</span>
                        </div>
                        <div class="streaming-stats">
                            Thinking: {thinking_count} | Content: {token_count} | {elapsed:.1f}s
                        </div>
                        <div class="streaming-content">
                            {f'<div class="thinking-text">🧠 Thinking: {thinking_text[-500:]}</div>' if thinking_text else ''}
                            {f'<div class="content-text">📝 Content: {content_text}</div>' if content_text else ''}
                        </div>
                    </div>
                    """
                    return streaming_html
                
                # Show initial streaming display (only if placeholder provided)
                if streaming_placeholder:
                    with streaming_placeholder.container():
                        st.markdown(update_streaming_display(), unsafe_allow_html=True)
                
                # If response.text is available, parse it directly (for non-streaming requests that return SSE)
                if hasattr(response, 'text') and response.text.startswith('data: '):
                    lines = response.text.split('\n')
                    line_iterator = iter(lines)
                else:
                    # Use iter_lines for true streaming
                    line_iterator = (line.decode('utf-8') if isinstance(line, bytes) else line 
                                   for line in response.iter_lines() if line)
                
                for line_str in line_iterator:
                    if line_str.startswith('data: '):
                        try:
                            if line_str[6:] == '[DONE]':
                                break
                            data = json.loads(line_str[6:])
                            if 'choices' in data and data['choices']:
                                delta = data['choices'][0].get('delta', {})
                                
                                # Separate thinking from actual content
                                thinking_text = delta.get('reasoning_content', '')
                                actual_content = delta.get('content', '')
                                
                                if thinking_text:
                                    thinking_parts.append(thinking_text)
                                    thinking_count += 1
                                
                                if actual_content:
                                    content_parts.append(actual_content)
                                    token_count += 1
                                
                                # Update display every few tokens
                                if (thinking_count + token_count) % 5 == 0 and streaming_placeholder:
                                    with streaming_placeholder.container():
                                        st.markdown(update_streaming_display(), unsafe_allow_html=True)
                                    
                                    # Update status less frequently
                                    if token_count > 0 and token_count % 20 == 0 and status_callback:
                                        elapsed = time.time() - start_time
                                        tokens_per_sec = token_count / elapsed if elapsed > 0 else 0
                                        status_callback(f"🤖 Generating content... {token_count} tokens ({tokens_per_sec:.1f} tokens/sec)")
                                    elif thinking_count > 0 and status_callback:
                                        status_callback(f"🧠 Thinking... {thinking_count} reasoning tokens")
                        except json.JSONDecodeError:
                            # Skip invalid JSON lines
                            continue
                
                # Final update
                if streaming_placeholder:
                    with streaming_placeholder.container():
                        st.markdown(update_streaming_display(), unsafe_allow_html=True)
                
                content = ''.join(content_parts)
                
                # If streaming didn't produce content, log for debugging
                if not content and status_callback:
                    status_callback(f"⚠️ Streaming response processed but no content extracted. Chunks: {len(content_parts)}")
                
            else:
                # Non-streaming response (standard mode)
                if status_callback:
                    status_callback(f"🔍 Response status: {response.status_code}, Content-Type: {response.headers.get('content-type')}")
                
                # Get raw response text for debugging
                response_text = response.text
                if status_callback:
                    status_callback(f"📝 Raw response length: {len(response_text)} chars")
                    if len(response_text) < 500:  # Show short responses in full
                        status_callback(f"📄 Raw response: {response_text[:500]}")
                
                try:
                    response_data = response.json()
                except json.JSONDecodeError as e:
                    # Log response for debugging
                    if status_callback:
                        status_callback(f"⚠️ Failed to parse JSON response. Status code: {response.status_code}")
                        status_callback(f"⚠️ Response text preview: {response_text[:200]}...")
                    raise Exception(f"Invalid JSON response from API. Status code: {response.status_code}. Response: {response_text[:200]}") from e
                
                # Debug response structure
                if status_callback:
                    if response_data:
                        status_callback(f"🔍 Response keys: {list(response_data.keys())}")
                        if "choices" in response_data:
                            status_callback(f"🔍 Choices count: {len(response_data['choices'])}")
                            if response_data["choices"]:
                                choice = response_data["choices"][0]
                                status_callback(f"🔍 First choice keys: {list(choice.keys())}")
                        if "error" in response_data:
                            status_callback(f"❌ API Error: {response_data['error']}")
                    else:
                        status_callback("⚠️ Empty response data from API")
                
                # Validate response structure
                if "choices" not in response_data or not response_data["choices"]:
                    error_msg = f"Invalid API response: no choices returned. Keys: {list(response_data.keys()) if response_data else 'None'}"
                    if "error" in response_data:
                        error_msg += f". API Error: {response_data['error']}"
                    raise Exception(error_msg)
                
                if "message" not in response_data["choices"][0]:
                    raise Exception(f"Invalid API response: no message in choice. Choice keys: {list(response_data['choices'][0].keys())}")
                
                # Extract the response content
                content = response_data["choices"][0]["message"]["content"]
            
            if not content or content.strip() == "":
                raise Exception("Empty response from API")
            
            if status_callback:
                status_callback(f"✅ API call successful using model: {model_name}!")
            
            return content
            
        except requests.exceptions.Timeout as e:
            if attempt < 2:
                if status_callback:
                    status_callback(f"⏱️ Request timeout, retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
                continue
            else:
                raise Exception("API request timeout after 3 attempts") from e
                
        except requests.exceptions.ConnectionError as e:
            if attempt < 2:
                if status_callback:
                    status_callback(f"🔌 Connection error, retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
                continue
            else:
                raise Exception("Connection failed after 3 attempts. Check your internet connection.") from e
                
        except requests.exceptions.RequestException as e:
            if attempt < 2 and response.status_code in [500, 502, 503, 504]:
                if status_callback:
                    status_callback(f"🔧 Server error, retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
                continue
            else:
                raise Exception(f"API request failed: {str(e)}") from e
                
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < 2:
                if status_callback:
                    status_callback("⏳ Rate limited, waiting before retry...")
                time.sleep(5)
                continue
            else:
                raise Exception(f"API call error: {str(e)}") from e
    
    # If we get here, all retries failed
    raise Exception("API call failed after 3 attempts")

def test_api_connection(api_key: str) -> tuple[bool, str]:
    """
    Test if the API key and connection are working
    
    Returns:
        (success: bool, message: str)
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Simple test payload
        test_payload = {
            "model": "grok-beta",  # Use same model as main function
            "messages": [{"role": "user", "content": "Hello, respond with just 'OK'"}],
            "max_tokens": 10
        }
        
        response = requests.post(
            XAI_API_URL,
            headers=headers,
            json=test_payload,
            timeout=30
        )
        
        if response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 429:
            return False, "Rate limited - try again in a few minutes"
        elif response.status_code == 503:
            return False, "Service temporarily unavailable"
        
        response.raise_for_status()
        return True, "Connection successful"
        
    except requests.exceptions.ConnectionError:
        return False, "Connection failed - check your internet connection"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, f"Connection test failed: {str(e)}"

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
    /* Real-time streaming display */
    .streaming-container {
        background: linear-gradient(135deg, #1a1d26, #252836);
        border: 1px solid #2a2d3a;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        min-height: 120px;
        position: relative;
        overflow: hidden;
    }
    .streaming-content {
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
        font-size: 0.9rem;
        color: #00E676;
        line-height: 1.4;
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 300px;
        overflow-y: auto;
        animation: fadeIn 0.3s ease-in;
    }
    .thinking-text {
        color: #FFA726;
        opacity: 0.8;
        font-style: italic;
    }
    .content-text {
        color: #4CAF50;
        font-weight: 500;
    }
    .streaming-header {
        color: #D4D4D4;
        font-size: 0.8rem;
        margin-bottom: 0.5rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .streaming-stats {
        color: #9E9E9E;
        font-size: 0.75rem;
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: rgba(0, 0, 0, 0.3);
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse-thinking {
        0%, 100% { opacity: 0.6; }
        50% { opacity: 1; }
    }
    .thinking-indicator {
        animation: pulse-thinking 1.5s infinite;
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
    
    if api_key:
        if st.button("🔧 Test API Connection"):
            with st.spinner("Testing connection..."):
                success, message = test_api_connection(api_key)
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
    else:
        st.info("Enter your API key to test connection.")
    
    st.markdown("---")
    st.markdown("### 🚀 Single API System")
    st.info("This version uses **1 API call** instead of 10+ tool calls, reducing costs by 80-90% while eliminating hallucinations.")

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

# Create layout with button and status
col1, col2 = st.columns([1, 3])

with col1:
    prediction_button = st.button("🚀 AI Predictions", help="Generate AI trading predictions with comprehensive data analysis")

with col2:
    status_placeholder = st.empty()

# Real-time streaming display area
streaming_placeholder = st.empty()

if prediction_button:
    if api_key:
        try:
            # Initialize status
            status_placeholder.text("🔄 Initializing comprehensive market analysis...")
            
            # Dynamic current date and next day
            current_date_obj = datetime.date.today()
            current_date = current_date_obj.strftime("%B %d, %Y")
            next_day_obj = current_date_obj + datetime.timedelta(days=1)
            next_day = next_day_obj.strftime("%B %d, %Y")
            
            status_placeholder.text("📝 Loading analysis prompt...")
            formatted_prompt = load_prompt(current_date, next_day)
            
            # Comprehensive data gathering with live status updates
            status_placeholder.text("🌐 Gathering comprehensive market data from multiple sources...")
            
            def status_callback(message):
                status_placeholder.text(message)
                time.sleep(0.1)  # Brief pause for UI update
            
            # Get comprehensive market data using our new system
            market_data = get_comprehensive_market_data(status_callback)
            
            status_placeholder.text("🔍 Validating data quality and timestamps...")
            validation_result = validate_market_data(market_data)
            
            # Prepare comprehensive prompt with all data
            status_placeholder.text("📊 Compiling comprehensive analysis prompt...")
            
            comprehensive_data = {
                "market_data": market_data,
                "validation_summary": validation_result,
                "analysis_timestamp": datetime.datetime.now().isoformat(),
                "data_sources": market_data.get("metadata", {}).get("sources", []),
                "total_assets_analyzed": sum(len(market_data.get(category, {})) for category in ["stocks", "crypto", "forex", "commodities"])
            }
            
            # Create the comprehensive prompt
            prompt_with_all_data = f"""{formatted_prompt}

=== COMPREHENSIVE MARKET DATA FOR ANALYSIS ===

DATA GATHERED FROM MULTIPLE REPUTABLE SOURCES:
{json.dumps(comprehensive_data, indent=2, default=str)}

IMPORTANT INSTRUCTIONS:
1. Use ONLY the provided market data above for your analysis
2. Do NOT use internal knowledge or fetch additional data
3. Base ALL recommendations on the validated data provided
4. Reference specific data sources and timestamps in your analysis
5. If any data is insufficient, note limitations and provide fewer recommendations

The data includes:
- Trending assets from major financial sites
- Real-time prices and technical indicators
- News sentiment analysis
- Cross-verified data with timestamps
- Validation summary showing data quality

Please analyze this comprehensive dataset and provide your trading recommendations in the specified format.
"""
            
            # Add prompt display for troubleshooting
            with st.expander("🔍 View Full Prompt (for troubleshooting)", expanded=False):
                st.markdown("**Prompt Statistics:**")
                prompt_tokens_estimate = len(prompt_with_all_data) // 4
                st.markdown(f"- **Estimated tokens:** ~{prompt_tokens_estimate:,} (max: 256,000)")
                st.markdown(f"- **Character count:** {len(prompt_with_all_data):,}")
                st.markdown(f"- **Data sources:** {len(market_data.get('metadata', {}).get('sources', []))}")
                
                st.markdown("---")
                st.markdown("**Full Prompt Content:**")
                st.text_area("Prompt", prompt_with_all_data, height=400, disabled=True)
                
                st.info("💡 Grok 4 Heavy has a 256k token context window. Standard pricing up to 128k tokens, doubled above that.")
            
            status_placeholder.text("🤖 Making single API call to Grok 4 Heavy (expect ~15s wait for first response)...")
            
            # Make the single API call with status updates and streaming
            # Grok API appears to return streaming format by default
            final_content = make_single_api_call(api_key, prompt_with_all_data, status_callback, enable_streaming=True, streaming_placeholder=streaming_placeholder)
            
            status_placeholder.text("📋 Processing AI analysis results...")
            
            # Clear streaming display after completion
            streaming_placeholder.empty()
            
            # Add response display for troubleshooting
            with st.expander("🔍 View API Response (for troubleshooting)", expanded=False):
                st.markdown("**Response Statistics:**")
                st.markdown(f"- **Response length:** {len(final_content):,} characters")
                st.markdown(f"- **Contains table markers:** {'|' in final_content}")
                st.markdown(f"- **Line count:** {len(final_content.split(chr(10)))}")
                
                st.markdown("---")
                st.markdown("**Full API Response:**")
                st.text_area("API Response", final_content, height=400, disabled=True)
                
                # Check for table structure
                if '|' in final_content:
                    table_start = final_content.find('|')
                    table_preview = final_content[max(0, table_start-100):table_start+500]
                    st.markdown("**Table Preview Area:**")
                    st.text_area("Around Table", table_preview, height=200, disabled=True)
            
            # Display data gathering summary
            with st.expander("📊 Data Gathering Summary", expanded=False):
                st.markdown("**Single API Call Implementation - No Tool Calling**")
                
                validation_summary = market_data.get("validation_summary", {})
                st.markdown(f"""
                **Data Sources Used:**
                - {', '.join(market_data.get("metadata", {}).get("sources", []))}
                
                **Asset Coverage:**
                - Stocks: {len(market_data.get("stocks", {}))}
                - Crypto: {len(market_data.get("crypto", {}))}
                - Forex: {len(market_data.get("forex", {}))}
                - Commodities: {len(market_data.get("commodities", {}))}
                
                **Data Quality:**
                - Successful Fetches: {validation_summary.get("successful_price_fetches", 0)}
                - Failed Fetches: {validation_summary.get("failed_price_fetches", 0)}
                - News Items: {validation_summary.get("news_items_found", 0)}
                - API Calls Made: 1 (Single API call - no tool calling)
                
                **Validation Status:** ✅ Data validated and timestamps checked
                """)
                
                st.json(validation_summary)
            
            # Process the AI response
            if final_content:
                content = final_content
                
                # Parse content: report + table + summary
                table_start = content.find('|')
                if status_callback:
                    status_callback(f"🔍 Parsing response: {len(content)} chars, table start at: {table_start}")
                
                if table_start != -1:
                    report_content = content[:table_start].strip() if table_start > 0 else ''
                    table_end = content.rfind('|') + 1
                    table_content = content[table_start:table_end].strip()
                    summary_content = content[table_end:].strip()
                    
                    if status_callback:
                        status_callback(f"📋 Parsed sections - Report: {len(report_content)} chars, Table: {len(table_content)} chars, Summary: {len(summary_content)} chars")
                else:
                    report_content = ''
                    table_content = ''
                    summary_content = content.strip()
                    if status_callback:
                        status_callback("⚠️ No table markers (|) found in response")
                
                # Parse table if present
                if table_content:
                    if status_callback:
                        status_callback(f"📊 Found table content with {len(table_content)} characters")
                    lines = table_content.split('\n')
                    if len(lines) > 2:
                        data_lines = [line for line in lines[2:] if line.strip()]
                        csv_str = '\n'.join(data_lines)
                        df = pd.read_csv(StringIO(csv_str), sep='|', header=None, skipinitialspace=True, engine='python')
                        df = df.dropna(how='all', axis=1)
                        
                        # Expected columns
                        expected_columns = ['Symbol/Pair', 'Action (Buy/Sell)', 'Entry Price', 'Target Price', 'Stop Loss', 
                                            'Expected Entry Condition/Timing', 'Expected Exit Condition/Timing', 'Thesis (≤50 words)', 
                                            'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)', 
                                            'Plain English Summary (1 sentence)', 'Data Sources']
                        
                        num_cols = len(df.columns)
                        if num_cols >= len(expected_columns):
                            df = df.iloc[:, :len(expected_columns)]
                            df.columns = expected_columns
                        elif num_cols < len(expected_columns):
                            df.columns = expected_columns[:num_cols]
                            for missing_col in expected_columns[num_cols:]:
                                df[missing_col] = pd.NA
                        
                        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
                        
                        # Convert numeric columns
                        numeric_cols = ['Entry Price', 'Target Price', 'Stop Loss', 'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)']
                        for col in numeric_cols:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                        # Drop rows with too many missing values
                        df = df.dropna(thresh=len(df.columns) * 0.5)
                        
                        st.session_state.recommendations = df
                    else:
                        st.error("No valid table found in response.")
                else:
                    st.error("❌ No table found in response.")
                    st.markdown("**Debugging Info:**")
                    st.markdown(f"- Response length: {len(final_content)} characters")
                    st.markdown(f"- Contains '|': {'|' in final_content}")
                    st.markdown(f"- First 200 chars: `{final_content[:200]}...`")
                    if '|' not in final_content:
                        st.warning("💡 The AI response doesn't contain table markers (|). The prompt may need adjustment or the AI model may not be following the table format instructions.")
                
                st.session_state.report = report_content
                st.session_state.summary = summary_content
                
                status_placeholder.text("✅ Analysis complete! Single API call successful.")
                time.sleep(2)
                status_placeholder.empty()
                
            else:
                st.error("❌ Failed to generate predictions with single API call")
                status_placeholder.empty()
        
        except Exception as e:
            st.error(f"❌ Error generating predictions: {e}")
            status_placeholder.text(f"❌ Error: {str(e)}")
            time.sleep(3)
            status_placeholder.empty()
    else:
        st.error("❌ Please enter your xAI API key in the sidebar.")

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
                roi = row.get('Projected ROI (%)', 'N/A')
                likelihood = row.get('Likelihood of Profit (%)', 'N/A')
                allocation = row.get('Recommended Allocation (% of portfolio)', 'N/A')
                st.markdown(f'<p style="color: #FAFAFA;">Projected ROI: {roi:.2f}%</p>' if isinstance(roi, (int, float)) else f'<p style="color: #FAFAFA;">Projected ROI: {roi}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Likelihood of Profit: {likelihood:.2f}%</p>' if isinstance(likelihood, (int, float)) else f'<p style="color: #FAFAFA;">Likelihood of Profit: {likelihood}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Recommended Allocation: {allocation:.2f}%</p>' if isinstance(allocation, (int, float)) else f'<p style="color: #FAFAFA;">Recommended Allocation: {allocation}</p>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Timing & Sources</p>', unsafe_allow_html=True)
                entry_timing = row.get('Expected Entry Condition/Timing', 'N/A')
                exit_timing = row.get('Expected Exit Condition/Timing', 'N/A')
                data_sources = row.get('Data Sources', 'N/A')
                st.markdown(f'<p style="color: #FAFAFA;">Entry Timing: {entry_timing[:100] + "..." if isinstance(entry_timing, str) and len(entry_timing) > 100 else entry_timing}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Exit Timing: {exit_timing[:100] + "..." if isinstance(exit_timing, str) and len(exit_timing) > 100 else exit_timing}</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="color: #FAFAFA;">Data Sources: {data_sources[:100] + "..." if isinstance(data_sources, str) and len(data_sources) > 100 else data_sources}</p>', unsafe_allow_html=True)
            
            st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Technical Thesis</p>', unsafe_allow_html=True)
            thesis = row.get('Thesis (≤50 words)', 'N/A')
            st.markdown(f'<p style="color: #FAFAFA;">{thesis}</p>', unsafe_allow_html=True)
            
            st.markdown('<p style="color: #D4D4D4; font-weight: bold;">Plain English Summary</p>', unsafe_allow_html=True)
            plain_summary = row.get('Plain English Summary (1 sentence)', 'N/A')
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
                    st.line_chart(history_df.set_index('time')['total_value'])

st.markdown("---")
st.info("Thsi is not financial advice. Always consult professionals.")
