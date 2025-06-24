#!/usr/bin/env python3
"""Test script to verify the new memory system implementation."""

import asyncio
import json
from datetime import datetime, timedelta
from memory.user_memory import UserMemoryManager
from utils.config import Config

async def test_memory_system():
    """Test the complete memory system with conversation history."""
    
    # Initialize - use direct Redis URL for testing
    redis_url = "redis://localhost:6379/0"
    memory = UserMemoryManager(redis_url)
    test_user_id = "test_user_123"
    
    print("🧪 Testing Memory System Implementation\n")
    
    # 1. Clear any existing test data
    print("1️⃣ Clearing existing test data...")
    await memory.delete_all_data_for_user(test_user_id)
    
    # 2. Simulate a conversation with timestamps
    print("\n2️⃣ Simulating conversation...")
    
    # Add messages with different timestamps
    base_time = datetime.now()
    
    # Old messages (for summary)
    old_messages = [
        {"role": "user", "content": "Hi, my name is John", "timestamp": (base_time - timedelta(hours=3)).isoformat()},
        {"role": "assistant", "content": "Nice to meet you John! Tell me more about yourself", "timestamp": (base_time - timedelta(hours=3, minutes=-1)).isoformat()},
        {"role": "user", "content": "I work as a software engineer", "timestamp": (base_time - timedelta(hours=2, minutes=30)).isoformat()},
        {"role": "assistant", "content": "That's fascinating! Tell me more about your work", "timestamp": (base_time - timedelta(hours=2, minutes=29)).isoformat()},
        {"role": "user", "content": "I love coding and my family is very supportive", "timestamp": (base_time - timedelta(hours=2)).isoformat()},
        {"role": "assistant", "content": "How wonderful! Family support is so important", "timestamp": (base_time - timedelta(hours=2, minutes=-1)).isoformat()},
    ]
    
    # Recent messages
    recent_messages = [
        {"role": "user", "content": "What do you think about AI?", "timestamp": (base_time - timedelta(minutes=10)).isoformat()},
        {"role": "assistant", "content": "AI is pretty amazing! It's changing so many fields", "timestamp": (base_time - timedelta(minutes=9)).isoformat()},
        {"role": "user", "content": "Yeah, especially in healthcare", "timestamp": (base_time - timedelta(minutes=5)).isoformat()},
        {"role": "assistant", "content": "Absolutely! The medical applications are incredible", "timestamp": (base_time - timedelta(minutes=4)).isoformat()},
    ]
    
    # Add all messages to history
    all_messages = old_messages + recent_messages
    for msg in all_messages:
        await memory.add_to_conversation_history(test_user_id, msg)
        print(f"   Added: [{msg['role']}] {msg['content'][:50]}...")
    
    # 3. Test retrieval with summary
    print("\n3️⃣ Testing conversation retrieval with summary...")
    conversation_data = await memory.get_conversation_with_summary(test_user_id, recent_count=4)
    
    print(f"\n📊 Total messages in history: {conversation_data.get('total_messages', 0)}")
    print(f"📝 Recent messages returned: {len(conversation_data.get('recent_messages', []))}")
    
    # 4. Display temporal summary
    print("\n4️⃣ Generated Temporal Summary:")
    print("-" * 50)
    print(conversation_data.get('temporal_summary', 'No summary generated'))
    print("-" * 50)
    
    # 5. Display recent messages
    print("\n5️⃣ Recent Messages (last 4):")
    for msg in conversation_data.get('recent_messages', []):
        role = "User" if msg['role'] == 'user' else "Nadia"
        print(f"   {role}: {msg['content']}")
    
    # 6. Test anti-muletilla detection
    print("\n6️⃣ Testing anti-muletilla detection...")
    
    # Add more messages with repeated phrases
    for i in range(3):
        await memory.add_to_conversation_history(test_user_id, {
            "role": "user",
            "content": f"Test message {i}",
            "timestamp": (base_time - timedelta(hours=1, minutes=30-i)).isoformat()
        })
        await memory.add_to_conversation_history(test_user_id, {
            "role": "assistant", 
            "content": "That sounds interesting! Tell me more",
            "timestamp": (base_time - timedelta(hours=1, minutes=29-i)).isoformat()
        })
    
    # Get new summary
    conversation_data = await memory.get_conversation_with_summary(test_user_id, recent_count=4)
    print("\n📝 Updated summary (should show repeated phrases):")
    print("-" * 50)
    print(conversation_data.get('temporal_summary', 'No summary generated'))
    print("-" * 50)
    
    # 7. Verify conversation history integrity
    print("\n7️⃣ Verifying full conversation history...")
    full_history = await memory.get_conversation_history(test_user_id)
    print(f"   Total messages stored: {len(full_history)}")
    print(f"   First message: {full_history[0]['content'][:30]}..." if full_history else "   No messages")
    print(f"   Last message: {full_history[-1]['content'][:30]}..." if full_history else "   No messages")
    
    # Clean up
    await memory.delete_all_data_for_user(test_user_id)
    await memory.close()
    
    print("\n✅ Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_memory_system())