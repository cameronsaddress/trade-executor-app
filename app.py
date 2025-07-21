import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
import time
import datetime
import warnings
import json
from typing import Dict, List, Any

# Import the single API data fetch system with fallback and timeout fixes
try:
    # Try the fixed version first (with timeout fixes)
    from enhanced_data_fetcher_fixed import get_comprehensive_market_data_fixed as get_comprehensive_market_data
    from single_api_data_fetch import validate_market_data  # Use validation from original
    ENHANCED_DATA_AVAILABLE = True
    TIMEOUT_FIXES_AVAILABLE = True
except ImportError:
    try:
        # Fallback to original enhanced version
        from single_api_data_fetch import get_comprehensive_market_data, validate_market_data
        ENHANCED_DATA_AVAILABLE = True
        TIMEOUT_FIXES_AVAILABLE = False
    except ImportError:
        ENHANCED_DATA_AVAILABLE = False
        TIMEOUT_FIXES_AVAILABLE = False
        # Fallback to basic data generation
        def get_comprehensive_market_data(status_callback=None):
            """Basic fallback data generation"""
            if status_callback:
                status_callback("📊 Using basic data gathering (enhanced system not available)")

            import yfinance as yf
            basic_stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
            basic_crypto = ["BTC-USD", "ETH-USD", "ADA-USD", "SOL-USD"]

            market_data = {
                "stocks": {},
                "crypto": {},
                "forex": {},
                "commodities": {},
                "metadata": {
                    "sources": ["yahoo_finance_basic"],
                    "timestamp": datetime.datetime.now().isoformat(),
                    "data_age_hours": 0
                }
            }

            # Get basic stock data
            for symbol in basic_stocks:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        market_data["stocks"][symbol] = {
                            "symbol": symbol,
                            "current_price": current_price,
                            "price_change_pct": ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0,
                            "volume": int(hist['Volume'].iloc[-1]),
                            "data_source": "yahoo_finance_basic",
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                except Exception as e:
                    if status_callback:
                        status_callback(f"⚠️ Failed to fetch {symbol}: {str(e)}")

            # Get basic crypto data
            for symbol in basic_crypto:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="5d")
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        market_data["crypto"][symbol] = {
                            "symbol": symbol,
                            "current_price": current_price,
                            "price_change_pct": ((current_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0,
                            "volume": int(hist['Volume'].iloc[-1]),
                            "data_source": "yahoo_finance_basic",
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                except Exception as e:
                    if status_callback:
                        status_callback(f"⚠️ Failed to fetch {symbol}: {str(e)}")

            return market_data

        def validate_market_data(market_data):
            """Basic validation for fallback data"""
            total_assets = sum(len(market_data.get(cat, {})) for cat in ["stocks", "crypto", "forex", "commodities"])
            return {
                "total_assets_found": total_assets,
                "successful_price_fetches": total_assets,
                "failed_price_fetches": 0,
                "news_items_found": 0,
                "data_quality_score": 0.8 if total_assets > 0 else 0.0
            }

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

                    # Create streaming display HTML with auto-scroll
                    stream_id = f"stream_{int(time.time() * 1000)}"  # Unique ID for this stream
                    streaming_html = f"""
                    <div class="streaming-container">
                        <div class="streaming-header">
                            <span>🤖 Grok 4 Heavy Live Response</span>
                            <span class="thinking-indicator">●</span>
                        </div>
                        <div class="streaming-stats">
                            Thinking: {thinking_count} | Content: {token_count} | {elapsed:.1f}s
                        </div>
                        <div id="{stream_id}" class="streaming-content auto-scroll">
                            {f'<div class="thinking-text">🧠 Thinking: {thinking_text[-500:]}</div>' if thinking_text else ''}
                            {f'<div class="content-text">📝 Content: {content_text}</div>' if content_text else ''}
                        </div>
                    </div>
                    <script>
                        // Auto-scroll to bottom when content updates
                        setTimeout(function() {{
                            var element = document.getElementById('{stream_id}');
                            if (element) {{
                                element.scrollTop = element.scrollHeight;
                            }}
                        }}, 100);
                    </script>
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
                                    # Filter out any stray HTML tags from streaming content
                                    if actual_content.strip() in ["</div>", "<div>", "</div", "<div"]:
                                        print(f"WARNING: Filtering out HTML tag from stream: {actual_content}")
                                    else:
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
    /* Enhanced Professional Trading Card Styles */
    .trading-card {
        background: linear-gradient(135deg, #1E212A 0%, #252836 100%) !important;
        border: 1px solid #2a2d3a;
        border-radius: 16px;
        padding: 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2);
        margin-bottom: 2rem;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        position: relative;
        backdrop-filter: blur(10px);
    }

    .trading-card:hover {
        transform: translateY(-4px) scale(1.01);
        box-shadow: 0 16px 64px rgba(0, 0, 0, 0.6), 0 8px 24px rgba(76, 175, 80, 0.2);
        border-color: #4CAF50;
    }

    .trading-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #4CAF50, #2196F3, #FF9800, #4CAF50);
        background-size: 300% 100%;
        animation: shimmer 4s ease-in-out infinite;
        z-index: 1;
    }

    .trading-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: url("data:image/svg+xml,%3Csvg width='20' height='20' viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.01' fill-rule='evenodd'%3E%3Ccircle cx='3' cy='3' r='3'/%3E%3Ccircle cx='13' cy='13' r='3'/%3E%3C/g%3E%3C/svg%3E");
        pointer-events: none;
        z-index: 0;
    }

    @keyframes shimmer {
        0%, 100% { background-position: 300% 0; }
        50% { background-position: -300% 0; }
    }

    /* Card Header */
    .card-header {
        background: linear-gradient(135deg, #1a1d26, #2a2d3a);
        padding: 1.25rem 1.75rem;
        border-bottom: 2px solid rgba(76, 175, 80, 0.2);
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: relative;
        z-index: 2;
    }

    .card-header::before {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, #4CAF50, transparent);
        animation: borderGlow 2s ease-in-out infinite alternate;
    }

    @keyframes borderGlow {
        0% { opacity: 0.3; }
        100% { opacity: 0.7; }
    }

    .card-header h4 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }

    .action-badge {
        padding: 0.4rem 1rem;
        border-radius: 25px;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.75px;
        background: linear-gradient(135deg, var(--action-color), var(--action-color-dark));
        color: white;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }

    .action-badge::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
        transition: left 0.6s ease;
    }

    .action-badge:hover::before {
        left: 100%;
    }

    .header-controls {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .copy-button, .expand-button, .info-button {
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        color: #D4D4D4;
        padding: 0.5rem;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        backdrop-filter: blur(5px);
    }

    .copy-button:hover, .expand-button:hover, .info-button:hover {
        background: rgba(76, 175, 80, 0.2);
        border-color: #4CAF50;
        color: #4CAF50;
        transform: scale(1.1);
    }

    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: #9E9E9E;
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #4CAF50;
        animation: pulse 2s infinite;
    }

    .confidence-badge {
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid #4CAF50;
        color: #4CAF50;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Card Content */
    .card-content {
        padding: 1.75rem;
        position: relative;
        z-index: 1;
    }

    /* Section Dividers */
    .section-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(76, 175, 80, 0.3), transparent);
        margin: 1.5rem 0;
        position: relative;
    }

    .section-divider::before {
        content: '';
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        width: 6px;
        height: 6px;
        background: #4CAF50;
        border-radius: 50%;
        box-shadow: 0 0 8px rgba(76, 175, 80, 0.5);
    }

    /* Price Section Styling */
    .price-section {
        background: linear-gradient(135deg, rgba(42, 45, 58, 0.5), rgba(26, 29, 38, 0.5));
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(76, 175, 80, 0.3);
        border-left: 4px solid #4CAF50;
        position: relative;
        overflow: hidden;
    }

    .price-section::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, #4CAF50, transparent);
        opacity: 0.6;
    }

    .price-section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }

    .price-section-title {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #4CAF50;
        font-weight: 600;
        font-size: 1.1rem;
    }

    .quick-calc {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: #9E9E9E;
        background: rgba(255, 255, 255, 0.05);
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .price-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
        padding: 0.75rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.02);
        transition: all 0.3s ease;
        position: relative;
    }

    .price-row:hover {
        background: rgba(76, 175, 80, 0.1);
        border-color: rgba(76, 175, 80, 0.3);
        transform: translateX(4px);
    }

    .price-row:last-child {
        border-bottom: none;
        margin-bottom: 0;
    }

    .price-label {
        color: #9E9E9E;
        font-size: 0.95rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .price-value {
        color: #FAFAFA;
        font-size: 1.15rem;
        font-weight: 600;
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .price-change {
        font-size: 0.8rem;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-weight: 500;
    }

    .price-change.positive {
        background: rgba(76, 175, 80, 0.2);
        color: #4CAF50;
    }

    .price-change.negative {
        background: rgba(244, 67, 54, 0.2);
        color: #F44336;
    }

    .copy-price {
        opacity: 0;
        cursor: pointer;
        color: #9E9E9E;
        transition: all 0.3s ease;
        font-size: 0.8rem;
    }

    .price-row:hover .copy-price {
        opacity: 1;
    }

    .copy-price:hover {
        color: #4CAF50;
        transform: scale(1.2);
    }

    /* Risk/Reward Visualization */
    .risk-reward-chart {
        background: rgba(26, 29, 38, 0.5);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .risk-reward-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .risk-reward-title {
        color: #4CAF50;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .risk-reward-ratio {
        background: rgba(76, 175, 80, 0.1);
        color: #4CAF50;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    .risk-reward-bars {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }

    .risk-bar, .reward-bar {
        height: 8px;
        border-radius: 4px;
        transition: all 0.3s ease;
        position: relative;
    }

    .risk-bar {
        background: linear-gradient(90deg, #F44336, #FF7043);
        flex: 1;
    }

    .reward-bar {
        background: linear-gradient(90deg, #4CAF50, #66BB6A);
        flex: 2;
    }

    .risk-label, .reward-label {
        font-size: 0.8rem;
        font-weight: 500;
        min-width: 3rem;
        text-align: center;
    }

    .risk-label {
        color: #F44336;
    }

    .reward-label {
        color: #4CAF50;
    }

    /* Progress Bar Styles */
    .progress-container {
        margin-bottom: 1rem;
    }

    .progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }

    .progress-label {
        color: #D4D4D4;
        font-weight: 500;
        font-size: 0.9rem;
    }

    .progress-value {
        color: #FAFAFA;
        font-weight: 600;
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    }

    .progress-bar {
        height: 8px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        overflow: hidden;
        position: relative;
    }

    .progress-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 1.5s ease-out, background 0.3s ease;
        position: relative;
        background: linear-gradient(90deg, var(--progress-color), var(--progress-color-light));
    }

    .progress-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        animation: progressShine 2s ease-in-out infinite;
    }

    @keyframes progressShine {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }

    /* Metrics Grid */
    .metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }

    /* Analysis Section */
    .analysis-section {
        background: linear-gradient(135deg, rgba(26, 29, 38, 0.7), rgba(42, 45, 58, 0.5));
        border-radius: 12px;
        padding: 0;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(76, 175, 80, 0.2);
        overflow: hidden;
        transition: all 0.3s ease;
    }

    .analysis-section:hover {
        border-color: rgba(76, 175, 80, 0.4);
        box-shadow: 0 4px 16px rgba(76, 175, 80, 0.1);
    }

    .analysis-header {
        background: rgba(76, 175, 80, 0.1);
        padding: 1rem 1.25rem;
        cursor: pointer;
        transition: all 0.3s ease;
        position: relative;
    }

    .analysis-header:hover {
        background: rgba(76, 175, 80, 0.15);
    }

    .analysis-title {
        color: #4CAF50;
        font-weight: 600;
        margin: 0;
        font-size: 1.05rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        justify-content: space-between;
    }

    .analysis-title-left {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .expand-icon {
        transition: transform 0.3s ease;
        color: #9E9E9E;
        font-size: 0.9rem;
    }

    .expand-icon.expanded {
        transform: rotate(180deg);
    }

    .analysis-content {
        color: #D4D4D4;
        line-height: 1.7;
        font-size: 0.95rem;
        padding: 1.25rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        background: rgba(0, 0, 0, 0.1);
    }

    .analysis-content.collapsed {
        display: none;
    }

    .analysis-content.expanded {
        display: block;
        animation: slideDown 0.3s ease-out;
    }

    @keyframes slideDown {
        from {
            opacity: 0;
            max-height: 0;
        }
        to {
            opacity: 1;
            max-height: 200px;
        }
    }

    .analysis-summary {
        color: #FAFAFA;
        font-weight: 500;
        margin-bottom: 0.75rem;
        font-size: 1rem;
    }

    .analysis-details {
        color: #B0BEC5;
        font-size: 0.9rem;
        line-height: 1.6;
    }

    .analysis-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    .analysis-tag {
        background: rgba(76, 175, 80, 0.1);
        color: #4CAF50;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
        border: 1px solid rgba(76, 175, 80, 0.3);
    }

    /* Tooltip System */
    .tooltip {
        position: relative;
        cursor: help;
        border-bottom: 1px dotted #9E9E9E;
    }

    .tooltip::before {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(26, 29, 38, 0.95);
        color: #FAFAFA;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        font-size: 0.8rem;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: all 0.3s ease;
        border: 1px solid rgba(76, 175, 80, 0.3);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 1000;
    }

    .tooltip:hover::before {
        opacity: 1;
        transform: translateX(-50%) translateY(-4px);
    }

    /* Enhanced Interactive Brokers Button */
    .ib-button-container {
        padding: 1rem 1.5rem;
        background: rgba(26, 29, 38, 0.3);
        border-top: 1px solid #2a2d3a;
        text-align: center;
    }

    .ib-button {
        background: linear-gradient(135deg, #2962FF 0%, #1e88e5 100%);
        color: white;
        padding: 0.875rem 2rem;
        border-radius: 8px;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 0.75rem;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s ease;
        border: none;
        box-shadow: 0 4px 16px rgba(41, 98, 255, 0.3);
        position: relative;
        overflow: hidden;
    }

    .ib-button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        transition: left 0.5s ease;
    }

    .ib-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(41, 98, 255, 0.4);
        background: linear-gradient(135deg, #1e88e5 0%, #2962FF 100%);
    }

    .ib-button:hover::before {
        left: 100%;
    }

    .ib-disclaimer {
        font-size: 0.8rem;
        color: #9E9E9E;
        margin-top: 0.75rem;
        font-style: italic;
    }

    /* Icon Styles */
    .icon {
        width: 16px;
        height: 16px;
        display: inline-block;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
        .metrics-grid {
            grid-template-columns: 1fr;
        }
        .card-header {
            padding: 1rem;
        }
        .card-content {
            padding: 1rem;
        }
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
    .streaming-content {
        max-height: 300px;
        overflow-y: auto;
        scroll-behavior: smooth;
    }
    .auto-scroll {
        animation: scrollToBottom 0.3s ease-out;
    }
    @keyframes scrollToBottom {
        from { scroll-behavior: auto; }
        to { scroll-behavior: smooth; }
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

    /* Troubleshooting sidebar panel */
    .troubleshooting-panel {
        background: linear-gradient(135deg, #1a1d26, #252836);
        border: 1px solid #2a2d3a;
        border-radius: 8px;
        margin-top: 1rem;
        overflow: hidden;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }

    .troubleshooting-toggle {
        background: linear-gradient(90deg, #1E212A, #2A2D38);
        border: none;
        color: #D4D4D4;
        padding: 0.75rem 1rem;
        width: 100%;
        text-align: left;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .troubleshooting-toggle:hover {
        background: linear-gradient(90deg, #252836, #2A2D38);
        color: #FAFAFA;
    }

    .troubleshooting-toggle-icon {
        font-size: 1rem;
        transition: transform 0.3s ease;
    }

    .troubleshooting-toggle-icon.expanded {
        transform: rotate(90deg);
    }

    .troubleshooting-content {
        padding: 1rem;
        border-top: 1px solid #2a2d3a;
        background: #1E212A;
    }

    .troubleshooting-section {
        margin-bottom: 1.5rem;
        padding: 1rem;
        background: rgba(42, 45, 58, 0.3);
        border-radius: 6px;
        border-left: 3px solid #2962FF;
    }

    .troubleshooting-section h4 {
        color: #4CAF50 !important;
        margin: 0 0 0.5rem 0 !important;
        font-size: 0.9rem;
    }

    .troubleshooting-stats {
        background: rgba(0, 0, 0, 0.2);
        padding: 0.5rem;
        border-radius: 4px;
        margin-bottom: 0.75rem;
        font-size: 0.8rem;
        color: #9E9E9E;
    }

    .troubleshooting-text-area {
        background: #0E1117 !important;
        border: 1px solid #2a2d3a !important;
        color: #FAFAFA !important;
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace !important;
        font-size: 0.8rem !important;
        line-height: 1.4 !important;
        border-radius: 4px !important;
        max-height: 300px;
        resize: vertical;
    }

    /* Sidebar troubleshooting button styling */
    div[data-testid="stSidebar"] button[key="troubleshooting_toggle"] {
        background: linear-gradient(90deg, #1E212A, #2A2D38) !important;
        border: 1px solid #2a2d3a !important;
        color: #D4D4D4 !important;
        border-radius: 6px !important;
        padding: 0.5rem 0.75rem !important;
        font-size: 0.85rem !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        margin-bottom: 0.5rem !important;
    }

    div[data-testid="stSidebar"] button[key="troubleshooting_toggle"]:hover {
        background: linear-gradient(90deg, #252836, #2A2D38) !important;
        color: #FAFAFA !important;
        border-color: #4CAF50 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    }

    /* Compact troubleshooting sections in sidebar */
    div[data-testid="stSidebar"] .stTextArea textarea {
        background: #0E1117 !important;
        border: 1px solid #2a2d3a !important;
        color: #FAFAFA !important;
        font-family: 'Monaco', 'Menlo', 'Consolas', monospace !important;
        font-size: 0.75rem !important;
        line-height: 1.3 !important;
        border-radius: 4px !important;
    }

    div[data-testid="stSidebar"] h4 {
        font-size: 0.9rem !important;
        margin-bottom: 0.5rem !important;
        color: #4CAF50 !important;
    }

    /* Terminal-style frame for data gathering activity */
    .data-terminal {
        background: #0a0a0a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
        font-size: 0.8rem;
        color: #00ff00;
        position: relative;
        height: 400px;
        overflow-y: auto;
        scroll-behavior: smooth;
        box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1);
    }

    .data-terminal::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background:
            radial-gradient(circle at 25% 25%, transparent 2px, rgba(0, 255, 0, 0.03) 2px),
            linear-gradient(0deg, transparent 24%, rgba(0, 255, 0, 0.02) 25%, rgba(0, 255, 0, 0.02) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, 0.02) 75%, rgba(0, 255, 0, 0.02) 76%, transparent 77%);
        background-size: 4px 4px;
        pointer-events: none;
        z-index: 1;
    }

    .terminal-header {
        background: linear-gradient(90deg, #1a1a1a, #2a2a2a);
        color: #00ff00;
        padding: 0.5rem 1rem;
        margin: -1rem -1rem 1rem -1rem;
        border-radius: 8px 8px 0 0;
        border-bottom: 1px solid #333;
        font-size: 0.9rem;
        font-weight: bold;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        position: relative;
        z-index: 2;
    }

    .terminal-content {
        position: relative;
        z-index: 2;
        line-height: 1.4;
        white-space: pre-wrap;
        word-break: break-word;
        scroll-behavior: smooth;
    }

    .terminal-line {
        margin-bottom: 0.2rem;
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
    }

    .terminal-timestamp {
        color: #666;
        font-size: 0.7rem;
        min-width: 60px;
        flex-shrink: 0;
    }

    .terminal-status {
        color: #00ff00;
        min-width: 20px;
        flex-shrink: 0;
    }

    .terminal-message {
        color: #00ff00;
        flex: 1;
    }

    .terminal-url {
        color: #00aaff;
        text-decoration: underline;
    }

    .terminal-function {
        color: #ffaa00;
        font-weight: bold;
    }

    .terminal-success {
        color: #00ff00;
    }

    .terminal-warning {
        color: #ffaa00;
    }

    .terminal-error {
        color: #ff0000;
    }

    .terminal-info {
        color: #00aaff;
    }

    .terminal-method {
        color: #ff6600;
        font-weight: bold;
    }

    .terminal-parameter {
        color: #aa00ff;
    }

    .terminal-response {
        color: #00ffaa;
    }

    .terminal-circuit-breaker {
        color: #ff9900;
        font-weight: bold;
    }

    .terminal-timeout {
        color: #ff4444;
        font-weight: bold;
    }

    /* Enhanced auto-scroll functionality */
    .terminal-auto-scroll {
        animation: scrollGlow 0.5s ease-in-out;
    }

    .enhanced-auto-scroll {
        scroll-behavior: smooth;
        transition: all 0.3s ease;
    }

    /* Auto-scroll visual feedback */
    .auto-scrolling {
        box-shadow: inset 0 0 20px rgba(0, 255, 0, 0.4) !important;
        transition: box-shadow 0.3s ease;
    }

    @keyframes scrollGlow {
        0% { box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1); }
        50% { box-shadow: inset 0 0 20px rgba(0, 255, 0, 0.3); }
        100% { box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1); }
    }

    /* Terminal scroll controls */
    .terminal-controls {
        display: flex;
        gap: 0.5rem;
        margin-left: 1rem;
        margin-right: 0.5rem;
    }

    .terminal-scroll-btn {
        background: rgba(0, 255, 0, 0.1);
        border: 1px solid rgba(0, 255, 0, 0.3);
        color: #00ff00;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
        cursor: pointer;
        opacity: 0.6;
        transition: all 0.3s ease;
        white-space: nowrap;
        min-width: 45px;
    }

    .terminal-scroll-btn:hover {
        background: rgba(0, 255, 0, 0.2);
        border-color: #00ff00;
        opacity: 1;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 255, 0, 0.3);
    }

    .terminal-scroll-btn:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0, 255, 0, 0.3);
    }

    /* Terminal anchor for scroll positioning */
    .terminal-anchor {
        height: 1px;
        width: 100%;
    }

    /* Responsive scroll controls */
    @media (max-width: 768px) {
        .terminal-controls {
            gap: 0.25rem;
            margin-left: 0.5rem;
        }

        .terminal-scroll-btn {
            padding: 0.15rem 0.3rem;
            font-size: 0.6rem;
            min-width: 35px;
        }

        .terminal-header {
            flex-wrap: wrap;
            gap: 0.25rem;
        }
    }

    /* Enhanced terminal content scrolling - merged with existing rule above */

    /* Smooth scroll behavior for all terminal elements */
    .data-terminal {
        scroll-behavior: smooth;
    }

    /* Terminal blinking cursor */
    .terminal-cursor {
        animation: blink 1s infinite;
        color: #00ff00;
    }

    @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0; }
    }

    /* Status indicators */
    .status-active { color: #00ff00; }
    .status-degraded { color: #ffaa00; }
    .status-failed { color: #ff0000; }
    .status-timeout { color: #ff4444; }
    </style>
""", unsafe_allow_html=True)

# Add interactive JavaScript components using streamlit.components
interactive_js = """
<script>
    // Enhanced Trading Card Interactive Features
    document.addEventListener('DOMContentLoaded', function() {

        // Copy to clipboard functionality
        function copyToClipboard(text, button) {
            navigator.clipboard.writeText(text).then(function() {
                const originalIcon = button.innerHTML;
                button.innerHTML = '✓';
                button.style.color = '#4CAF50';
                setTimeout(() => {
                    button.innerHTML = originalIcon;
                    button.style.color = '';
                }, 2000);
            }).catch(function(err) {
                console.error('Failed to copy: ', err);
                button.innerHTML = '✗';
                button.style.color = '#F44336';
                setTimeout(() => {
                    button.innerHTML = originalIcon;
                    button.style.color = '';
                }, 2000);
            });
        }

        // Expandable section functionality
        function toggleSection(header) {
            const content = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');

            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                content.classList.add('expanded');
                icon.classList.add('expanded');
            } else {
                content.classList.remove('expanded');
                content.classList.add('collapsed');
                icon.classList.remove('expanded');
            }
        }

        // Real-time price calculation
        function calculateRiskReward(entryPrice, targetPrice, stopLoss) {
            const risk = Math.abs(entryPrice - stopLoss);
            const reward = Math.abs(targetPrice - entryPrice);
            return reward / risk;
        }

        // Status indicator updates
        function updateStatusIndicator(element, status) {
            const dot = element.querySelector('.status-dot');
            if (dot) {
                dot.style.background = status === 'active' ? '#4CAF50' :
                                     status === 'warning' ? '#FF9800' : '#F44336';
            }
        }

        // Initialize tooltips
        function initializeTooltips() {
            const tooltips = document.querySelectorAll('.tooltip');
            tooltips.forEach(tooltip => {
                tooltip.addEventListener('mouseenter', function() {
                    this.style.zIndex = '1001';
                });
                tooltip.addEventListener('mouseleave', function() {
                    this.style.zIndex = '';
                });
            });
        }

        // Initialize interactive elements
        function initializeInteractiveElements() {
            // Add copy buttons to price values
            const priceValues = document.querySelectorAll('.price-value');
            priceValues.forEach(priceValue => {
                if (!priceValue.querySelector('.copy-price')) {
                    const copyBtn = document.createElement('span');
                    copyBtn.className = 'copy-price';
                    copyBtn.innerHTML = '📋';
                    copyBtn.title = 'Copy price';
                    copyBtn.onclick = () => copyToClipboard(priceValue.textContent.trim(), copyBtn);
                    priceValue.appendChild(copyBtn);
                }
            });

            // Add expand/collapse to analysis sections
            const analysisHeaders = document.querySelectorAll('.analysis-header');
            analysisHeaders.forEach(header => {
                if (!header.querySelector('.expand-icon')) {
                    const expandIcon = document.createElement('span');
                    expandIcon.className = 'expand-icon';
                    expandIcon.innerHTML = '▼';
                    header.querySelector('.analysis-title').appendChild(expandIcon);
                }

                header.onclick = () => toggleSection(header);

                // Initially collapse all sections except the first
                const content = header.nextElementSibling;
                if (content && !header.closest('.analysis-section').classList.contains('first-section')) {
                    content.classList.add('collapsed');
                }
            });

            // Initialize risk/reward calculations
            const tradingCards = document.querySelectorAll('.trading-card');
            tradingCards.forEach(card => {
                const entryPriceEl = card.querySelector('.price-row:nth-child(1) .price-value');
                const targetPriceEl = card.querySelector('.price-row:nth-child(2) .price-value');
                const stopLossEl = card.querySelector('.price-row:nth-child(3) .price-value');

                if (entryPriceEl && targetPriceEl && stopLossEl) {
                    const entryPrice = parseFloat(entryPriceEl.textContent.replace(/[$,]/g, ''));
                    const targetPrice = parseFloat(targetPriceEl.textContent.replace(/[$,]/g, ''));
                    const stopLoss = parseFloat(stopLossEl.textContent.replace(/[$,]/g, ''));

                    if (!isNaN(entryPrice) && !isNaN(targetPrice) && !isNaN(stopLoss)) {
                        const ratio = calculateRiskReward(entryPrice, targetPrice, stopLoss);

                        // Add risk/reward visualization if not exists
                        const priceSection = card.querySelector('.price-section');
                        if (priceSection && !priceSection.querySelector('.risk-reward-chart')) {
                            const riskRewardChart = document.createElement('div');
                            riskRewardChart.className = 'risk-reward-chart';
                            riskRewardChart.innerHTML = `
                                <div class="risk-reward-header">
                                    <div class="risk-reward-title">
                                        <span>⚖️</span>
                                        Risk/Reward Ratio
                                    </div>
                                    <div class="risk-reward-ratio">${ratio.toFixed(2)}:1</div>
                                </div>
                                <div class="risk-reward-bars">
                                    <div class="risk-label">Risk</div>
                                    <div class="risk-bar"></div>
                                    <div class="reward-bar"></div>
                                    <div class="reward-label">Reward</div>
                                </div>
                            `;
                            priceSection.appendChild(riskRewardChart);
                        }
                    }
                }
            });
        }

        // Real-time updates
        function startRealTimeUpdates() {
            setInterval(() => {
                // Update status indicators
                const statusDots = document.querySelectorAll('.status-dot');
                statusDots.forEach(dot => {
                    // Simulate real-time status updates
                    const isActive = Math.random() > 0.1; // 90% uptime simulation
                    updateStatusIndicator(dot.closest('.status-indicator'), isActive ? 'active' : 'warning');
                });

                // Update timestamp displays
                const now = new Date();
                const timeElements = document.querySelectorAll('.last-updated');
                timeElements.forEach(el => {
                    el.textContent = `Last updated: ${now.toLocaleTimeString()}`;
                });
            }, 30000); // Update every 30 seconds
        }

        // Initialize everything
        initializeTooltips();
        initializeInteractiveElements();
        startRealTimeUpdates();

        // Reinitialize when Streamlit reruns
        window.addEventListener('beforeunload', function() {
            // Cleanup if needed
        });
    });

    // Copy trade details function
    window.copyTradeDetails = function(symbol, action, entryPrice, targetPrice, stopLoss) {
        const tradeDetails = `Trade Alert: ${action} ${symbol}
Entry: ${entryPrice}
Target: ${targetPrice}
Stop Loss: ${stopLoss}
Generated by RegalAssets AI Trading System`;

        copyToClipboard(tradeDetails, { innerHTML: '✓' });
    };

    // Enhanced hover effects with sound feedback (optional)
    document.addEventListener('mouseover', function(e) {
        if (e.target.classList.contains('trading-card') ||
            e.target.closest('.trading-card')) {
            // Add subtle sound feedback for premium feel (if audio enabled)
            // playHoverSound(); // Uncomment if audio feedback desired
        }
    });

    // Keyboard shortcuts for power users
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'c':
                    // Copy first visible price when Ctrl+C is pressed
                    const firstPrice = document.querySelector('.price-value');
                    if (firstPrice) {
                        e.preventDefault();
                        copyToClipboard(firstPrice.textContent.trim(), firstPrice);
                    }
                    break;
                case 'e':
                    // Toggle all expansion states
                    e.preventDefault();
                    const allHeaders = document.querySelectorAll('.analysis-header');
                    allHeaders.forEach(header => toggleSection(header));
                    break;
            }
        }
    });
</script>
"""

# Execute JavaScript using streamlit components
components.html(interactive_js, height=0)

st.title("RegalAssets")

# Initialize troubleshooting session state early
if 'troubleshooting_panel_open' not in st.session_state:
    st.session_state.troubleshooting_panel_open = False
if 'last_prompt' not in st.session_state:
    st.session_state.last_prompt = ""
if 'last_api_response' not in st.session_state:
    st.session_state.last_api_response = ""
if 'last_prompt_stats' not in st.session_state:
    st.session_state.last_prompt_stats = {}
if 'last_response_stats' not in st.session_state:
    st.session_state.last_response_stats = {}
if 'terminal_logs' not in st.session_state:
    st.session_state.terminal_logs = []
if 'terminal_active' not in st.session_state:
    st.session_state.terminal_active = False
if 'circuit_breaker_states' not in st.session_state:
    st.session_state.circuit_breaker_states = {}

# Terminal logging functions
def add_terminal_log(log_type, message, details=None, url=None, function_name=None, status="info"):
    """Add a log entry to the terminal display"""
    # Safety check - initialize if not already done (e.g., from threads)
    if 'terminal_logs' not in st.session_state:
        st.session_state.terminal_logs = []

    # Prevent HTML content from being added to terminal logs
    message_str = str(message) if message else ""
    details_str = str(details) if details else ""

    # Check for HTML tags in message or details
    html_tags = ["<div", "</div", "terminal-anchor", "terminal-bottom", "<script", "</script", "<html", "</html"]
    if any(tag in message_str.lower() for tag in html_tags):
        print(f"WARNING: HTML detected in terminal message, skipping: {message_str[:100]}")
        return
    if any(tag in details_str.lower() for tag in html_tags):
        print(f"WARNING: HTML detected in terminal details, skipping: {details_str[:100]}")
        return

    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "type": log_type,
        "status": status,
        "message": message,
        "details": details,
        "url": url,
        "function_name": function_name,
        "full_timestamp": datetime.datetime.now().isoformat()
    }

    # Keep only last 100 entries to prevent memory issues
    if len(st.session_state.terminal_logs) >= 100:
        st.session_state.terminal_logs = st.session_state.terminal_logs[-50:]

    st.session_state.terminal_logs.append(log_entry)

def format_terminal_line(log_entry):
    """Format a terminal log entry for display"""
    import html
    timestamp = log_entry["timestamp"]
    status = log_entry["status"]
    message = log_entry["message"]
    details = log_entry.get("details", "")
    url = log_entry.get("url", "")
    function_name = log_entry.get("function_name", "")

    # Status indicator
    status_char = {
        "success": "✓",
        "warning": "⚠",
        "error": "✗",
        "info": "ℹ",
        "method": "→",
        "request": "↗",
        "response": "↙",
        "timeout": "⏱",
        "circuit": "⊗"
    }.get(status, "•")

    # Color class for status
    status_class = {
        "success": "terminal-success",
        "warning": "terminal-warning",
        "error": "terminal-error",
        "info": "terminal-info",
        "method": "terminal-method",
        "request": "terminal-info",
        "response": "terminal-response",
        "timeout": "terminal-timeout",
        "circuit": "terminal-circuit-breaker"
    }.get(status, "terminal-info")

    # Build the line content with proper HTML escaping
    line_parts = []

    if function_name:
        line_parts.append(f'<span class="terminal-function">{html.escape(function_name)}()</span>')

    if url:
        line_parts.append(f'<span class="terminal-url">{html.escape(url)}</span>')

    # Escape HTML in message and details to prevent raw HTML display
    escaped_message = html.escape(message)
    line_parts.append(escaped_message)

    if details:
        escaped_details = html.escape(details)
        line_parts.append(f'<span class="terminal-parameter">{escaped_details}</span>')

    line_content = " ".join(line_parts)
    return f'''
    <div class="terminal-line">
        <span class="terminal-timestamp">{timestamp}</span>
        <span class="terminal-status {status_class}">{status_char}</span>
        <span class="terminal-message">{line_content}</span>
    </div>
    '''

def render_terminal_display():
    """Render the complete terminal display with enhanced auto-scroll functionality"""
    if not st.session_state.terminal_active:
        return ""

    # Terminal header with scroll controls
    active_sources = len([log for log in st.session_state.terminal_logs[-10:] if log.get("status") == "success"])
    total_logs = len(st.session_state.terminal_logs)

    # Generate unique terminal ID for this render
    terminal_id = f"terminal_{int(time.time() * 1000)}"
    header = (
        f'<div class="terminal-header">'
        f'<span>🖥️ Data Gathering Terminal</span>'
        f'<span style="margin-left: auto; font-size: 0.8rem;">'
        f'{total_logs} events | {active_sources} recent success'
        f'</span>'
        f'<div class="terminal-controls">'
        f'<button id="scroll-to-top-{terminal_id}" class="terminal-scroll-btn" title="Scroll to top">↑ Top</button>'
        f'<button id="scroll-to-bottom-{terminal_id}" class="terminal-scroll-btn" title="Scroll to bottom">↓ Bottom</button>'
        f'</div>'
        f'<span class="terminal-cursor">█</span>'
        f'</div>'
    )

    # Terminal content with enhanced auto-scroll container
    content_lines = []
    for log_entry in st.session_state.terminal_logs[-50:]:  # Show last 50 entries
        # Skip any log entries that might contain raw HTML (defensive check)
        message = str(log_entry.get("message", ""))
        details = str(log_entry.get("details", ""))

        # Check both message and details for HTML content
        if any(html_tag in message.lower() for html_tag in ["<div", "</div", "terminal-anchor", "terminal-bottom", "<script", "</script"]):
            continue
        if any(html_tag in details.lower() for html_tag in ["<div", "</div", "terminal-anchor", "terminal-bottom", "<script", "</script"]):
            continue

        formatted_line = format_terminal_line(log_entry)
        content_lines.append(formatted_line)

    # Join content lines
    joined_lines = "".join(content_lines)

    # Build terminal content with proper structure - ensure no newlines that could break parsing
    # Add the anchor div at the bottom for auto-scrolling
    terminal_content = f'<div id="{terminal_id}" class="terminal-content enhanced-auto-scroll">{joined_lines}<div id="terminal-bottom-{terminal_id}" class="terminal-anchor"></div></div>'

    # Enhanced JavaScript for auto-scroll functionality
    # Wrap everything in the main terminal container
    terminal_html = f'''
    <div class="data-terminal terminal-auto-scroll">
        {header}
        {terminal_content}
    </div>
    <script>
        (function() {{
            const terminalId = '{terminal_id}';
            const terminal = document.getElementById(terminalId);
            const scrollToTopBtn = document.getElementById('scroll-to-top-' + terminalId);
            const scrollToBottomBtn = document.getElementById('scroll-to-bottom-' + terminalId);
            const bottomAnchor = document.getElementById('terminal-bottom-' + terminalId);

            // Debug logging
            console.log("Terminal auto-scroll init:", {{
                terminalId: terminalId,
                terminalFound: !!terminal,
                bottomAnchorFound: !!bottomAnchor,
                scrollButtonsFound: !!scrollToTopBtn && !!scrollToBottomBtn
            }});

            if (!terminal) {{
                console.error("Terminal element not found!");
                return;
            }}

            let isUserScrolling = false;
            let autoScrollEnabled = true;
            let scrollTimeout;

            // Detect user manual scrolling
            terminal.addEventListener('scroll', function(e) {{
                clearTimeout(scrollTimeout);

                // Check if user scrolled away from bottom
                const isAtBottom = terminal.scrollTop + terminal.clientHeight >= terminal.scrollHeight - 10;

                if (!isAtBottom && autoScrollEnabled) {{
                    isUserScrolling = true;
                    autoScrollEnabled = false;

                    // Show scroll controls when user scrolls up
                    if (scrollToTopBtn) scrollToTopBtn.style.opacity = '1';
                    if (scrollToBottomBtn) scrollToBottomBtn.style.opacity = '1';
                }} else if (isAtBottom) {{
                    isUserScrolling = false;
                    autoScrollEnabled = true;

                    // Hide scroll controls when at bottom
                    if (scrollToTopBtn) scrollToTopBtn.style.opacity = '0.6';
                    if (scrollToBottomBtn) scrollToBottomBtn.style.opacity = '0.6';
                }}

                // Re-enable auto-scroll after user stops scrolling for 3 seconds
                scrollTimeout = setTimeout(function() {{
                    if (isAtBottom) {{
                        autoScrollEnabled = true;
                        isUserScrolling = false;
                    }}
                }}, 3000);
            }});

            // Scroll to top button
            if (scrollToTopBtn) {{
                scrollToTopBtn.addEventListener('click', function() {{
                    terminal.scrollTo({{
                        top: 0,
                        behavior: 'smooth'
                    }});
                    autoScrollEnabled = false;
                    isUserScrolling = true;
                }});
            }}

            // Scroll to bottom button
            if (scrollToBottomBtn) {{
                scrollToBottomBtn.addEventListener('click', function() {{
                    terminal.scrollTo({{
                        top: terminal.scrollHeight,
                        behavior: 'smooth'
                    }});
                    autoScrollEnabled = true;
                    isUserScrolling = false;
                }});
            }}

            // Enhanced auto-scroll function
            function autoScrollToBottom() {{
                if (autoScrollEnabled && !isUserScrolling && terminal) {{
                    // Scroll to the bottom anchor if it exists, otherwise scroll to terminal height
                    if (bottomAnchor) {{
                        bottomAnchor.scrollIntoView({{
                            behavior: 'smooth',
                            block: 'end'
                        }});
                    }} else {{
                        // Fallback to terminal scrollHeight
                        terminal.scrollTo({{
                            top: terminal.scrollHeight,
                            behavior: 'smooth'
                        }});
                    }}

                    // Add visual feedback for auto-scroll
                    terminal.classList.add('auto-scrolling');
                    setTimeout(function() {{
                        terminal.classList.remove('auto-scrolling');
                    }}, 300);
                }}
            }}

            // Observer for content changes (new log entries)
            const observer = new MutationObserver(function(mutations) {{
                let contentChanged = false;
                mutations.forEach(function(mutation) {{
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {{
                        contentChanged = true;
                    }}
                }});

                if (contentChanged) {{
                    // Delay auto-scroll slightly to allow content to render
                    setTimeout(autoScrollToBottom, 100);
                }}
            }});

            // Start observing content changes
            observer.observe(terminal, {{
                childList: true,
                subtree: true
            }});

            // Initial auto-scroll after content loads
            setTimeout(autoScrollToBottom, 100);

            // Periodic check for new content (fallback)
            const periodicScroll = setInterval(function() {{
                if (terminal && document.contains(terminal)) {{
                    // Check if we're at the bottom before auto-scrolling
                    const isAtBottom = terminal.scrollTop + terminal.clientHeight >= terminal.scrollHeight - 10;
                    if (isAtBottom || autoScrollEnabled) {{
                        autoScrollToBottom();
                    }}
                }} else {{
                    clearInterval(periodicScroll);
                    observer.disconnect();
                }}
            }}, 500);

            // Cleanup function when terminal is removed
            setTimeout(function() {{
                if (!document.contains(terminal)) {{
                    observer.disconnect();
                    clearInterval(periodicScroll);
                }}
            }}, 30000); // Clean up after 30 seconds if terminal is gone
        }})();
    </script>
    '''

    return terminal_html

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
    if ENHANCED_DATA_AVAILABLE and TIMEOUT_FIXES_AVAILABLE:
        st.success("✅ Enhanced data system with timeout fixes (10+ sources)")
        st.info("Using **1 API call** with enhanced data from 10+ finance sources. **Timeout fixes active** - resolves CoinGecko blocking issues.")
    elif ENHANCED_DATA_AVAILABLE:
        st.warning("⚠️ Enhanced data system (timeout fixes recommended)")
        st.info("Using **1 API call** with enhanced data from 10+ finance sources. Consider updating to version with timeout fixes.")
    else:
        st.warning("⚠️ Basic data system (enhanced unavailable)")
        st.info("Using **1 API call** with basic data gathering. Install enhanced system for 10+ sources.")

    # Troubleshooting panel in sidebar
    st.markdown("---")

    # Toggle button for troubleshooting panel with status indicator
    has_data = bool(st.session_state.last_prompt or st.session_state.last_api_response)
    button_icon = "🐛" if st.session_state.troubleshooting_panel_open else "⚙️"
    status_indicator = " 🔴" if has_data else ""
    arrow = "▼" if st.session_state.troubleshooting_panel_open else "▶"
    button_text = f"{button_icon} Debug {arrow}{status_indicator}"

    help_text = "View prompt and API response details" + (" (Data available)" if has_data else " (Run analysis first)")

    if st.button(button_text, key="troubleshooting_toggle", help=help_text):
        st.session_state.troubleshooting_panel_open = not st.session_state.troubleshooting_panel_open

    # Show troubleshooting content if panel is open
    if st.session_state.troubleshooting_panel_open:
        if has_data:
            # Prompt section with collapsible details
            with st.expander("🔍 Prompt Analysis", expanded=False):
                if st.session_state.last_prompt_stats:
                    stats = st.session_state.last_prompt_stats
                    st.markdown(f"""
                    **Statistics:**
                    - Tokens: ~{stats.get('tokens', 0):,}
                    - Characters: {stats.get('chars', 0):,}
                    - Sources: {stats.get('sources', 0)}
                    """)

                if st.session_state.last_prompt:
                    st.text_area("Full Prompt", st.session_state.last_prompt, height=150, disabled=True, key="sidebar_prompt")

            # Response section with collapsible details
            with st.expander("🤖 API Response", expanded=False):
                if st.session_state.last_response_stats:
                    stats = st.session_state.last_response_stats
                    st.markdown(f"""
                    **Statistics:**
                    - Length: {stats.get('length', 0):,} chars
                    - Has Table: {'✅' if stats.get('has_table', False) else '❌'}
                    - Lines: {stats.get('lines', 0)}
                    """)

                if st.session_state.last_api_response:
                    st.text_area("Full Response", st.session_state.last_api_response, height=150, disabled=True, key="sidebar_response")

                    # Show table preview if available
                    if '|' in st.session_state.last_api_response:
                        table_start = st.session_state.last_api_response.find('|')
                        table_preview = st.session_state.last_api_response[max(0, table_start-100):table_start+500]
                        st.text_area("Table Preview", table_preview, height=100, disabled=True, key="sidebar_table_preview")
        else:
            st.info("💡 Generate predictions first to view debug data")

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


# Create layout with button, status, and terminal
# Main button
prediction_button = st.button("🚀 Gather and Analyze with AI", help="Gather comprehensive market data and generate AI trading predictions")

# Terminal display area (below button)
terminal_placeholder = st.empty()

# Status display area
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

            # Thread-safe status callback that queues messages
            status_messages = []

            # Initialize terminal for data gathering
            st.session_state.terminal_active = True
            st.session_state.terminal_logs = []  # Clear previous logs

            # Enhanced status callback with terminal integration
            def status_callback(message):
                # Just collect messages, don't update UI from thread
                status_messages.append(message)

                # Parse message for terminal logging
                parse_and_log_message(message)

                # Safe console logging with exception handling
                try:
                    print(f"Status: {message}")  # Console logging for debugging
                except (BrokenPipeError, OSError, IOError):
                    # Fallback logging mechanism - write to a log file if console fails
                    try:
                        import logging
                        import os
                        # Create logger if not exists
                        if not hasattr(status_callback, '_logger'):
                            log_file = os.path.join(os.getcwd(), 'trade_executor.log')
                            logging.basicConfig(
                                filename=log_file,
                                level=logging.INFO,
                                format='%(asctime)s - %(message)s',
                                filemode='a'
                            )
                            status_callback._logger = logging.getLogger('trade_executor')
                        status_callback._logger.info(f"Status: {message}")
                    except Exception:
                        # If all logging fails, silently continue - the important thing
                        # is that status_messages.append() still works for UI updates
                        pass

            def parse_and_log_message(message):
                """Parse status messages and add appropriate terminal logs"""
                if "Starting enhanced market data discovery" in message:
                    add_terminal_log("system", "Initializing enhanced data fetcher", status="info", function_name="get_comprehensive_market_data")
                elif "🔍 Trying" in message:
                    # Parse discovery method messages like "🔍 Trying yahoo_trending (timeout: 30s)..."
                    method_name = message.split("Trying ")[1].split(" ")[0] if "Trying " in message else "unknown"
                    timeout_match = message.split("timeout: ")[1].split("s")[0] if "timeout: " in message else "N/A"
                    add_terminal_log("discovery", f"Discovering assets via {method_name}", status="info",
                                   details=f"timeout: {timeout_match}s", function_name=f"discover_{method_name}")
                elif "yahoo_trending" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("request", "Yahoo trending assets discovered", status="success", url="finance.yahoo.com", function_name="discover_yahoo_trending")
                    else:
                        add_terminal_log("request", "Yahoo trending discovery", status="info", url="finance.yahoo.com", function_name="discover_yahoo_trending")
                elif "coingecko_trending" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("request", "CoinGecko trending crypto discovered", status="success", url="api.coingecko.com", function_name="discover_coingecko_trending")
                    else:
                        add_terminal_log("request", "CoinGecko trending discovery", status="info", url="api.coingecko.com", function_name="discover_coingecko_trending")
                elif "marketwatch_movers" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("request", "MarketWatch movers discovered", status="success", url="marketwatch.com", function_name="discover_marketwatch_movers")
                    else:
                        add_terminal_log("request", "MarketWatch movers discovery", status="info", url="marketwatch.com", function_name="discover_marketwatch_movers")
                elif "cnbc_trending" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("request", "CNBC trending assets discovered", status="success", url="cnbc.com", function_name="discover_cnbc_trending")
                    else:
                        add_terminal_log("request", "CNBC trending discovery", status="info", url="cnbc.com", function_name="discover_cnbc_trending")
                elif "bloomberg_active" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("request", "Bloomberg active stocks discovered", status="success", url="bloomberg.com", function_name="discover_bloomberg_active")
                    else:
                        add_terminal_log("request", "Bloomberg active discovery", status="info", url="bloomberg.com", function_name="discover_bloomberg_active")
                elif "investing_com_hot" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("request", "Investing.com hot assets discovered", status="success", url="investing.com", function_name="discover_investing_com_hot")
                    else:
                        add_terminal_log("request", "Investing.com hot discovery", status="info", url="investing.com", function_name="discover_investing_com_hot")
                elif "volume_analysis" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("system", "High volume analysis completed", status="success", function_name="discover_volume_analysis")
                    else:
                        add_terminal_log("system", "High volume analysis", status="info", function_name="discover_volume_analysis")
                elif "sector_rotation" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("system", "Sector rotation analysis completed", status="success", function_name="discover_sector_rotation")
                    else:
                        add_terminal_log("system", "Sector rotation analysis", status="info", function_name="discover_sector_rotation")
                elif "momentum_analysis" in message.lower():
                    if "✅" in message or "completed" in message.lower():
                        add_terminal_log("system", "Momentum analysis completed", status="success", function_name="discover_momentum_analysis")
                    else:
                        add_terminal_log("system", "Momentum analysis", status="info", function_name="discover_momentum_analysis")
                elif "yahoo_finance" in message.lower():
                    if "success" in message.lower() or "✅" in message:
                        add_terminal_log("request", "Yahoo Finance API call successful", status="success", url="finance.yahoo.com", function_name="fetch_yahoo_data")
                    elif "failed" in message.lower() or "❌" in message:
                        add_terminal_log("request", "Yahoo Finance API call failed", status="error", url="finance.yahoo.com", function_name="fetch_yahoo_data")
                    else:
                        add_terminal_log("request", "Connecting to Yahoo Finance", status="info", url="finance.yahoo.com", function_name="fetch_yahoo_data")
                elif "coingecko" in message.lower():
                    if "timeout" in message.lower() or "⏱" in message:
                        add_terminal_log("request", "CoinGecko request timeout", status="timeout", url="api.coingecko.com", function_name="fetch_coingecko_data")
                    elif "circuit breaker" in message.lower():
                        add_terminal_log("circuit", "CoinGecko circuit breaker triggered", status="circuit", url="api.coingecko.com", function_name="fetch_coingecko_data")
                    elif "success" in message.lower() or "✅" in message:
                        add_terminal_log("request", "CoinGecko API call successful", status="success", url="api.coingecko.com", function_name="fetch_coingecko_data")
                    elif "failed" in message.lower() or "❌" in message:
                        add_terminal_log("request", "CoinGecko API call failed", status="error", url="api.coingecko.com", function_name="fetch_coingecko_data")
                    else:
                        add_terminal_log("request", "Connecting to CoinGecko", status="info", url="api.coingecko.com", function_name="fetch_coingecko_data")
                elif "marketwatch" in message.lower():
                    if "success" in message.lower() or "✅" in message:
                        add_terminal_log("request", "MarketWatch scraping successful", status="success", url="marketwatch.com", function_name="scrape_marketwatch")
                    elif "failed" in message.lower() or "❌" in message:
                        add_terminal_log("request", "MarketWatch scraping failed", status="error", url="marketwatch.com", function_name="scrape_marketwatch")
                    else:
                        add_terminal_log("request", "Scraping MarketWatch", status="info", url="marketwatch.com", function_name="scrape_marketwatch")
                elif "cnbc" in message.lower():
                    if "success" in message.lower() or "✅" in message:
                        add_terminal_log("request", "CNBC data extraction successful", status="success", url="cnbc.com", function_name="fetch_cnbc_data")
                    elif "failed" in message.lower() or "❌" in message:
                        add_terminal_log("request", "CNBC data extraction failed", status="error", url="cnbc.com", function_name="fetch_cnbc_data")
                    else:
                        add_terminal_log("request", "Extracting CNBC data", status="info", url="cnbc.com", function_name="fetch_cnbc_data")
                elif "bloomberg" in message.lower():
                    if "success" in message.lower() or "✅" in message:
                        add_terminal_log("request", "Bloomberg data retrieved", status="success", url="bloomberg.com", function_name="fetch_bloomberg_data")
                    elif "failed" in message.lower() or "❌" in message:
                        add_terminal_log("request", "Bloomberg data failed", status="error", url="bloomberg.com", function_name="fetch_bloomberg_data")
                    else:
                        add_terminal_log("request", "Accessing Bloomberg", status="info", url="bloomberg.com", function_name="fetch_bloomberg_data")
                elif "reuters" in message.lower():
                    add_terminal_log("request", "Reuters financial data", status="info", url="reuters.com", function_name="fetch_reuters_data")
                elif "investing.com" in message.lower():
                    add_terminal_log("request", "Investing.com analysis", status="info", url="investing.com", function_name="fetch_investing_data")
                elif "circuit breaker" in message.lower():
                    add_terminal_log("circuit", "Circuit breaker status update", status="circuit", details=message.split(":")[-1].strip() if ":" in message else "")
                elif "timeout" in message.lower():
                    add_terminal_log("timeout", "Operation timeout detected", status="timeout", details=message.split(":")[-1].strip() if ":" in message else "")
                elif "✅" in message:
                    add_terminal_log("system", message.replace("✅", "").strip(), status="success")
                elif "⚠️" in message:
                    add_terminal_log("system", message.replace("⚠️", "").strip(), status="warning")
                elif "❌" in message:
                    add_terminal_log("system", message.replace("❌", "").strip(), status="error")
                elif "📊" in message or "🔍" in message or "🌐" in message:
                    add_terminal_log("system", message.replace("📊", "").replace("🔍", "").replace("🌐", "").strip(), status="info")
                else:
                    # Generic log entry for unmatched messages
                    add_terminal_log("system", message, status="info")

            # Function to safely update UI from main thread
            def update_status_display():
                if status_messages:
                    # Show the last message
                    status_placeholder.text(status_messages[-1])
                    # Optionally show progress count
                    if len(status_messages) > 1:
                        status_placeholder.text(f"{status_messages[-1]} ({len(status_messages)} steps completed)")

                # Update terminal display
                terminal_html = render_terminal_display()
                if terminal_html:
                    terminal_placeholder.markdown(terminal_html, unsafe_allow_html=True)

            # Show initial gathering message and terminal
            add_terminal_log("system", "Starting comprehensive market data gathering", status="info", function_name="main")
            update_status_display()

            with st.spinner("🌐 Gathering market data from 10+ sources... This may take 15-30 seconds"):
                # Get comprehensive market data using our new system
                market_data = get_comprehensive_market_data(status_callback)

                # Update terminal during gathering process
                for _ in range(5):  # Periodic updates during gathering
                    time.sleep(0.5)
                    update_status_display()

            # Update status display with final message count
            add_terminal_log("system", "Data gathering phase completed", status="success", function_name="main")
            update_status_display()

            if status_messages:
                status_placeholder.text(f"✅ Data gathering complete! ({len(status_messages)} steps)")
            else:
                status_placeholder.text("✅ Data gathering complete!")

            status_placeholder.text("🔍 Validating data quality and timestamps...")
            add_terminal_log("system", "Starting data validation and quality checks", status="info", function_name="validate_market_data")
            update_status_display()

            validation_result = validate_market_data(market_data)

            # Data Quality Threshold Check - Prevent API call if >25% sources fail
            status_placeholder.text("🎯 Checking data quality threshold...")
            add_terminal_log("system", "Performing data quality threshold check", status="info", function_name="calculate_failure_percentage")
            update_status_display()

            # Calculate failure percentage based on validation results
            def calculate_failure_percentage(validation_result):
                """Calculate the percentage of failed data sources"""
                if ENHANCED_DATA_AVAILABLE:
                    # Use enhanced validation data
                    validation_summary = validation_result.get("validation_summary", {})
                    successful_fetches = validation_summary.get("successful_price_fetches", 0)
                    failed_fetches = validation_summary.get("failed_price_fetches", 0)
                    total_sources = len(validation_summary.get("data_sources_used", []))

                    # Calculate source-level failures
                    source_reliability = validation_summary.get("source_reliability_scores", {})
                    failed_sources = sum(1 for score in source_reliability.values() if score < 0.5)

                    # Use the higher failure rate between fetch-level and source-level
                    total_attempts = max(successful_fetches + failed_fetches, total_sources, 1)
                    fetch_failure_rate = (failed_fetches / total_attempts) * 100
                    source_failure_rate = (failed_sources / max(total_sources, 1)) * 100

                    return max(fetch_failure_rate, source_failure_rate), {
                        "total_sources": total_sources,
                        "failed_sources": failed_sources,
                        "successful_fetches": successful_fetches,
                        "failed_fetches": failed_fetches,
                        "source_reliability": source_reliability
                    }
                else:
                    # Use basic validation data
                    successful_fetches = validation_result.get("successful_price_fetches", 0)
                    failed_fetches = validation_result.get("failed_price_fetches", 0)
                    total_attempts = max(successful_fetches + failed_fetches, 1)
                    failure_rate = (failed_fetches / total_attempts) * 100

                    return failure_rate, {
                        "total_sources": 1,
                        "failed_sources": 1 if failed_fetches > 0 else 0,
                        "successful_fetches": successful_fetches,
                        "failed_fetches": failed_fetches,
                        "source_reliability": {}
                    }

            failure_percentage, failure_details = calculate_failure_percentage(validation_result)

            # Check if failure rate exceeds 25% threshold
            FAILURE_THRESHOLD = 25.0

            add_terminal_log("system", f"Data quality check: {failure_percentage:.1f}% failure rate",
                           status="warning" if failure_percentage > FAILURE_THRESHOLD else "success",
                           details=f"Threshold: {FAILURE_THRESHOLD}%", function_name="quality_check")
            update_status_display()

            if failure_percentage > FAILURE_THRESHOLD:
                status_placeholder.empty()

                st.error(f"🚨 Data Quality Threshold Exceeded: {failure_percentage:.1f}% > {FAILURE_THRESHOLD}%")

                with st.container():
                    st.markdown("### ⚠️ Insufficient Data Quality for Analysis")
                    st.markdown(f"""
                    **Current Status:**
                    - **Failure Rate:** {failure_percentage:.1f}% (threshold: {FAILURE_THRESHOLD}%)
                    - **Total Sources:** {failure_details['total_sources']}
                    - **Failed Sources:** {failure_details['failed_sources']}
                    - **Successful Fetches:** {failure_details['successful_fetches']}
                    - **Failed Fetches:** {failure_details['failed_fetches']}
                    """)

                    # Show detailed source failures if available
                    if failure_details['source_reliability']:
                        st.markdown("**Source Reliability Scores:**")
                        reliability_df = pd.DataFrame([
                            {"Source": source, "Reliability": f"{score:.2%}", "Status": "✅ Good" if score >= 0.5 else "❌ Poor"}
                            for source, score in failure_details['source_reliability'].items()
                        ])
                        st.dataframe(reliability_df, use_container_width=True)

                    st.markdown("""
                    **Impact:**
                    - Poor data quality could lead to inaccurate trading recommendations
                    - Missing price data may result in outdated or incorrect analysis
                    - Unreliable sources could compromise decision-making

                    **Recommended Actions:**
                    1. **Retry:** Wait a few minutes and try again (networks/APIs may recover)
                    2. **Check Network:** Ensure stable internet connection
                    3. **Proceed Anyway:** Use available data with reduced confidence (not recommended)
                    """)

                    # Action buttons
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if st.button("🔄 Retry Data Gathering", key="retry_data"):
                            st.rerun()

                    with col2:
                        if st.button("⚠️ Proceed with Poor Data", key="proceed_anyway"):
                            st.session_state['force_proceed'] = True
                            st.rerun()

                    with col3:
                        if st.button("📊 View Raw Data", key="view_raw_data"):
                            with st.expander("Raw Market Data", expanded=True):
                                st.json(market_data)

                # Stop execution here - don't make the API call
                st.stop()

            # Check if user forced to proceed despite poor data quality
            elif 'force_proceed' in st.session_state and st.session_state['force_proceed']:
                st.warning(f"⚠️ Proceeding with reduced data quality ({failure_percentage:.1f}% failure rate)")
                st.session_state['force_proceed'] = False  # Reset flag
            else:
                st.success(f"✅ Data quality acceptable ({failure_percentage:.1f}% failure rate)")

            # Prepare comprehensive prompt with all data
            status_placeholder.text("📊 Compiling comprehensive analysis prompt...")

            comprehensive_data = {
                "market_data": market_data,
                "validation_summary": validation_result,
                "analysis_timestamp": datetime.datetime.now().isoformat(),
                "data_sources": market_data.get("metadata", {}).get("sources", []),
                "total_assets_analyzed": sum(len(market_data.get(category, {})) for category in ["stocks", "crypto", "forex", "commodities"])
            }

            # Debug: Check if market data is actually populated
            if not market_data or all(len(market_data.get(cat, {})) == 0 for cat in ["stocks", "crypto", "forex", "commodities"]):
                st.error("⚠️ No market data found! Data gathering may have failed.")
                add_terminal_log("system", "WARNING: Market data is empty or missing", status="error", function_name="data_check")

            # Create the comprehensive prompt with aggressive table enforcement
            prompt_with_all_data = f"""{formatted_prompt}

=== COMPREHENSIVE MARKET DATA FOR ANALYSIS ===

DATA GATHERED FROM MULTIPLE REPUTABLE SOURCES:
{json.dumps(comprehensive_data, indent=2, default=str)}

CRITICAL FINAL INSTRUCTIONS:
1. Use ONLY the provided market data above for your analysis
2. Do NOT use internal knowledge or fetch additional data
3. Base ALL recommendations on the validated data provided
4. Reference specific data sources and timestamps in your analysis
5. If any data is insufficient, note limitations and provide fewer recommendations

**ABSOLUTELY MANDATORY: YOUR RESPONSE MUST INCLUDE A MARKDOWN TABLE**
You MUST format your trading recommendations as a table using this EXACT format:

| Symbol/Pair | Action (Buy/Sell) | Entry Price | Target Price | Stop Loss | Expected Entry Condition/Timing | Expected Exit Condition/Timing | Thesis (≤50 words) | Projected ROI (%) | Likelihood of Profit (%) | Recommended Allocation (% of portfolio) | Plain English Summary (1 sentence) | Data Sources |
|-------------|-------------------|-------------|--------------|-----------|----------------------------------|--------------------------------|---------------------|-------------------|-------------------------|------------------------------------------|-----------------------------------|--------------|

EVEN IF DATA IS INSUFFICIENT OR EMPTY, YOU MUST STILL PROVIDE THE TABLE STRUCTURE WITH AT LEAST ONE EXAMPLE ROW:

| N/A | Hold | 0.00 | 0.00 | 0.00 | Data insufficient for analysis | Refresh data sources | Insufficient data for recommendations | 0.0 | 0 | 0 | No trading opportunities identified due to insufficient data quality. | Data refresh needed |

Start each data row with a pipe character (|) and separate ALL columns with pipes (|). This table format is NOT optional - responses without a proper table will be rejected.

The data includes:
- Trending assets from major financial sites
- Real-time prices and technical indicators
- News sentiment analysis
- Cross-verified data with timestamps
- Validation summary showing data quality

Please analyze this comprehensive dataset and provide your trading recommendations in the MANDATORY table format specified above.

REMINDER: YOUR RESPONSE MUST INCLUDE A MARKDOWN TABLE WITH THESE EXACT COLUMNS:
| Symbol | Action | Entry | Target | Stop | ROI% | Thesis |

Start your table immediately after your market analysis. Use pipe characters (|) to separate columns. Include at least 3 trading recommendations based on the data provided.
"""

            # Store prompt data for troubleshooting sidebar
            prompt_tokens_estimate = len(prompt_with_all_data) // 4
            st.session_state.last_prompt = prompt_with_all_data
            st.session_state.last_prompt_stats = {
                'tokens': prompt_tokens_estimate,
                'chars': len(prompt_with_all_data),
                'sources': len(market_data.get('metadata', {}).get('sources', []))
            }

            status_placeholder.text("🤖 Making single API call to Grok 4 Heavy (expect ~15s wait for first response)...")
            add_terminal_log("request", "Initiating AI analysis request", status="info", url="api.x.ai/v1/chat/completions", function_name="make_single_api_call")
            add_terminal_log("system", f"Prompt tokens: ~{prompt_tokens_estimate:,}", status="info", details=f"{len(prompt_with_all_data):,} chars", function_name="prepare_prompt")
            update_status_display()

            # Make the single API call with status updates and streaming
            # Grok API appears to return streaming format by default
            final_content = make_single_api_call(api_key, prompt_with_all_data, status_callback, enable_streaming=True, streaming_placeholder=streaming_placeholder)

            add_terminal_log("response", "AI analysis response received", status="success", details=f"{len(final_content):,} chars", function_name="make_single_api_call")
            update_status_display()

            status_placeholder.text("📋 Processing AI analysis results...")

            # Clear streaming display after completion
            if streaming_placeholder:
                streaming_placeholder.empty()

            # Store API response data for troubleshooting sidebar
            st.session_state.last_api_response = final_content
            st.session_state.last_response_stats = {
                'length': len(final_content),
                'has_table': '|' in final_content,
                'lines': len(final_content.split('\n'))
            }

            # Display data gathering summary
            with st.expander("📊 Data Gathering Summary", expanded=False):
                st.markdown("**Single API Call Implementation - No Tool Calling**")

                # Debug: Show market data structure
                st.markdown("**Debug - Market Data Structure:**")
                st.json({
                    "has_stocks": bool(market_data.get("stocks")),
                    "has_crypto": bool(market_data.get("crypto")),
                    "has_forex": bool(market_data.get("forex")),
                    "has_commodities": bool(market_data.get("commodities")),
                    "has_metadata": bool(market_data.get("metadata")),
                    "keys": list(market_data.keys()) if market_data else []
                })

                validation_summary = market_data.get("validation_summary", {})

                # Include quality threshold metrics
                failure_percentage_summary, failure_details_summary = calculate_failure_percentage(validation_result)
                quality_status = "✅ Passed" if failure_percentage_summary <= FAILURE_THRESHOLD else "❌ Failed"
                st.markdown(f"""
                **Data Quality Threshold Check:**
                - **Status:** {quality_status} ({failure_percentage_summary:.1f}% failure rate)
                - **Threshold:** {FAILURE_THRESHOLD}% maximum failure rate
                - **Result:** {'API call proceeded' if failure_percentage_summary <= FAILURE_THRESHOLD else 'API call would be blocked'}

                **Data Sources Used:**
                - {', '.join(market_data.get("metadata", {}).get("sources", []))}

                **Asset Coverage:**
                - Stocks: {len(market_data.get("stocks", {}))}
                - Crypto: {len(market_data.get("crypto", {}))}
                - Forex: {len(market_data.get("forex", {}))}
                - Commodities: {len(market_data.get("commodities", {}))}

                **Data Quality Metrics:**
                - Successful Fetches: {validation_summary.get("successful_price_fetches", 0)}
                - Failed Fetches: {validation_summary.get("failed_price_fetches", 0)}
                - Total Sources: {failure_details_summary['total_sources']}
                - Failed Sources: {failure_details_summary['failed_sources']}
                - News Items: {validation_summary.get("news_items_found", 0)}
                - API Calls Made: 1 (Single API call - no tool calling)

                **Validation Status:** ✅ Data validated and timestamps checked
                """)

                # Show source reliability if available
                if failure_details_summary['source_reliability']:
                    st.markdown("**Source Reliability Breakdown:**")
                    reliability_summary_df = pd.DataFrame([
                        {"Source": source, "Reliability": f"{score:.1%}"}
                        for source, score in failure_details_summary['source_reliability'].items()
                    ])
                    st.dataframe(reliability_summary_df, use_container_width=True)

                # Show the actual validation result
                st.markdown("**Validation Result:**")
                st.json(validation_result)

            # Process the AI response
            if final_content:
                # Clean any stray HTML tags from content
                content = final_content
                if content.strip().endswith("</div>"):
                    print("WARNING: Removing stray </div> from AI response")
                    content = content.rstrip().rstrip("</div>").strip()
                add_terminal_log("system", "Starting response parsing", status="info", function_name="parse_ai_response")
                update_status_display()

                # Parse content: report + table + summary
                table_start = content.find('|')
                add_terminal_log("system", f"Table parsing: {len(content)} chars, table at position {table_start}",
                               status="info" if table_start != -1 else "warning", function_name="parse_table_content")
                update_status_display()

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
                    try:
                        if status_callback:
                            status_callback(f"📊 Found table content with {len(table_content)} characters")
                        lines = table_content.split('\n')

                        # Debug: Log the first few lines to understand the structure
                        if status_callback and len(lines) > 0:
                            status_callback(f"🔍 Table has {len(lines)} lines, first line: {lines[0][:100] if lines else 'empty'}")

                        if len(lines) > 2:
                            # Skip header rows and get data lines
                            data_lines = []
                            for i, line in enumerate(lines[2:]):
                                line = line.strip()
                                if line and line.count('|') >= 2:  # Ensure line has at least 2 pipes (minimum for a valid row)
                                    # Clean up the line: remove leading/trailing pipes
                                    if line.startswith('|'):
                                        line = line[1:]
                                    if line.endswith('|'):
                                        line = line[:-1]
                                    data_lines.append(line)

                            if not data_lines:
                                raise ValueError("No valid data rows found in table")

                            # Create CSV string
                            csv_str = '\n'.join(data_lines)

                            # Debug: Log CSV content
                            if status_callback:
                                status_callback(f"📋 Processing {len(data_lines)} data rows")

                            # Parse CSV with error handling
                            try:
                                df = pd.read_csv(StringIO(csv_str), sep='|', header=None, skipinitialspace=True, engine='python')
                            except pd.errors.ParserError as e:
                                # If parsing fails, try to parse line by line
                                if status_callback:
                                    status_callback(f"⚠️ Standard parsing failed: {str(e)}, trying line-by-line parsing")

                                # Parse each line manually
                                parsed_rows = []
                                for line_num, line in enumerate(data_lines):
                                    try:
                                        # Split by pipe and clean each field
                                        fields = [field.strip() for field in line.split('|')]
                                        if fields:  # Only add non-empty rows
                                            parsed_rows.append(fields)
                                    except Exception as line_error:
                                        if status_callback:
                                            status_callback(f"⚠️ Skipping line {line_num + 3}: {str(line_error)}")

                                if not parsed_rows:
                                    raise ValueError("No valid rows could be parsed from table")

                                # Create DataFrame from parsed rows
                                # Find the maximum number of columns
                                max_cols = max(len(row) for row in parsed_rows)
                                # Pad shorter rows with empty strings
                                for row in parsed_rows:
                                    while len(row) < max_cols:
                                        row.append('')

                                df = pd.DataFrame(parsed_rows)

                            # Drop empty columns
                            df = df.dropna(how='all', axis=1)

                            # Remove completely empty rows
                            df = df[df.apply(lambda x: x.str.strip() if x.dtype == "object" else x).ne('').any(axis=1)]

                            # Support both simplified and full formats
                            simplified_columns = ['Symbol', 'Action', 'Entry', 'Target', 'Stop', 'ROI%', 'Thesis']
                            expected_columns = ['Symbol/Pair', 'Action (Buy/Sell)', 'Entry Price', 'Target Price', 'Stop Loss',
                                                'Expected Entry Condition/Timing', 'Expected Exit Condition/Timing', 'Thesis (≤50 words)',
                                                'Projected ROI (%)', 'Likelihood of Profit (%)', 'Recommended Allocation (% of portfolio)',
                                                'Plain English Summary (1 sentence)', 'Data Sources']

                            num_cols = len(df.columns)
                            # Check if it's simplified format (7 columns)
                            if num_cols == len(simplified_columns):
                                df.columns = simplified_columns
                                # Convert to full format for consistency
                                df['Symbol/Pair'] = df['Symbol']
                                df['Action (Buy/Sell)'] = df['Action']
                                df['Entry Price'] = df['Entry']
                                df['Target Price'] = df['Target']
                                df['Stop Loss'] = df['Stop']
                                df['Projected ROI (%)'] = df['ROI%']
                                df['Thesis (≤50 words)'] = df['Thesis']
                                # Add missing columns with defaults
                                df['Expected Entry Condition/Timing'] = 'Market open'
                                df['Expected Exit Condition/Timing'] = 'Target reached'
                                df['Likelihood of Profit (%)'] = 70
                                df['Recommended Allocation (% of portfolio)'] = 5
                                df['Plain English Summary (1 sentence)'] = df['Thesis']
                                df['Data Sources'] = 'yfinance_safe'
                                # Reorder to match expected columns
                                df = df[expected_columns]
                                num_cols = len(expected_columns)
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

                            add_terminal_log("system", f"Successfully parsed {len(df)} trading recommendations",
                                           status="success", function_name="parse_recommendations_table")
                            update_status_display()

                            st.session_state.recommendations = df
                        else:
                            st.error("No valid table found in response (less than 3 lines).")

                    except pd.errors.ParserError as e:
                        st.error(f"❌ Failed to parse table: {str(e)}")
                        st.markdown("**Table parsing error details:**")
                        st.markdown("- Error type: CSV parsing error")
                        st.markdown(f"- Error message: {str(e)}")
                        st.markdown("**Debug info:**")
                        if table_content:
                            lines = table_content.split('\n')
                            st.markdown(f"- Table lines: {len(lines)}")
                            if lines:
                                st.markdown(f"- First line: `{lines[0][:100]}...`")
                                if len(lines) > 2:
                                    st.markdown(f"- Third line (first data): `{lines[2][:100]}...`")
                        st.markdown("**Possible causes:**")
                        st.markdown("- Inconsistent number of columns in table rows")
                        st.markdown("- Missing or extra pipe delimiters")
                        st.markdown("- Special characters in table cells")

                    except ValueError as e:
                        st.error(f"❌ Table validation error: {str(e)}")
                        st.markdown("**Debug info:**")
                        st.markdown(f"- Table content length: {len(table_content)} chars")
                        st.markdown("- Table might be malformed or empty")

                    except Exception as e:
                        st.error(f"❌ Unexpected error parsing table: {str(e)}")
                        st.markdown(f"**Error type:** {type(e).__name__}")
                        st.markdown(f"**Error details:** {str(e)}")
                        # Log the table content for debugging
                        if table_content:
                            with st.expander("🔍 Show raw table content for debugging"):
                                st.text(table_content)
                else:
                    st.error("❌ No table found in response.")
                    st.markdown("**Debugging Info:**")
                    st.markdown(f"- Response length: {len(final_content)} characters")
                    st.markdown(f"- Contains '|': {'|' in final_content}")
                    st.markdown(f"- First 200 chars: `{final_content[:200]}...`")

                    # Check for alternative table formats or missed tables
                    if '|' not in final_content:
                        st.warning("💡 The AI response doesn't contain table markers (|). The prompt may need adjustment or the AI model may not be following the table format instructions.")
                        st.info("🔄 **Trying alternative table detection...**")

                        # Look for potential table data in text format
                        lines = final_content.split('\n')
                        potential_table_lines = []
                        for line in lines:
                            # Look for lines that might be table rows (contain multiple commas, tabs, or structured data)
                            if any(keyword in line.lower() for keyword in ['symbol', 'buy', 'sell', 'price', 'target', 'stop']):
                                potential_table_lines.append(line.strip())

                        if potential_table_lines:
                            st.markdown("**Potential table data found in text format:**")
                            for line in potential_table_lines[:5]:  # Show first 5 lines
                                st.code(line)
                            st.warning("⚠️ The AI provided trading recommendations but not in the required table format. Please try the analysis again.")
                        else:
                            st.warning("⚠️ No structured trading data found in the response. The AI may need clearer instructions.")
                    else:
                        st.info("🔍 Table markers found but parsing failed. Check the table structure in the API response viewer.")

                st.session_state.report = report_content
                st.session_state.summary = summary_content

                # Final terminal logs
                add_terminal_log("system", "AI analysis completed successfully", status="success", function_name="main")
                add_terminal_log("system", "Terminal session ended", status="info", function_name="main")
                update_status_display()

                status_placeholder.text("✅ Analysis complete! Single API call successful.")
                time.sleep(2)

                # Deactivate terminal after completion
                st.session_state.terminal_active = False
                terminal_placeholder.empty()
                status_placeholder.empty()

            else:
                # Error case - deactivate terminal
                add_terminal_log("system", "Failed to generate predictions", status="error", function_name="main")
                update_status_display()
                time.sleep(1)
                st.session_state.terminal_active = False
                terminal_placeholder.empty()

                st.error("❌ Failed to generate predictions with single API call")
                status_placeholder.empty()

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()

            # Terminal logging for exception
            add_terminal_log("system", f"Exception occurred: {type(e).__name__}", status="error", function_name="main", details=str(e))
            update_status_display()
            time.sleep(1)
            st.session_state.terminal_active = False
            terminal_placeholder.empty()

            st.error(f"❌ Error generating predictions: {e}")

            # Show detailed error in expander
            with st.expander("🔍 Error Details", expanded=True):
                st.code(error_details)
                st.error(f"Error Type: {type(e).__name__}")
                st.error(f"Error Message: {str(e)}")

            status_placeholder.text(f"❌ Error: {str(e)}")

            # Log to console for debugging
            print(f"ERROR in app.py: {type(e).__name__}: {str(e)}")
            print(error_details)
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

    for _, row in df.iterrows():
        # Extract all data
        symbol = row['Symbol/Pair']
        action = row['Action (Buy/Sell)']
        entry_price = row['Entry Price'] if pd.notna(row['Entry Price']) else 'N/A'
        target_price = row['Target Price'] if pd.notna(row['Target Price']) else 'N/A'
        stop_loss = row['Stop Loss'] if pd.notna(row['Stop Loss']) else 'N/A'
        roi = row.get('Projected ROI (%)', 'N/A')
        likelihood = row.get('Likelihood of Profit (%)', 'N/A')
        allocation = row.get('Recommended Allocation (% of portfolio)', 'N/A')
        entry_timing = row.get('Expected Entry Condition/Timing', 'N/A')
        exit_timing = row.get('Expected Exit Condition/Timing', 'N/A')
        data_sources = row.get('Data Sources', 'N/A')
        thesis = row.get('Thesis (≤50 words)', 'N/A')
        plain_summary = row.get('Plain English Summary (1 sentence)', 'N/A')

        # Color scheme based on action
        action_color = "#4CAF50" if action == "Buy" else "#F44336"
        action_color_dark = "#388E3C" if action == "Buy" else "#D32F2F"

        # Progress bar colors
        roi_color = "#4CAF50" if isinstance(roi, (int, float)) and roi > 0 else "#F44336"
        roi_color_light = "#81C784" if isinstance(roi, (int, float)) and roi > 0 else "#EF5350"

        likelihood_color = "#2196F3" if isinstance(likelihood, (int, float)) and likelihood >= 60 else "#FF9800" if isinstance(likelihood, (int, float)) and likelihood >= 40 else "#F44336"
        likelihood_color_light = "#64B5F6" if isinstance(likelihood, (int, float)) and likelihood >= 60 else "#FFB74D" if isinstance(likelihood, (int, float)) and likelihood >= 40 else "#EF5350"

        allocation_color = "#9C27B0"
        allocation_color_light = "#BA68C8"

        # Format IBKR link
        ibkr_symbol = symbol.replace('-USD', '').replace('=X', '')
        trade_url = f"https://www.interactivebrokers.com/en/trading/trade.php?symbol={ibkr_symbol}"

        # Calculate confidence score and risk/reward ratio
        confidence_score = min(likelihood, 85) if isinstance(likelihood, (int, float)) else 65
        risk_amount = abs(entry_price - stop_loss) if isinstance(entry_price, (int, float)) and isinstance(stop_loss, (int, float)) else 0
        reward_amount = abs(target_price - entry_price) if isinstance(target_price, (int, float)) and isinstance(entry_price, (int, float)) else 0
        risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

        # Market hours check (simplified)
        current_hour = datetime.datetime.now().hour
        market_open = 9 <= current_hour <= 16  # Basic market hours
        market_status = "🟢 Market Open" if market_open else "🔴 Market Closed"

        # Format values for JavaScript
        entry_price_str = f"${entry_price:.2f}" if isinstance(entry_price, (int, float)) else str(entry_price)
        target_price_str = f"${target_price:.2f}" if isinstance(target_price, (int, float)) else str(target_price)
        stop_loss_str = f"${stop_loss:.2f}" if isinstance(stop_loss, (int, float)) else str(stop_loss)

        # Create beautiful enhanced trading card using container
        with st.container():
            # Build HTML with embedded CSS for components.html
            card_html = f"""
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}

            .trading-card {{
                background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                border: 1px solid #333;
                border-radius: 12px;
                padding: 24px;
                margin: 16px 0;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                color: #FAFAFA;
            }}

            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
                padding-bottom: 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .card-header h4 {{
                color: #FAFAFA;
                margin: 0;
                font-size: 24px;
                font-weight: 600;
            }}

            .action-badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                margin-left: 12px;
                color: white;
                text-transform: uppercase;
            }}

            .status-indicator {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin-top: 8px;
                color: #999;
                font-size: 14px;
            }}

            .status-dot {{
                width: 8px;
                height: 8px;
                background: #F44336;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }}

            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
                100% {{ opacity: 1; }}
            }}

            .header-controls {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}

            .confidence-badge {{
                background: rgba(33, 150, 243, 0.2);
                color: #2196F3;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                border: 1px solid rgba(33, 150, 243, 0.3);
            }}

            .copy-button, .info-button {{
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: #FAFAFA;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                transition: all 0.3s;
            }}

            .copy-button:hover, .info-button:hover {{
                background: rgba(255, 255, 255, 0.2);
                transform: translateY(-2px);
            }}

            .card-content {{
                padding-top: 24px;
            }}

            .metrics-grid {{
                display: grid;
                grid-template-columns: 1.5fr 1fr;
                gap: 24px;
            }}

            .price-section {{
                background: rgba(255, 255, 255, 0.05);
                padding: 20px;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .price-section-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 16px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .price-section-title {{
                font-size: 18px;
                font-weight: 600;
                color: #FAFAFA;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .quick-calc {{
                background: rgba(76, 175, 80, 0.2);
                color: #4CAF50;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }}

            .price-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}

            .price-row:last-child {{
                border-bottom: none;
            }}

            .price-label {{
                color: #999;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .price-value {{
                font-size: 20px;
                font-weight: 700;
                color: #FAFAFA;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .copy-price {{
                font-size: 14px;
                cursor: pointer;
                opacity: 0.5;
                transition: opacity 0.3s;
            }}

            .copy-price:hover {{
                opacity: 1;
            }}

            .price-change {{
                font-size: 14px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 4px;
            }}

            .price-change.positive {{
                color: #4CAF50;
                background: rgba(76, 175, 80, 0.1);
            }}

            .price-change.negative {{
                color: #F44336;
                background: rgba(244, 67, 54, 0.1);
            }}

            .section-divider {{
                height: 1px;
                background: rgba(255, 255, 255, 0.1);
                margin: 20px 0;
            }}

            .risk-reward-chart {{
                margin-top: 20px;
                padding: 16px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 8px;
            }}

            .risk-reward-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}

            .risk-reward-title {{
                color: #FAFAFA;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .risk-reward-ratio {{
                color: #4CAF50;
                font-size: 18px;
                font-weight: 700;
            }}

            .risk-reward-bars {{
                display: flex;
                align-items: center;
                gap: 12px;
                margin-top: 12px;
            }}

            .risk-bar {{
                height: 24px;
                background: linear-gradient(90deg, #F44336, #EF5350);
                border-radius: 4px;
            }}

            .reward-bar {{
                height: 24px;
                background: linear-gradient(90deg, #4CAF50, #66BB6A);
                border-radius: 4px;
            }}

            .risk-label, .reward-label {{
                font-size: 12px;
                font-weight: 600;
                color: #999;
                min-width: 50px;
            }}

            .progress-container {{
                margin-bottom: 20px;
            }}

            .progress-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }}

            .progress-label {{
                color: #999;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .progress-value {{
                font-size: 18px;
                font-weight: 700;
                color: #FAFAFA;
            }}

            .progress-bar {{
                height: 8px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                overflow: hidden;
            }}

            .progress-fill {{
                height: 100%;
                transition: width 0.5s ease;
            }}

            .analysis-section {{
                background: rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                margin-bottom: 16px;
                overflow: hidden;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .analysis-header {{
                padding: 16px 20px;
                cursor: pointer;
                user-select: none;
                transition: background 0.3s;
            }}

            .analysis-header:hover {{
                background: rgba(255, 255, 255, 0.05);
            }}

            .analysis-title {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                color: #FAFAFA;
                font-weight: 600;
            }}

            .analysis-title-left {{
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .expand-icon {{
                transition: transform 0.3s;
                color: #999;
            }}

            .analysis-content {{
                padding: 0 20px 20px;
                max-height: 500px;
                overflow: hidden;
                transition: max-height 0.3s ease;
            }}

            .analysis-content.collapsed {{
                max-height: 0;
                padding-bottom: 0;
            }}

            .analysis-summary {{
                color: #FAFAFA;
                font-weight: 600;
                margin-bottom: 8px;
            }}

            .analysis-details {{
                color: #CCC;
                line-height: 1.6;
                font-size: 14px;
            }}

            .analysis-tags {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 12px;
            }}

            .analysis-tag {{
                background: rgba(33, 150, 243, 0.2);
                color: #64B5F6;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }}

            .ib-button-container {{
                text-align: center;
                margin-top: 32px;
                padding-top: 24px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .ib-button {{
                display: inline-block;
                padding: 16px 32px;
                background: linear-gradient(135deg, var(--action-color), var(--action-color-dark));
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                transition: all 0.3s;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            }}

            .ib-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
            }}

            .ib-disclaimer {{
                color: #666;
                font-size: 12px;
                margin-top: 12px;
            }}

            .icon {{
                font-size: 16px;
            }}

            .tooltip {{
                position: relative;
            }}

            .tooltip[data-tooltip]:hover::after {{
                content: attr(data-tooltip);
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.9);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                white-space: nowrap;
                z-index: 1000;
                margin-bottom: 8px;
            }}
        </style>

        <script>
            function copyToClipboard(text, element) {{
                navigator.clipboard.writeText(text).then(function() {{
                    const originalText = element.innerHTML;
                    element.innerHTML = '✓';
                    setTimeout(function() {{
                        element.innerHTML = originalText;
                    }}, 1000);
                }});
            }}

            function copyTradeDetails(symbol, action, entry, target, stop) {{
                const details = `${{symbol}} ${{action}}\\nEntry: ${{entry}}\\nTarget: ${{target}}\\nStop: ${{stop}}`;
                copyToClipboard(details, event.target);
            }}

            document.addEventListener('DOMContentLoaded', function() {{
                // Toggle analysis sections
                const headers = document.querySelectorAll('.analysis-header');
                headers.forEach(header => {{
                    header.addEventListener('click', function() {{
                        const content = this.nextElementSibling;
                        const icon = this.querySelector('.expand-icon');

                        content.classList.toggle('collapsed');
                        icon.style.transform = content.classList.contains('collapsed') ? 'rotate(0deg)' : 'rotate(180deg)';
                    }});
                }});
            }});
        </script>

        <div class="trading-card" style="--action-color: {action_color}; --action-color-dark: {action_color_dark};">
            <div class="card-header">
                <div>
                    <h4>
                        {symbol}
                        <span class="action-badge" style="background: linear-gradient(135deg, {action_color}, {action_color_dark});">
                            {action}
                        </span>
                    </h4>
                    <div class="status-indicator">
                        <div class="status-dot"></div>
                        <span>{market_status}</span>
                        <span class="last-updated">Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}</span>
                    </div>
                </div>
                <div class="header-controls">
                    <div class="confidence-badge tooltip" data-tooltip="AI confidence in this recommendation based on data quality and market conditions">
                        {confidence_score:.0f}% Confidence
                    </div>
                    <button class="copy-button tooltip" data-tooltip="Copy trade details to clipboard" onclick="copyTradeDetails('{symbol}', '{action}', '{entry_price_str}', '{target_price_str}', '{stop_loss_str}')">
                        📋
                    </button>
                    <button class="info-button tooltip" data-tooltip="Additional market information and context">
                        ℹ️
                    </button>
                    <!-- TradingView Widget BEGIN -->
                    <div class="tradingview-widget-container">
                      <div class="tradingview-widget-container__widget"></div>
                    </div>
                    <!-- TradingView Widget END -->
                </div>
            </div>

            <div class="card-content">
                <div class="metrics-grid">
                    <div class="price-section">
                        <div class="price-section-header">
                            <div class="price-section-title">
                                <span class="icon">💰</span>
                                Price Levels
                            </div>
                            <div class="quick-calc tooltip" data-tooltip="Quick calculation: Potential return vs risk">
                                R/R: {risk_reward_ratio:.1f}:1
                            </div>
                        </div>
                        <div class="price-row">
                            <span class="price-label tooltip" data-tooltip="Recommended entry point for this position">
                                <span class="icon">🎯</span>
                                Entry Price
                            </span>
                            <span class="price-value">
                                {entry_price_str}
                                <span class="copy-price" onclick="copyToClipboard('{entry_price_str}', this)">📋</span>
                            </span>
                        </div>
                        <div class="price-row">
                            <span class="price-label tooltip" data-tooltip="Target price for profit taking">
                                <span class="icon">🚀</span>
                                Target Price
                            </span>
                            <span class="price-value">
                                {target_price_str}
                                <span class="copy-price" onclick="copyToClipboard('{target_price_str}', this)">📋</span>
                                {f'<span class="price-change positive">+{((target_price - entry_price) / entry_price * 100):.1f}%</span>' if isinstance(target_price, (int, float)) and isinstance(entry_price, (int, float)) and target_price > entry_price else ''}
                            </span>
                        </div>
                        <div class="price-row">
                            <span class="price-label tooltip" data-tooltip="Stop loss level to limit downside risk">
                                <span class="icon">🛡️</span>
                                Stop Loss
                            </span>
                            <span class="price-value">
                                {stop_loss_str}
                                <span class="copy-price" onclick="copyToClipboard('{stop_loss_str}', this)">📋</span>
                                {f'<span class="price-change negative">{((stop_loss - entry_price) / entry_price * 100):.1f}%</span>' if isinstance(stop_loss, (int, float)) and isinstance(entry_price, (int, float)) and stop_loss < entry_price else ''}
                            </span>
                        </div>

                        <!-- Risk/Reward Visualization -->
                        <div class="section-divider"></div>
                        <div class="risk-reward-chart">
                            <div class="risk-reward-header">
                                <div class="risk-reward-title">
                                    <span>⚖️</span>
                                    Risk/Reward Analysis
                                </div>
                                <div class="risk-reward-ratio tooltip" data-tooltip="Higher ratios indicate better risk-adjusted returns">
                                    {risk_reward_ratio:.2f}:1 Ratio
                                </div>
                            </div>
                            <div class="risk-reward-bars">
                                <div class="risk-label">Risk</div>
                                <div class="risk-bar" style="flex: 1;"></div>
                                <div class="reward-bar" style="flex: {max(risk_reward_ratio, 0.1)};"></div>
                                <div class="reward-label">Reward</div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <div class="progress-container" style="--progress-color: {roi_color}; --progress-color-light: {roi_color_light};">
                            <div class="progress-header">
                                <span class="progress-label">
                                    <span class="icon">📈</span>
                                    Projected ROI
                                </span>
                                <span class="progress-value">{'%.2f%%' % roi if isinstance(roi, (int, float)) else roi}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {min(abs(roi), 100) if isinstance(roi, (int, float)) else 0}%; background: linear-gradient(90deg, {roi_color}, {roi_color_light});"></div>
                            </div>
                        </div>

                        <div class="progress-container" style="--progress-color: {likelihood_color}; --progress-color-light: {likelihood_color_light};">
                            <div class="progress-header">
                                <span class="progress-label">
                                    <span class="icon">🎯</span>
                                    Success Probability
                                </span>
                                <span class="progress-value">{'%.0f%%' % likelihood if isinstance(likelihood, (int, float)) else likelihood}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {likelihood if isinstance(likelihood, (int, float)) else 0}%; background: linear-gradient(90deg, {likelihood_color}, {likelihood_color_light});"></div>
                            </div>
                        </div>

                        <div class="progress-container" style="--progress-color: {allocation_color}; --progress-color-light: {allocation_color_light};">
                            <div class="progress-header">
                                <span class="progress-label">
                                    <span class="icon">⚖️</span>
                                    Portfolio Allocation
                                </span>
                                <span class="progress-value">{'%.2f%%' % allocation if isinstance(allocation, (int, float)) else allocation}</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {min(allocation * 4, 100) if isinstance(allocation, (int, float)) else 0}%; background: linear-gradient(90deg, {allocation_color}, {allocation_color_light});"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="section-divider"></div>

                <div class="analysis-section first-section">
                    <div class="analysis-header">
                        <div class="analysis-title">
                            <div class="analysis-title-left">
                                <span class="icon">💡</span>
                                Technical Analysis
                            </div>
                            <span class="expand-icon">▼</span>
                        </div>
                    </div>
                    <div class="analysis-content">
                        <div class="analysis-summary">Market Technical Overview</div>
                        <div class="analysis-details">{thesis}</div>
                        <div class="analysis-tags">
                            <span class="analysis-tag">Technical Indicators</span>
                            <span class="analysis-tag">Price Action</span>
                            <span class="analysis-tag">Chart Patterns</span>
                        </div>
                    </div>
                </div>

                <div class="analysis-section">
                    <div class="analysis-header">
                        <div class="analysis-title">
                            <div class="analysis-title-left">
                                <span class="icon">📝</span>
                                Plain English Summary
                            </div>
                            <span class="expand-icon">▼</span>
                        </div>
                    </div>
                    <div class="analysis-content collapsed">
                        <div class="analysis-summary">Trade Rationale in Simple Terms</div>
                        <div class="analysis-details">{plain_summary}</div>
                        <div class="analysis-tags">
                            <span class="analysis-tag">Beginner Friendly</span>
                            <span class="analysis-tag">Key Points</span>
                        </div>
                    </div>
                </div>

                <div class="analysis-section">
                    <div class="analysis-header">
                        <div class="analysis-title">
                            <div class="analysis-title-left">
                                <span class="icon">⏱️</span>
                                Timing & Market Context
                            </div>
                            <span class="expand-icon">▼</span>
                        </div>
                    </div>
                    <div class="analysis-content collapsed">
                        <div class="analysis-summary">Strategic Timing Considerations</div>
                        <div class="analysis-details">
                            <strong>Entry Timing:</strong> {entry_timing}<br><br>
                            <strong>Exit Timing:</strong> {exit_timing}<br><br>
                            <strong>Data Sources:</strong> {data_sources}
                        </div>
                        <div class="analysis-tags">
                            <span class="analysis-tag">Market Hours</span>
                            <span class="analysis-tag">Economic Calendar</span>
                            <span class="analysis-tag">Data Quality</span>
                        </div>
                    </div>
                </div>

                <div class="analysis-section">
                    <div class="analysis-header">
                        <div class="analysis-title">
                            <div class="analysis-title-left">
                                <span class="icon">📊</span>
                                Portfolio Impact
                            </div>
                            <span class="expand-icon">▼</span>
                        </div>
                    </div>
                    <div class="analysis-content collapsed">
                        <div class="analysis-summary">How This Trade Affects Your Portfolio</div>
                        <div class="analysis-details">
                            <strong>Allocation:</strong> {'%.2f%%' % allocation if isinstance(allocation, (int, float)) else allocation} of total portfolio<br><br>
                            <strong>Correlation:</strong> Consider existing positions in similar assets<br><br>
                            <strong>Risk Management:</strong> This position should align with your overall risk tolerance and diversification strategy
                        </div>
                        <div class="analysis-tags">
                            <span class="analysis-tag">Position Sizing</span>
                            <span class="analysis-tag">Diversification</span>
                            <span class="analysis-tag">Risk Management</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="ib-button-container">
                <a href="{trade_url}" target="_blank" class="ib-button">
                    <span class="icon">🚀</span>
                    {action} {symbol} on Interactive Brokers
                </a>
                <div class="ib-disclaimer">
                    Pre-populated order details may require manual entry. Interactive Brokers is top-rated for execution quality.
                </div>
            </div>
        </div>
        """

            # Render the card HTML using components for better HTML handling
            components.html(card_html, height=1200, scrolling=False)

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
st.info("This is not financial advice. Always consult professionals.")
