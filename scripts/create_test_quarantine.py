#!/usr/bin/env python3
"""Create test quarantine data for testing."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import DatabaseManager
from dotenv import load_dotenv

load_dotenv()


async def create_test_data():
    """Create test quarantine data."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False
    
    db = DatabaseManager(db_url)
    await db.initialize()
    
    try:
        print("🧪 Creating test quarantine data...")
        
        # Create test user with nickname
        test_user_id = "test_user_demo"
        async with db._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_current_status (user_id, customer_status, nickname)
                VALUES ($1, 'PROSPECT', 'Test User Demo')
                ON CONFLICT (user_id) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    customer_status = EXCLUDED.customer_status
            """, test_user_id)
        
        # Activate protocol
        success = await db.activate_protocol(test_user_id, "demo_script", "Demo protocol for testing")
        print(f"✅ Protocol activated: {success}")
        
        # Create test quarantine messages
        messages = [
            "Hey there! How are you today?",
            "I'm really interested in your services",
            "Can you tell me more about what you offer?",
            "This is a longer message to test how the interface handles longer text content that might wrap to multiple lines"
        ]
        
        for i, msg in enumerate(messages):
            quarantine_id = await db.save_quarantine_message(
                test_user_id,
                f"demo_msg_{i}",
                msg,
                1000 + i
            )
            print(f"✅ Created quarantine message {i+1}: {quarantine_id}")
        
        # Check results
        quarantine_messages = await db.get_quarantine_messages(limit=10)
        print(f"\n✅ Total quarantine messages: {len(quarantine_messages)}")
        
        stats = await db.get_protocol_stats()
        print(f"✅ Protocol stats: {stats}")
        
        print("\n🎉 Test data created successfully!")
        print("🔗 Now you can test the dashboard at: http://localhost:3000")
        print("👀 Go to the Quarantine tab to see the test messages")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create test data: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.close()


if __name__ == "__main__":
    success = asyncio.run(create_test_data())
    sys.exit(0 if success else 1)