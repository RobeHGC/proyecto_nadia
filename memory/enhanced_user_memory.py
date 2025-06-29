# memory/enhanced_user_memory.py
"""Enhanced UserMemoryManager with MongoDB persistent storage for RAG integration."""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from memory.user_memory import UserMemoryManager
from utils.config import Config

# RAG imports (with fallback if not available)
try:
    from knowledge.mongodb_manager import MongoDBManager, get_mongodb_manager, UserPreference
    MONGODB_AVAILABLE = True
except ImportError:
    logging.getLogger(__name__).warning("MongoDB not available for enhanced memory")
    MONGODB_AVAILABLE = False

logger = logging.getLogger(__name__)


class EnhancedUserMemoryManager(UserMemoryManager):
    """Enhanced UserMemoryManager with MongoDB persistent storage."""
    
    def __init__(self, redis_url: str = None, max_history_length: int = 50, max_context_size_kb: int = 100):
        """Initialize enhanced memory manager with MongoDB support."""
        super().__init__(redis_url, max_history_length, max_context_size_kb)
        
        # MongoDB integration
        self.mongodb_manager = None
        self._mongodb_initialized = False
        
        # Configuration for persistent storage
        self.persistent_storage_config = {
            "store_long_term_preferences": True,
            "conversation_retention_days": 30,
            "auto_extract_interests": True,
            "semantic_search_enabled": True
        }
        
        if MONGODB_AVAILABLE:
            logger.info("Enhanced memory manager with MongoDB support initialized")
    
    async def _initialize_mongodb(self):
        """Initialize MongoDB connection on first use."""
        if MONGODB_AVAILABLE and not self._mongodb_initialized:
            try:
                self.mongodb_manager = await get_mongodb_manager()
                self._mongodb_initialized = True
                logger.info("MongoDB initialized for enhanced memory")
            except Exception as e:
                logger.warning(f"Failed to initialize MongoDB for memory: {e}")
                self.mongodb_manager = None
    
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Get user context enhanced with persistent storage."""
        # Get base context from Redis
        context = await super().get_user_context(user_id)
        
        # Enhance with MongoDB data if available
        if self.persistent_storage_config["store_long_term_preferences"]:
            await self._enhance_context_with_persistent_data(user_id, context)
        
        return context
    
    async def _enhance_context_with_persistent_data(self, user_id: str, context: Dict[str, Any]):
        """Enhance context with persistent MongoDB data."""
        await self._initialize_mongodb()
        
        if not self.mongodb_manager:
            return
        
        try:
            # Get user preferences from MongoDB
            user_prefs = await self.mongodb_manager.get_user_preferences(user_id)
            
            if user_prefs:
                # Add persistent preferences to context
                context["persistent_data"] = {
                    "interests": user_prefs.get("interests", []),
                    "conversation_patterns": user_prefs.get("conversation_patterns", {}),
                    "response_preferences": user_prefs.get("response_preferences", {}),
                    "last_updated": user_prefs.get("last_updated")
                }
                
                # Add summary of user interests for prompt enhancement
                if user_prefs.get("interests"):
                    interests_summary = ", ".join(user_prefs["interests"][:5])
                    context["user_interests_summary"] = f"User has shown interest in: {interests_summary}"
                
                logger.debug(f"Enhanced context for user {user_id} with persistent data")
        
        except Exception as e:
            logger.error(f"Error enhancing context with persistent data: {e}")
    
    async def store_user_interaction_persistent(
        self, 
        user_id: str, 
        user_message: str, 
        ai_response: str,
        extracted_interests: List[str] = None,
        response_feedback: Dict[str, Any] = None
    ) -> bool:
        """Store user interaction in persistent storage for long-term learning."""
        await self._initialize_mongodb()
        
        if not self.mongodb_manager:
            return False
        
        try:
            # Extract interests from conversation if enabled
            if self.persistent_storage_config["auto_extract_interests"] and not extracted_interests:
                extracted_interests = await self._extract_interests_from_message(user_message)
            
            # Store/update user preferences
            if extracted_interests or response_feedback:
                success = await self._update_user_preferences(
                    user_id, 
                    extracted_interests, 
                    response_feedback
                )
                if success:
                    logger.debug(f"Updated persistent preferences for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing persistent interaction: {e}")
            return False
    
    async def _extract_interests_from_message(self, message: str) -> List[str]:
        """Extract potential interests from user message using simple heuristics."""
        # Simple keyword-based interest extraction
        # In a production system, this could use NLP/ML models
        
        interest_keywords = {
            "technology": ["tech", "computer", "coding", "programming", "AI", "software"],
            "sports": ["football", "soccer", "basketball", "tennis", "gym", "fitness"],
            "travel": ["vacation", "trip", "travel", "hotel", "flight", "country"],
            "food": ["restaurant", "cooking", "recipe", "food", "dinner", "lunch"],
            "music": ["song", "music", "band", "concert", "guitar", "piano"],
            "movies": ["movie", "film", "cinema", "actor", "netflix", "show"],
            "books": ["book", "read", "novel", "author", "library", "story"],
            "art": ["art", "painting", "drawing", "museum", "gallery", "design"],
            "gaming": ["game", "gaming", "play", "xbox", "playstation", "switch"],
            "health": ["health", "doctor", "medicine", "workout", "exercise", "yoga"]
        }
        
        message_lower = message.lower()
        detected_interests = []
        
        for interest_category, keywords in interest_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_interests.append(interest_category)
        
        return detected_interests[:3]  # Limit to top 3 interests per message
    
    async def _update_user_preferences(
        self, 
        user_id: str, 
        interests: List[str] = None,
        response_feedback: Dict[str, Any] = None
    ) -> bool:
        """Update user preferences in persistent storage."""
        if not self.mongodb_manager:
            return False
        
        try:
            # Get existing preferences
            existing_prefs = await self.mongodb_manager.get_user_preferences(user_id)
            
            # Merge interests
            current_interests = existing_prefs.get("interests", []) if existing_prefs else []
            if interests:
                # Add new interests, avoiding duplicates
                all_interests = list(set(current_interests + interests))
                # Keep most recent 15 interests
                current_interests = all_interests[-15:]
            
            # Merge response preferences
            current_response_prefs = existing_prefs.get("response_preferences", {}) if existing_prefs else {}
            if response_feedback:
                current_response_prefs.update(response_feedback)
            
            # Create updated preferences
            updated_prefs = UserPreference(
                user_id=user_id,
                interests=current_interests,
                conversation_patterns=existing_prefs.get("conversation_patterns", {}) if existing_prefs else {},
                response_preferences=current_response_prefs
            )
            
            # Store in MongoDB
            success = await self.mongodb_manager.store_user_preferences(updated_prefs)
            return success
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False
    
    async def get_user_conversation_history_semantic(
        self, 
        user_id: str, 
        query: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get user conversation history with optional semantic search."""
        await self._initialize_mongodb()
        
        # Get recent history from Redis (fallback/primary)
        recent_history = await self.get_conversation_history(user_id, limit)
        
        # If MongoDB available and semantic search enabled, enhance with semantic results
        if (self.mongodb_manager and 
            self.persistent_storage_config["semantic_search_enabled"] and 
            query):
            
            try:
                # This would use the vector search engine to find relevant conversations
                # For now, return Redis results (semantic search integration would go here)
                logger.debug(f"Semantic search for user {user_id} with query: {query}")
                
            except Exception as e:
                logger.warning(f"Semantic search failed, using Redis history: {e}")
        
        return recent_history
    
    async def cleanup_old_persistent_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        """Clean up old persistent data beyond retention period."""
        await self._initialize_mongodb()
        
        if not self.mongodb_manager:
            return {"error": "MongoDB not available"}
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Clean up old conversation embeddings
            collection = self.mongodb_manager.db[self.mongodb_manager.collections["conversation_embeddings"]]
            result = await collection.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            deleted_count = result.deleted_count
            
            logger.info(f"Cleaned up {deleted_count} old conversation embeddings")
            
            return {
                "deleted_embeddings": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up persistent data: {e}")
            return {"error": str(e)}
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        # Get base Redis stats
        base_stats = {
            "redis_available": True,
            "mongodb_available": self._mongodb_initialized,
            "persistent_storage_config": self.persistent_storage_config,
            "max_history_length": self.max_history_length,
            "max_context_size_kb": self.max_context_size_kb
        }
        
        # Add MongoDB stats if available
        if self.mongodb_manager:
            try:
                mongodb_stats = await self.mongodb_manager.get_collection_stats()
                base_stats["mongodb_collections"] = mongodb_stats
            except Exception as e:
                base_stats["mongodb_error"] = str(e)
        
        return base_stats


# Factory function to create enhanced memory manager
async def create_enhanced_memory_manager(redis_url: str = None) -> EnhancedUserMemoryManager:
    """Create and initialize enhanced memory manager."""
    manager = EnhancedUserMemoryManager(redis_url)
    await manager._initialize_mongodb()
    return manager