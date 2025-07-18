# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit-based AI-powered trade analysis application that generates trading recommendations using xAI's Grok 4 Heavy model. The app provides a professional TradingView-style interface for displaying trade opportunities across multiple asset classes (stocks, forex, crypto, commodities).

## Key Development Commands

```bash
# Run the application locally
streamlit run app.py

# Install dependencies
pip install -r requirements.txt

# Run code quality checks (via Trunk)
trunk check
trunk fmt
```

## Architecture & Key Components

### Core Files
- **app.py**: Main Streamlit application with tool-calling implementation
- **tools.py**: Tool functions for real-time data fetching and validation
- **prompt.txt**: AI prompt template with dynamic date placeholders ({current_date}, {next_day})
- **test_validators.py**: Comprehensive validation system for tool-calling
- **requirements.txt**: Python dependencies (streamlit, requests, pandas, yfinance, beautifulsoup4)

### Key Features Implementation
1. **AI Integration**: Uses xAI's Grok 4 Heavy API endpoint at `https://api.x.ai/v1/chat/completions`
2. **Tool-Calling System**: Implements function calling with 6 core tools:
   - `fetch_current_price`: Real-time price fetching with validation
   - `search_web_for_news`: Financial news search with date filtering
   - `browse_page_for_data`: Web scraping for market data
   - `validate_data`: Data freshness and quality validation
   - `code_execution_for_backtest`: Safe Python execution for backtesting
   - `get_onchain_metrics`: Cryptocurrency on-chain metrics
3. **Real-time Data**: Fetches live prices via yfinance and validates data age
4. **Trading Integration**: Generates direct Interactive Brokers trading links
5. **Portfolio Tracking**: Optional feature to track and visualize portfolio performance
6. **Validation System**: Comprehensive testing and validation framework

### Tool-Calling Architecture

The application implements a sophisticated tool-calling system:

**Tool Schema Definition**: Each tool is defined with proper OpenAI function calling schema
**Tool Execution Loop**: The `execute_with_tools()` function handles the iterative tool-calling process
**Tool Function Mapping**: Maps tool names to actual Python functions in `tools.py`
**Validation Integration**: All tool calls are validated for data freshness and accuracy

### Critical Code Patterns

When modifying the AI prompt:
- Preserve the {current_date} and {next_day} placeholders
- Maintain the strict output format (market report + table + summary)
- Keep the 13-column table structure for trade recommendations
- Ensure tool usage requirements are clearly specified

When working with tool functions:
- All tools must return structured data with timestamps
- Implement proper error handling and fallback mechanisms
- Validate data age (≤5 minutes for prices, ≤12 hours for news)
- Use the validation system to ensure data quality

When working with the Streamlit UI:
- Follow the existing dark theme CSS styling
- Use st.container() and st.columns() for layout consistency
- Implement proper error handling with st.error() for user feedback
- Display tool execution history for transparency

When adding new features:
- Follow the tool-calling pattern for external data access
- Implement proper validation for new data sources
- Add corresponding test cases to the validation system
- Maintain the professional trading terminal aesthetic

## Development Environment

The project includes a DevContainer configuration that:
- Uses Python 3.11 on Debian
- Auto-installs dependencies
- Runs the app automatically on port 8501
- Includes Python and Pylance VS Code extensions

## Code Quality

Trunk is configured with multiple linters and security scanners:
- **Formatters**: Black, isort
- **Linters**: Ruff, Bandit
- **Security**: Checkov, OSV Scanner, Trufflehog

Always run `trunk check` before committing changes.

## Important Considerations

1. **API Key Security**: The app currently accepts API keys via UI input. Consider environment variables for production.
2. **Comprehensive Testing**: The project includes a full test suite:
   - **test_validators.py**: Core validation classes
   - **test_suite.py**: Unit tests for all components
   - **run_tests.py**: Main test runner with comprehensive validation
   - **streamlit_test_integration.py**: Real-time validation integration
3. **Tool-Calling Validation**: All tool calls are validated for:
   - Data freshness (≤5 minutes for prices, ≤12 hours for news)
   - Price accuracy (±1% tolerance against live data)
   - Hallucination detection (prevents use of outdated internal knowledge)
4. **State Management**: Streamlit reloads the entire script on interaction. Use st.session_state for persistence.
5. **Performance**: Tool-calling can involve multiple API calls. The system implements:
   - Parallel processing where possible
   - Caching for frequently accessed data
   - Timeout handling for external calls
6. **Error Handling**: Comprehensive error handling includes:
   - Tool execution failures with graceful degradation
   - Network timeout handling
   - Data validation with automatic retry mechanisms
7. **Data Quality**: All data sources are validated:
   - Timestamp validation for freshness
   - Cross-verification between multiple sources
   - Automatic filtering of stale or invalid data

## Tool-Calling Best Practices

1. **Mandatory Tool Usage**: The AI must use tools for all data access - no internal knowledge allowed
2. **Data Citation**: All tool calls must be documented in the "Data Sources" column
3. **Validation Integration**: Use the validation system to ensure data quality
4. **Error Recovery**: Implement fallback mechanisms for failed tool calls
5. **Performance Monitoring**: Track tool execution times and success rates