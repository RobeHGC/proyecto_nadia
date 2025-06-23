"""
Dual Database Manager for NADIA

Manages both Analytics and Rapport databases with intelligent data routing.
Analytics DB: Complete data for metrics, training, business intelligence
Rapport DB: Fast, optimized data for emotional connection and personalization
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.models import DatabaseManager
from database.rapport_manager import RapportDatabaseManager

logger = logging.getLogger(__name__)


class DualDatabaseManager:
    """Manages dual database architecture for optimal performance and rapport building."""
    
    def __init__(self, analytics_url: str, rapport_url: str):
        """Initialize both database managers."""
        self.analytics_db = DatabaseManager(analytics_url)
        self.rapport_db = RapportDatabaseManager(rapport_url)
        
        # Flags for graceful degradation
        self.analytics_available = True
        self.rapport_available = True
        
    async def initialize(self):
        """Initialize both database connections."""
        try:
            # Initialize analytics DB
            await self.analytics_db.initialize()
            logger.info("Analytics database initialized")
        except Exception as e:
            logger.error(f"Analytics DB initialization failed: {e}")
            self.analytics_available = False
            
        try:
            # Initialize rapport DB
            await self.rapport_db.initialize()
            logger.info("Rapport database initialized")
        except Exception as e:
            logger.error(f"Rapport DB initialization failed: {e}")
            self.rapport_available = False
            
        if not self.analytics_available and not self.rapport_available:
            raise Exception("Both databases failed to initialize")
            
    async def close(self):
        """Close both database connections."""
        if self.analytics_available:
            await self.analytics_db.close()
        if self.rapport_available:
            await self.rapport_db.close()
    
    # ════════════════════════════════════════════════════════════════
    # MAIN INTERACTION SAVING (DUAL WRITE)
    # ════════════════════════════════════════════════════════════════
    
    async def save_interaction(self, review_item) -> str:
        """Save interaction to both databases with optimized data distribution."""
        analytics_task = None
        rapport_success = False
        
        try:
            # 1. Fast save to rapport DB (synchronous - critical for user experience)
            if self.rapport_available:
                rapport_success = await self._save_to_rapport_db(review_item)
                if rapport_success:
                    logger.debug(f"Saved to rapport DB: {review_item.id}")
            
            # 2. Complete save to analytics DB (asynchronous - for metrics)
            if self.analytics_available:
                analytics_task = asyncio.create_task(
                    self._save_to_analytics_db(review_item)
                )
                logger.debug(f"Queued for analytics DB: {review_item.id}")
            
            # Return immediately for user experience, analytics saves in background
            return review_item.id
            
        except Exception as e:
            logger.error(f"Error in dual save for {review_item.id}: {e}")
            
            # Fallback: save only to available database
            if self.analytics_available and not rapport_success:
                try:
                    return await self.analytics_db.save_interaction(review_item)
                except Exception as fallback_e:
                    logger.error(f"Fallback to analytics failed: {fallback_e}")
            
            raise e
    
    async def _save_to_rapport_db(self, review_item) -> bool:
        """Save essential data to rapport database for fast access."""
        try:
            user_id = review_item.user_id
            user_message = review_item.user_message
            
            # 1. Update/create user profile
            await self.rapport_db.get_or_create_user_profile(user_id)
            
            # 2. Extract and save preferences
            preferences = self.rapport_db.extract_preferences_from_text(user_message)
            for category, preference, confidence in preferences:
                await self.rapport_db.add_user_preference(user_id, category, preference, confidence)
            
            # 3. Extract and save emotional state
            emotion, intensity, confidence = self.rapport_db.extract_emotional_state(user_message)
            if emotion != 'neutral':
                await self.rapport_db.record_emotional_state(
                    user_id, emotion, intensity, user_message[:200], confidence
                )
            
            # 4. Update interaction patterns
            message_length = len(user_message)
            current_hour = datetime.now().hour
            
            # Simple communication style detection
            style = 'casual'
            if '?' in user_message:
                style = 'inquisitive'
            elif any(word in user_message.lower() for word in ['love', 'sexy', 'hot', 'beautiful']):
                style = 'flirty'
            elif len(user_message) > 200:
                style = 'expressive'
                
            await self.rapport_db.update_interaction_patterns(
                user_id,
                avg_message_length=message_length,
                communication_style=style,
                preferred_chat_times=[current_hour]
            )
            
            # 5. Save conversation snapshot (every 5th interaction)
            # This is a simplified approach - in production you'd want more sophisticated triggering
            profile = await self.rapport_db.get_or_create_user_profile(user_id)
            message_count = profile.get('total_messages', 0) + 1
            
            if message_count % 5 == 0:  # Every 5 messages
                # Create simple conversation summary
                summary = f"User discussed: {user_message[:100]}..."
                key_topics = [pref[1] for pref in preferences[:3]]  # Top 3 preferences as topics
                
                # Determine intimacy level based on message content
                intimacy_level = 1
                if any(word in user_message.lower() for word in ['personal', 'private', 'secret']):
                    intimacy_level = 3
                elif any(word in user_message.lower() for word in ['love', 'feel', 'heart']):
                    intimacy_level = 4
                
                await self.rapport_db.save_conversation_snapshot(
                    user_id, summary, key_topics, emotion, 
                    [{'role': 'user', 'content': user_message, 'timestamp': datetime.now().isoformat()}],
                    intimacy_level
                )
            
            # 6. Update personalization cache
            quick_facts = {}
            if preferences:
                quick_facts['recent_interests'] = [pref[1] for pref in preferences[:3]]
            if emotion != 'neutral':
                quick_facts['recent_mood'] = emotion
                
            if quick_facts:
                conversation_starters = self._generate_conversation_starters(preferences, emotion)
                await self.rapport_db.update_personalization_cache(
                    user_id, quick_facts, conversation_starters, emotion
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving to rapport DB: {e}")
            return False
    
    async def _save_to_analytics_db(self, review_item) -> str:
        """Save complete data to analytics database."""
        try:
            return await self.analytics_db.save_interaction(review_item)
        except Exception as e:
            logger.error(f"Error saving to analytics DB: {e}")
            raise
    
    def _generate_conversation_starters(self, preferences: List, emotion: str) -> List[str]:
        """Generate personalized conversation starters based on user data."""
        starters = []
        
        # Based on preferences
        for category, preference, confidence in preferences[:2]:
            if category == 'music':
                starters.append(f"Have you heard any good {preference} lately?")
            elif category == 'food':
                starters.append(f"Any good {preference} recommendations?")
            elif category == 'hobbies':
                starters.append(f"How's your {preference} going?")
        
        # Based on emotional state
        if emotion == 'happy':
            starters.append("You seem in a great mood! What's making you smile?")
        elif emotion == 'stressed':
            starters.append("You sound like you could use a break. Want to chat about something fun?")
        elif emotion == 'excited':
            starters.append("I can feel your excitement! Tell me more!")
        
        # Generic fallbacks
        if not starters:
            starters = [
                "What's been the highlight of your day?",
                "Any interesting plans for today?",
                "How are you feeling right now?"
            ]
        
        return starters[:3]  # Return max 3 starters
    
    # ════════════════════════════════════════════════════════════════
    # READ OPERATIONS (SMART ROUTING)
    # ════════════════════════════════════════════════════════════════
    
    async def get_user_context_for_ai(self, user_id: str) -> Dict[str, Any]:
        """Get optimized user context for AI processing (from rapport DB)."""
        if not self.rapport_available:
            # Fallback to analytics DB
            return await self._get_context_from_analytics(user_id)
            
        try:
            return await self.rapport_db.get_user_rapport_context(user_id)
        except Exception as e:
            logger.error(f"Error getting context from rapport DB: {e}")
            if self.analytics_available:
                return await self._get_context_from_analytics(user_id)
            return {}
    
    async def _get_context_from_analytics(self, user_id: str) -> Dict[str, Any]:
        """Fallback: get context from analytics database."""
        try:
            # This would need to be implemented to extract relevant data
            # from the analytics database in a rapport-like format
            logger.warning(f"Using analytics DB fallback for user context: {user_id}")
            return {}
        except Exception as e:
            logger.error(f"Analytics DB fallback failed: {e}")
            return {}
    
    async def get_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get specific interaction (from analytics DB for completeness)."""
        if self.analytics_available:
            return await self.analytics_db.get_interaction(interaction_id)
        return None
    
    async def get_interactions_for_dashboard(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get interactions for dashboard (from analytics DB)."""
        if self.analytics_available:
            return await self.analytics_db.get_interactions(limit, offset)
        return []
    
    # ════════════════════════════════════════════════════════════════
    # USER-SPECIFIC OPERATIONS
    # ════════════════════════════════════════════════════════════════
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete user data from both databases (GDPR compliance)."""
        rapport_success = False
        analytics_success = False
        
        if self.rapport_available:
            try:
                # Delete from rapport DB
                async with self.rapport_db.pool.acquire() as conn:
                    await conn.execute("DELETE FROM user_profiles WHERE user_id = $1", user_id)
                rapport_success = True
                logger.info(f"Deleted user {user_id} from rapport database")
            except Exception as e:
                logger.error(f"Error deleting user {user_id} from rapport DB: {e}")
        
        if self.analytics_available:
            try:
                # Delete from analytics DB
                analytics_success = await self.analytics_db.delete_user_data(user_id)
                logger.info(f"Deleted user {user_id} from analytics database")
            except Exception as e:
                logger.error(f"Error deleting user {user_id} from analytics DB: {e}")
        
        return rapport_success or analytics_success
    
    # ════════════════════════════════════════════════════════════════
    # HEALTH & MONITORING
    # ════════════════════════════════════════════════════════════════
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of both databases."""
        status = {
            'analytics_db': {'available': False, 'error': None},
            'rapport_db': {'available': False, 'error': None}
        }
        
        # Test analytics DB
        if self.analytics_available:
            try:
                # Simple health check
                await self.analytics_db.get_interactions(limit=1)
                status['analytics_db']['available'] = True
            except Exception as e:
                status['analytics_db']['error'] = str(e)
                self.analytics_available = False
        
        # Test rapport DB
        if self.rapport_available:
            try:
                # Simple health check
                async with self.rapport_db.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                status['rapport_db']['available'] = True
            except Exception as e:
                status['rapport_db']['error'] = str(e)
                self.rapport_available = False
        
        return status
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics from both databases."""
        stats = {}
        
        if self.analytics_available:
            try:
                # Get analytics stats
                stats['analytics'] = await self.analytics_db.get_database_stats()
            except Exception as e:
                stats['analytics'] = {'error': str(e)}
        
        if self.rapport_available:
            try:
                # Get rapport stats
                async with self.rapport_db.pool.acquire() as conn:
                    rapport_stats = await conn.fetchrow("""
                        SELECT 
                            (SELECT COUNT(*) FROM user_profiles) as total_users,
                            (SELECT COUNT(*) FROM user_preferences) as total_preferences,
                            (SELECT COUNT(*) FROM emotional_states) as total_emotional_records,
                            (SELECT COUNT(*) FROM conversation_snapshots) as total_conversations
                    """)
                    stats['rapport'] = dict(rapport_stats) if rapport_stats else {}
            except Exception as e:
                stats['rapport'] = {'error': str(e)}
        
        return stats
    
    # ════════════════════════════════════════════════════════════════
    # MAINTENANCE
    # ════════════════════════════════════════════════════════════════
    
    async def cleanup_old_data(self) -> Dict[str, Any]:
        """Clean up old data from both databases."""
        results = {}
        
        if self.rapport_available:
            try:
                results['rapport'] = await self.rapport_db.cleanup_old_data()
            except Exception as e:
                results['rapport'] = {'error': str(e)}
        
        if self.analytics_available:
            try:
                # Analytics cleanup would go here
                results['analytics'] = {'message': 'No cleanup needed for analytics DB'}
            except Exception as e:
                results['analytics'] = {'error': str(e)}
        
        return results