#!/usr/bin/env python3
"""Test quarantine functionality."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


async def test_quarantine():
    """Test quarantine functionality."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False
    
    db = DatabaseManager(db_url)
    await db.initialize()
    
    try:
        print("🧪 Testing Protocol de Silencio...")
        
        # Test 1: Get quarantine stats (should work even with empty data)
        print("\n1️⃣ Testing quarantine stats...")
        stats = await db.get_protocol_stats()
        print(f"✅ Stats: {stats}")
        
        # Test 2: Get quarantine messages (should work even with empty data)
        print("\n2️⃣ Testing quarantine messages...")
        messages = await db.get_quarantine_messages(limit=10)
        print(f"✅ Found {len(messages)} quarantine messages")
        
        # Test 3: Test protocol activation
        print("\n3️⃣ Testing protocol activation...")
        test_user_id = "test_user_123"
        success = await db.activate_protocol(test_user_id, "test_script", "Testing protocol")
        print(f"✅ Protocol activation: {success}")
        
        # Test 4: Check protocol status
        print("\n4️⃣ Testing protocol status check...")
        status = await db.get_protocol_status(test_user_id)
        print(f"✅ Protocol status: {status}")
        
        # Test 5: Add a test quarantine message
        print("\n5️⃣ Testing quarantine message creation...")
        quarantine_id = await db.save_quarantine_message(
            test_user_id, 
            "test_message_456", 
            "This is a test quarantine message",
            123456
        )
        print(f"✅ Quarantine message created: {quarantine_id}")
        
        # Test 6: Get quarantine messages again
        print("\n6️⃣ Testing quarantine messages with data...")
        messages = await db.get_quarantine_messages(limit=10)
        print(f"✅ Found {len(messages)} quarantine messages")
        if messages:
            print(f"   Latest message: {messages[0]['message_text'][:50]}...")
        
        # Test 7: Deactivate protocol
        print("\n7️⃣ Testing protocol deactivation...")
        success = await db.deactivate_protocol(test_user_id, "test_script", "Test completed")
        print(f"✅ Protocol deactivation: {success}")
        
        # Test 8: Clean up - delete test message
        print("\n8️⃣ Cleaning up test data...")
        deleted = await db.delete_quarantine_message("test_message_456")
        print(f"✅ Test message deleted: {deleted}")
        
        print("\n🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.close()


if __name__ == "__main__":
    success = asyncio.run(test_quarantine())
    sys.exit(0 if success else 1)