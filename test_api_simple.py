#!/usr/bin/env python3
"""
Simple test to verify the API call with enhanced debugging works
"""

import sys
import os

# Add current directory to Python path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import make_single_api_call

def test_simple_api_call():
    """Test a simple API call with the enhanced debugging"""
    
    # Get API key from user
    api_key = input("Enter your xAI API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided")
        return
    
    # Simple test prompt
    test_prompt = "Hello! Please respond with exactly this message: 'API test successful - Grok 4 Heavy is working!'"
    
    print("🧪 Testing API call with enhanced debugging...")
    print(f"Prompt: {test_prompt}")
    print("-" * 50)
    
    # Track status messages
    status_messages = []
    
    def status_callback(message):
        print(f"Status: {message}")
        status_messages.append(message)
    
    try:
        # Make the API call
        result = make_single_api_call(
            api_key=api_key,
            prompt_with_data=test_prompt,
            status_callback=status_callback,
            enable_streaming=False  # Disable streaming for now
        )
        
        print("-" * 50)
        print("✅ API call completed successfully!")
        print(f"Response: '{result}'")
        print("-" * 50)
        print("📊 Status messages received:")
        for i, msg in enumerate(status_messages, 1):
            print(f"{i}. {msg}")
            
    except Exception as e:
        print("-" * 50)
        print(f"❌ API call failed: {e}")
        print("-" * 50)
        print("📊 Status messages received:")
        for i, msg in enumerate(status_messages, 1):
            print(f"{i}. {msg}")

if __name__ == "__main__":
    test_simple_api_call()