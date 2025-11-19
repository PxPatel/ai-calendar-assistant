"""
Test Google Gemini API connection
Uses the latest google-genai package (not google-generativeai)
"""
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
MODEL = os.getenv("GOOGLE_GEMINI_MODEL")

def test_gemini_basic():
    """Test basic Gemini API connection"""
    print("Testing Google Gemini API...")
    print("=" * 50)
    
    try:
        # Get API key
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
        if not api_key:
            print("❌ GOOGLE_GEMINI_API_KEY not found in .env file")
            return False
        
        # Initialize client
        client = genai.Client(api_key=api_key)
        
        # Test API call with latest SDK
        response = client.models.generate_content(
            model=MODEL,  # Latest model
            contents='Say "API is working!" if you can read this.'
        )
        
        print(f"✅ Gemini API Response: {response.text}")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("=" * 50)
        return False

def test_gemini_json_output():
    """Test JSON-structured output"""
    print("\nTesting JSON output...")
    print("=" * 50)
    
    try:
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        prompt = """
Parse this scheduling request and return ONLY valid JSON (no markdown, no code blocks):

User request: "Schedule 3 hours for homework due Friday"

Return JSON with this structure:
{
  "action": "schedule_task",
  "task_name": "homework",
  "duration_minutes": 180,
  "deadline": "2024-11-22",
  "priority": "normal"
}

Return ONLY the JSON object.
"""
        
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )
        
        print("Raw response:")
        print(response.text)
        print("\n✅ JSON output test complete")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("=" * 50)
        return False

if __name__ == '__main__':
    print("\n🧪 Gemini API Test Suite")
    print("=" * 50)
    
    # Run tests
    basic_ok = test_gemini_basic()
    
    if basic_ok:
        json_ok = test_gemini_json_output()
        
        if basic_ok and json_ok:
            print("\n🎉 All Gemini tests passed!")
            print("You're ready to use Gemini in your project.")
        else:
            print("\n⚠️ Some tests failed. Check the errors above.")
    else:
        print("\n⚠️ Basic connection failed. Check your API key.")