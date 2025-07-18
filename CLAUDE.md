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
- **app.py**: Main Streamlit application containing all business logic and UI
- **prompt.txt**: AI prompt template with dynamic date placeholders ({current_date}, {next_day})
- **requirements.txt**: Python dependencies (streamlit, requests, pandas, yfinance)

### Key Features Implementation
1. **AI Integration**: Uses xAI's Grok 4 Heavy API endpoint at `https://api.grok.x.ai/v1/chat/completions`
2. **Real-time Data**: Fetches live prices via yfinance for validation
3. **Trading Integration**: Generates direct Interactive Brokers trading links
4. **Portfolio Tracking**: Optional feature to track and visualize portfolio performance

### Critical Code Patterns

When modifying the AI prompt:
- Preserve the {current_date} and {next_day} placeholders
- Maintain the strict output format (market report + table + summary)
- Keep the 13-column table structure for trade recommendations

When working with the Streamlit UI:
- Follow the existing dark theme CSS styling
- Use st.container() and st.columns() for layout consistency
- Implement proper error handling with st.error() for user feedback

When adding new features:
- Check if data pre-fetching is needed (see pre_fetch_data function)
- Follow the existing pattern for TradingView widget integration
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
2. **No Tests**: The project lacks a test suite. When adding complex features, consider adding tests.
3. **State Management**: Streamlit reloads the entire script on interaction. Use st.session_state for persistence.
4. **Performance**: Large AI responses and multiple yfinance calls can be slow. Consider caching where appropriate.
5. **Error Handling**: Always wrap external API calls (xAI, yfinance) in try-except blocks with user-friendly error messages.