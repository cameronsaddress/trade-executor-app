"""
Streamlit integration for real-time validation of tool-calling implementation
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime
from test_validators import ValidationOrchestrator, create_mock_grok_response_with_tools


def add_validation_dashboard():
    """Add validation dashboard to Streamlit app"""
    
    # Initialize validation orchestrator in session state
    if 'validation_orchestrator' not in st.session_state:
        st.session_state.validation_orchestrator = ValidationOrchestrator()
    
    # Add validation sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Validation Dashboard")
    
    # Toggle test mode
    test_mode = st.sidebar.checkbox("Enable Validation Mode", value=False)
    
    if test_mode:
        # Show validation controls
        st.sidebar.markdown("#### Validation Controls")
        
        # Manual validation trigger
        if st.sidebar.button("🧪 Run Manual Validation"):
            run_manual_validation()
        
        # Mock response test
        if st.sidebar.button("🔬 Test Mock Response"):
            test_mock_response()
        
        # Show current validation metrics
        show_validation_metrics()
        
        # Show validation history
        show_validation_history()


def run_manual_validation():
    """Run manual validation on current session data"""
    
    orchestrator = st.session_state.validation_orchestrator
    
    # Get current response and recommendations
    response = st.session_state.get('report', '') + st.session_state.get('summary', '')
    recommendations = st.session_state.get('recommendations', None)
    
    if not response and recommendations is None:
        st.sidebar.warning("No data to validate. Generate predictions first.")
        return
    
    # Run validation
    with st.spinner("Running validation..."):
        results = orchestrator.validate_prediction_response(response, recommendations)
        
        # Store results
        if 'validation_results' not in st.session_state:
            st.session_state.validation_results = []
        
        st.session_state.validation_results.append(results)
        
        # Show results
        display_validation_results(results)


def test_mock_response():
    """Test validation with mock response"""
    
    orchestrator = ValidationOrchestrator()
    
    # Create mock response
    mock_response = create_mock_grok_response_with_tools()
    response_text = mock_response['choices'][0]['message']['content']
    
    # Log mock tool calls
    for tool_call in mock_response['choices'][0]['message']['tool_calls']:
        orchestrator.tool_logger.log_call(
            tool_call['id'],
            tool_call['function']['name'],
            json.loads(tool_call['function']['arguments']),
            {'status': 'success', 'timestamp': datetime.now().isoformat()}
        )
    
    # Create mock recommendations
    mock_recommendations = pd.DataFrame({
        'Symbol/Pair': ['BTC-USD', 'ETH-USD'],
        'Action (Buy/Sell)': ['Buy', 'Buy'],
        'Entry Price': [119856.45, 3987.23],
        'Target Price': [125000.00, 4250.00],
        'Stop Loss': [117000.00, 3850.00]
    })
    
    # Run validation
    results = orchestrator.validate_prediction_response(response_text, mock_recommendations)
    
    # Display results
    display_validation_results(results, title="Mock Response Validation")


def display_validation_results(results, title="Validation Results"):
    """Display validation results in Streamlit"""
    
    st.markdown(f"### {title}")
    
    # Overall status
    status_color = "green" if results['overall_valid'] else "red"
    status_text = "✅ VALID" if results['overall_valid'] else "❌ INVALID"
    st.markdown(f"**Status:** :{status_color}[{status_text}]")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Tools Called", results['summary']['tools_called'])
    
    with col2:
        accuracy = results['summary']['price_accuracy_rate']
        st.metric("Price Accuracy", f"{accuracy:.1%}")
    
    with col3:
        st.metric("Hallucinations", results['summary']['hallucination_count'])
    
    with col4:
        st.metric("Critical Issues", results['summary']['critical_issues'])
    
    # Detailed sections
    tabs = st.tabs(["Tool Usage", "Price Validation", "Hallucination Check", "Raw Data"])
    
    with tabs[0]:
        st.markdown("#### Tool Usage Report")
        if results['tool_usage']['total_calls'] > 0:
            st.success(f"✅ {results['tool_usage']['total_calls']} tool calls detected")
            st.write("**Tools Used:**", ", ".join(results['tool_usage']['tools_used']))
            
            if results['tool_usage']['data_sources']:
                st.write("**Data Sources:**")
                for source in results['tool_usage']['data_sources']:
                    st.write(f"- {source}")
        else:
            st.error("❌ No tool calls detected - potential hallucination!")
    
    with tabs[1]:
        st.markdown("#### Price Validation Details")
        if results['price_accuracy']['checks']:
            for check in results['price_accuracy']['checks']:
                status = "✅" if check['valid'] else "❌"
                st.write(f"{status} **{check['symbol']}**: {check['message']}")
        else:
            st.info("No price validations performed")
    
    with tabs[2]:
        st.markdown("#### Hallucination Detection")
        if results['hallucinations']:
            for hallucination in results['hallucinations']:
                severity_color = "red" if hallucination['severity'] == 'critical' else "orange"
                st.markdown(f":{severity_color}[{hallucination['severity'].upper()}] **{hallucination['type']}**: {hallucination.get('detail', hallucination.get('indicator'))}")
        else:
            st.success("✅ No hallucinations detected")
    
    with tabs[3]:
        st.markdown("#### Raw Validation Data")
        st.json(results)


def show_validation_metrics():
    """Show current validation metrics"""
    
    if 'validation_results' not in st.session_state or not st.session_state.validation_results:
        st.sidebar.info("No validation history available")
        return
    
    # Calculate aggregate metrics
    results_list = st.session_state.validation_results
    
    total_validations = len(results_list)
    valid_count = sum(1 for r in results_list if r['overall_valid'])
    avg_tool_calls = sum(r['summary']['tools_called'] for r in results_list) / total_validations
    avg_accuracy = sum(r['summary']['price_accuracy_rate'] for r in results_list) / total_validations
    
    st.sidebar.markdown("#### Current Metrics")
    st.sidebar.metric("Success Rate", f"{valid_count/total_validations:.1%}")
    st.sidebar.metric("Avg Tool Calls", f"{avg_tool_calls:.1f}")
    st.sidebar.metric("Avg Price Accuracy", f"{avg_accuracy:.1%}")


def show_validation_history():
    """Show validation history"""
    
    if 'validation_results' not in st.session_state or not st.session_state.validation_results:
        return
    
    with st.sidebar.expander("📊 Validation History"):
        history_df = pd.DataFrame([
            {
                'Timestamp': r['timestamp'],
                'Valid': '✅' if r['overall_valid'] else '❌',
                'Tools': r['summary']['tools_called'],
                'Accuracy': f"{r['summary']['price_accuracy_rate']:.1%}",
                'Issues': r['summary']['hallucination_count']
            }
            for r in st.session_state.validation_results[-10:]  # Last 10 validations
        ])
        
        st.dataframe(history_df, use_container_width=True)


def create_price_monitoring_widget():
    """Create a widget to monitor live prices vs AI predictions"""
    
    st.markdown("### 📈 Live Price Monitoring")
    
    if st.session_state.get('recommendations') is not None:
        df = st.session_state.recommendations
        
        # Add real-time price validation
        if st.button("🔄 Validate Current Prices"):
            with st.spinner("Fetching live prices..."):
                orchestrator = ValidationOrchestrator()
                
                validation_results = []
                for _, row in df.iterrows():
                    symbol = row['Symbol/Pair']
                    if pd.notna(row.get('Entry Price')):
                        ai_price = float(row['Entry Price'])
                        
                        # Validate against live price
                        valid, msg = orchestrator.price_checker.validate_price(symbol, ai_price)
                        validation_results.append({
                            'Symbol': symbol,
                            'AI Price': f"${ai_price:.2f}",
                            'Status': '✅' if valid else '❌',
                            'Details': msg
                        })
                
                # Display results
                validation_df = pd.DataFrame(validation_results)
                st.dataframe(validation_df, use_container_width=True)
                
                # Show summary
                valid_count = sum(1 for r in validation_results if r['Status'] == '✅')
                total_count = len(validation_results)
                
                if valid_count == total_count:
                    st.success(f"✅ All {total_count} prices validated successfully!")
                else:
                    st.warning(f"⚠️ {valid_count}/{total_count} prices validated. Check flagged items.")


def add_continuous_monitoring():
    """Add continuous monitoring capabilities"""
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔄 Continuous Monitoring")
    
    # Auto-validation toggle
    auto_validate = st.sidebar.checkbox("Auto-validate predictions", value=False)
    
    if auto_validate:
        # Set up auto-validation
        if 'auto_validation_interval' not in st.session_state:
            st.session_state.auto_validation_interval = 60  # 1 minute
        
        interval = st.sidebar.slider("Validation Interval (seconds)", 30, 300, 60)
        st.session_state.auto_validation_interval = interval
        
        # Status indicator
        st.sidebar.success("🟢 Auto-validation enabled")
        
        # Last validation time
        if 'last_validation' in st.session_state:
            last_time = st.session_state.last_validation
            st.sidebar.info(f"Last validation: {last_time}")
    
    # Manual refresh
    if st.sidebar.button("🔄 Refresh Validation"):
        st.session_state.last_validation = datetime.now().strftime("%H:%M:%S")
        st.rerun()


def create_validation_alerts():
    """Create alert system for validation issues"""
    
    if 'validation_results' not in st.session_state:
        return
    
    # Check latest validation results
    latest_results = st.session_state.validation_results[-1] if st.session_state.validation_results else None
    
    if latest_results and not latest_results['overall_valid']:
        # Show alert for invalid results
        st.error("🚨 **Validation Alert**: Latest predictions failed validation!")
        
        # Show specific issues
        if latest_results['summary']['critical_issues'] > 0:
            st.error(f"Critical issues detected: {latest_results['summary']['critical_issues']}")
        
        if latest_results['summary']['tools_called'] == 0:
            st.error("No tool calls detected - AI may be hallucinating!")
        
        if latest_results['summary']['price_accuracy_rate'] < 0.9:
            st.warning(f"Low price accuracy: {latest_results['summary']['price_accuracy_rate']:.1%}")


# Integration function to add to main app
def integrate_validation_system():
    """
    Main integration function to add validation system to Streamlit app
    Call this in your main app.py file
    """
    
    # Add validation dashboard
    add_validation_dashboard()
    
    # Add price monitoring widget
    create_price_monitoring_widget()
    
    # Add continuous monitoring
    add_continuous_monitoring()
    
    # Show validation alerts
    create_validation_alerts()
    
    # Add CSS for validation styling
    st.markdown("""
    <style>
    .validation-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .validation-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .validation-warning {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 10px;
        border-radius: 4px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    # Test the validation dashboard
    st.title("Validation Dashboard Test")
    
    # Initialize session state
    if 'recommendations' not in st.session_state:
        st.session_state.recommendations = pd.DataFrame({
            'Symbol/Pair': ['BTC-USD', 'ETH-USD'],
            'Action (Buy/Sell)': ['Buy', 'Buy'],
            'Entry Price': [119800, 3990],
            'Target Price': [125000, 4200],
            'Stop Loss': [117000, 3850]
        })
    
    # Run integration
    integrate_validation_system()