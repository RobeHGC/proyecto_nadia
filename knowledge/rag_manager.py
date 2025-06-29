# knowledge/rag_manager.py
"""RAG (Retrieval-Augmented Generation) manager for knowledge enhancement."""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .mongodb_manager import MongoDBManager, get_mongodb_manager, UserPreference
from .embeddings_service import EmbeddingsService, get_embeddings_service

# Import local embeddings service for fallback/alternative
try:
    from .local_embeddings_service import LocalEmbeddingsService, get_local_embeddings_service
    LOCAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    LOCAL_EMBEDDINGS_AVAILABLE = False
from .vector_search import VectorSearchEngine, get_vector_search_engine, SearchQuery, SearchResult

# Import hybrid memory manager for integration
try:
    from memory.hybrid_memory_manager import HybridMemoryManager, MemoryItem, MemoryTier
    HYBRID_MEMORY_AVAILABLE = True
except ImportError:
    HYBRID_MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Context retrieved for RAG enhancement."""
    relevant_documents: List[SearchResult]
    user_preferences: Optional[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]
    context_summary: str
    confidence_score: float


@dataclass
class RAGResponse:
    """Response from RAG system with enhancement context."""
    enhanced_prompt: str
    context_used: RAGContext
    success: bool
    error_message: Optional[str] = None


class RAGManager:
    """Manages Retrieval-Augmented Generation for NADIA."""
    
    def __init__(
        self, 
        mongodb_manager: MongoDBManager = None,
        embeddings_service: EmbeddingsService = None,
        vector_search: VectorSearchEngine = None,
        use_local_embeddings: bool = False,
        local_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        hybrid_memory_manager: HybridMemoryManager = None,
        enable_memory_integration: bool = True
    ):
        """Initialize RAG manager."""
        self.mongodb_manager = mongodb_manager
        self.embeddings_service = embeddings_service
        self.vector_search = vector_search
        self.use_local_embeddings = use_local_embeddings
        self.local_model = local_model
        self.hybrid_memory_manager = hybrid_memory_manager
        self.enable_memory_integration = enable_memory_integration and HYBRID_MEMORY_AVAILABLE
        self._initialized = False
        
        # RAG configuration
        self.config = {
            "max_context_length": 2000,  # Max characters for context injection
            "min_similarity_threshold": 0.7,  # Min similarity for document relevance
            "max_documents": 3,  # Max documents to include in context
            "include_conversation_history": True,
            "include_user_preferences": True,
            "context_weight": 0.3,  # How much to weight context vs original prompt
            "embeddings_type": "local" if use_local_embeddings else "openai",
            "memory_integration": {
                "enabled": self.enable_memory_integration,
                "retrieve_memories": True,
                "store_interactions": True,
                "memory_weight": 0.2,  # Weight for hybrid memory vs traditional RAG
                "min_memory_importance": 0.4
            }
        }
    
    async def initialize(self):
        """Initialize all services."""
        if not self._initialized:
            if self.mongodb_manager is None:
                self.mongodb_manager = await get_mongodb_manager()
            
            # Initialize embeddings service based on configuration
            if self.embeddings_service is None:
                if self.use_local_embeddings and LOCAL_EMBEDDINGS_AVAILABLE:
                    logger.info(f"Initializing local embeddings service with model: {self.local_model}")
                    self.embeddings_service = get_local_embeddings_service(self.local_model)
                else:
                    if self.use_local_embeddings and not LOCAL_EMBEDDINGS_AVAILABLE:
                        logger.warning("Local embeddings requested but not available, falling back to OpenAI")
                    logger.info("Initializing OpenAI embeddings service")
                    self.embeddings_service = get_embeddings_service()
            
            if self.vector_search is None:
                self.vector_search = await get_vector_search_engine()
            
            # Initialize hybrid memory manager if enabled
            if self.enable_memory_integration and self.hybrid_memory_manager is None:
                import os
                database_url = os.getenv('DATABASE_URL')
                mongodb_uri = os.getenv('MONGODB_URI')
                if database_url:
                    self.hybrid_memory_manager = HybridMemoryManager(database_url, mongodb_uri)
                    await self.hybrid_memory_manager.initialize()
                    logger.info("Hybrid memory manager initialized for RAG integration")
                else:
                    logger.warning("DATABASE_URL not available, disabling memory integration")
                    self.enable_memory_integration = False
                    self.config["memory_integration"]["enabled"] = False
            
            self._initialized = True
            logger.info("RAG Manager initialized successfully")
    
    async def enhance_prompt_with_context(
        self, 
        user_message: str, 
        user_id: str,
        conversation_context: Dict[str, Any] = None
    ) -> RAGResponse:
        """Enhance a prompt with relevant context from knowledge base and hybrid memory."""
        await self.initialize()
        
        try:
            # Step 1: Retrieve relevant knowledge documents
            relevant_docs = await self._retrieve_relevant_documents(user_message)
            
            # Step 2: Get user preferences and history
            user_prefs = await self._get_user_context(user_id)
            conversation_history = await self._get_relevant_conversation_history(user_id, user_message)
            
            # Step 3: HYBRID MEMORY INTEGRATION - Retrieve relevant memories
            hybrid_memories = []
            if self.enable_memory_integration and self.hybrid_memory_manager:
                hybrid_memories = await self._retrieve_hybrid_memories(user_id, user_message)
            
            # Step 4: Build enhanced context summary including hybrid memories
            context_summary = await self._build_enhanced_context_summary(
                relevant_docs, 
                user_prefs, 
                conversation_history,
                hybrid_memories
            )
            
            # Step 5: Calculate enhanced confidence score
            confidence_score = self._calculate_enhanced_confidence_score(
                relevant_docs, user_prefs, conversation_history, hybrid_memories
            )
            
            # Step 6: Create enhanced RAG context
            rag_context = RAGContext(
                relevant_documents=relevant_docs,
                user_preferences=user_prefs,
                conversation_history=conversation_history,
                context_summary=context_summary,
                confidence_score=confidence_score
            )
            
            # Add hybrid memories to RAG context metadata
            if hasattr(rag_context, 'metadata'):
                rag_context.metadata['hybrid_memories'] = hybrid_memories
            else:
                rag_context.metadata = {'hybrid_memories': hybrid_memories}
            
            # Step 7: Enhance the original prompt
            enhanced_prompt = await self._create_enhanced_prompt(user_message, rag_context)
            
            logger.info(f"Enhanced prompt for user {user_id} with {len(relevant_docs)} docs and {len(hybrid_memories)} memories")
            
            return RAGResponse(
                enhanced_prompt=enhanced_prompt,
                context_used=rag_context,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error enhancing prompt with RAG: {e}")
            return RAGResponse(
                enhanced_prompt=user_message,  # Fallback to original
                context_used=RAGContext([], None, [], "", 0.0),
                success=False,
                error_message=str(e)
            )
    
    async def _retrieve_relevant_documents(self, user_message: str) -> List[SearchResult]:
        """Retrieve relevant documents from knowledge base."""
        try:
            # Create search query
            search_query = SearchQuery(
                text=user_message,
                min_similarity=self.config["min_similarity_threshold"],
                max_results=self.config["max_documents"]
            )
            
            # Search for relevant documents
            results = await self.vector_search.search_similar_documents(search_query)
            
            logger.debug(f"Retrieved {len(results)} relevant documents")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving relevant documents: {e}")
            return []
    
    async def _get_user_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preferences and context."""
        if not self.config["include_user_preferences"]:
            return None
        
        try:
            user_prefs = await self.mongodb_manager.get_user_preferences(user_id)
            return user_prefs
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return None
    
    async def _get_relevant_conversation_history(self, user_id: str, user_message: str) -> List[Dict[str, Any]]:
        """Get relevant conversation history using semantic search."""
        if not self.config["include_conversation_history"]:
            return []
        
        try:
            history = await self.vector_search.search_conversation_history(
                user_id=user_id,
                query_text=user_message,
                limit=3,
                min_similarity=0.6
            )
            
            logger.debug(f"Retrieved {len(history)} relevant conversation entries")
            return history
            
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def _build_context_summary(
        self, 
        documents: List[SearchResult], 
        user_prefs: Optional[Dict[str, Any]], 
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Build a concise context summary for prompt enhancement."""
        context_parts = []
        
        # Add relevant documents
        if documents:
            doc_summaries = []
            for doc in documents:
                # Truncate long content
                content_preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                doc_summaries.append(f"- {doc.title}: {content_preview}")
            
            context_parts.append("Relevant Knowledge:")
            context_parts.extend(doc_summaries)
        
        # Add user preferences
        if user_prefs and user_prefs.get("interests"):
            interests = ", ".join(user_prefs["interests"][:5])  # Limit to top 5
            context_parts.append(f"User Interests: {interests}")
        
        # Add conversation patterns
        if conversation_history:
            context_parts.append("Related Previous Topics:")
            for conv in conversation_history[:2]:  # Limit to most relevant
                msg_preview = conv["message_text"][:100] + "..." if len(conv["message_text"]) > 100 else conv["message_text"]
                context_parts.append(f"- {msg_preview}")
        
        context_summary = "\n".join(context_parts)
        
        # Truncate if too long
        if len(context_summary) > self.config["max_context_length"]:
            context_summary = context_summary[:self.config["max_context_length"]] + "..."
        
        return context_summary
    
    def _calculate_confidence_score(
        self, 
        documents: List[SearchResult], 
        user_prefs: Optional[Dict[str, Any]], 
        conversation_history: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence score for the retrieved context."""
        score = 0.0
        
        # Document relevance score (0-0.6)
        if documents:
            avg_similarity = sum(doc.similarity_score for doc in documents) / len(documents)
            score += min(avg_similarity * 0.6, 0.6)
        
        # User preferences availability (0-0.2)
        if user_prefs and user_prefs.get("interests"):
            score += 0.2
        
        # Conversation history relevance (0-0.2)
        if conversation_history:
            avg_conv_similarity = sum(conv["similarity_score"] for conv in conversation_history) / len(conversation_history)
            score += min(avg_conv_similarity * 0.2, 0.2)
        
        return min(score, 1.0)
    
    async def _create_enhanced_prompt(self, original_message: str, rag_context: RAGContext) -> str:
        """Create enhanced prompt with RAG context."""
        if not rag_context.context_summary or rag_context.confidence_score < 0.3:
            # Low confidence, use original message
            return original_message
        
        # Create enhanced prompt template
        enhanced_prompt = f"""User Message: {original_message}

Relevant Context:
{rag_context.context_summary}

Instructions: Use the relevant context above to provide a more informed and personalized response. Stay true to Nadia's personality while incorporating relevant knowledge when appropriate."""
        
        return enhanced_prompt
    
    async def store_user_interaction(
        self, 
        user_id: str, 
        user_message: str, 
        ai_response: str,
        conversation_id: str = None
    ) -> bool:
        """Store user interaction for future learning."""
        await self.initialize()
        
        try:
            # Generate embedding for the interaction
            interaction_text = f"User: {user_message}\nNadia: {ai_response}"
            embedding_result = await self.embeddings_service.get_embedding(interaction_text)
            
            if not embedding_result:
                logger.warning(f"Failed to generate embedding for interaction with user {user_id}")
                return False
            
            # Store conversation embedding
            success = await self.mongodb_manager.store_conversation_embedding(
                user_id=user_id,
                conversation_id=conversation_id or f"conv_{user_id}_{int(datetime.now().timestamp())}",
                message_text=user_message,
                embedding=embedding_result.embedding,
                metadata={
                    "ai_response": ai_response,
                    "interaction_text": interaction_text,
                    "embedding_model": embedding_result.model,
                    "token_count": embedding_result.token_count
                }
            )
            
            if success:
                logger.debug(f"Stored interaction embedding for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error storing user interaction: {e}")
            return False
    
    async def learn_user_preferences(
        self, 
        user_id: str, 
        interests: List[str] = None,
        response_feedback: Dict[str, Any] = None
    ) -> bool:
        """Learn and update user preferences."""
        await self.initialize()
        
        try:
            # Get existing preferences
            existing_prefs = await self.mongodb_manager.get_user_preferences(user_id)
            
            # Merge with new data
            if existing_prefs:
                current_interests = existing_prefs.get("interests", [])
                current_patterns = existing_prefs.get("conversation_patterns", {})
                current_response_prefs = existing_prefs.get("response_preferences", {})
            else:
                current_interests = []
                current_patterns = {}
                current_response_prefs = {}
            
            # Update interests
            if interests:
                # Add new interests, remove duplicates
                all_interests = list(set(current_interests + interests))
                # Keep most recent 20 interests
                current_interests = all_interests[-20:]
            
            # Update response preferences
            if response_feedback:
                current_response_prefs.update(response_feedback)
            
            # Create updated preferences
            updated_prefs = UserPreference(
                user_id=user_id,
                interests=current_interests,
                conversation_patterns=current_patterns,
                response_preferences=current_response_prefs
            )
            
            success = await self.mongodb_manager.store_user_preferences(updated_prefs)
            if success:
                logger.info(f"Updated preferences for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error learning user preferences: {e}")
            return False
    
    async def get_rag_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics."""
        await self.initialize()
        
        try:
            # Get component stats
            search_stats = await self.vector_search.get_search_stats()
            mongodb_stats = await self.mongodb_manager.get_collection_stats()
            embeddings_stats = self.embeddings_service.get_cache_stats()
            
            return {
                "rag_config": self.config,
                "mongodb_stats": mongodb_stats,
                "embeddings_stats": embeddings_stats,
                "search_stats": search_stats,
                "system_status": "operational" if self._initialized else "not_initialized"
            }
            
        except Exception as e:
            logger.error(f"Error getting RAG stats: {e}")
            return {"error": str(e)}
    
    # === HYBRID MEMORY INTEGRATION METHODS ===
    
    async def _retrieve_hybrid_memories(self, user_id: str, user_message: str) -> List[Dict[str, Any]]:
        """Retrieve relevant memories from hybrid memory system."""
        try:
            if not self.hybrid_memory_manager:
                return []
            
            # Retrieve relevant memories
            memories = await self.hybrid_memory_manager.retrieve_memories(
                user_id=user_id,
                query=user_message,
                memory_types=['conversation', 'preference', 'factual', 'emotional'],
                limit=3,
                min_importance=self.config["memory_integration"]["min_memory_importance"]
            )
            
            # Convert MemoryItem objects to dictionaries for context
            memory_dicts = []
            for memory in memories:
                memory_dict = {
                    'content': memory.content,
                    'memory_type': memory.memory_type,
                    'importance': memory.importance,
                    'timestamp': memory.timestamp.isoformat(),
                    'tier': memory.tier.value,
                    'metadata': memory.metadata,
                    'retrieval_count': memory.retrieval_count
                }
                memory_dicts.append(memory_dict)
            
            logger.debug(f"Retrieved {len(memory_dicts)} hybrid memories for user {user_id}")
            return memory_dicts
            
        except Exception as e:
            logger.error(f"Error retrieving hybrid memories: {e}")
            return []
    
    async def _build_enhanced_context_summary(
        self, 
        documents: List[SearchResult], 
        user_prefs: Optional[Dict[str, Any]], 
        conversation_history: List[Dict[str, Any]],
        hybrid_memories: List[Dict[str, Any]]
    ) -> str:
        """Build enhanced context summary including hybrid memories."""
        context_parts = []
        
        # Add relevant documents (traditional RAG)
        if documents:
            doc_summaries = []
            for doc in documents:
                content_preview = doc.content[:150] + "..." if len(doc.content) > 150 else doc.content
                doc_summaries.append(f"- {doc.title}: {content_preview}")
            
            context_parts.append("Knowledge Base:")
            context_parts.extend(doc_summaries)
        
        # Add hybrid memories (NEW)
        if hybrid_memories:
            memory_summaries = []
            for memory in hybrid_memories:
                content_preview = memory['content'][:120] + "..." if len(memory['content']) > 120 else memory['content']
                importance_indicator = "⭐" if memory['importance'] > 0.7 else ""
                tier_indicator = f"[{memory['tier']}]"
                memory_summaries.append(f"- {importance_indicator}{tier_indicator} {content_preview}")
            
            context_parts.append("Relevant Memories:")
            context_parts.extend(memory_summaries)
        
        # Add user preferences
        if user_prefs and user_prefs.get("interests"):
            interests = ", ".join(user_prefs["interests"][:4])  # Limit to top 4
            context_parts.append(f"User Interests: {interests}")
        
        # Add conversation patterns (reduced to make room for memories)
        if conversation_history:
            context_parts.append("Recent Context:")
            for conv in conversation_history[:1]:  # Reduced to 1 item
                msg_preview = conv["message_text"][:80] + "..." if len(conv["message_text"]) > 80 else conv["message_text"]
                context_parts.append(f"- {msg_preview}")
        
        context_summary = "\n".join(context_parts)
        
        # Truncate if too long (increased limit for hybrid context)
        max_length = self.config["max_context_length"] + 500  # Allow more space for hybrid memories
        if len(context_summary) > max_length:
            context_summary = context_summary[:max_length] + "..."
        
        return context_summary
    
    def _calculate_enhanced_confidence_score(
        self, 
        documents: List[SearchResult], 
        user_prefs: Optional[Dict[str, Any]], 
        conversation_history: List[Dict[str, Any]],
        hybrid_memories: List[Dict[str, Any]]
    ) -> float:
        """Calculate enhanced confidence score including hybrid memories."""
        score = 0.0
        
        # Document relevance score (0-0.4, reduced)
        if documents:
            avg_similarity = sum(doc.similarity_score for doc in documents) / len(documents)
            score += min(avg_similarity * 0.4, 0.4)
        
        # Hybrid memories score (0-0.3, NEW)
        if hybrid_memories:
            avg_importance = sum(mem['importance'] for mem in hybrid_memories) / len(hybrid_memories)
            memory_score = avg_importance * 0.3
            score += min(memory_score, 0.3)
        
        # User preferences availability (0-0.15, reduced)
        if user_prefs and user_prefs.get("interests"):
            score += 0.15
        
        # Conversation history relevance (0-0.15, reduced)
        if conversation_history:
            avg_conv_similarity = sum(conv["similarity_score"] for conv in conversation_history) / len(conversation_history)
            score += min(avg_conv_similarity * 0.15, 0.15)
        
        return min(score, 1.0)
    
    async def store_interaction_in_hybrid_memory(
        self, 
        user_id: str, 
        user_message: str, 
        ai_response: str,
        conversation_id: str = None,
        importance_override: float = None
    ) -> bool:
        """Store interaction in hybrid memory system."""
        try:
            if not self.enable_memory_integration or not self.hybrid_memory_manager:
                return False
            
            # Calculate importance
            importance = importance_override if importance_override is not None else self._calculate_interaction_importance(user_message, ai_response)
            
            # Store user message
            user_memory = MemoryItem(
                user_id=user_id,
                content=user_message,
                timestamp=datetime.now(),
                memory_type='conversation',
                importance=importance + 0.1,  # User messages slightly more important
                tier=MemoryTier.HOT,
                metadata={
                    'role': 'user',
                    'conversation_id': conversation_id,
                    'source': 'rag_integration',
                    'ai_response_summary': ai_response[:100] + "..." if len(ai_response) > 100 else ai_response
                }
            )
            
            await self.hybrid_memory_manager.store_memory(user_memory)
            
            # Store AI response
            ai_memory = MemoryItem(
                user_id=user_id,
                content=ai_response,
                timestamp=datetime.now(),
                memory_type='conversation',
                importance=importance,
                tier=MemoryTier.HOT,
                metadata={
                    'role': 'assistant',
                    'conversation_id': conversation_id,
                    'source': 'rag_integration',
                    'user_message_summary': user_message[:100] + "..." if len(user_message) > 100 else user_message
                }
            )
            
            await self.hybrid_memory_manager.store_memory(ai_memory)
            
            logger.debug(f"Stored interaction in hybrid memory for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing interaction in hybrid memory: {e}")
            return False
    
    def _calculate_interaction_importance(self, user_message: str, ai_response: str) -> float:
        """Calculate importance score for an interaction."""
        try:
            user_content = user_message.lower()
            ai_content = ai_response.lower()
            
            importance = 0.3  # Base importance
            
            # User message importance factors
            important_user_keywords = [
                'name', 'work', 'job', 'family', 'hobby', 'like', 'love', 'hate',
                'remember', 'important', 'prefer', 'favorite', 'always', 'never'
            ]
            
            for keyword in important_user_keywords:
                if keyword in user_content:
                    importance += 0.1
                    if importance >= 0.8:
                        break
            
            # Question importance
            if '?' in user_message:
                importance += 0.05
            
            # Length importance
            if len(user_message) > 100:
                importance += 0.05
            
            # AI response quality indicators
            if len(ai_response) > 200:  # Detailed response
                importance += 0.05
            
            if any(word in ai_content for word in ['because', 'explained', 'detailed', 'specific']):
                importance += 0.05
            
            return min(importance, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating interaction importance: {e}")
            return 0.5


# Global RAG manager instance
_rag_manager: Optional[RAGManager] = None


async def get_rag_manager(
    use_local_embeddings: bool = False,
    local_model: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> RAGManager:
    """Get global RAG manager instance."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager(
            use_local_embeddings=use_local_embeddings,
            local_model=local_model
        )
        await _rag_manager.initialize()
    return _rag_manager


async def get_local_rag_manager(
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> RAGManager:
    """Get RAG manager instance configured for local embeddings."""
    try:
        return await get_rag_manager(use_local_embeddings=True, local_model=model)
    except Exception as e:
        logger.warning(f"MongoDB RAG manager failed, falling back to local file-based RAG: {e}")
        # Import and use local file-based RAG manager
        from .local_rag_manager import get_local_rag_manager as get_local_file_rag
        return await get_local_file_rag()