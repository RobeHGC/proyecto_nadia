# api/knowledge_routes.py
"""Knowledge management API routes for RAG system."""
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# RAG imports (with fallback if not available)
try:
    from knowledge.rag_manager import RAGManager, get_rag_manager
    from knowledge.mongodb_manager import KnowledgeDocument
    from knowledge.vector_search import SearchQuery, SearchResult
    RAG_AVAILABLE = True
except ImportError:
    logger.warning("RAG system not available for API routes")
    RAG_AVAILABLE = False
    # Define dummy classes when RAG is not available
    class RAGManager:
        pass
    class KnowledgeDocument:
        pass
    class SearchQuery:
        pass
    class SearchResult:
        pass

# Create router
knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Pydantic models for API requests/responses
class DocumentUploadRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=10, max_length=50000)
    source: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    source: str
    category: str
    created_at: datetime
    metadata: Dict[str, Any]

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    category_filter: Optional[str] = None
    source_filter: Optional[str] = None
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0)
    max_results: int = Field(default=5, ge=1, le=20)

class SearchResultResponse(BaseModel):
    document_id: str
    title: str
    content: str
    source: str
    category: str
    similarity_score: float
    metadata: Dict[str, Any]

class UserLearningRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    interests: Optional[List[str]] = None
    response_feedback: Optional[Dict[str, Any]] = None

class KnowledgeStatsResponse(BaseModel):
    rag_system_status: str
    total_documents: int
    total_users_with_preferences: int
    total_conversation_embeddings: int
    embeddings_cache_size: int
    mongodb_collections: Dict[str, int]


# Dependency to get RAG manager
async def get_rag_dependency() -> RAGManager:
    """Dependency to get RAG manager instance."""
    if not RAG_AVAILABLE:
        raise HTTPException(status_code=503, detail="RAG system not available")
    
    try:
        return await get_rag_manager()
    except Exception as e:
        logger.error(f"Failed to get RAG manager: {e}")
        raise HTTPException(status_code=503, detail="RAG system unavailable")


