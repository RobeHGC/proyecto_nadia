"""
Memory strategies and agent configuration system for NADIA
Implements different memory management strategies for different agent types.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from utils.redis_mixin import RedisConnectionMixin
from utils.constants import *

# Import hybrid memory components
try:
    from memory.hybrid_memory_manager import HybridMemoryManager, MemoryItem, MemoryTier
    HYBRID_MEMORY_AVAILABLE = True
except ImportError:
    HYBRID_MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)

class MemoryStrategy(Enum):
    """Available memory strategies for agents."""
    REDIS_ONLY = "redis_only"  # Hot memory only, fast but limited
    HYBRID = "hybrid"  # Multi-tier memory system
    FULL_PERSISTENT = "full_persistent"  # Everything goes to persistent storage
    CONTEXT_AWARE = "context_aware"  # Dynamic strategy based on context

class AgentType(Enum):
    """Agent types with different memory needs."""
    SUPERVISOR = "supervisor"  # Main orchestrator
    LLM1 = "llm1"  # Creative generation (Gemini)
    LLM2 = "llm2"  # Response refinement (GPT-4o-mini)
    CONSTITUTION = "constitution"  # Safety checking
    RAG = "rag"  # Knowledge retrieval

@dataclass
class MemoryConfig:
    """Configuration for agent memory behavior."""
    strategy: MemoryStrategy
    context_window_tokens: int
    compression_threshold: float  # When to compress context (0.0-1.0)
    retrieval_k: int  # Number of memories to retrieve
    temperature: float  # For LLM configuration
    max_memory_age_days: int = 30
    memory_tier_strategy: str = "frequency"  # "frequency", "recency", "importance"
    auto_consolidation: bool = True
    consolidation_interval_hours: int = 24
    
    # Strategy-specific settings
    strategy_params: Dict[str, Any] = field(default_factory=dict)

class AgentConfigurationManager:
    """Manages agent configurations and memory strategies."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url
        self.db_pool = None
        self._config_cache: Dict[str, MemoryConfig] = {}
        self._last_cache_update: Optional[datetime] = None
        self.cache_ttl_seconds = 300  # 5 minutes
        
        # Default configurations
        self._default_configs = self._create_default_configs()
    
    def _create_default_configs(self) -> Dict[AgentType, MemoryConfig]:
        """Create default memory configurations for each agent type."""
        return {
            AgentType.SUPERVISOR: MemoryConfig(
                strategy=MemoryStrategy.HYBRID,
                context_window_tokens=8000,
                compression_threshold=0.75,
                retrieval_k=5,
                temperature=0.7,
                max_memory_age_days=30,
                memory_tier_strategy="importance",
                strategy_params={
                    "enable_cross_user_learning": False,
                    "priority_memory_types": ["conversation", "preference", "emotional"],
                    "context_enhancement_weight": 0.3
                }
            ),
            AgentType.LLM1: MemoryConfig(
                strategy=MemoryStrategy.HYBRID,
                context_window_tokens=6000,
                compression_threshold=0.80,
                retrieval_k=3,
                temperature=0.8,
                max_memory_age_days=14,
                memory_tier_strategy="recency",
                strategy_params={
                    "creative_context_boost": True,
                    "emotional_context_weight": 0.4,
                    "personality_consistency_check": True
                }
            ),
            AgentType.LLM2: MemoryConfig(
                strategy=MemoryStrategy.HYBRID,
                context_window_tokens=4000,
                compression_threshold=0.85,
                retrieval_k=2,
                temperature=0.6,
                max_memory_age_days=7,
                memory_tier_strategy="frequency",
                strategy_params={
                    "refinement_focus": True,
                    "style_consistency_weight": 0.5,
                    "brevity_optimization": True
                }
            ),
            AgentType.CONSTITUTION: MemoryConfig(
                strategy=MemoryStrategy.REDIS_ONLY,
                context_window_tokens=2000,
                compression_threshold=0.90,
                retrieval_k=1,
                temperature=0.3,
                max_memory_age_days=1,
                memory_tier_strategy="recency",
                strategy_params={
                    "safety_pattern_learning": True,
                    "violation_memory_persistence": True,
                    "context_sanitization": True
                }
            ),
            AgentType.RAG: MemoryConfig(
                strategy=MemoryStrategy.FULL_PERSISTENT,
                context_window_tokens=10000,
                compression_threshold=0.70,
                retrieval_k=8,
                temperature=0.5,
                max_memory_age_days=90,
                memory_tier_strategy="importance",
                strategy_params={
                    "semantic_enhancement": True,
                    "knowledge_graph_integration": False,  # Future feature
                    "multi_modal_memory": False,  # Future feature
                    "cross_conversation_learning": True
                }
            )
        }
    
    async def initialize(self):
        """Initialize the configuration manager."""
        if self.database_url:
            import asyncpg
            self.db_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=5,
                command_timeout=30
            )
            logger.info("Agent configuration manager initialized with database")
        else:
            logger.warning("No database URL provided, using default configurations only")
    
    async def close(self):
        """Close database connections."""
        if self.db_pool:
            await self.db_pool.close()
    
    async def get_agent_config(self, agent_type: AgentType) -> MemoryConfig:
        """Get configuration for a specific agent type."""
        # Check cache first
        cache_key = agent_type.value
        if self._is_cache_valid() and cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        # Try to load from database
        if self.db_pool:
            db_config = await self._load_config_from_db(agent_type)
            if db_config:
                self._config_cache[cache_key] = db_config
                return db_config
        
        # Fall back to default configuration
        default_config = self._default_configs.get(agent_type)
        if default_config:
            self._config_cache[cache_key] = default_config
            return default_config
        
        # Last resort: create minimal config
        logger.warning(f"No configuration found for agent type {agent_type}, using minimal config")
        minimal_config = MemoryConfig(
            strategy=MemoryStrategy.REDIS_ONLY,
            context_window_tokens=4000,
            compression_threshold=0.8,
            retrieval_k=3,
            temperature=0.7
        )
        self._config_cache[cache_key] = minimal_config
        return minimal_config
    
    async def update_agent_config(self, agent_type: AgentType, config: MemoryConfig) -> bool:
        """Update configuration for an agent type."""
        try:
            if self.db_pool:
                success = await self._save_config_to_db(agent_type, config)
                if success:
                    # Update cache
                    self._config_cache[agent_type.value] = config
                    self._last_cache_update = datetime.utcnow()
                    logger.info(f"Updated configuration for agent {agent_type.value}")
                    return True
            else:
                # Update in-memory cache only
                self._config_cache[agent_type.value] = config
                self._last_cache_update = datetime.utcnow()
                logger.info(f"Updated in-memory configuration for agent {agent_type.value}")
                return True
            
        except Exception as e:
            logger.error(f"Error updating agent config for {agent_type.value}: {e}")
            return False
        
        return False
    
    async def get_memory_strategy_for_context(
        self, 
        agent_type: AgentType,
        context_size: int,
        user_activity_level: str = "normal",
        conversation_complexity: str = "normal"
    ) -> Tuple[MemoryStrategy, Dict[str, Any]]:
        """Get optimal memory strategy based on context."""
        config = await self.get_agent_config(agent_type)
        
        # Base strategy from configuration
        strategy = config.strategy
        params = config.strategy_params.copy()
        
        # Dynamic adjustments based on context
        if strategy == MemoryStrategy.CONTEXT_AWARE:
            if context_size > config.context_window_tokens * 0.8:
                # High context load - use compression
                strategy = MemoryStrategy.HYBRID
                params.update({
                    "aggressive_compression": True,
                    "reduce_retrieval_k": True
                })
            elif user_activity_level == "high":
                # High activity - prefer fast access
                strategy = MemoryStrategy.REDIS_ONLY
                params.update({
                    "prioritize_speed": True,
                    "cache_aggressive": True
                })
            elif conversation_complexity == "high":
                # Complex conversation - need full memory
                strategy = MemoryStrategy.FULL_PERSISTENT
                params.update({
                    "deep_context_retrieval": True,
                    "cross_conversation_context": True
                })
            else:
                # Normal case - use hybrid
                strategy = MemoryStrategy.HYBRID
        
        return strategy, params
    
    async def get_consolidation_schedule(self) -> Dict[AgentType, datetime]:
        """Get next consolidation time for each agent type."""
        schedule = {}
        
        for agent_type in AgentType:
            config = await self.get_agent_config(agent_type)
            if config.auto_consolidation:
                # Calculate next consolidation time
                next_consolidation = datetime.utcnow() + timedelta(
                    hours=config.consolidation_interval_hours
                )
                schedule[agent_type] = next_consolidation
        
        return schedule
    
    async def get_prompt_template(self, template_id: str, variables: Dict[str, Any] = None) -> str:
        """Get prompt template with variable substitution."""
        if not self.db_pool:
            return ""
        
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT template, variables FROM prompt_library WHERE prompt_id = $1 AND active = true",
                    template_id
                )
                
                if not row:
                    logger.warning(f"Prompt template {template_id} not found")
                    return ""
                
                template = row["template"]
                default_variables = row["variables"] or {}
                
                # Merge default variables with provided variables
                all_variables = {**default_variables, **(variables or {})}
                
                # Substitute variables
                for key, value in all_variables.items():
                    template = template.replace(f"{{{{{key}}}}}", str(value))
                
                return template
                
        except Exception as e:
            logger.error(f"Error getting prompt template {template_id}: {e}")
            return ""
    
    async def optimize_config_for_performance(
        self, 
        agent_type: AgentType, 
        performance_metrics: Dict[str, float]
    ) -> bool:
        """Optimize agent configuration based on performance metrics."""
        try:
            config = await self.get_agent_config(agent_type)
            original_config = config
            optimized = False
            
            # Optimize based on latency
            if performance_metrics.get("avg_latency_ms", 0) > 2000:
                # High latency - reduce context and retrieval
                config.context_window_tokens = min(config.context_window_tokens, 4000)
                config.retrieval_k = max(1, config.retrieval_k - 1)
                config.compression_threshold = min(0.95, config.compression_threshold + 0.05)
                optimized = True
                logger.info(f"Optimized {agent_type.value} for latency")
            
            # Optimize based on memory usage
            if performance_metrics.get("memory_usage_mb", 0) > 500:
                # High memory usage - increase compression
                config.compression_threshold = min(0.95, config.compression_threshold + 0.10)
                config.max_memory_age_days = max(7, config.max_memory_age_days - 7)
                optimized = True
                logger.info(f"Optimized {agent_type.value} for memory usage")
            
            # Optimize based on context quality
            if performance_metrics.get("context_relevance_score", 1.0) < 0.6:
                # Low context quality - increase retrieval and reduce compression
                config.retrieval_k = min(10, config.retrieval_k + 1)
                config.compression_threshold = max(0.5, config.compression_threshold - 0.05)
                optimized = True
                logger.info(f"Optimized {agent_type.value} for context quality")
            
            # Save optimized configuration
            if optimized:
                success = await self.update_agent_config(agent_type, config)
                if success:
                    logger.info(f"Applied performance optimizations for {agent_type.value}")
                    return True
                else:
                    # Revert to original config if save failed
                    self._config_cache[agent_type.value] = original_config
                    return False
            
            return True  # No optimization needed
            
        except Exception as e:
            logger.error(f"Error optimizing config for {agent_type.value}: {e}")
            return False
    
    def _is_cache_valid(self) -> bool:
        """Check if configuration cache is still valid."""
        if self._last_cache_update is None:
            return False
        
        age_seconds = (datetime.utcnow() - self._last_cache_update).total_seconds()
        return age_seconds < self.cache_ttl_seconds
    
    async def _load_config_from_db(self, agent_type: AgentType) -> Optional[MemoryConfig]:
        """Load configuration from database."""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM agent_config WHERE agent_type = $1",
                    agent_type.value
                )
                
                if row:
                    # Convert database row to MemoryConfig
                    config = MemoryConfig(
                        strategy=MemoryStrategy(row["memory_strategy"]),
                        context_window_tokens=row["context_window_tokens"],
                        compression_threshold=float(row["compression_threshold"]),
                        retrieval_k=row["retrieval_k"],
                        temperature=float(row["temperature"]),
                        max_memory_age_days=row.get("max_memory_age_days", 30),
                        memory_tier_strategy=row.get("memory_tier_strategy", "frequency")
                    )
                    
                    # Add strategy-specific parameters from default config
                    default_config = self._default_configs.get(agent_type)
                    if default_config:
                        config.strategy_params = default_config.strategy_params.copy()
                    
                    return config
                
        except Exception as e:
            logger.error(f"Error loading config from database for {agent_type.value}: {e}")
        
        return None
    
    async def _save_config_to_db(self, agent_type: AgentType, config: MemoryConfig) -> bool:
        """Save configuration to database."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO agent_config (
                        agent_type, memory_strategy, context_window_tokens,
                        compression_threshold, retrieval_k, temperature,
                        max_memory_age_days, memory_tier_strategy, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (agent_type) DO UPDATE SET
                        memory_strategy = $2,
                        context_window_tokens = $3,
                        compression_threshold = $4,
                        retrieval_k = $5,
                        temperature = $6,
                        max_memory_age_days = $7,
                        memory_tier_strategy = $8,
                        updated_at = NOW()
                """,
                agent_type.value,
                config.strategy.value,
                config.context_window_tokens,
                config.compression_threshold,
                config.retrieval_k,
                config.temperature,
                config.max_memory_age_days,
                config.memory_tier_strategy
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving config to database for {agent_type.value}: {e}")
            return False

# Global configuration manager
_config_manager: Optional[AgentConfigurationManager] = None

async def get_agent_config_manager(database_url: str = None) -> AgentConfigurationManager:
    """Get global agent configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = AgentConfigurationManager(database_url)
        await _config_manager.initialize()
    return _config_manager

async def get_memory_config_for_agent(agent_type: AgentType) -> MemoryConfig:
    """Convenience function to get memory config for an agent."""
    config_manager = await get_agent_config_manager()
    return await config_manager.get_agent_config(agent_type)