"""
Validation classes for testing tool-calling implementation
"""
import datetime
import json
import time
from typing import Dict, List, Tuple, Any
import pandas as pd
import yfinance as yf


class ToolCallLogger:
    """Logs and tracks all tool calls made by the AI"""
    
    def __init__(self):
        self.calls = []
        self.start_times = {}
        
    def start_call(self, call_id: str, tool_name: str, params: Dict):
        """Log the start of a tool call"""
        self.start_times[call_id] = time.time()
        
    def log_call(self, call_id: str, tool_name: str, params: Dict, response: Any):
        """Log a completed tool call"""
        duration_ms = None
        if call_id in self.start_times:
            duration_ms = (time.time() - self.start_times[call_id]) * 1000
            del self.start_times[call_id]
            
        self.calls.append({
            'call_id': call_id,
            'tool': tool_name,
            'params': params,
            'response': response,
            'timestamp': datetime.datetime.now().isoformat(),
            'duration_ms': duration_ms
        })
        
    def get_tool_usage_report(self) -> Dict:
        """Generate a report of tool usage"""
        if not self.calls:
            return {
                'total_calls': 0,
                'tools_used': [],
                'avg_response_time': 0,
                'data_sources': []
            }
            
        tools_used = list(set(c['tool'] for c in self.calls))
        avg_time = sum(c['duration_ms'] for c in self.calls if c['duration_ms']) / len(self.calls)
        
        # Extract data sources from responses
        data_sources = []
        for call in self.calls:
            if call['tool'] == 'browse_page' and 'params' in call:
                data_sources.append(call['params'].get('url', ''))
            elif call['tool'] == 'web_search' and 'response' in call:
                # Extract URLs from search results
                if isinstance(call['response'], dict) and 'results' in call['response']:
                    for result in call['response']['results']:
                        data_sources.append(result.get('url', ''))
                        
        return {
            'total_calls': len(self.calls),
            'tools_used': tools_used,
            'avg_response_time': avg_time,
            'data_sources': list(set(data_sources)),
            'call_details': self.calls
        }


