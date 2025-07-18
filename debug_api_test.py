#!/usr/bin/env python3
"""
Debug script to test the API response directly
"""

import requests
import json

def test_grok_api():
    """Test the Grok API directly to debug the response structure"""
    
    # This is just for testing - replace with your actual API key
    api_key = input("Enter your xAI API key: ")
    
    url = "https://api.x.ai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "trade-analysis-app/1.0"
    }
    
    # Simple test payload
    payload = {
        "model": "grok-4",
        "messages": [{"role": "user", "content": "Hello, please respond with just 'API test successful'"}],
        "max_tokens": 50,
        "temperature": 0.1
    }
    
    print("🧪 Testing API endpoint...")
    print(f"URL: {url}")
    print(f"Model: {payload['model']}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response Length: {len(response.text)} chars")
        print("-" * 50)
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response Text: {response.text}")
            return
        
        print("Raw Response Text:")
        print(response.text)
        print("-" * 50)
        
        try:
            response_data = response.json()
            print("Parsed JSON Response:")
            print(json.dumps(response_data, indent=2))
            print("-" * 50)
            
            # Check structure
            if "choices" in response_data:
                print(f"✅ Found 'choices' key with {len(response_data['choices'])} items")
                if response_data["choices"]:
                    choice = response_data["choices"][0]
                    print(f"First choice keys: {list(choice.keys())}")
                    if "message" in choice:
                        print(f"Message keys: {list(choice['message'].keys())}")
                        if "content" in choice["message"]:
                            content = choice["message"]["content"]
                            print(f"✅ Content: '{content}'")
                        else:
                            print("❌ No 'content' in message")
                    else:
                        print("❌ No 'message' in choice")
                else:
                    print("❌ Empty choices array")
            else:
                print("❌ No 'choices' key in response")
                
            if "error" in response_data:
                print(f"❌ API Error: {response_data['error']}")
                
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_grok_api()