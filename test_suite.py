"""
Comprehensive test suite for tool-calling validation
"""
import unittest
import pandas as pd
import json
from datetime import datetime, timedelta
from test_validators import (
    ToolCallLogger,
    DataFreshnessValidator,
    PriceAccuracyChecker,
    HallucinationDetector,
    ValidationOrchestrator,
    create_mock_grok_response_with_tools,
    MOCK_TOOL_RESPONSES
)


class TestToolCallLogger(unittest.TestCase):
    """Test tool call logging functionality"""
    
    def setUp(self):
        self.logger = ToolCallLogger()
        
    def test_log_single_call(self):
        """Test logging a single tool call"""
        self.logger.log_call(
            'call_001',
            'web_search',
            {'query': 'BTC price today'},
            {'results': [{'title': 'BTC Price', 'url': 'example.com'}]}
        )
        
        report = self.logger.get_tool_usage_report()
        self.assertEqual(report['total_calls'], 1)
        self.assertEqual(report['tools_used'], ['web_search'])
        self.assertEqual(len(report['data_sources']), 1)
        
    def test_multiple_tool_calls(self):
        """Test logging multiple tool calls"""
        calls = [
            ('call_001', 'web_search', {'query': 'BTC price'}, {'results': []}),
            ('call_002', 'browse_page', {'url': 'example.com'}, {'content': 'page content'}),
            ('call_003', 'web_search', {'query': 'ETH price'}, {'results': []})
        ]
        
        for call_id, tool, params, response in calls:
            self.logger.log_call(call_id, tool, params, response)
            
        report = self.logger.get_tool_usage_report()
        self.assertEqual(report['total_calls'], 3)
        self.assertEqual(set(report['tools_used']), {'web_search', 'browse_page'})
        
    def test_timing_measurement(self):
        """Test that timing is measured correctly"""
        self.logger.start_call('call_001', 'web_search', {'query': 'test'})
        import time
        time.sleep(0.1)  # 100ms delay
        self.logger.log_call('call_001', 'web_search', {'query': 'test'}, {'results': []})
        
        report = self.logger.get_tool_usage_report()
        self.assertGreater(report['avg_response_time'], 90)  # Should be ~100ms


