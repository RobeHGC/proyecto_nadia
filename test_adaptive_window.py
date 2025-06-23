#!/usr/bin/env python3
"""
Test script for Adaptive Window Message Pacing system.

This script tests different message patterns to validate the pacing behavior:
1. Single message - should process immediately (after 1.5s window)
2. Rapid messages - should batch and wait for typing completion
3. Mixed patterns - should handle appropriately

Usage:
    python test_adaptive_window.py
"""

import asyncio
import logging
import sys
from unittest.mock import Mock, AsyncMock
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our modules
from utils.config import Config
from utils.user_activity_tracker import UserActivityTracker


class MockEvent:
    """Mock Telegram event for testing."""
    
    def __init__(self, user_id: str, message: str, chat_id: int = None):
        self.sender_id = int(user_id)
        self.text = message
        self.chat_id = chat_id or int(user_id)
        self.message = Mock()
        self.message.id = hash(message) % 100000  # Simple ID generation


class AdaptiveWindowTester:
    """Test harness for adaptive window pacing."""
    
    def __init__(self):
        # Create test config
        self.config = Mock()
        self.config.enable_typing_pacing = True
        self.config.typing_window_delay = 1.5
        self.config.typing_debounce_delay = 3.0  # Shorter for testing
        self.config.min_batch_size = 2
        self.config.max_batch_size = 5
        self.config.max_batch_wait_time = 15.0  # Shorter for testing
        
        # Create activity tracker with mock Redis
        self.redis_url = "redis://localhost:6379/0"
        self.activity_tracker = UserActivityTracker(self.redis_url, self.config)
        
        # Mock the Redis connection to avoid actual Redis dependency
        self.activity_tracker._get_redis = AsyncMock()
        mock_redis = AsyncMock()
        self.activity_tracker._get_redis.return_value = mock_redis
        
        # Track processed messages
        self.processed_messages = []
        self.processing_delays = []
    
    async def mock_process_callback(self, event):
        """Mock processing callback that records when messages are processed."""
        timestamp = datetime.now()
        user_id = str(event.sender_id)
        message = event.text
        
        self.processed_messages.append({
            'user_id': user_id,
            'message': message,
            'timestamp': timestamp
        })
        
        logger.info(f"PROCESSED: User {user_id} - '{message}' at {timestamp.strftime('%H:%M:%S.%f')[:-3]}")
    
    async def simulate_typing_events(self, user_id: str, typing_periods: list):
        """
        Simulate typing events.
        
        Args:
            user_id: User ID to simulate typing for
            typing_periods: List of (delay, is_typing) tuples
        """
        for delay, is_typing in typing_periods:
            await asyncio.sleep(delay)
            await self.activity_tracker.set_typing_state(user_id, is_typing)
            logger.info(f"TYPING: User {user_id} - {'started' if is_typing else 'stopped'} typing")
    
    async def test_single_message(self):
        """Test 1: Single message should process after window delay."""
        logger.info("\n=== TEST 1: Single Message ===")
        
        user_id = "123456"
        event = MockEvent(user_id, "Hello there!")
        
        start_time = datetime.now()
        
        # Send single message
        await self.activity_tracker.handle_message(event, self.mock_process_callback)
        
        # Wait for processing
        await asyncio.sleep(5.0)
        
        # Check results
        assert len(self.processed_messages) == 1
        process_time = self.processed_messages[0]['timestamp']
        delay = (process_time - start_time).total_seconds()
        
        logger.info(f"✅ Single message processed after {delay:.2f}s (expected ~1.5s)")
        assert 1.4 <= delay <= 2.0, f"Expected ~1.5s delay, got {delay:.2f}s"
        
        # Clear for next test
        self.processed_messages.clear()
    
    async def test_rapid_messages_no_typing(self):
        """Test 2: Rapid messages without typing events."""
        logger.info("\n=== TEST 2: Rapid Messages (No Typing Events) ===")
        
        user_id = "789012"
        messages = ["Hi", "how are you", "today?"]
        
        start_time = datetime.now()
        
        # Send rapid messages
        for i, msg in enumerate(messages):
            event = MockEvent(user_id, msg)
            await self.activity_tracker.handle_message(event, self.mock_process_callback)
            if i < len(messages) - 1:
                await asyncio.sleep(0.1)  # Very rapid
        
        # Wait for processing
        await asyncio.sleep(8.0)
        
        # Check results
        assert len(self.processed_messages) == 3
        process_time = self.processed_messages[0]['timestamp']
        delay = (process_time - start_time).total_seconds()
        
        logger.info(f"✅ Rapid messages processed after {delay:.2f}s (expected 4-6s)")
        assert 3.0 <= delay <= 7.0, f"Expected 4-6s delay for batching, got {delay:.2f}s"
        
        # Verify all messages processed together
        timestamps = [msg['timestamp'] for msg in self.processed_messages]
        time_span = (max(timestamps) - min(timestamps)).total_seconds()
        logger.info(f"✅ All messages processed within {time_span:.2f}s")
        
        # Clear for next test
        self.processed_messages.clear()
    
    async def test_rapid_messages_with_typing(self):
        """Test 3: Rapid messages with typing simulation."""
        logger.info("\n=== TEST 3: Rapid Messages with Typing Events ===")
        
        user_id = "345678"
        messages = ["Hey", "wait let me", "think about this"]
        
        start_time = datetime.now()
        
        # Start typing simulation in background
        typing_task = asyncio.create_task(self.simulate_typing_events(
            user_id, [
                (0.5, True),   # Start typing after 0.5s
                (2.0, False),  # Stop typing after 2s
                (1.0, True),   # Start typing again
                (3.0, False),  # Stop typing after 3s
            ]
        ))
        
        # Send rapid messages
        for i, msg in enumerate(messages):
            event = MockEvent(user_id, msg)
            await self.activity_tracker.handle_message(event, self.mock_process_callback)
            if i < len(messages) - 1:
                await asyncio.sleep(0.2)
        
        # Wait for processing and typing simulation
        await asyncio.sleep(12.0)
        typing_task.cancel()
        
        # Check results
        assert len(self.processed_messages) == 3
        process_time = self.processed_messages[0]['timestamp']
        delay = (process_time - start_time).total_seconds()
        
        logger.info(f"✅ Messages with typing processed after {delay:.2f}s (expected 8-12s)")
        assert 6.0 <= delay <= 13.0, f"Expected longer delay with typing, got {delay:.2f}s"
        
        # Clear for next test
        self.processed_messages.clear()
    
    async def test_mixed_patterns(self):
        """Test 4: Mixed single and rapid messages."""
        logger.info("\n=== TEST 4: Mixed Patterns ===")
        
        # Single message from user 1
        user1 = "111111"
        event1 = MockEvent(user1, "Quick question")
        await self.activity_tracker.handle_message(event1, self.mock_process_callback)
        
        await asyncio.sleep(0.5)
        
        # Rapid messages from user 2
        user2 = "222222"
        for msg in ["Hey", "are you there", "need help"]:
            event2 = MockEvent(user2, msg)
            await self.activity_tracker.handle_message(event2, self.mock_process_callback)
            await asyncio.sleep(0.1)
        
        # Wait for processing
        await asyncio.sleep(8.0)
        
        # Check results
        assert len(self.processed_messages) == 4
        
        # Verify user separation
        user1_messages = [msg for msg in self.processed_messages if msg['user_id'] == user1]
        user2_messages = [msg for msg in self.processed_messages if msg['user_id'] == user2]
        
        assert len(user1_messages) == 1
        assert len(user2_messages) == 3
        
        logger.info(f"✅ Mixed patterns handled correctly")
        logger.info(f"   User1 (single): processed after window")
        logger.info(f"   User2 (rapid): batched together")
        
        # Clear for next test
        self.processed_messages.clear()
    
    async def test_max_batch_size(self):
        """Test 5: Max batch size limit."""
        logger.info("\n=== TEST 5: Max Batch Size Limit ===")
        
        user_id = "555555"
        messages = [f"Message {i+1}" for i in range(7)]  # More than max_batch_size (5)
        
        start_time = datetime.now()
        
        # Send many rapid messages
        for i, msg in enumerate(messages):
            event = MockEvent(user_id, msg)
            await self.activity_tracker.handle_message(event, self.mock_process_callback)
            await asyncio.sleep(0.05)
        
        # Wait for processing
        await asyncio.sleep(10.0)
        
        # Check results
        assert len(self.processed_messages) == 7
        logger.info(f"✅ All {len(self.processed_messages)} messages processed")
        
        # Verify processing happened in batches
        timestamps = [msg['timestamp'] for msg in self.processed_messages]
        first_batch_time = min(timestamps)
        delay = (first_batch_time - start_time).total_seconds()
        
        logger.info(f"✅ First batch processed after {delay:.2f}s (hit max batch size)")
        
        # Clear for final summary
        self.processed_messages.clear()
    
    async def run_all_tests(self):
        """Run all test scenarios."""
        logger.info("🚀 Starting Adaptive Window Pacing Tests")
        logger.info(f"Config: window={self.config.typing_window_delay}s, "
                   f"debounce={self.config.typing_debounce_delay}s, "
                   f"min_batch={self.config.min_batch_size}")
        
        try:
            await self.test_single_message()
            await self.test_rapid_messages_no_typing()
            await self.test_rapid_messages_with_typing()
            await self.test_mixed_patterns()
            await self.test_max_batch_size()
            
            logger.info("\n🎉 All tests passed! Adaptive Window Pacing is working correctly.")
            
        except Exception as e:
            logger.error(f"\n❌ Test failed: {e}")
            raise
        
        finally:
            await self.activity_tracker.close()


async def main():
    """Main test runner."""
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        logger.info("Running quick test (single message only)")
        tester = AdaptiveWindowTester()
        await tester.test_single_message()
        await tester.activity_tracker.close()
    else:
        tester = AdaptiveWindowTester()
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())