@knowledge_router.post("/documents", response_model=Dict[str, str])
async def upload_knowledge_document(
    document: DocumentUploadRequest,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Upload a new knowledge document to the RAG system."""
    try:
        # Generate unique document ID
        document_id = str(uuid.uuid4())
        
        # Add document to vector search engine
        success = await rag_manager.vector_search.add_knowledge_document(
            document_id=document_id,
            title=document.title,
            content=document.content,
            source=document.source,
            category=document.category,
            metadata=document.metadata
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store document")
        
        logger.info(f"Uploaded knowledge document: {document_id}")
        
        return {
            "document_id": document_id,
            "status": "uploaded",
            "title": document.title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading knowledge document: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@knowledge_router.get("/documents/search", response_model=List[SearchResultResponse])
async def search_knowledge_documents(
    query: str,
    category_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
    min_similarity: float = 0.7,
    max_results: int = 5,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Search knowledge documents using semantic similarity."""
    try:
        # Create search query
        search_query = SearchQuery(
            text=query,
            category_filter=category_filter,
            source_filter=source_filter,
            min_similarity=min_similarity,
            max_results=max_results
        )
        
        # Perform search
        results = await rag_manager.vector_search.search_similar_documents(search_query)
        
        # Convert to response format
        response_results = []
        for result in results:
            response_results.append(SearchResultResponse(
                document_id=result.document_id,
                title=result.title,
                content=result.content,
                source=result.source,
                category=result.category,
                similarity_score=result.similarity_score,
                metadata=result.metadata
            ))
        
        logger.info(f"Knowledge search returned {len(results)} results for query: {query}")
        return response_results
        
    except Exception as e:
        logger.error(f"Error searching knowledge documents: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@knowledge_router.post("/user-learning", response_model=Dict[str, str])
async def update_user_learning(
    learning_data: UserLearningRequest,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Update user learning preferences and patterns."""
    try:
        success = await rag_manager.learn_user_preferences(
            user_id=learning_data.user_id,
            interests=learning_data.interests,
            response_feedback=learning_data.response_feedback
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update user learning")
        
        logger.info(f"Updated learning data for user: {learning_data.user_id}")
        
        return {
            "user_id": learning_data.user_id,
            "status": "updated",
            "message": "User learning preferences updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user learning: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user learning")


@knowledge_router.get("/user/{user_id}/preferences", response_model=Dict[str, Any])
async def get_user_preferences(
    user_id: str,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Get user preferences and learning data."""
    try:
        preferences = await rag_manager.mongodb_manager.get_user_preferences(user_id)
        
        if not preferences:
            return {
                "user_id": user_id,
                "preferences_found": False,
                "message": "No preferences found for this user"
            }
        
        return {
            "user_id": user_id,
            "preferences_found": True,
            "interests": preferences.get("interests", []),
            "conversation_patterns": preferences.get("conversation_patterns", {}),
            "response_preferences": preferences.get("response_preferences", {}),
            "last_updated": preferences.get("last_updated")
        }
        
    except Exception as e:
        logger.error(f"Error getting user preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user preferences")


@knowledge_router.get("/user/{user_id}/conversations/search", response_model=List[Dict[str, Any]])
async def search_user_conversations(
    user_id: str,
    query: str,
    limit: int = 5,
    min_similarity: float = 0.6,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Search user's conversation history using semantic similarity."""
    try:
        results = await rag_manager.vector_search.search_conversation_history(
            user_id=user_id,
            query_text=query,
            limit=limit,
            min_similarity=min_similarity
        )
        
        logger.info(f"Found {len(results)} similar conversations for user {user_id}")
        return results
        
    except Exception as e:
        logger.error(f"Error searching user conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to search conversations")


@knowledge_router.get("/suggestions/{user_id}", response_model=List[SearchResultResponse])
async def get_knowledge_suggestions(
    user_id: str,
    context: Optional[str] = None,
    limit: int = 3,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Get knowledge suggestions based on user preferences and context."""
    try:
        # Get user preferences
        user_prefs = await rag_manager.mongodb_manager.get_user_preferences(user_id)
        
        if not user_prefs or not user_prefs.get("interests"):
            return []
        
        # Use user interests as search queries
        suggestions = []
        for interest in user_prefs["interests"][:3]:  # Top 3 interests
            search_query = SearchQuery(
                text=f"{interest} {context or ''}".strip(),
                min_similarity=0.6,
                max_results=2
            )
            
            results = await rag_manager.vector_search.search_similar_documents(search_query)
            for result in results:
                suggestions.append(SearchResultResponse(
                    document_id=result.document_id,
                    title=result.title,
                    content=result.content[:200] + "..." if len(result.content) > 200 else result.content,
                    source=result.source,
                    category=result.category,
                    similarity_score=result.similarity_score,
                    metadata=result.metadata
                ))
        
        # Remove duplicates and limit results
        seen_ids = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion.document_id not in seen_ids:
                seen_ids.add(suggestion.document_id)
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= limit:
                    break
        
        logger.info(f"Generated {len(unique_suggestions)} knowledge suggestions for user {user_id}")
        return unique_suggestions
        
    except Exception as e:
        logger.error(f"Error getting knowledge suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get suggestions")


@knowledge_router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Get comprehensive RAG system statistics."""
    try:
        stats = await rag_manager.get_rag_stats()
        
        return KnowledgeStatsResponse(
            rag_system_status=stats.get("system_status", "unknown"),
            total_documents=stats.get("mongodb_stats", {}).get("knowledge_documents", 0),
            total_users_with_preferences=stats.get("mongodb_stats", {}).get("user_preferences", 0),
            total_conversation_embeddings=stats.get("mongodb_stats", {}).get("conversation_embeddings", 0),
            embeddings_cache_size=stats.get("embeddings_stats", {}).get("cache_size", 0),
            mongodb_collections=stats.get("mongodb_stats", {})
        )
        
    except Exception as e:
        logger.error(f"Error getting knowledge stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats")


@knowledge_router.delete("/documents/{document_id}", response_model=Dict[str, str])
async def delete_knowledge_document(
    document_id: str,
    rag_manager: RAGManager = Depends(get_rag_dependency)
):
    """Delete a knowledge document from the system."""
    try:
        # Delete from MongoDB
        collection = rag_manager.mongodb_manager.db[rag_manager.mongodb_manager.collections["knowledge_documents"]]
        result = await collection.delete_one({"_id": document_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        
        logger.info(f"Deleted knowledge document: {document_id}")
        
        return {
            "document_id": document_id,
            "status": "deleted",
            "message": "Document deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting knowledge document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


# Health check endpoint for RAG system
@knowledge_router.get("/health", response_model=Dict[str, Any])
async def knowledge_health_check():
    """Health check for RAG system components."""
    health_status = {
        "rag_available": RAG_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }
    
    if RAG_AVAILABLE:
        try:
            rag_manager = await get_rag_manager()
            health_status["mongodb_connected"] = rag_manager.mongodb_manager is not None
            health_status["embeddings_service"] = rag_manager.embeddings_service is not None
            health_status["vector_search"] = rag_manager.vector_search is not None
            health_status["status"] = "healthy"
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
    else:
        health_status["status"] = "not_available"
        health_status["message"] = "RAG system dependencies not installed"
    
    return health_status