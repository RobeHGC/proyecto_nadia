# knowledge/rag_manager.py
"""RAG (Retrieval-Augmented Generation) manager for knowledge enhancement."""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .mongodb_manager import MongoDBManager, get_mongodb_manager, UserPreference
from .embeddings_service import EmbeddingsService, get_embeddings_service
from .vector_search import VectorSearchEngine, get_vector_search_engine, SearchQuery, SearchResult

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
        vector_search: VectorSearchEngine = None
    ):
        """Initialize RAG manager."""
        self.mongodb_manager = mongodb_manager
        self.embeddings_service = embeddings_service
        self.vector_search = vector_search
        self._initialized = False
        
        # RAG configuration
        self.config = {
            "max_context_length": 2000,  # Max characters for context injection
            "min_similarity_threshold": 0.7,  # Min similarity for document relevance
            "max_documents": 3,  # Max documents to include in context
            "include_conversation_history": True,
            "include_user_preferences": True,
            "context_weight": 0.3  # How much to weight context vs original prompt
        }
    
    async def initialize(self):
        """Initialize all services."""
        if not self._initialized:
            if self.mongodb_manager is None:
                self.mongodb_manager = await get_mongodb_manager()
            if self.embeddings_service is None:
                self.embeddings_service = get_embeddings_service()
            if self.vector_search is None:
                self.vector_search = await get_vector_search_engine()
            self._initialized = True
            logger.info("RAG Manager initialized successfully")
    
    async def enhance_prompt_with_context(
        self, 
        user_message: str, 
        user_id: str,
        conversation_context: Dict[str, Any] = None
    ) -> RAGResponse:
        """Enhance a prompt with relevant context from knowledge base."""
        await self.initialize()
        
        try:
            # Step 1: Retrieve relevant knowledge documents
            relevant_docs = await self._retrieve_relevant_documents(user_message)
            
            # Step 2: Get user preferences and history
            user_prefs = await self._get_user_context(user_id)
            conversation_history = await self._get_relevant_conversation_history(user_id, user_message)
            
            # Step 3: Build context summary
            context_summary = await self._build_context_summary(
                relevant_docs, 
                user_prefs, 
                conversation_history
            )
            
            # Step 4: Calculate confidence score
            confidence_score = self._calculate_confidence_score(relevant_docs, user_prefs, conversation_history)
            
            # Step 5: Create RAG context
            rag_context = RAGContext(
                relevant_documents=relevant_docs,
                user_preferences=user_prefs,
                conversation_history=conversation_history,
                context_summary=context_summary,
                confidence_score=confidence_score
            )
            
            # Step 6: Enhance the original prompt
            enhanced_prompt = await self._create_enhanced_prompt(user_message, rag_context)
            
            logger.info(f"Enhanced prompt for user {user_id} with {len(relevant_docs)} documents")
            
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


# Global RAG manager instance
_rag_manager: Optional[RAGManager] = None


async def get_rag_manager() -> RAGManager:
    """Get global RAG manager instance."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager()
        await _rag_manager.initialize()
    return _rag_manager