# Testing Strategy for Tool-Calling Implementation

## Overview
This document outlines a comprehensive testing strategy to validate that the AI model (Grok4_Heavy) is actually calling tools and not hallucinating data, especially for real-time prices and news.

## 1. Test Scenarios

### 1.1 Tool Execution Verification
- **Objective**: Verify tools are actually called, not simulated
- **Test Cases**:
  - Monitor API calls to verify `web_search` and `browse_page` tools are invoked
  - Track tool call timestamps and parameters
  - Validate tool responses are incorporated into analysis

### 1.2 Data Freshness Validation
- **Objective**: Ensure all data is from current date with ≤5 minute timestamps
- **Test Cases**:
  - Verify BTC price is ~$120k range (December 2024), not outdated $60k
  - Check all timestamps are within 5 minutes of request time
  - Validate date filters in web_search queries (e.g., `after:{current_date} before:{next_day}`)

### 1.3 Price Accuracy Validation
- **Objective**: Confirm prices match current market data
- **Test Cases**:
  - Cross-reference AI-reported prices with yfinance real-time data
  - Verify price consistency across multiple sources (±1% tolerance)
  - Flag any prices that differ >1% from live data

### 1.4 No Hallucination Checks
- **Objective**: Prevent AI from using internal knowledge or outdated data
- **Test Cases**:
  - Verify every data point has explicit tool call citation
  - Check for presence of verification steps in AI response
  - Validate no data older than current date is used

## 2. Mock Data Design

### 2.1 Tool Response Mocks
```python
# Mock responses for testing tool functions
MOCK_TOOL_RESPONSES = {
    'web_search': {
        'query': 'BTC price December 2024 after:2024-12-18 before:2024-12-19',
        'response': {
            'results': [
                {
                    'title': 'Bitcoin Price Today - Live BTC/USD',
                    'url': 'https://www.investing.com/crypto/bitcoin',
                    'snippet': 'BTC/USD: $119,856.45 as of 2024-12-18 14:32:00 UTC',
                    'timestamp': '2024-12-18T14:32:00Z'
                }
            ]
        }
    },
    'browse_page': {
        'url': 'https://finance.yahoo.com/quote/BTC-USD',
        'response': {
            'content': 'Bitcoin USD (BTC-USD) Price: $119,743.21',
            'timestamp': '2024-12-18T14:33:15Z',
            'extracted_data': {
                'price': 119743.21,
                'change_pct': 2.34,
                'volume': 28456789012
            }
        }
    }
}
```

### 2.2 Price Validation Data
```python
# Expected price ranges for December 2024
EXPECTED_PRICE_RANGES = {
    'BTC-USD': (115000, 125000),  # ~$120k range
    'ETH-USD': (3800, 4200),      # ~$4k range
    'NVDA': (450, 550),           # Post-split adjusted
    'TSLA': (380, 420),
    'AAPL': (195, 205),
    'GOLD': (2050, 2150)
}
```

## 3. Testing Implementation Plan

### 3.1 Tool Call Logger
```python
class ToolCallLogger:
    def __init__(self):
        self.calls = []
        
    def log_call(self, tool_name, params, response, timestamp):
        self.calls.append({
            'tool': tool_name,
            'params': params,
            'response': response,
            'timestamp': timestamp,
            'duration_ms': None  # To be calculated
        })
        
    def get_tool_usage_report(self):
        return {
            'total_calls': len(self.calls),
            'tools_used': list(set(c['tool'] for c in self.calls)),
            'avg_response_time': self._calc_avg_response_time(),
            'data_sources': self._extract_sources()
        }
```

### 3.2 Data Freshness Validator
```python
class DataFreshnessValidator:
    def __init__(self, max_age_minutes=5):
        self.max_age_minutes = max_age_minutes
        
    def validate_timestamp(self, timestamp_str, current_time):
        """Validate data timestamp is within acceptable range"""
        data_time = datetime.fromisoformat(timestamp_str)
        age_minutes = (current_time - data_time).total_seconds() / 60
        return age_minutes <= self.max_age_minutes
        
    def validate_search_query(self, query, current_date):
        """Ensure search queries have proper date filters"""
        return f"after:{current_date}" in query
```