class DataFreshnessValidator:
    """Validates that data is fresh and from current date"""
    
    def __init__(self, max_age_minutes: int = 5):
        self.max_age_minutes = max_age_minutes
        
    def validate_timestamp(self, timestamp_str: str, current_time: datetime.datetime = None) -> bool:
        """Validate data timestamp is within acceptable range"""
        if current_time is None:
            current_time = datetime.datetime.now()
            
        try:
            # Handle various timestamp formats
            if 'T' in timestamp_str:
                data_time = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Try parsing other formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%B %d, %Y %H:%M:%S']:
                    try:
                        data_time = datetime.datetime.strptime(timestamp_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return False
                    
            # Convert to timezone-naive for comparison
            if data_time.tzinfo:
                data_time = data_time.replace(tzinfo=None)
            if current_time.tzinfo:
                current_time = current_time.replace(tzinfo=None)
                
            age_minutes = (current_time - data_time).total_seconds() / 60
            return age_minutes <= self.max_age_minutes
            
        except Exception as e:
            print(f"Error parsing timestamp {timestamp_str}: {e}")
            return False
            
    def validate_search_query(self, query: str, current_date: str = None) -> Tuple[bool, str]:
        """Ensure search queries have proper date filters"""
        if current_date is None:
            current_date = datetime.date.today().strftime("%Y-%m-%d")
            
        has_after = f"after:{current_date}" in query
        next_day = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        has_before = f"before:{next_day}" in query or "before:" in query
        
        if has_after and has_before:
            return True, "Query has proper date filters"
        elif has_after:
            return False, "Query missing 'before' date filter"
        elif has_before:
            return False, "Query missing 'after' date filter"
        else:
            return False, "Query missing both date filters"


class PriceAccuracyChecker:
    """Validates AI-reported prices against live market data"""
    
    def __init__(self, tolerance_pct: float = 1.0):
        self.tolerance_pct = tolerance_pct
        
    def validate_price(self, symbol: str, ai_price: float, live_price: float = None) -> Tuple[bool, str]:
        """Compare AI-reported price with live market data"""
        if live_price is None:
            # Fetch live price
            try:
                live_price = self.fetch_live_price(symbol)
            except Exception as e:
                return False, f"Could not fetch live price: {e}"
                
        if live_price == 0:
            return False, "Invalid live price (0)"
            
        diff_pct = abs(ai_price - live_price) / live_price * 100
        
        if diff_pct <= self.tolerance_pct:
            return True, f"Price within tolerance: {diff_pct:.2f}% (AI: ${ai_price:.2f}, Live: ${live_price:.2f})"
        else:
            return False, f"Price difference too large: {diff_pct:.2f}% (AI: ${ai_price:.2f}, Live: ${live_price:.2f})"
            
    def fetch_live_price(self, symbol: str) -> float:
        """Fetch current live price for symbol"""
        # Handle forex pairs
        if '/' in symbol:
            symbol = symbol.replace('/', '') + '=X'
            
        data = yf.download(symbol, period='1d', interval='1m', progress=False)
        if data.empty:
            raise ValueError(f"No data available for {symbol}")
            
        return float(data['Close'].iloc[-1])
        
    def validate_price_range(self, symbol: str, ai_price: float, expected_ranges: Dict[str, Tuple[float, float]]) -> Tuple[bool, str]:
        """Validate price is within expected range"""
        if symbol not in expected_ranges:
            return True, "No expected range defined"
            
        min_price, max_price = expected_ranges[symbol]
        
        if min_price <= ai_price <= max_price:
            return True, f"Price ${ai_price:.2f} within expected range ${min_price}-${max_price}"
        else:
            return False, f"Price ${ai_price:.2f} outside expected range ${min_price}-${max_price}"


class HallucinationDetector:
    """Detects potential hallucinations in AI responses"""
    
    def __init__(self):
        self.outdated_indicators = [
            "As of my last update",
            "Based on my training data",
            "historically",
            "typically",
            "usually around",
            "approximately",
            "last known"
        ]
        
    def check_for_hallucinations(self, response_text: str, tool_logger: ToolCallLogger) -> List[Dict]:
        """Check response for potential hallucinations"""
        issues = []
        
        # Check for outdated language
        for indicator in self.outdated_indicators:
            if indicator.lower() in response_text.lower():
                issues.append({
                    'type': 'outdated_language',
                    'indicator': indicator,
                    'severity': 'warning'
                })
                
        # Check if data points have tool citations
        # Look for prices in text
        import re
        price_pattern = r'\$[\d,]+\.?\d*'
        prices_found = re.findall(price_pattern, response_text)
        
        if prices_found and tool_logger.get_tool_usage_report()['total_calls'] == 0:
            issues.append({
                'type': 'uncited_data',
                'detail': f"Found {len(prices_found)} prices but no tool calls",
                'severity': 'critical'
            })
            
        # Check for specific outdated prices (e.g., BTC at $60k)
        if '$60' in response_text and 'BTC' in response_text:
            issues.append({
                'type': 'outdated_price',
                'detail': 'BTC price appears outdated (~$60k instead of ~$120k)',
                'severity': 'critical'
            })
            
        return issues


class ValidationOrchestrator:
    """Orchestrates all validation checks"""
    
    def __init__(self):
        self.tool_logger = ToolCallLogger()
        self.freshness_validator = DataFreshnessValidator()
        self.price_checker = PriceAccuracyChecker()
        self.hallucination_detector = HallucinationDetector()
        
        # Expected price ranges for December 2024
        self.expected_ranges = {
            'BTC-USD': (115000, 125000),
            'ETH-USD': (3800, 4200),
            'NVDA': (450, 550),
            'TSLA': (380, 420),
            'AAPL': (195, 205),
            'GC=F': (2050, 2150)  # Gold futures
        }
        
    def validate_prediction_response(self, response: str, recommendations_df: pd.DataFrame = None) -> Dict:
        """Run all validation checks on a prediction response"""
        results = {
            'timestamp': datetime.datetime.now().isoformat(),
            'tool_usage': self.tool_logger.get_tool_usage_report(),
            'data_freshness': {'valid': 0, 'invalid': 0, 'checks': []},
            'price_accuracy': {'valid': 0, 'invalid': 0, 'checks': []},
            'hallucinations': [],
            'overall_valid': True
        }
        
        # Check for hallucinations
        results['hallucinations'] = self.hallucination_detector.check_for_hallucinations(
            response, self.tool_logger
        )
        
        # Validate prices if recommendations provided
        if recommendations_df is not None:
            for _, row in recommendations_df.iterrows():
                symbol = row['Symbol/Pair']
                if pd.notna(row.get('Entry Price')):
                    ai_price = float(row['Entry Price'])
                    
                    # Check against live price
                    valid, msg = self.price_checker.validate_price(symbol, ai_price)
                    results['price_accuracy']['checks'].append({
                        'symbol': symbol,
                        'ai_price': ai_price,
                        'valid': valid,
                        'message': msg
                    })
                    
                    if valid:
                        results['price_accuracy']['valid'] += 1
                    else:
                        results['price_accuracy']['invalid'] += 1
                        results['overall_valid'] = False
                        
                    # Check against expected range
                    range_valid, range_msg = self.price_checker.validate_price_range(
                        symbol, ai_price, self.expected_ranges
                    )
                    if not range_valid:
                        results['hallucinations'].append({
                            'type': 'price_out_of_range',
                            'detail': range_msg,
                            'severity': 'warning'
                        })
                        
        # Check for critical hallucinations
        critical_hallucinations = [h for h in results['hallucinations'] if h['severity'] == 'critical']
        if critical_hallucinations:
            results['overall_valid'] = False
            
        # Calculate summary metrics
        total_price_checks = results['price_accuracy']['valid'] + results['price_accuracy']['invalid']
        results['summary'] = {
            'tools_called': results['tool_usage']['total_calls'],
            'price_accuracy_rate': results['price_accuracy']['valid'] / total_price_checks if total_price_checks > 0 else 0,
            'hallucination_count': len(results['hallucinations']),
            'critical_issues': len(critical_hallucinations)
        }
        
        return results
        
    def generate_test_report(self, validation_results: Dict) -> str:
        """Generate a human-readable test report"""
        report = f"""
# Validation Report
Generated: {validation_results['timestamp']}

## Summary
- Overall Valid: {'✅ PASS' if validation_results['overall_valid'] else '❌ FAIL'}
- Tools Called: {validation_results['summary']['tools_called']}
- Price Accuracy: {validation_results['summary']['price_accuracy_rate']:.1%}
- Hallucinations: {validation_results['summary']['hallucination_count']}
- Critical Issues: {validation_results['summary']['critical_issues']}

## Tool Usage
Total Calls: {validation_results['tool_usage']['total_calls']}
Tools Used: {', '.join(validation_results['tool_usage']['tools_used'])}
Data Sources: {len(validation_results['tool_usage']['data_sources'])}

## Price Validation
"""
        for check in validation_results['price_accuracy']['checks']:
            status = "✅" if check['valid'] else "❌"
            report += f"{status} {check['symbol']}: {check['message']}\n"
            
        if validation_results['hallucinations']:
            report += "\n## Potential Hallucinations\n"
            for h in validation_results['hallucinations']:
                report += f"- [{h['severity'].upper()}] {h['type']}: {h.get('detail', h.get('indicator', ''))}\n"
                
        return report


# Mock tool responses for testing
MOCK_TOOL_RESPONSES = {
    'web_search': {
        'BTC price December 2024': {
            'results': [
                {
                    'title': 'Bitcoin Price Hits New High Above $119,000',
                    'url': 'https://www.coindesk.com/price/bitcoin',
                    'snippet': 'Bitcoin (BTC) trading at $119,856.45 as of December 18, 2024, 14:32 UTC',
                    'timestamp': '2024-12-18T14:32:00Z'
                }
            ]
        }
    },
    'browse_page': {
        'https://finance.yahoo.com/quote/BTC-USD': {
            'content': 'Bitcoin USD (BTC-USD) Real-time Price: $119,743.21',
            'timestamp': '2024-12-18T14:33:15Z',
            'extracted_data': {
                'price': 119743.21,
                'change_pct': 2.34,
                'volume': 28456789012,
                'market_cap': 2356789012345
            }
        }
    }
}


def create_mock_grok_response_with_tools() -> Dict:
    """Create a mock Grok API response that includes tool calls"""
    return {
        'choices': [{
            'message': {
                'content': """Based on my real-time analysis using web_search and browse_page tools, here are today's top opportunities:

Tool calls executed:
1. web_search: "top 10 high ROI assets December 18 2024 after:2024-12-18 before:2024-12-19"
2. browse_page: https://www.investing.com/crypto/bitcoin (verified BTC at $119,856.45)
3. browse_page: https://finance.yahoo.com/quote/ETH-USD (verified ETH at $3,987.23)

| Symbol/Pair | Action (Buy/Sell) | Entry Price | Target Price | Stop Loss | Expected Entry Condition/Timing | Expected Exit Condition/Timing | Thesis (≤50 words) | Projected ROI (%) | Likelihood of Profit (%) | Recommended Allocation (% of portfolio) | Plain English Summary (1 sentence) | Data Sources |
|-------------|-------------------|-------------|--------------|-----------|--------------------------------|-------------------------------|-------------------|-------------------|------------------------|--------------------------------------|-----------------------------------|-----------------|
| BTC-USD | Buy | 119856.45 | 125000.00 | 117000.00 | RSI dip below 65 within 2 hours | Target hit or 3 days | Strong momentum above 200 MA, institutional buying surge per on-chain data | 4.29 | 68.5 | 15.0 | Buy Bitcoin on momentum with tight stop loss | investing.com, yahoo finance, glassnode |
| ETH-USD | Buy | 3987.23 | 4250.00 | 3850.00 | Immediate entry on breakout | Target or stop hit | Layer 2 adoption accelerating, deflationary supply dynamics | 6.59 | 71.2 | 12.0 | Ethereum breaking out with strong fundamentals | yahoo finance, etherscan, defillama |""",
                'tool_calls': [
                    {
                        'id': 'call_001',
                        'type': 'function',
                        'function': {
                            'name': 'web_search',
                            'arguments': json.dumps({
                                'query': 'top 10 high ROI assets December 18 2024 after:2024-12-18 before:2024-12-19'
                            })
                        }
                    },
                    {
                        'id': 'call_002',
                        'type': 'function',
                        'function': {
                            'name': 'browse_page',
                            'arguments': json.dumps({
                                'url': 'https://www.investing.com/crypto/bitcoin'
                            })
                        }
                    }
                ]
            }
        }]
    }