"""
Typing indicator and realistic message cadence for human-like messaging.
Implements realistic typing patterns based on message length and content.
"""
import asyncio
import logging
import random
from typing import Optional

from telethon import TelegramClient

logger = logging.getLogger(__name__)


class TypingSimulator:
    """Simulates realistic typing patterns for human-like messaging."""
    
    # Constants for typing simulation
    WORDS_PER_MINUTE = 60  # Average typing speed
    CHARS_PER_WORD = 5     # Average characters per word
    TYPING_PAUSE_MIN = 0.5  # Minimum pause between typing bursts (seconds)
    TYPING_PAUSE_MAX = 2.0  # Maximum pause between typing bursts (seconds)
    THINKING_PAUSE_MIN = 1.0  # Minimum thinking pause (seconds) 
    THINKING_PAUSE_MAX = 3.0  # Maximum thinking pause (seconds)
    
    def __init__(self, client: TelegramClient):
        self.client = client
        
    def calculate_typing_time(self, text: str) -> float:
        """Calculate realistic typing time based on text length."""
        chars = len(text)
        words = chars / self.CHARS_PER_WORD
        typing_time = (words / self.WORDS_PER_MINUTE) * 60
        
        # Add some variation (±20%)
        variation = random.uniform(0.8, 1.2)
        return typing_time * variation
    
    def calculate_reading_time(self, text: str) -> float:
        """Calculate time to read/process incoming message."""
        # Average reading speed: 200-300 words per minute
        words = len(text.split())
        reading_time = (words / 250) * 60  # 250 WPM average
        
        # Minimum 0.5s, maximum 5s for very long messages
        return max(0.5, min(5.0, reading_time))
    
    async def send_typing_action(self, chat_id: int, duration: float):
        """Send typing indicator for specified duration."""
        try:
            # Use context manager for typing action
            async with self.client.action(chat_id, 'typing'):
                await asyncio.sleep(duration)
            
        except Exception as e:
            logger.error(f"Error sending typing action: {e}")
    
    async def simulate_human_cadence(self, chat_id: int, bubbles: list[str], 
                                   previous_message: Optional[str] = None):
        """
        Simulate realistic human messaging cadence with typing indicators.
        
        Args:
            chat_id: Telegram chat ID
            bubbles: List of message bubbles to send
            previous_message: Previous message to simulate reading time
        """
        try:
            # Initial thinking/reading pause
            if previous_message:
                reading_time = self.calculate_reading_time(previous_message)
                await asyncio.sleep(reading_time)
            else:
                # Initial thinking pause
                thinking_time = random.uniform(self.THINKING_PAUSE_MIN, self.THINKING_PAUSE_MAX)
                await asyncio.sleep(thinking_time)
            
            for i, bubble in enumerate(bubbles):
                if not bubble.strip():
                    continue
                    
                # Calculate typing time for this bubble
                typing_time = self.calculate_typing_time(bubble)
                
                # Show typing indicator while "typing"
                async with self.client.action(chat_id, 'typing'):
                    await asyncio.sleep(typing_time)
                
                # Send message
                await self.client.send_message(chat_id, bubble.strip())
                
                # Pause between bubbles (except for last one)
                if i < len(bubbles) - 1:
                    pause = random.uniform(self.TYPING_PAUSE_MIN, self.TYPING_PAUSE_MAX)
                    await asyncio.sleep(pause)
                    
            logger.info(f"Sent {len(bubbles)} bubbles with realistic cadence to chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error in human cadence simulation: {e}")
            # Fallback: send messages without typing simulation
            for bubble in bubbles:
                if bubble.strip():
                    await self.client.send_message(chat_id, bubble.strip())
                    await asyncio.sleep(0.5)  # Basic fallback pause

    async def simulate_emoji_reaction_delay(self, chat_id: int, message_id: int, 
                                          emoji: str = "❤️"):
        """Simulate delayed emoji reaction like a human would."""
        try:
            # Random delay before reacting (1-5 seconds)
            delay = random.uniform(1.0, 5.0)
            await asyncio.sleep(delay)
            
            # Send reaction (if supported by user's Telegram client)
            # This is a placeholder - actual reaction implementation depends on API
            logger.info(f"Would react with {emoji} to message {message_id} in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error simulating emoji reaction: {e}")