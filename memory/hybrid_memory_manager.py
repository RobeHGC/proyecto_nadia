"""
Hybrid Memory Manager for NADIA
Implements 3-tier memory architecture: Hot (Redis), Warm (PostgreSQL), Cold (MongoDB)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient
from sentence_transformers import SentenceTransformer

from utils.redis_mixin import RedisConnectionMixin
from utils.constants import *
from utils.datetime_helpers import now_iso, time_ago_text
from knowledge.local_embeddings_service import LocalEmbeddingsService

logger = logging.getLogger(__name__)

class MemoryTier(Enum):
    """Memory tiers for hybrid storage"""
    HOT = "hot"        # Redis - immediate access, recent conversations
    WARM = "warm"      # PostgreSQL - frequent access, structured data
    COLD = "cold"      # MongoDB - archival, semantic search
    ARCHIVED = "archived"  # Long-term storage, rarely accessed

@dataclass
class MemoryItem:
    """Standard memory item across all tiers"""
    user_id: str
    content: str
    timestamp: datetime
    memory_type: str  # 'conversation', 'preference', 'emotional', 'factual'
    importance: float  # 0.0 to 1.0
    tier: MemoryTier
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    retrieval_count: int = 0
    last_retrieved: Optional[datetime] = None

class HybridMemoryManager(RedisConnectionMixin):
    """
    Manages 3-tier memory system:
    - Redis: Hot memory (recent conversations, 0-7 days)
    - PostgreSQL: Warm memory (structured data, preferences, 7-30 days)
    - MongoDB: Cold memory (semantic search, long-term storage, 30+ days)
    """
    
    def __init__(self, database_url: str, mongodb_uri: Optional[str] = None):
        super().__init__()
        self.database_url = database_url
        self.mongodb_uri = mongodb_uri
        self.db_pool: Optional[asyncpg.Pool] = None
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.embeddings_service = LocalEmbeddingsService()
        
        # Memory tier thresholds (in days)
        self.HOT_TIER_DAYS = 7
        self.WARM_TIER_DAYS = 30
        self.COLD_TIER_DAYS = 90
        
        # Cache for agent configurations
        self._agent_configs: Dict[str, Dict] = {}
        self._prompt_templates: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize all storage connections"""
        # Initialize PostgreSQL pool
        self.db_pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30
        )
        
        # Initialize MongoDB if available
        if self.mongodb_uri:
            self.mongo_client = AsyncIOMotorClient(self.mongodb_uri)
            # Test connection
            await self.mongo_client.admin.command('ismaster')
            logger.info("MongoDB connection established")
        
        # Load agent configurations
        await self._load_agent_configs()
        await self._load_prompt_templates()
        
        logger.info("Hybrid Memory Manager initialized")
    
    async def close(self):
        """Close all connections"""
        if self.db_pool:
            await self.db_pool.close()
        if self.mongo_client:
            self.mongo_client.close()
    
    # === MEMORY STORAGE OPERATIONS ===
    
    async def store_memory(self, memory_item: MemoryItem, auto_tier: bool = True) -> str:
        """Store memory item in appropriate tier"""
        if auto_tier:
            memory_item.tier = self._determine_tier(memory_item)
        
        memory_id = f"{memory_item.user_id}_{int(memory_item.timestamp.timestamp())}"
        
        if memory_item.tier == MemoryTier.HOT:
            await self._store_in_redis(memory_id, memory_item)
        elif memory_item.tier == MemoryTier.WARM:
            await self._store_in_postgres(memory_id, memory_item)
        elif memory_item.tier in [MemoryTier.COLD, MemoryTier.ARCHIVED]:
            if self.mongo_client:
                await self._store_in_mongodb(memory_id, memory_item)
            else:
                # Fallback to PostgreSQL if MongoDB not available
                await self._store_in_postgres(memory_id, memory_item)
        
        # Update user memory profile
        await self._update_user_profile(memory_item.user_id, memory_item)
        
        logger.debug(f"Stored memory {memory_id} in {memory_item.tier.value} tier")
        return memory_id
    
    async def retrieve_memories(
        self, 
        user_id: str, 
        query: Optional[str] = None,
        memory_types: Optional[List[str]] = None,
        limit: int = 10,
        min_importance: float = 0.0
    ) -> List[MemoryItem]:
        """Retrieve memories across all tiers"""
        all_memories = []
        
        # Search hot tier (Redis)
        hot_memories = await self._search_redis(user_id, query, memory_types, limit)
        all_memories.extend(hot_memories)
        
        # Search warm tier (PostgreSQL)
        warm_memories = await self._search_postgres(user_id, query, memory_types, limit)
        all_memories.extend(warm_memories)
        
        # Search cold tier (MongoDB) - semantic search if query provided
        if self.mongo_client and query:
            cold_memories = await self._search_mongodb(user_id, query, memory_types, limit)
            all_memories.extend(cold_memories)
        
        # Filter by importance and sort
        filtered_memories = [
            m for m in all_memories 
            if m.importance >= min_importance
        ]
        
        # Sort by importance and recency
        filtered_memories.sort(
            key=lambda m: (m.importance, m.timestamp), 
            reverse=True
        )
        
        # Update retrieval stats
        for memory in filtered_memories[:limit]:
            await self._update_retrieval_stats(memory)
        
        return filtered_memories[:limit]
    
    # === MEMORY CONSOLIDATION ===
    
    async def consolidate_memories(self, user_id: str) -> Dict[str, int]:
        """Consolidate memories across tiers based on age and importance"""
        stats = {"promoted": 0, "demoted": 0, "archived": 0, "compressed": 0}
        
        # Get user's memory profile
        profile = await self._get_user_profile(user_id)
        if not profile:
            return stats
        
        current_time = datetime.utcnow()
        
        # Move memories between tiers based on age and access patterns
        
        # 1. Hot -> Warm (Redis to PostgreSQL)
        hot_memories = await self._get_redis_memories(user_id)
        for memory in hot_memories:
            age_days = (current_time - memory.timestamp).days
            if age_days > self.HOT_TIER_DAYS or memory.importance < 0.3:
                await self._move_memory(memory, MemoryTier.WARM)
                stats["demoted"] += 1
        
        # 2. Warm -> Cold (PostgreSQL to MongoDB)
        warm_memories = await self._get_postgres_memories(user_id)
        for memory in warm_memories:
            age_days = (current_time - memory.timestamp).days
            if age_days > self.WARM_TIER_DAYS or memory.retrieval_count == 0:
                if self.mongo_client:
                    await self._move_memory(memory, MemoryTier.COLD)
                    stats["demoted"] += 1
        
        # 3. Cold -> Archived (MongoDB archival)
        if self.mongo_client:
            cold_memories = await self._get_mongodb_memories(user_id)
            for memory in cold_memories:
                age_days = (current_time - memory.timestamp).days
                if age_days > self.COLD_TIER_DAYS:
                    memory.tier = MemoryTier.ARCHIVED
                    await self._store_in_mongodb(f"{user_id}_{int(memory.timestamp.timestamp())}", memory)
                    stats["archived"] += 1
        
        # Update consolidation timestamp
        await self._update_consolidation_timestamp(user_id)
        
        logger.info(f"Memory consolidation for {user_id}: {stats}")
        return stats
    
    # === CONFIGURATION MANAGEMENT ===
    
    async def get_agent_config(self, agent_type: str) -> Dict[str, Any]:
        """Get configuration for specific agent type"""
        if agent_type not in self._agent_configs:
            await self._load_agent_configs()
        
        return self._agent_configs.get(agent_type, {
            "memory_strategy": "hybrid",
            "context_window_tokens": 8000,
            "compression_threshold": 0.75,
            "retrieval_k": 5,
            "temperature": 0.7
        })
    
    async def get_prompt_template(self, prompt_id: str, variables: Dict[str, Any] = None) -> str:
        """Get prompt template with variable substitution"""
        if prompt_id not in self._prompt_templates:
            await self._load_prompt_templates()
        
        template_data = self._prompt_templates.get(prompt_id)
        if not template_data:
            logger.warning(f"Prompt template {prompt_id} not found")
            return ""
        
        template = template_data["template"]
        
        # Substitute variables
        if variables:
            for key, value in variables.items():
                template = template.replace(f"{{{{{key}}}}}", str(value))
        
        return template
    
    # === PRIVATE METHODS ===
    
    def _determine_tier(self, memory_item: MemoryItem) -> MemoryTier:
        """Determine appropriate tier for memory item"""
        age_hours = (datetime.utcnow() - memory_item.timestamp).total_seconds() / 3600
        
        if age_hours < 24 * self.HOT_TIER_DAYS and memory_item.importance >= 0.3:
            return MemoryTier.HOT
        elif age_hours < 24 * self.WARM_TIER_DAYS and memory_item.importance >= 0.2:
            return MemoryTier.WARM
        else:
            return MemoryTier.COLD
    
    async def _store_in_redis(self, memory_id: str, memory_item: MemoryItem):
        """Store memory in Redis (hot tier)"""
        r = await self._get_redis()
        
        memory_data = {
            "user_id": memory_item.user_id,
            "content": memory_item.content,
            "timestamp": memory_item.timestamp.isoformat(),
            "memory_type": memory_item.memory_type,
            "importance": memory_item.importance,
            "metadata": json.dumps(memory_item.metadata),
            "tier": memory_item.tier.value
        }
        
        # Store in user's memory hash
        await r.hset(f"memory:hot:{memory_item.user_id}", memory_id, json.dumps(memory_data))
        
        # Set expiration for hot tier
        await r.expire(f"memory:hot:{memory_item.user_id}", WEEK_IN_SECONDS)
    
    async def _store_in_postgres(self, memory_id: str, memory_item: MemoryItem):
        """Store memory in PostgreSQL (warm tier)"""
        async with self.db_pool.acquire() as conn:
            # Check if interaction metadata exists, if not create it
            await conn.execute("""
                INSERT INTO memory_interaction_metadata 
                (interaction_id, user_id, memory_importance, memory_tags, emotional_context)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (interaction_id) DO UPDATE SET
                memory_importance = $3,
                memory_tags = $4,
                emotional_context = $5,
                updated_at = NOW()
            """, 
            hash(memory_id) % 2147483647,  # Convert to valid integer
            memory_item.user_id,
            memory_item.importance,
            json.dumps(memory_item.metadata.get("tags", [])),
            json.dumps(memory_item.metadata.get("emotional_context", {}))
            )
    
    async def _store_in_mongodb(self, memory_id: str, memory_item: MemoryItem):
        """Store memory in MongoDB (cold tier)"""
        if not self.mongo_client:
            return
        
        # Generate embedding for semantic search
        if not memory_item.embedding:
            memory_item.embedding = await self.embeddings_service.get_embedding(memory_item.content)
        
        db = self.mongo_client.nadia_memory
        collection = db.memories
        
        doc = {
            "_id": memory_id,
            "user_id": memory_item.user_id,
            "content": memory_item.content,
            "timestamp": memory_item.timestamp,
            "memory_type": memory_item.memory_type,
            "importance": memory_item.importance,
            "tier": memory_item.tier.value,
            "metadata": memory_item.metadata,
            "embedding": memory_item.embedding,
            "retrieval_count": memory_item.retrieval_count,
            "last_retrieved": memory_item.last_retrieved,
            "created_at": datetime.utcnow()
        }
        
        await collection.replace_one({"_id": memory_id}, doc, upsert=True)
    
    async def _search_redis(self, user_id: str, query: Optional[str], memory_types: Optional[List[str]], limit: int) -> List[MemoryItem]:
        """Search memories in Redis"""
        r = await self._get_redis()
        
        memory_data = await r.hgetall(f"memory:hot:{user_id}")
        memories = []
        
        for memory_id, data_str in memory_data.items():
            try:
                data = json.loads(data_str)
                memory = MemoryItem(
                    user_id=data["user_id"],
                    content=data["content"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    memory_type=data["memory_type"],
                    importance=data["importance"],
                    tier=MemoryTier(data["tier"]),
                    metadata=json.loads(data["metadata"])
                )
                
                # Filter by memory type if specified
                if memory_types and memory.memory_type not in memory_types:
                    continue
                
                # Simple text search if query provided
                if query and query.lower() not in memory.content.lower():
                    continue
                
                memories.append(memory)
            except Exception as e:
                logger.error(f"Error parsing Redis memory {memory_id}: {e}")
        
        return memories[:limit]
    
    async def _search_postgres(self, user_id: str, query: Optional[str], memory_types: Optional[List[str]], limit: int) -> List[MemoryItem]:
        """Search memories in PostgreSQL"""
        # This would typically join with interactions table
        # For now, return empty list as placeholder
        return []
    
    async def _search_mongodb(self, user_id: str, query: str, memory_types: Optional[List[str]], limit: int) -> List[MemoryItem]:
        """Search memories in MongoDB using embedding similarity"""
        if not self.mongo_client:
            return []
        
        # Generate query embedding
        query_embedding = await self.embeddings_service.get_embedding(query)
        
        db = self.mongo_client.nadia_memory
        collection = db.memories
        
        # MongoDB aggregation pipeline for similarity search
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$addFields": {
                    "similarity": {
                        "$let": {
                            "vars": {
                                "dot_product": {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": "$embedding"}]},
                                        "initialValue": 0,
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {"$multiply": [
                                                    {"$arrayElemAt": ["$embedding", "$$this"]},
                                                    {"$arrayElemAt": [query_embedding, "$$this"]}
                                                ]}
                                            ]
                                        }
                                    }
                                }
                            },
                            "in": "$$dot_product"
                        }
                    }
                }
            },
            {"$sort": {"similarity": -1}},
            {"$limit": limit}
        ]
        
        memories = []
        async for doc in collection.aggregate(pipeline):
            memory = MemoryItem(
                user_id=doc["user_id"],
                content=doc["content"],
                timestamp=doc["timestamp"],
                memory_type=doc["memory_type"],
                importance=doc["importance"],
                tier=MemoryTier(doc["tier"]),
                metadata=doc["metadata"],
                embedding=doc["embedding"],
                retrieval_count=doc.get("retrieval_count", 0),
                last_retrieved=doc.get("last_retrieved")
            )
            memories.append(memory)
        
        return memories
    
    async def _load_agent_configs(self):
        """Load agent configurations from database"""
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM agent_config")
            
            for row in rows:
                self._agent_configs[row["agent_type"]] = dict(row)
    
    async def _load_prompt_templates(self):
        """Load prompt templates from database"""
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM prompt_library WHERE active = true")
            
            for row in rows:
                self._prompt_templates[row["prompt_id"]] = dict(row)
    
    async def _update_user_profile(self, user_id: str, memory_item: MemoryItem):
        """Update user memory profile"""
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO memory_user_profiles 
                (user_id, last_interaction, total_interactions, memory_tier)
                VALUES ($1, $2, 1, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                last_interaction = $2,
                total_interactions = memory_user_profiles.total_interactions + 1,
                memory_tier = $3,
                updated_at = NOW()
            """, user_id, memory_item.timestamp, memory_item.tier.value)
    
    async def _get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get user memory profile"""
        if not self.db_pool:
            return None
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memory_user_profiles WHERE user_id = $1", 
                user_id
            )
            return dict(row) if row else None
    
    async def _update_retrieval_stats(self, memory: MemoryItem):
        """Update memory retrieval statistics"""
        memory.retrieval_count += 1
        memory.last_retrieved = datetime.utcnow()
        
        # Update in appropriate tier
        if memory.tier == MemoryTier.HOT:
            # Update Redis
            pass
        elif memory.tier == MemoryTier.WARM:
            # Update PostgreSQL
            pass
        elif memory.tier in [MemoryTier.COLD, MemoryTier.ARCHIVED]:
            # Update MongoDB
            if self.mongo_client:
                db = self.mongo_client.nadia_memory
                await db.memories.update_one(
                    {"user_id": memory.user_id, "timestamp": memory.timestamp},
                    {
                        "$inc": {"retrieval_count": 1},
                        "$set": {"last_retrieved": memory.last_retrieved}
                    }
                )
    
    async def _move_memory(self, memory: MemoryItem, target_tier: MemoryTier):
        """Move memory between tiers"""
        # Store in target tier
        old_tier = memory.tier
        memory.tier = target_tier
        
        memory_id = f"{memory.user_id}_{int(memory.timestamp.timestamp())}"
        
        if target_tier == MemoryTier.WARM:
            await self._store_in_postgres(memory_id, memory)
        elif target_tier in [MemoryTier.COLD, MemoryTier.ARCHIVED]:
            await self._store_in_mongodb(memory_id, memory)
        
        # Remove from old tier (if different)
        if old_tier == MemoryTier.HOT and target_tier != MemoryTier.HOT:
            r = await self._get_redis()
            await r.hdel(f"memory:hot:{memory.user_id}", memory_id)
    
    async def _get_redis_memories(self, user_id: str) -> List[MemoryItem]:
        """Get all memories from Redis for a user"""
        return await self._search_redis(user_id, None, None, 1000)
    
    async def _get_postgres_memories(self, user_id: str) -> List[MemoryItem]:
        """Get all memories from PostgreSQL for a user"""
        return await self._search_postgres(user_id, None, None, 1000)
    
    async def _get_mongodb_memories(self, user_id: str) -> List[MemoryItem]:
        """Get all memories from MongoDB for a user"""
        if not self.mongo_client:
            return []
        
        db = self.mongo_client.nadia_memory
        memories = []
        
        async for doc in db.memories.find({"user_id": user_id}):
            memory = MemoryItem(
                user_id=doc["user_id"],
                content=doc["content"],
                timestamp=doc["timestamp"],
                memory_type=doc["memory_type"],
                importance=doc["importance"],
                tier=MemoryTier(doc["tier"]),
                metadata=doc["metadata"],
                embedding=doc.get("embedding"),
                retrieval_count=doc.get("retrieval_count", 0),
                last_retrieved=doc.get("last_retrieved")
            )
            memories.append(memory)
        
        return memories
    
    async def _update_consolidation_timestamp(self, user_id: str):
        """Update last consolidation timestamp for user"""
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE memory_user_profiles 
                SET last_memory_consolidation = NOW()
                WHERE user_id = $1
            """, user_id)