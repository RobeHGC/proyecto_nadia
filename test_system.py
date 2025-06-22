#!/usr/bin/env python3
"""
Simple test script to verify system setup without running full test suite.
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_environment():
    """Test environment variables are set."""
    print("🔍 Checking environment variables...")
    
    required_vars = {
        'OPENAI_API_KEY': 'OpenAI API',
        'GEMINI_API_KEY': 'Gemini API', 
        'REDIS_URL': 'Redis URL',
        'API_ID': 'Telegram API ID',
        'API_HASH': 'Telegram API Hash',
        'PHONE_NUMBER': 'Phone Number'
    }
    
    all_good = True
    for var, name in required_vars.items():
        value = os.getenv(var)
        if value:
            # Show last 4 chars for API keys, full for others
            if 'KEY' in var or 'HASH' in var:
                display = f"...{value[-4:]}"
            else:
                display = value
            print(f"✅ {name}: {display}")
        else:
            print(f"❌ {name}: NOT SET")
            all_good = False
    
    return all_good

async def test_imports():
    """Test all required imports work."""
    print("\n🔍 Testing imports...")
    
    try:
        from utils.config import Config
        print("✅ Config imported")
        
        from llms.openai_client import OpenAIClient
        print("✅ OpenAI client imported")
        
        from llms.gemini_client import GeminiClient
        print("✅ Gemini client imported")
        
        from llms.model_registry import get_model_registry
        print("✅ Model registry imported")
        
        from llms.dynamic_router import get_dynamic_router
        print("✅ Dynamic router imported")
        
        from agents.supervisor_agent import SupervisorAgent
        print("✅ Supervisor agent imported")
        
        from cognition.constitution import Constitution
        print("✅ Constitution imported")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

async def test_config():
    """Test configuration loading."""
    print("\n🔍 Testing configuration...")
    
    try:
        from utils.config import Config
        config = Config.from_env()
        
        print(f"✅ Config loaded")
        print(f"  - LLM Profile: {config.llm_profile}")
        print(f"  - LLM1: {config.llm1_provider}/{config.llm1_model}")
        print(f"  - LLM2: {config.llm2_provider}/{config.llm2_model}")
        
        # Test profile validation
        if config.validate_profile():
            print(f"✅ Profile '{config.llm_profile}' is valid")
        else:
            print(f"❌ Profile '{config.llm_profile}' is invalid")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

async def test_model_registry():
    """Test model registry."""
    print("\n🔍 Testing model registry...")
    
    try:
        from llms.model_registry import get_model_registry
        registry = get_model_registry()
        
        # List profiles
        profiles = registry.list_available_profiles()
        print(f"✅ Found {len(profiles)} profiles: {', '.join(profiles)}")
        
        # Get current profile
        default_profile = registry.get_default_profile()
        print(f"✅ Default profile: {default_profile}")
        
        # Test cost estimation
        estimate = registry.estimate_conversation_cost(
            messages=100,
            profile=default_profile
        )
        print(f"✅ Cost estimate for 100 messages: ${estimate['total_cost']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model registry error: {e}")
        return False

async def test_redis():
    """Test Redis connection."""
    print("\n🔍 Testing Redis connection...")
    
    try:
        import redis.asyncio as redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        
        r = await redis.from_url(redis_url)
        await r.ping()
        print(f"✅ Redis connected at {redis_url}")
        await r.aclose()
        
        return True
        
    except Exception as e:
        print(f"❌ Redis error: {e}")
        print("   Make sure Redis is running: sudo service redis-server start")
        return False

async def test_simple_llm():
    """Test simple LLM call."""
    print("\n🔍 Testing LLM connectivity...")
    
    openai_key = os.getenv('OPENAI_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    
    if not openai_key or not gemini_key:
        print("❌ API keys not set, skipping LLM test")
        return False
    
    try:
        # Test OpenAI
        from llms.openai_client import OpenAIClient
        openai_client = OpenAIClient(openai_key, "gpt-3.5-turbo")
        messages = [{"role": "user", "content": "Say 'test passed' and nothing else"}]
        response = await openai_client.generate_response(messages, temperature=0)
        print(f"✅ OpenAI test: {response}")
        
        # Test Gemini
        from llms.gemini_client import GeminiClient
        gemini_client = GeminiClient(gemini_key, "gemini-2.0-flash-exp")
        response = await gemini_client.generate_response(messages, temperature=0)
        print(f"✅ Gemini test: {response}")
        
        return True
        
    except Exception as e:
        print(f"❌ LLM test error: {e}")
        return False

async def main():
    """Run all tests."""
    print("🚀 NADIA System Setup Verification")
    print("=" * 50)
    
    tests = [
        ("Environment Variables", test_environment),
        ("Python Imports", test_imports),
        ("Configuration", test_config),
        ("Model Registry", test_model_registry),
        ("Redis Connection", test_redis),
        ("LLM Connectivity", test_simple_llm)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = await test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Your system is ready.")
        print("\nNext steps:")
        print("1. Run the verification script: python scripts/verify_multi_llm.py")
        print("2. Start the API server: python api/server.py")
        print("3. Start the bot: python userbot.py")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Set missing environment variables in .env file")
        print("- Install missing dependencies: pip install -r requirements.txt")
        print("- Start Redis: sudo service redis-server start")

if __name__ == "__main__":
    asyncio.run(main())