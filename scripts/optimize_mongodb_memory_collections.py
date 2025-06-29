#!/usr/bin/env python3
"""
MongoDB Collection Optimizer for Hybrid Memory System
Creates optimal indexes and collection structures for memory queries.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBMemoryOptimizer:
    """Optimizes MongoDB collections for hybrid memory system performance."""
    
    def __init__(self, mongodb_uri: str):
        self.mongodb_uri = mongodb_uri
        self.client: AsyncIOMotorClient = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB."""
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client.nadia_memory
        
        # Test connection
        await self.client.admin.command('ismaster')
        logger.info("Connected to MongoDB")
    
    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
    
    async def optimize_memory_collections(self) -> Dict[str, Any]:
        """Optimize all memory-related collections."""
        results = {
            "collections_created": [],
            "indexes_created": [],
            "optimization_stats": {},
            "errors": []
        }
        
        try:
            # 1. Create and optimize memories collection
            await self._optimize_memories_collection(results)
            
            # 2. Create and optimize user_preferences collection
            await self._optimize_user_preferences_collection(results)
            
            # 3. Create and optimize conversation_embeddings collection
            await self._optimize_conversation_embeddings_collection(results)
            
            # 4. Create and optimize memory_analytics collection
            await self._optimize_memory_analytics_collection(results)
            
            # 5. Set up collection-level optimizations
            await self._apply_collection_level_optimizations(results)
            
            logger.info("MongoDB memory collections optimization completed successfully")
            
        except Exception as e:
            error_msg = f"Error during MongoDB optimization: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results
    
    async def _optimize_memories_collection(self, results: Dict[str, Any]):
        """Optimize the main memories collection."""
        collection_name = "memories"
        collection = self.db[collection_name]
        
        # Create collection if it doesn't exist
        collections = await self.db.list_collection_names()
        if collection_name not in collections:
            await self.db.create_collection(collection_name)
            results["collections_created"].append(collection_name)
            logger.info(f"Created collection: {collection_name}")
        
        # Define indexes for optimal memory queries
        indexes_to_create = [
            # Primary query patterns
            {"keys": [("user_id", 1), ("timestamp", -1)], "name": "user_timestamp_idx"},
            {"keys": [("user_id", 1), ("memory_type", 1)], "name": "user_memory_type_idx"},
            {"keys": [("user_id", 1), ("importance", -1)], "name": "user_importance_idx"},
            {"keys": [("user_id", 1), ("tier", 1)], "name": "user_tier_idx"},
            
            # Performance optimization indexes
            {"keys": [("importance", -1), ("timestamp", -1)], "name": "importance_timestamp_idx"},
            {"keys": [("memory_type", 1), ("tier", 1)], "name": "memory_type_tier_idx"},
            {"keys": [("retrieval_count", -1)], "name": "retrieval_count_idx"},
            {"keys": [("last_retrieved", -1)], "name": "last_retrieved_idx"},
            
            # Compound indexes for complex queries
            {"keys": [("user_id", 1), ("memory_type", 1), ("importance", -1)], "name": "user_type_importance_idx"},
            {"keys": [("user_id", 1), ("tier", 1), ("timestamp", -1)], "name": "user_tier_timestamp_idx"},
            
            # Text search index for content
            {"keys": [("content", "text"), ("metadata.tags", "text")], "name": "content_text_idx"},
            
            # Sparse indexes for optional fields
            {"keys": [("embedding", 1)], "name": "embedding_idx", "sparse": True},
            {"keys": [("metadata.conversation_id", 1)], "name": "conversation_id_idx", "sparse": True}
        ]
        
        await self._create_indexes(collection, indexes_to_create, results)
    
    async def _optimize_user_preferences_collection(self, results: Dict[str, Any]):
        """Optimize user preferences collection."""
        collection_name = "user_preferences"
        collection = self.db[collection_name]
        
        # Create collection if it doesn't exist
        collections = await self.db.list_collection_names()
        if collection_name not in collections:
            await self.db.create_collection(collection_name)
            results["collections_created"].append(collection_name)
            logger.info(f"Created collection: {collection_name}")
        
        indexes_to_create = [
            {"keys": [("user_id", 1)], "name": "user_id_idx", "unique": True},
            {"keys": [("updated_at", -1)], "name": "updated_at_idx"},
            {"keys": [("interests", 1)], "name": "interests_idx"},
            {"keys": [("conversation_patterns.last_topic", 1)], "name": "last_topic_idx", "sparse": True}
        ]
        
        await self._create_indexes(collection, indexes_to_create, results)
    
    async def _optimize_conversation_embeddings_collection(self, results: Dict[str, Any]):
        """Optimize conversation embeddings collection."""
        collection_name = "conversation_embeddings"
        collection = self.db[collection_name]
        
        # Create collection if it doesn't exist
        collections = await self.db.list_collection_names()
        if collection_name not in collections:
            await self.db.create_collection(collection_name)
            results["collections_created"].append(collection_name)
            logger.info(f"Created collection: {collection_name}")
        
        indexes_to_create = [
            {"keys": [("user_id", 1), ("timestamp", -1)], "name": "user_timestamp_idx"},
            {"keys": [("conversation_id", 1)], "name": "conversation_id_idx"},
            {"keys": [("embedding_model", 1)], "name": "embedding_model_idx"},
            {"keys": [("metadata.interaction_type", 1)], "name": "interaction_type_idx", "sparse": True},
            {"keys": [("message_text", "text")], "name": "message_text_idx"}
        ]
        
        await self._create_indexes(collection, indexes_to_create, results)
    
    async def _optimize_memory_analytics_collection(self, results: Dict[str, Any]):
        """Optimize memory analytics collection for performance monitoring."""
        collection_name = "memory_analytics"
        collection = self.db[collection_name]
        
        # Create collection if it doesn't exist
        collections = await self.db.list_collection_names()
        if collection_name not in collections:
            await self.db.create_collection(collection_name)
            results["collections_created"].append(collection_name)
            logger.info(f"Created collection: {collection_name}")
        
        indexes_to_create = [
            {"keys": [("user_id", 1), ("event_date", -1)], "name": "user_event_date_idx"},
            {"keys": [("event_type", 1), ("timestamp", -1)], "name": "event_type_timestamp_idx"},
            {"keys": [("memory_tier", 1)], "name": "memory_tier_idx"},
            {"keys": [("performance_metrics.latency_ms", 1)], "name": "latency_idx", "sparse": True}
        ]
        
        await self._create_indexes(collection, indexes_to_create, results)
    
    async def _create_indexes(self, collection, indexes_to_create: List[Dict], results: Dict[str, Any]):
        """Create indexes for a collection."""
        for index_def in indexes_to_create:
            try:
                keys = index_def["keys"]
                options = {k: v for k, v in index_def.items() if k != "keys"}
                
                # Check if index already exists
                existing_indexes = await collection.list_indexes().to_list(length=None)
                index_exists = any(
                    idx.get("name") == options.get("name") 
                    for idx in existing_indexes
                )
                
                if not index_exists:
                    await collection.create_index(keys, **options)
                    results["indexes_created"].append(f"{collection.name}.{options.get('name', 'unnamed')}")
                    logger.info(f"Created index: {collection.name}.{options.get('name')}")
                else:
                    logger.debug(f"Index already exists: {collection.name}.{options.get('name')}")
                    
            except Exception as e:
                error_msg = f"Error creating index {options.get('name', 'unnamed')} on {collection.name}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
    
    async def _apply_collection_level_optimizations(self, results: Dict[str, Any]):
        """Apply collection-level optimizations."""
        try:
            # Set up TTL indexes for automatic cleanup
            
            # 1. Memories collection - archive old low-importance memories
            memories_collection = self.db.memories
            try:
                # TTL index for archived memories (delete after 1 year)
                await memories_collection.create_index(
                    [("timestamp", 1)],
                    expireAfterSeconds=365 * 24 * 3600,  # 1 year
                    partialFilterExpression={"tier": "archived", "importance": {"$lt": 0.3}},
                    name="archived_memory_ttl_idx"
                )
                results["indexes_created"].append("memories.archived_memory_ttl_idx")
                logger.info("Created TTL index for archived memories")
            except Exception as e:
                logger.warning(f"Could not create TTL index for archived memories: {e}")
            
            # 2. Conversation embeddings - cleanup old embeddings
            conv_collection = self.db.conversation_embeddings
            try:
                # TTL index for old conversation embeddings (delete after 6 months)
                await conv_collection.create_index(
                    [("timestamp", 1)],
                    expireAfterSeconds=180 * 24 * 3600,  # 6 months
                    name="conversation_embedding_ttl_idx"
                )
                results["indexes_created"].append("conversation_embeddings.conversation_embedding_ttl_idx")
                logger.info("Created TTL index for conversation embeddings")
            except Exception as e:
                logger.warning(f"Could not create TTL index for conversation embeddings: {e}")
            
            # 3. Memory analytics - cleanup old analytics
            analytics_collection = self.db.memory_analytics
            try:
                # TTL index for old analytics (delete after 3 months)
                await analytics_collection.create_index(
                    [("timestamp", 1)],
                    expireAfterSeconds=90 * 24 * 3600,  # 3 months
                    name="memory_analytics_ttl_idx"
                )
                results["indexes_created"].append("memory_analytics.memory_analytics_ttl_idx")
                logger.info("Created TTL index for memory analytics")
            except Exception as e:
                logger.warning(f"Could not create TTL index for memory analytics: {e}")
            
            # Get collection statistics
            collections = ["memories", "user_preferences", "conversation_embeddings", "memory_analytics"]
            for coll_name in collections:
                try:
                    stats = await self.db.command("collStats", coll_name)
                    results["optimization_stats"][coll_name] = {
                        "count": stats.get("count", 0),
                        "size": stats.get("size", 0),
                        "avgObjSize": stats.get("avgObjSize", 0),
                        "totalIndexSize": stats.get("totalIndexSize", 0),
                        "indexCount": len(stats.get("indexDetails", {}))
                    }
                except Exception as e:
                    logger.warning(f"Could not get stats for collection {coll_name}: {e}")
                    
        except Exception as e:
            error_msg = f"Error applying collection-level optimizations: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
    
    async def create_sample_data(self, create_samples: bool = False) -> Dict[str, Any]:
        """Create sample data for testing (optional)."""
        if not create_samples:
            return {"message": "Sample data creation skipped"}
        
        results = {"samples_created": 0, "errors": []}
        
        try:
            # Sample memory document
            sample_memory = {
                "_id": "sample_user_1_1719675000",
                "user_id": "sample_user_1",
                "content": "I love hiking in the mountains, especially in Chipinque.",
                "timestamp": datetime.utcnow(),
                "memory_type": "preference",
                "importance": 0.8,
                "tier": "hot",
                "metadata": {
                    "role": "user",
                    "tags": ["hobbies", "outdoor_activities", "monterrey"],
                    "source": "conversation_history"
                },
                "embedding": [0.1] * 384,  # Sample embedding
                "retrieval_count": 3,
                "last_retrieved": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }
            
            # Insert sample memory
            memories_collection = self.db.memories
            await memories_collection.replace_one(
                {"_id": sample_memory["_id"]}, 
                sample_memory, 
                upsert=True
            )
            results["samples_created"] += 1
            
            # Sample user preferences
            sample_preferences = {
                "user_id": "sample_user_1",
                "interests": ["hiking", "mountains", "nature", "photography"],
                "conversation_patterns": {
                    "preferred_response_length": "medium",
                    "topics_discussed": ["hobbies", "travel", "work"],
                    "last_topic": "hiking"
                },
                "response_preferences": {
                    "tone": "friendly",
                    "detail_level": "moderate"
                },
                "updated_at": datetime.utcnow()
            }
            
            prefs_collection = self.db.user_preferences
            await prefs_collection.replace_one(
                {"user_id": sample_preferences["user_id"]}, 
                sample_preferences, 
                upsert=True
            )
            results["samples_created"] += 1
            
            logger.info(f"Created {results['samples_created']} sample documents")
            
        except Exception as e:
            error_msg = f"Error creating sample data: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        
        return results

