"""
NADIA Rapport Database Manager

Optimized database layer for fast emotional connection and user memory.
Handles user profiles, preferences, emotional states, and conversation memory.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

logger = logging.getLogger(__name__)


class RapportDatabaseManager:
    """Fast database manager for rapport building and emotional connection."""
    
    def __init__(self, database_url: str):
        """Initialize rapport database manager."""
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        
        # Cache for frequent queries
        self._user_cache = {}
        self._cache_expiry = {}
        self._cache_duration = 300  # 5 minutes
        
    async def initialize(self):
        """Initialize database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            logger.info("Rapport database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize rapport database: {e}")
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Rapport database connection pool closed")
    
    # ════════════════════════════════════════════════════════════════
    # USER PROFILE MANAGEMENT
    # ════════════════════════════════════════════════════════════════
    
    async def get_or_create_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile or create if doesn't exist."""
        try:
            async with self.pool.acquire() as conn:
                # Try to get existing profile
                profile = await conn.fetchrow("""
                    SELECT * FROM user_profiles WHERE user_id = $1
                """, user_id)
                
                if profile:
                    return dict(profile)
                
                # Create new profile
                await conn.execute("""
                    INSERT INTO user_profiles (user_id, created_at, last_active)
                    VALUES ($1, NOW(), NOW())
                """, user_id)
                
                # Return the new profile
                profile = await conn.fetchrow("""
                    SELECT * FROM user_profiles WHERE user_id = $1
                """, user_id)
                
                logger.info(f"Created new user profile for {user_id}")
                return dict(profile)
                
        except Exception as e:
            logger.error(f"Error managing user profile for {user_id}: {e}")
            return {}
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user profile information."""
        try:
            if not updates:
                return True
            
            # Build dynamic query
            set_clauses = []
            values = []
            param_count = 1
            
            for key, value in updates.items():
                if key in ['name', 'age', 'location', 'occupation', 'timezone', 'language']:
                    set_clauses.append(f"{key} = ${param_count}")
                    values.append(value)
                    param_count += 1
            
            if not set_clauses:
                return True
            
            # Always update last_active
            set_clauses.append(f"last_active = ${param_count}")
            values.append(datetime.now())
            values.append(user_id)  # For WHERE clause
            
            query = f"""
                UPDATE user_profiles 
                SET {', '.join(set_clauses)}
                WHERE user_id = ${param_count + 1}
            """
            
            async with self.pool.acquire() as conn:
                await conn.execute(query, *values)
            
            # Clear cache
            self._clear_user_cache(user_id)
            logger.debug(f"Updated profile for user {user_id}: {list(updates.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user profile for {user_id}: {e}")
            return False
    
    # ════════════════════════════════════════════════════════════════
    # PREFERENCES & INTERESTS
    # ════════════════════════════════════════════════════════════════
    
    async def add_user_preference(self, user_id: str, category: str, preference: str, confidence: float = 1.0) -> bool:
        """Add or update a user preference."""
        try:
            async with self.pool.acquire() as conn:
                # Check if preference already exists
                existing = await conn.fetchrow("""
                    SELECT id, mentioned_count FROM user_preferences
                    WHERE user_id = $1 AND category = $2 AND preference = $3
                """, user_id, category, preference)
                
                if existing:
                    # Update existing preference
                    await conn.execute("""
                        UPDATE user_preferences
                        SET confidence = GREATEST(confidence, $1),
                            mentioned_count = mentioned_count + 1,
                            last_mentioned = NOW()
                        WHERE id = $2
                    """, confidence, existing['id'])
                else:
                    # Insert new preference
                    await conn.execute("""
                        INSERT INTO user_preferences 
                        (user_id, category, preference, confidence, mentioned_count)
                        VALUES ($1, $2, $3, $4, 1)
                    """, user_id, category, preference, confidence)
                
                logger.debug(f"Added preference for {user_id}: {category} -> {preference}")
                return True
                
        except Exception as e:
            logger.error(f"Error adding preference for {user_id}: {e}")
            return False
    
    async def get_user_preferences(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user preferences ordered by relevance."""
        try:
            async with self.pool.acquire() as conn:
                preferences = await conn.fetch("""
                    SELECT category, preference, confidence, mentioned_count, last_mentioned
                    FROM user_preferences
                    WHERE user_id = $1
                    ORDER BY confidence DESC, mentioned_count DESC, last_mentioned DESC
                    LIMIT $2
                """, user_id, limit)
                
                return [dict(pref) for pref in preferences]
                
        except Exception as e:
            logger.error(f"Error getting preferences for {user_id}: {e}")
            return []
    
    # ════════════════════════════════════════════════════════════════
    # EMOTIONAL STATE TRACKING
    # ════════════════════════════════════════════════════════════════
    
    async def record_emotional_state(self, user_id: str, state: str, intensity: float = 5.0, 
                                   context: str = None, confidence: float = 0.8) -> bool:
        """Record user's emotional state."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO emotional_states 
                    (user_id, state, intensity, context, confidence)
                    VALUES ($1, $2, $3, $4, $5)
                """, user_id, state, intensity, context, confidence)
                
                logger.debug(f"Recorded emotional state for {user_id}: {state} (intensity: {intensity})")
                return True
                
        except Exception as e:
            logger.error(f"Error recording emotional state for {user_id}: {e}")
            return False
    
    async def get_recent_emotional_states(self, user_id: str, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent emotional states for a user."""
        try:
            async with self.pool.acquire() as conn:
                states = await conn.fetch("""
                    SELECT state, intensity, context, detected_at, confidence
                    FROM emotional_states
                    WHERE user_id = $1 AND detected_at >= NOW() - INTERVAL '%d days'
                    ORDER BY detected_at DESC
                    LIMIT $2
                """, user_id, limit)
                
                return [dict(state) for state in states]
                
        except Exception as e:
            logger.error(f"Error getting emotional states for {user_id}: {e}")
            return []
    
    async def get_emotional_summary(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get emotional summary for a user."""
        try:
            async with self.pool.acquire() as conn:
                summary = await conn.fetchrow("""
                    SELECT 
                        AVG(intensity) as avg_intensity,
                        COUNT(*) as total_states,
                        MODE() WITHIN GROUP (ORDER BY state) as dominant_emotion,
                        MAX(detected_at) as last_emotional_event
                    FROM emotional_states
                    WHERE user_id = $1 AND detected_at >= NOW() - INTERVAL '%d days'
                """, user_id)
                
                if summary and summary['total_states'] > 0:
                    return dict(summary)
                return {'avg_intensity': 5.0, 'total_states': 0, 'dominant_emotion': 'neutral', 'last_emotional_event': None}
                
        except Exception as e:
            logger.error(f"Error getting emotional summary for {user_id}: {e}")
            return {'avg_intensity': 5.0, 'total_states': 0, 'dominant_emotion': 'neutral', 'last_emotional_event': None}
    
    # ════════════════════════════════════════════════════════════════
    # CONVERSATION MEMORY
    # ════════════════════════════════════════════════════════════════
    
    async def save_conversation_snapshot(self, user_id: str, summary: str, key_topics: List[str],
                                       emotional_tone: str, messages: List[Dict], intimacy_level: int = 1) -> bool:
        """Save conversation snapshot for quick recall."""
        try:
            async with self.pool.acquire() as conn:
                # Keep only last 15 messages for performance
                recent_messages = messages[-15:] if len(messages) > 15 else messages
                
                await conn.execute("""
                    INSERT INTO conversation_snapshots
                    (user_id, summary, key_topics, emotional_tone, messages, message_count, intimacy_level)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, user_id, summary, key_topics, emotional_tone, 
                json.dumps(recent_messages), len(messages), intimacy_level)
                
                # Keep only last 10 snapshots per user
                await conn.execute("""
                    DELETE FROM conversation_snapshots 
                    WHERE user_id = $1 AND id NOT IN (
                        SELECT id FROM conversation_snapshots 
                        WHERE user_id = $1 
                        ORDER BY created_at DESC 
                        LIMIT 10
                    )
                """, user_id)
                
                logger.debug(f"Saved conversation snapshot for {user_id}: {len(key_topics)} topics")
                return True
                
        except Exception as e:
            logger.error(f"Error saving conversation snapshot for {user_id}: {e}")
            return False
    
    async def get_recent_conversations(self, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Get recent conversation snapshots."""
        try:
            async with self.pool.acquire() as conn:
                conversations = await conn.fetch("""
                    SELECT summary, key_topics, emotional_tone, intimacy_level, created_at, message_count
                    FROM conversation_snapshots
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, user_id, limit)
                
                return [dict(conv) for conv in conversations]
                
        except Exception as e:
            logger.error(f"Error getting conversations for {user_id}: {e}")
            return []
    
    # ════════════════════════════════════════════════════════════════
    # PERSONALIZATION CACHE
    # ════════════════════════════════════════════════════════════════
    
    async def update_personalization_cache(self, user_id: str, quick_facts: Dict, 
                                         conversation_starters: List[str], recent_mood: str = None) -> bool:
        """Update fast lookup cache for personalization."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO personalization_cache 
                    (user_id, quick_facts, conversation_starters, recent_mood, cached_at, expires_at)
                    VALUES ($1, $2, $3, $4, NOW(), NOW() + INTERVAL '24 hours')
                    ON CONFLICT (user_id) DO UPDATE SET
                        quick_facts = $2,
                        conversation_starters = $3,
                        recent_mood = $4,
                        cached_at = NOW(),
                        expires_at = NOW() + INTERVAL '24 hours'
                """, user_id, json.dumps(quick_facts), conversation_starters, recent_mood)
                
                logger.debug(f"Updated personalization cache for {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating personalization cache for {user_id}: {e}")
            return False
    
    # ════════════════════════════════════════════════════════════════
    # COMPREHENSIVE USER CONTEXT
    # ════════════════════════════════════════════════════════════════
    
    async def get_user_rapport_context(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive context for rapport building - optimized single query."""
        cache_key = f"rapport_context_{user_id}"
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            return self._user_cache[cache_key]
        
        try:
            async with self.pool.acquire() as conn:
                # Use the database function for optimal performance
                context_json = await conn.fetchval("""
                    SELECT get_user_rapport_context($1)
                """, user_id)
                
                if context_json:
                    context = json.loads(context_json) if isinstance(context_json, str) else context_json
                    
                    # Cache the result
                    self._user_cache[cache_key] = context
                    self._cache_expiry[cache_key] = datetime.now() + timedelta(seconds=self._cache_duration)
                    
                    return context
                
                # Fallback: create new user
                await self.get_or_create_user_profile(user_id)
                return {'profile': {'user_id': user_id, 'name': None}, 'top_preferences': [], 
                       'recent_emotions': [], 'interaction_style': None, 'recent_conversations': []}
                
        except Exception as e:
            logger.error(f"Error getting rapport context for {user_id}: {e}")
            return {'profile': {'user_id': user_id, 'name': None}, 'top_preferences': [], 
                   'recent_emotions': [], 'interaction_style': None, 'recent_conversations': []}
    
    # ════════════════════════════════════════════════════════════════
    # INTERACTION PATTERNS
    # ════════════════════════════════════════════════════════════════
    
    async def update_interaction_patterns(self, user_id: str, **patterns) -> bool:
        """Update user interaction patterns."""
        try:
            async with self.pool.acquire() as conn:
                # Get current patterns or create new
                current = await conn.fetchrow("""
                    SELECT * FROM interaction_patterns WHERE user_id = $1
                """, user_id)
                
                if current:
                    # Update existing
                    updates = []
                    values = []
                    param_count = 1
                    
                    for key, value in patterns.items():
                        if key in ['preferred_chat_times', 'avg_message_length', 'preferred_topics', 
                                  'communication_style', 'response_time_preference', 'emoji_usage_frequency']:
                            updates.append(f"{key} = ${param_count}")
                            values.append(value)
                            param_count += 1
                    
                    if updates:
                        updates.append(f"updated_at = ${param_count}")
                        values.append(datetime.now())
                        values.append(user_id)
                        
                        query = f"""
                            UPDATE interaction_patterns 
                            SET {', '.join(updates)}
                            WHERE user_id = ${param_count + 1}
                        """
                        await conn.execute(query, *values)
                else:
                    # Create new
                    await conn.execute("""
                        INSERT INTO interaction_patterns (user_id, communication_style)
                        VALUES ($1, $2)
                    """, user_id, patterns.get('communication_style', 'casual'))
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating interaction patterns for {user_id}: {e}")
            return False
    
    # ════════════════════════════════════════════════════════════════
    # INTELLIGENT TEXT ANALYSIS
    # ════════════════════════════════════════════════════════════════
    
    def extract_preferences_from_text(self, text: str) -> List[Tuple[str, str, float]]:
        """Extract preferences from user message using simple pattern matching."""
        preferences = []
        text_lower = text.lower()
        
        # Music preferences
        music_patterns = [
            (r'i love (.+?) music', 'music', 0.9),
            (r'my favorite (?:artist|band) is (.+)', 'music', 0.8),
            (r'i like listening to (.+)', 'music', 0.7),
        ]
        
        # Food preferences  
        food_patterns = [
            (r'my favorite food is (.+)', 'food', 0.9),
            (r'i love eating (.+)', 'food', 0.8),
            (r'i like (.+?) food', 'food', 0.7),
        ]
        
        # Hobby patterns
        hobby_patterns = [
            (r'my hobby is (.+)', 'hobbies', 0.9),
            (r'i enjoy (.+)', 'hobbies', 0.6),
            (r'i like to (.+)', 'hobbies', 0.6),
        ]
        
        all_patterns = music_patterns + food_patterns + hobby_patterns
        
        for pattern, category, confidence in all_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                cleaned_match = match.strip()
                if len(cleaned_match) > 2 and len(cleaned_match) < 50:
                    preferences.append((category, cleaned_match, confidence))
        
        return preferences
    
    def extract_emotional_state(self, text: str) -> Tuple[str, float, float]:
        """Extract emotional state from text using simple sentiment analysis."""
        text_lower = text.lower()
        
        # Emotional indicators
        emotions = {
            'happy': ['happy', 'great', 'awesome', 'amazing', 'wonderful', 'excited', 'joy'],
            'sad': ['sad', 'depressed', 'down', 'upset', 'crying', 'hurt'],
            'angry': ['angry', 'mad', 'furious', 'annoyed', 'frustrated'],
            'stressed': ['stressed', 'overwhelmed', 'pressure', 'busy', 'tired'],
            'lonely': ['lonely', 'alone', 'isolated', 'miss'],
            'romantic': ['love', 'romance', 'kiss', 'date', 'relationship'],
            'excited': ['excited', 'can\'t wait', 'pumped', 'thrilled']
        }
        
        detected_emotions = []
        for emotion, keywords in emotions.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)
            if count > 0:
                intensity = min(10.0, 5.0 + count * 1.5)  # Base 5.0, increase with matches
                confidence = min(1.0, count * 0.3)  # Higher confidence with more matches
                detected_emotions.append((emotion, intensity, confidence))
        
        if detected_emotions:
            # Return strongest emotion
            return max(detected_emotions, key=lambda x: x[1] * x[2])
        
        return ('neutral', 5.0, 0.5)
    
    # ════════════════════════════════════════════════════════════════
    # CACHE MANAGEMENT
    # ════════════════════════════════════════════════════════════════
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache_expiry:
            return False
        return datetime.now() < self._cache_expiry[cache_key]
    
    def _clear_user_cache(self, user_id: str):
        """Clear all cache entries for a user."""
        keys_to_remove = [k for k in self._user_cache.keys() if user_id in k]
        for key in keys_to_remove:
            self._user_cache.pop(key, None)
            self._cache_expiry.pop(key, None)
    
    # ════════════════════════════════════════════════════════════════
    # MAINTENANCE
    # ════════════════════════════════════════════════════════════════
    
    async def cleanup_old_data(self) -> Dict[str, int]:
        """Clean up old data to maintain performance."""
        try:
            async with self.pool.acquire() as conn:
                # Clean old emotional states
                emotional_cleanup = await conn.fetchval("""
                    SELECT cleanup_old_emotional_states()
                """)
                
                # Clean expired cache
                cache_cleanup = await conn.execute("""
                    DELETE FROM personalization_cache 
                    WHERE expires_at < NOW()
                """)
                
                # Clean old conversation snapshots (keep last 10 per user)
                conversation_cleanup = await conn.execute("""
                    WITH ranked_conversations AS (
                        SELECT id, user_id, 
                               ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
                        FROM conversation_snapshots
                    )
                    DELETE FROM conversation_snapshots
                    WHERE id IN (
                        SELECT id FROM ranked_conversations WHERE rn > 10
                    )
                """)
                
                logger.info(f"Cleanup completed: {emotional_cleanup} emotions, {cache_cleanup} cache entries, {conversation_cleanup} conversations")
                
                return {
                    'emotional_states_cleaned': emotional_cleanup or 0,
                    'cache_entries_cleaned': int(cache_cleanup.split()[1]) if cache_cleanup else 0,
                    'conversations_cleaned': int(conversation_cleanup.split()[1]) if conversation_cleanup else 0
                }
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {'error': str(e)}