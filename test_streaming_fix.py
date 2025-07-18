#!/usr/bin/env python3
"""
Test script to verify the streaming SSE fix works
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import make_single_api_call

def test_streaming_fix():
    """Test the streaming SSE fix"""
    
    api_key = input("Enter your xAI API key: ").strip()
    
    if not api_key:
        print("❌ No API key provided")
        return
    
    # Simple test prompt
    test_prompt = "Please respond with exactly: 'Streaming test successful! The SSE parsing is working correctly.'"
    
    print("🧪 Testing streaming SSE fix...")
    print(f"Prompt: {test_prompt}")
    print("-" * 60)
    
    status_messages = []
    
    def status_callback(message):
        print(f"Status: {message}")
        status_messages.append(message)
    
    try:
        # Test with streaming enabled (should handle SSE format)
        result = make_single_api_call(
            api_key=api_key,
            prompt_with_data=test_prompt,
            status_callback=status_callback,
            enable_streaming=True
        )
        
        print("-" * 60)
        print("✅ Streaming API call completed!")
        print(f"Response length: {len(result)} characters")
        print(f"Response: '{result}'")
        print("-" * 60)
        
        # Check if we got the expected response
        if "streaming test successful" in result.lower():
            print("🎉 SUCCESS: Streaming SSE parsing is working correctly!")
        else:
            print("⚠️ WARNING: Got response but content may not be as expected")
        
        print("\n📊 Debugging messages:")
        for i, msg in enumerate(status_messages, 1):
            print(f"{i:2d}. {msg}")
            
    except Exception as e:
        print("-" * 60)
        print(f"❌ API call failed: {e}")
        print("-" * 60)
        print("📊 Debugging messages:")
        for i, msg in enumerate(status_messages, 1):
            print(f"{i:2d}. {msg}")
        
        print("\n🔍 Error Analysis:")
        error_str = str(e)
        if "Invalid JSON response" in error_str:
            print("- Still having JSON parsing issues")
        elif "Empty response" in error_str:
            print("- Response is empty after parsing")
        elif "choices" in error_str:
            print("- API response structure issue")
        else:
            print(f"- Other error: {error_str}")

if __name__ == "__main__":
    test_streaming_fix()