async def main():
    """Main optimization function."""
    # Get MongoDB URI from environment
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        logger.error("MONGODB_URI environment variable not set")
        return
    
    # Parse command line arguments
    import sys
    create_samples = "--create-samples" in sys.argv
    
    optimizer = MongoDBMemoryOptimizer(mongodb_uri)
    
    try:
        await optimizer.connect()
        
        logger.info("Starting MongoDB memory collections optimization...")
        results = await optimizer.optimize_memory_collections()
        
        # Print results
        print("\n" + "="*60)
        print("MONGODB MEMORY OPTIMIZATION RESULTS")
        print("="*60)
        
        print(f"\nCollections Created: {len(results['collections_created'])}")
        for collection in results['collections_created']:
            print(f"  ✓ {collection}")
        
        print(f"\nIndexes Created: {len(results['indexes_created'])}")
        for index in results['indexes_created']:
            print(f"  ✓ {index}")
        
        if results['optimization_stats']:
            print(f"\nCollection Statistics:")
            for coll_name, stats in results['optimization_stats'].items():
                print(f"  📊 {coll_name}:")
                print(f"     Documents: {stats['count']}")
                print(f"     Size: {stats['size']:,} bytes")
                print(f"     Indexes: {stats['indexCount']}")
                print(f"     Index Size: {stats['totalIndexSize']:,} bytes")
        
        if results['errors']:
            print(f"\nErrors: {len(results['errors'])}")
            for error in results['errors']:
                print(f"  ❌ {error}")
        
        # Create sample data if requested
        if create_samples:
            print(f"\nCreating sample data...")
            sample_results = await optimizer.create_sample_data(True)
            print(f"Sample documents created: {sample_results['samples_created']}")
        
        print(f"\n✅ Optimization completed successfully!")
        print(f"MongoDB is now optimized for hybrid memory queries.")
        
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        print(f"\n❌ Optimization failed: {e}")
    
    finally:
        await optimizer.close()

if __name__ == "__main__":
    asyncio.run(main())