class TestDataFreshnessValidator(unittest.TestCase):
    """Test data freshness validation"""
    
    def setUp(self):
        self.validator = DataFreshnessValidator(max_age_minutes=5)
        
    def test_fresh_timestamp_valid(self):
        """Test that fresh timestamps are valid"""
        current = datetime.now()
        fresh_time = (current - timedelta(minutes=3)).isoformat()
        self.assertTrue(self.validator.validate_timestamp(fresh_time, current))
        
    def test_stale_timestamp_invalid(self):
        """Test that stale timestamps are invalid"""
        current = datetime.now()
        stale_time = (current - timedelta(minutes=10)).isoformat()
        self.assertFalse(self.validator.validate_timestamp(stale_time, current))
        
    def test_search_query_validation(self):
        """Test search query date filter validation"""
        current_date = "2024-12-18"
        next_day = "2024-12-19"
        
        # Valid query
        valid_query = f"BTC price after:{current_date} before:{next_day}"
        valid, msg = self.validator.validate_search_query(valid_query, current_date)
        self.assertTrue(valid)
        
        # Invalid query (missing date filters)
        invalid_query = "BTC price today"
        valid, msg = self.validator.validate_search_query(invalid_query, current_date)
        self.assertFalse(valid)
        
    def test_various_timestamp_formats(self):
        """Test parsing various timestamp formats"""
        current = datetime.now()
        
        # ISO format
        iso_time = (current - timedelta(minutes=2)).isoformat()
        self.assertTrue(self.validator.validate_timestamp(iso_time, current))
        
        # UTC format
        utc_time = (current - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(self.validator.validate_timestamp(utc_time, current))
        
        # Standard format
        std_time = (current - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        self.assertTrue(self.validator.validate_timestamp(std_time, current))


class TestPriceAccuracyChecker(unittest.TestCase):
    """Test price accuracy validation"""
    
    def setUp(self):
        self.checker = PriceAccuracyChecker(tolerance_pct=1.0)
        
    def test_price_within_tolerance(self):
        """Test that prices within tolerance are valid"""
        valid, msg = self.checker.validate_price('BTC-USD', 119500, 120000)
        self.assertTrue(valid)
        self.assertIn("within tolerance", msg)
        
    def test_price_outside_tolerance(self):
        """Test that prices outside tolerance are invalid"""
        valid, msg = self.checker.validate_price('BTC-USD', 60000, 120000)
        self.assertFalse(valid)
        self.assertIn("too large", msg)
        
    def test_price_range_validation(self):
        """Test price range validation"""
        ranges = {'BTC-USD': (115000, 125000)}
        
        # Valid price
        valid, msg = self.checker.validate_price_range('BTC-USD', 120000, ranges)
        self.assertTrue(valid)
        
        # Invalid price (too low)
        valid, msg = self.checker.validate_price_range('BTC-USD', 60000, ranges)
        self.assertFalse(valid)
        
        # Invalid price (too high)
        valid, msg = self.checker.validate_price_range('BTC-USD', 200000, ranges)
        self.assertFalse(valid)
        
    def test_zero_price_handling(self):
        """Test handling of zero prices"""
        valid, msg = self.checker.validate_price('BTC-USD', 120000, 0)
        self.assertFalse(valid)
        self.assertIn("Invalid live price", msg)


class TestHallucinationDetector(unittest.TestCase):
    """Test hallucination detection"""
    
    def setUp(self):
        self.detector = HallucinationDetector()
        self.logger = ToolCallLogger()
        
    def test_outdated_language_detection(self):
        """Test detection of outdated language"""
        response = "As of my last update, BTC was trading around $60,000"
        issues = self.detector.check_for_hallucinations(response, self.logger)
        
        # Should detect outdated language
        outdated_issues = [i for i in issues if i['type'] == 'outdated_language']
        self.assertGreater(len(outdated_issues), 0)
        
    def test_uncited_data_detection(self):
        """Test detection of uncited data"""
        response = "Bitcoin is trading at $120,000 and Ethereum at $4,000"
        # No tool calls logged
        issues = self.detector.check_for_hallucinations(response, self.logger)
        
        # Should detect uncited data
        uncited_issues = [i for i in issues if i['type'] == 'uncited_data']
        self.assertGreater(len(uncited_issues), 0)
        
    def test_outdated_btc_price_detection(self):
        """Test detection of outdated BTC prices"""
        response = "BTC is currently trading at $60,000"
        issues = self.detector.check_for_hallucinations(response, self.logger)
        
        # Should detect outdated price
        price_issues = [i for i in issues if i['type'] == 'outdated_price']
        self.assertGreater(len(price_issues), 0)
        
    def test_clean_response_no_issues(self):
        """Test that clean responses don't trigger false positives"""
        response = "Based on real-time tool calls, current market conditions show..."
        
        # Log some tool calls
        self.logger.log_call('call_001', 'web_search', {}, {})
        
        issues = self.detector.check_for_hallucinations(response, self.logger)
        self.assertEqual(len(issues), 0)


class TestValidationOrchestrator(unittest.TestCase):
    """Test the full validation orchestration"""
    
    def setUp(self):
        self.orchestrator = ValidationOrchestrator()
        
    def test_complete_validation_pass(self):
        """Test a complete validation that should pass"""
        # Create mock recommendations
        recommendations = pd.DataFrame({
            'Symbol/Pair': ['BTC-USD', 'ETH-USD'],
            'Action (Buy/Sell)': ['Buy', 'Buy'],
            'Entry Price': [119800, 3990],
            'Target Price': [125000, 4200],
            'Stop Loss': [117000, 3850]
        })
        
        # Mock tool calls
        self.orchestrator.tool_logger.log_call(
            'call_001', 'web_search', 
            {'query': 'BTC price after:2024-12-18 before:2024-12-19'}, 
            {'results': [{'url': 'example.com'}]}
        )
        
        response = "Based on verified tool calls, current analysis shows BTC at $119,800"
        
        # Run validation
        results = self.orchestrator.validate_prediction_response(response, recommendations)
        
        # Should have tool usage
        self.assertGreater(results['tool_usage']['total_calls'], 0)
        
        # Should have price checks
        self.assertGreater(len(results['price_accuracy']['checks']), 0)
        
    def test_validation_with_hallucinations(self):
        """Test validation that detects hallucinations"""
        recommendations = pd.DataFrame({
            'Symbol/Pair': ['BTC-USD'],
            'Action (Buy/Sell)': ['Buy'],
            'Entry Price': [60000],  # Outdated price
            'Target Price': [65000],
            'Stop Loss': [58000]
        })
        
        response = "As of my last update, BTC is around $60,000"
        
        # No tool calls logged
        results = self.orchestrator.validate_prediction_response(response, recommendations)
        
        # Should detect issues
        self.assertGreater(len(results['hallucinations']), 0)
        self.assertFalse(results['overall_valid'])
        
    def test_report_generation(self):
        """Test generation of validation report"""
        # Create validation results
        results = {
            'timestamp': datetime.now().isoformat(),
            'tool_usage': {'total_calls': 3, 'tools_used': ['web_search', 'browse_page'], 'data_sources': []},
            'price_accuracy': {'valid': 2, 'invalid': 0, 'checks': []},
            'hallucinations': [],
            'overall_valid': True,
            'summary': {
                'tools_called': 3,
                'price_accuracy_rate': 1.0,
                'hallucination_count': 0,
                'critical_issues': 0
            }
        }
        
        report = self.orchestrator.generate_test_report(results)
        
        # Should contain key sections
        self.assertIn('Validation Report', report)
        self.assertIn('Overall Valid: ✅ PASS', report)
        self.assertIn('Tools Called: 3', report)
        self.assertIn('Price Accuracy: 100.0%', report)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete flow"""
    
    def test_mock_response_validation(self):
        """Test validation of mock Grok response"""
        orchestrator = ValidationOrchestrator()
        
        # Get mock response
        mock_response = create_mock_grok_response_with_tools()
        response_text = mock_response['choices'][0]['message']['content']
        
        # Log the tool calls from the mock response
        for tool_call in mock_response['choices'][0]['message']['tool_calls']:
            orchestrator.tool_logger.log_call(
                tool_call['id'],
                tool_call['function']['name'],
                json.loads(tool_call['function']['arguments']),
                MOCK_TOOL_RESPONSES.get(tool_call['function']['name'], {})
            )
        
        # Extract recommendations table
        table_start = response_text.find('|')
        table_end = response_text.rfind('|') + 1
        table_content = response_text[table_start:table_end]
        
        # Parse into DataFrame (simplified)
        lines = table_content.split('\n')
        data_lines = [line for line in lines[2:] if line.strip()]
        
        recommendations = pd.DataFrame({
            'Symbol/Pair': ['BTC-USD', 'ETH-USD'],
            'Action (Buy/Sell)': ['Buy', 'Buy'],
            'Entry Price': [119856.45, 3987.23],
            'Target Price': [125000.00, 4250.00],
            'Stop Loss': [117000.00, 3850.00]
        })
        
        # Run validation
        results = orchestrator.validate_prediction_response(response_text, recommendations)
        
        # Should have tool usage
        self.assertGreater(results['tool_usage']['total_calls'], 0)
        self.assertIn('web_search', results['tool_usage']['tools_used'])
        
        # Should have price validations
        self.assertGreater(len(results['price_accuracy']['checks']), 0)
        
        # Generate report
        report = orchestrator.generate_test_report(results)
        self.assertIn('Validation Report', report)
        
    def test_edge_case_empty_response(self):
        """Test handling of empty or invalid responses"""
        orchestrator = ValidationOrchestrator()
        
        # Empty response
        results = orchestrator.validate_prediction_response("", None)
        self.assertEqual(results['tool_usage']['total_calls'], 0)
        
        # Response with no table
        results = orchestrator.validate_prediction_response("No recommendations available", None)
        self.assertEqual(len(results['price_accuracy']['checks']), 0)


def run_specific_tests():
    """Run specific test scenarios"""
    
    print("Running Tool-Calling Validation Tests...")
    print("=" * 50)
    
    # Test 1: Tool Call Detection
    print("\n1. Testing Tool Call Detection...")
    orchestrator = ValidationOrchestrator()
    
    # Simulate response with no tool calls
    bad_response = "BTC is trading at $120,000 based on my analysis"
    results = orchestrator.validate_prediction_response(bad_response, None)
    
    if results['tool_usage']['total_calls'] == 0:
        print("✅ Correctly detected missing tool calls")
    else:
        print("❌ Failed to detect missing tool calls")
    
    # Test 2: Price Accuracy Check
    print("\n2. Testing Price Accuracy...")
    checker = PriceAccuracyChecker(tolerance_pct=1.0)
    
    # Test with expected current BTC price
    valid, msg = checker.validate_price('BTC-USD', 119500, 120000)
    if valid:
        print(f"✅ Price accuracy check passed: {msg}")
    else:
        print(f"❌ Price accuracy check failed: {msg}")
    
    # Test with outdated price
    valid, msg = checker.validate_price('BTC-USD', 60000, 120000)
    if not valid:
        print(f"✅ Correctly detected outdated price: {msg}")
    else:
        print(f"❌ Failed to detect outdated price: {msg}")
    
    # Test 3: Hallucination Detection
    print("\n3. Testing Hallucination Detection...")
    detector = HallucinationDetector()
    logger = ToolCallLogger()
    
    # Test with hallucinated response
    hallucinated_response = "As of my last update, BTC was around $60,000"
    issues = detector.check_for_hallucinations(hallucinated_response, logger)
    
    if len(issues) > 0:
        print(f"✅ Detected {len(issues)} potential hallucinations")
        for issue in issues:
            print(f"   - {issue['type']}: {issue.get('detail', issue.get('indicator'))}")
    else:
        print("❌ Failed to detect hallucinations")
    
    # Test 4: Data Freshness
    print("\n4. Testing Data Freshness...")
    validator = DataFreshnessValidator(max_age_minutes=5)
    
    # Fresh timestamp
    fresh_time = datetime.now().isoformat()
    if validator.validate_timestamp(fresh_time):
        print("✅ Fresh timestamp validation passed")
    else:
        print("❌ Fresh timestamp validation failed")
    
    # Stale timestamp
    stale_time = (datetime.now() - timedelta(minutes=10)).isoformat()
    if not validator.validate_timestamp(stale_time):
        print("✅ Stale timestamp correctly rejected")
    else:
        print("❌ Stale timestamp incorrectly accepted")
    
    print("\n" + "=" * 50)
    print("Test Summary Complete")


if __name__ == '__main__':
    # Run specific tests first
    run_specific_tests()
    
    # Run full test suite
    print("\n\nRunning Full Test Suite...")
    unittest.main(verbosity=2)