### 3.3 Price Accuracy Checker
```python
class PriceAccuracyChecker:
    def __init__(self, tolerance_pct=1.0):
        self.tolerance_pct = tolerance_pct
        
    def validate_price(self, symbol, ai_price, live_price):
        """Compare AI-reported price with live market data"""
        if live_price == 0:
            return False, "Invalid live price"
            
        diff_pct = abs(ai_price - live_price) / live_price * 100
        
        if diff_pct <= self.tolerance_pct:
            return True, f"Price within tolerance: {diff_pct:.2f}%"
        else:
            return False, f"Price difference too large: {diff_pct:.2f}%"
```

## 4. Streamlit Testing Interface

### 4.1 Test Dashboard Components
```python
# Add to Streamlit app for testing
def display_test_dashboard():
    st.sidebar.markdown("### Testing Controls")
    
    # Toggle test mode
    test_mode = st.sidebar.checkbox("Enable Test Mode")
    
    if test_mode:
        # Show tool call logs
        if 'tool_logger' in st.session_state:
            st.expander("Tool Call Logs").json(
                st.session_state.tool_logger.get_tool_usage_report()
            )
        
        # Show data validation results
        if 'validation_results' in st.session_state:
            st.expander("Data Validation Results").dataframe(
                st.session_state.validation_results
            )
        
        # Manual price check
        if st.sidebar.button("Run Price Validation"):
            run_price_validation_test()
```

### 4.2 Validation Results Display
```python
def display_validation_results(results):
    """Display comprehensive validation results"""
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tools Called", results['tools_called'])
    col2.metric("Data Freshness", f"{results['fresh_data_pct']:.1f}%")
    col3.metric("Price Accuracy", f"{results['accurate_prices_pct']:.1f}%")
    col4.metric("Hallucinations", results['hallucination_count'])
    
    # Detailed breakdown
    st.markdown("### Validation Details")
    
    # Tool usage
    st.markdown("#### Tool Usage")
    st.dataframe(results['tool_usage_details'])
    
    # Price validation
    st.markdown("#### Price Validation")
    for symbol, validation in results['price_validations'].items():
        status = "✅" if validation['valid'] else "❌"
        st.write(f"{status} {symbol}: {validation['message']}")
```

## 5. Edge Cases and Error Scenarios

### 5.1 Edge Cases to Test
1. **Market Closed**: Verify behavior when markets are closed
2. **API Rate Limits**: Handle tool call rate limiting gracefully
3. **Network Failures**: Test behavior with simulated network issues
4. **Invalid Symbols**: Ensure proper error handling for invalid tickers
5. **Extreme Volatility**: Test during high volatility periods
6. **Data Source Conflicts**: When sources report different prices >1%

### 5.2 Error Injection Testing
```python
class ErrorInjector:
    def __init__(self):
        self.error_scenarios = {
            'network_timeout': lambda: time.sleep(30),
            'invalid_response': lambda: {"error": "Invalid API key"},
            'rate_limit': lambda: {"error": "Rate limit exceeded"},
            'stale_data': lambda: self._generate_stale_data()
        }
    
    def inject_error(self, scenario):
        """Inject specific error scenario for testing"""
        if scenario in self.error_scenarios:
            return self.error_scenarios[scenario]()
```

## 6. Automated Test Suite

### 6.1 Unit Tests
```python
# test_tool_validation.py
import unittest
from datetime import datetime, timedelta

class TestToolValidation(unittest.TestCase):
    def test_data_freshness_valid(self):
        validator = DataFreshnessValidator(max_age_minutes=5)
        current = datetime.now()
        fresh_time = (current - timedelta(minutes=3)).isoformat()
        self.assertTrue(validator.validate_timestamp(fresh_time, current))
    
    def test_data_freshness_stale(self):
        validator = DataFreshnessValidator(max_age_minutes=5)
        current = datetime.now()
        stale_time = (current - timedelta(minutes=10)).isoformat()
        self.assertFalse(validator.validate_timestamp(stale_time, current))
    
    def test_price_accuracy_within_tolerance(self):
        checker = PriceAccuracyChecker(tolerance_pct=1.0)
        valid, msg = checker.validate_price('BTC-USD', 119500, 120000)
        self.assertTrue(valid)
    
    def test_price_accuracy_outside_tolerance(self):
        checker = PriceAccuracyChecker(tolerance_pct=1.0)
        valid, msg = checker.validate_price('BTC-USD', 60000, 120000)
        self.assertFalse(valid)
```

