#!/usr/bin/env python3
"""Script to inspect what's currently in Redis memory."""

import asyncio
import json
import redis.asyncio as redis
from datetime import datetime

async def inspect_redis_memory():
    """Inspect current Redis memory contents."""
    
    redis_url = "redis://localhost:6379/0"
    r = await redis.from_url(redis_url)
    
    print("🔍 Inspecting Redis Memory Contents\n")
    
    # 1. Find all user keys
    print("1️⃣ Finding all user conversation histories...")
    user_keys = []
    async for key in r.scan_iter(match="user:*:history"):
        key_str = key.decode() if isinstance(key, bytes) else key
        user_keys.append(key_str)
    
    print(f"   Found {len(user_keys)} user conversation histories")
    
    if not user_keys:
        print("   ❌ No conversation histories found in Redis")
        await r.aclose()
        return
    
    # 2. Inspect each user's memory
    print("\n2️⃣ Analyzing each user's conversation memory:\n")
    
    total_messages = 0
    for key in user_keys:
        user_id = key.split(':')[1]  # Extract user_id from "user:123:history"
        
        # Get conversation history
        history_data = await r.get(key)
        if history_data:
            history = json.loads(history_data)
            message_count = len(history)
            total_messages += message_count
            
            print(f"👤 User ID: {user_id}")
            print(f"   📊 Total messages: {message_count}")
            
            if history:
                # Show first and last messages
                first_msg = history[0]
                last_msg = history[-1]
                
                print(f"   📅 First message: {first_msg.get('timestamp', 'No timestamp')}")
                print(f"      [{first_msg.get('role', 'unknown')}]: {first_msg.get('content', '')[:50]}...")
                
                print(f"   📅 Last message: {last_msg.get('timestamp', 'No timestamp')}")
                print(f"      [{last_msg.get('role', 'unknown')}]: {last_msg.get('content', '')[:50]}...")
                
                # Count user vs assistant messages
                user_msgs = len([m for m in history if m.get('role') == 'user'])
                assistant_msgs = len([m for m in history if m.get('role') == 'assistant'])
                
                print(f"   💬 User messages: {user_msgs}")
                print(f"   🤖 Assistant messages: {assistant_msgs}")
                
                # Show recent conversation flow
                print(f"   📝 Last 3 exchanges:")
                recent = history[-6:] if len(history) >= 6 else history
                for msg in recent:
                    role_icon = "👤" if msg.get('role') == 'user' else "🤖"
                    content = msg.get('content', '')[:40]
                    timestamp = msg.get('timestamp', 'No time')
                    if timestamp != 'No time':
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = dt.strftime("%H:%M")
                        except:
                            time_str = "??"
                    else:
                        time_str = "??"
                    print(f"      {role_icon} [{time_str}]: {content}...")
                
                print()
    
    # 3. Show memory limits and configuration
    print(f"3️⃣ Memory Configuration Summary:")
    print(f"   📏 Total users with history: {len(user_keys)}")
    print(f"   📊 Total messages across all users: {total_messages}")
    print(f"   ⚙️  Configured limit: 50 messages per user")
    print(f"   ⏰ Expiration: 7 days for conversation history")
    
    # 4. Check for other relevant keys
    print(f"\n4️⃣ Other Redis keys related to the bot:")
    
    # WAL and review queues
    wal_keys = []
    async for key in r.scan_iter(match="nadia_*"):
        key_str = key.decode() if isinstance(key, bytes) else key
        wal_keys.append(key_str)
    
    print(f"   🔄 Bot operational keys: {len(wal_keys)}")
    for key in wal_keys:
        key_type = await r.type(key)
        key_type_str = key_type.decode() if isinstance(key_type, bytes) else key_type
        
        if key_type_str == 'list':
            length = await r.llen(key)
            print(f"      📋 {key}: {length} items (list)")
        elif key_type_str == 'hash':
            length = await r.hlen(key)
            print(f"      🗂️  {key}: {length} fields (hash)")
        elif key_type_str == 'zset':
            length = await r.zcard(key)
            print(f"      📊 {key}: {length} members (sorted set)")
        else:
            print(f"      🔑 {key}: ({key_type_str})")
    
    await r.aclose()
    
    print(f"\n✅ Redis inspection completed!")
    print(f"\n💡 Answer: Redis stores {total_messages} messages total across {len(user_keys)} users")
    print(f"   Each user can have up to 50 messages (not 50 total)")

if __name__ == "__main__":
    asyncio.run(inspect_redis_memory())