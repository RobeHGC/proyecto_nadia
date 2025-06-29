# knowledge/mongodb_manager.py
"""MongoDB connection and operations manager for RAG system."""
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import motor.motor_asyncio
from pymongo import IndexModel, TEXT
from pymongo.errors import DuplicateKeyError, ConnectionFailure

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeDocument:
    """Knowledge document structure for RAG."""
    id: str
    title: str
    content: str
    source: str
    category: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class UserPreference:
    """User preference and learning data."""
    user_id: str
    interests: List[str]
    conversation_patterns: Dict[str, Any]
    response_preferences: Dict[str, Any]
    last_updated: Optional[datetime] = None


class MongoDBManager:
    """MongoDB connection and operations manager."""
    
    def __init__(self, mongodb_url: str = None):
        """Initialize MongoDB connection."""
        self.mongodb_url = mongodb_url or os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.database_name = os.getenv("MONGODB_DATABASE", "nadia_knowledge")
        self.client = None
        self.db = None
        
        # Collection names
        self.collections = {
            "knowledge_documents": "knowledge_documents",
            "conversation_embeddings": "conversation_embeddings", 
            "user_preferences": "user_preferences",
            "nadia_knowledge_base": "nadia_knowledge_base"
        }
    
    async def connect(self) -> bool:
        """Establish MongoDB connection and setup collections."""
        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(self.mongodb_url)
            self.db = self.client[self.database_name]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"MongoDB connected successfully to {self.database_name}")
            
            # Setup collections and indexes
            await self._setup_collections()
            return True
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False
    
    async def _setup_collections(self):
        """Setup collections and create indexes."""
        # Knowledge documents collection
        knowledge_coll = self.db[self.collections["knowledge_documents"]]
        await knowledge_coll.create_indexes([
            IndexModel([("source", 1)]),
            IndexModel([("category", 1)]),
            IndexModel([("title", TEXT), ("content", TEXT)]),
            IndexModel([("created_at", -1)])
        ])
        
        # User preferences collection
        prefs_coll = self.db[self.collections["user_preferences"]]
        await prefs_coll.create_indexes([
            IndexModel([("user_id", 1)], unique=True),
            IndexModel([("last_updated", -1)])
        ])
        
        # Conversation embeddings collection  
        embeddings_coll = self.db[self.collections["conversation_embeddings"]]
        await embeddings_coll.create_indexes([
            IndexModel([("user_id", 1)]),
            IndexModel([("conversation_id", 1)]),
            IndexModel([("created_at", -1)])
        ])
        
        logger.info("MongoDB collections and indexes created successfully")
    
    async def store_knowledge_document(self, document: KnowledgeDocument) -> bool:
        """Store a knowledge document."""
        try:
            doc_data = {
                "_id": document.id,
                "title": document.title,
                "content": document.content,
                "source": document.source,
                "category": document.category,
                "embedding": document.embedding,
                "metadata": document.metadata or {},
                "created_at": document.created_at or datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            collection = self.db[self.collections["knowledge_documents"]]
            await collection.replace_one({"_id": document.id}, doc_data, upsert=True)
            logger.info(f"Stored knowledge document: {document.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store knowledge document {document.id}: {e}")
            return False
    
    async def search_knowledge_documents(
        self, 
        query: str = None,
        category: str = None,
        embedding: List[float] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search knowledge documents by text or embedding similarity."""
        try:
            collection = self.db[self.collections["knowledge_documents"]]
            search_filter = {}
            
            # Text search
            if query:
                search_filter["$text"] = {"$search": query}
            
            # Category filter
            if category:
                search_filter["category"] = category
            
            # If we have embedding, we'll do vector similarity (implemented later)
            # For now, do text-based search
            cursor = collection.find(search_filter).limit(limit)
            documents = await cursor.to_list(length=limit)
            
            logger.info(f"Found {len(documents)} knowledge documents for query: {query}")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to search knowledge documents: {e}")
            return []
    
    async def store_user_preferences(self, preferences: UserPreference) -> bool:
        """Store or update user preferences."""
        try:
            pref_data = {
                "user_id": preferences.user_id,
                "interests": preferences.interests,
                "conversation_patterns": preferences.conversation_patterns,
                "response_preferences": preferences.response_preferences,
                "last_updated": datetime.now(timezone.utc)
            }
            
            collection = self.db[self.collections["user_preferences"]]
            await collection.replace_one(
                {"user_id": preferences.user_id}, 
                pref_data, 
                upsert=True
            )
            logger.info(f"Updated preferences for user: {preferences.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store user preferences for {preferences.user_id}: {e}")
            return False
    
    async def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preferences by user ID."""
        try:
            collection = self.db[self.collections["user_preferences"]]
            preferences = await collection.find_one({"user_id": user_id})
            return preferences
            
        except Exception as e:
            logger.error(f"Failed to get user preferences for {user_id}: {e}")
            return None
    
    async def store_conversation_embedding(
        self,
        user_id: str,
        conversation_id: str,
        message_text: str,
        embedding: List[float],
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Store conversation embedding for semantic search."""
        try:
            doc_data = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_text": message_text,
                "embedding": embedding,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc)
            }
            
            collection = self.db[self.collections["conversation_embeddings"]]
            await collection.insert_one(doc_data)
            logger.debug(f"Stored conversation embedding for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store conversation embedding: {e}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, int]:
        """Get statistics for all collections."""
        stats = {}
        try:
            for name, collection_name in self.collections.items():
                collection = self.db[collection_name]
                count = await collection.count_documents({})
                stats[name] = count
            
            logger.info(f"MongoDB collection stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Global MongoDB manager instance
_mongodb_manager: Optional[MongoDBManager] = None


async def get_mongodb_manager() -> MongoDBManager:
    """Get global MongoDB manager instance."""
    global _mongodb_manager
    if _mongodb_manager is None:
        _mongodb_manager = MongoDBManager()
        await _mongodb_manager.connect()
    return _mongodb_manager