### 6.2 Integration Tests
```python
# test_integration.py
def test_full_prediction_flow():
    """Test complete prediction flow with validation"""
    
    # Initialize test components
    tool_logger = ToolCallLogger()
    freshness_validator = DataFreshnessValidator()
    price_checker = PriceAccuracyChecker()
    
    # Mock API response with tool calls
    mock_response = create_mock_grok_response_with_tools()
    
    # Validate tool calls were made
    assert len(tool_logger.calls) > 0
    assert 'web_search' in [c['tool'] for c in tool_logger.calls]
    assert 'browse_page' in [c['tool'] for c in tool_logger.calls]
    
    # Validate data freshness
    for call in tool_logger.calls:
        if 'timestamp' in call['response']:
            assert freshness_validator.validate_timestamp(
                call['response']['timestamp'],
                datetime.now()
            )
    
    # Validate prices
    extracted_prices = extract_prices_from_response(mock_response)
    live_prices = fetch_live_prices(extracted_prices.keys())
    
    for symbol, ai_price in extracted_prices.items():
        valid, msg = price_checker.validate_price(
            symbol, ai_price, live_prices[symbol]
        )
        assert valid, f"Price validation failed for {symbol}: {msg}"
```

## 7. Monitoring and Logging

### 7.1 Production Monitoring
```python
# monitoring.py
class ProductionMonitor:
    def __init__(self):
        self.metrics = {
            'tool_calls_per_request': [],
            'data_freshness_scores': [],
            'price_accuracy_scores': [],
            'hallucination_detections': []
        }
    
    def log_request(self, request_id, metrics):
        """Log metrics for each prediction request"""
        self.metrics['tool_calls_per_request'].append(
            metrics['tool_call_count']
        )
        self.metrics['data_freshness_scores'].append(
            metrics['freshness_score']
        )
        # ... etc
    
    def get_dashboard_metrics(self):
        """Get aggregated metrics for dashboard"""
        return {
            'avg_tool_calls': np.mean(self.metrics['tool_calls_per_request']),
            'data_freshness_rate': np.mean(self.metrics['data_freshness_scores']),
            'price_accuracy_rate': np.mean(self.metrics['price_accuracy_scores']),
            'hallucination_rate': sum(self.metrics['hallucination_detections']) / len(self.metrics['hallucination_detections'])
        }
```

### 7.2 Alert System
```python
class ValidationAlertSystem:
    def __init__(self, thresholds):
        self.thresholds = thresholds
        
    def check_alerts(self, metrics):
        alerts = []
        
        if metrics['hallucination_rate'] > self.thresholds['max_hallucination_rate']:
            alerts.append({
                'level': 'CRITICAL',
                'message': f"High hallucination rate: {metrics['hallucination_rate']:.2%}"
            })
        
        if metrics['data_freshness_rate'] < self.thresholds['min_freshness_rate']:
            alerts.append({
                'level': 'WARNING',
                'message': f"Low data freshness: {metrics['data_freshness_rate']:.2%}"
            })
        
        return alerts
```

## 8. Testing Checklist

### Pre-Deployment Testing
- [ ] Verify all tool calls are logged and traceable
- [ ] Confirm BTC price shows ~$120k range (December 2024)
- [ ] Validate all timestamps are within 5 minutes
- [ ] Check date filters in all web_search queries
- [ ] Verify price consistency across sources (±1%)
- [ ] Test error handling for all edge cases
- [ ] Run full integration test suite
- [ ] Validate monitoring and alerting systems

### Post-Deployment Monitoring
- [ ] Monitor tool call patterns in production
- [ ] Track data freshness metrics
- [ ] Alert on price accuracy degradation
- [ ] Log and investigate any hallucination detections
- [ ] Regular validation of live predictions
- [ ] Performance metrics tracking

## 9. Success Criteria

1. **Tool Calling**: 100% of predictions must show explicit tool usage
2. **Data Freshness**: >95% of data points must be ≤5 minutes old
3. **Price Accuracy**: >98% of prices within 1% of live market data
4. **No Hallucinations**: 0% tolerance for using outdated/internal prices
5. **Error Handling**: Graceful handling of all error scenarios
6. **Performance**: Tool calls complete within reasonable time limits

## 10. Continuous Improvement

1. **Weekly Reviews**: Analyze tool usage patterns and accuracy metrics
2. **A/B Testing**: Compare different prompt variations for better results
3. **Feedback Loop**: Incorporate user reports of inaccurate data
4. **Model Updates**: Adjust prompts based on testing results
5. **Tool Optimization**: Improve tool response times and reliability