# knowledge/vector_search.py
"""Vector search engine for semantic similarity in RAG system."""
import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import numpy as np

from .mongodb_manager import MongoDBManager, get_mongodb_manager
from .embeddings_service import EmbeddingsService, get_embeddings_service

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result of semantic search."""
    document_id: str
    title: str
    content: str
    source: str
    category: str
    similarity_score: float
    metadata: Dict[str, Any]


@dataclass
class SearchQuery:
    """Search query configuration."""
    text: str
    category_filter: Optional[str] = None
    source_filter: Optional[str] = None
    min_similarity: float = 0.7
    max_results: int = 5


class VectorSearchEngine:
    """Vector search engine for semantic similarity."""
    
    def __init__(self, mongodb_manager: MongoDBManager = None, embeddings_service: EmbeddingsService = None):
        """Initialize vector search engine."""
        self.mongodb_manager = mongodb_manager
        self.embeddings_service = embeddings_service
        self._initialized = False
    
    async def initialize(self):
        """Initialize services if not provided."""
        if not self._initialized:
            if self.mongodb_manager is None:
                self.mongodb_manager = await get_mongodb_manager()
            if self.embeddings_service is None:
                self.embeddings_service = get_embeddings_service()
            self._initialized = True
    
    async def search_similar_documents(self, query: SearchQuery) -> List[SearchResult]:
        """Search for documents semantically similar to query text."""
        await self.initialize()
        
        try:
            # Generate embedding for query
            embedding_result = await self.embeddings_service.get_embedding(query.text)
            if not embedding_result:
                logger.warning(f"Failed to generate embedding for query: {query.text}")
                return []
            
            query_embedding = embedding_result.embedding
            
            # Get candidate documents from MongoDB
            candidates = await self._get_candidate_documents(query)
            if not candidates:
                logger.info("No candidate documents found")
                return []
            
            # Calculate similarities and rank
            results = await self._calculate_similarities(query_embedding, candidates, query)
            
            # Filter by minimum similarity and limit results
            filtered_results = [
                result for result in results 
                if result.similarity_score >= query.min_similarity
            ]
            
            final_results = filtered_results[:query.max_results]
            
            logger.info(f"Found {len(final_results)} similar documents for query: {query.text[:50]}...")
            return final_results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def _get_candidate_documents(self, query: SearchQuery) -> List[Dict[str, Any]]:
        """Get candidate documents from MongoDB with optional filters."""
        search_filter = {}
        
        # Apply category filter
        if query.category_filter:
            search_filter["category"] = query.category_filter
        
        # Apply source filter
        if query.source_filter:
            search_filter["source"] = query.source_filter
        
        # Only get documents that have embeddings
        search_filter["embedding"] = {"$exists": True, "$ne": None}
        
        try:
            collection = self.mongodb_manager.db[self.mongodb_manager.collections["knowledge_documents"]]
            
            # Get documents with projections for efficiency
            cursor = collection.find(
                search_filter,
                {
                    "_id": 1,
                    "title": 1,
                    "content": 1,
                    "source": 1,
                    "category": 1,
                    "embedding": 1,
                    "metadata": 1
                }
            ).limit(1000)  # Reasonable limit for similarity calculation
            
            candidates = await cursor.to_list(length=1000)
            logger.debug(f"Retrieved {len(candidates)} candidate documents")
            return candidates
            
        except Exception as e:
            logger.error(f"Error retrieving candidate documents: {e}")
            return []
    
    async def _calculate_similarities(
        self, 
        query_embedding: List[float], 
        candidates: List[Dict[str, Any]], 
        query: SearchQuery
    ) -> List[SearchResult]:
        """Calculate cosine similarities and create ranked results."""
        results = []
        
        # Convert query embedding to numpy array for efficiency
        query_vector = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vector)
        
        if query_norm == 0:
            logger.warning("Query embedding has zero norm")
            return []
        
        for doc in candidates:
            try:
                # Extract document embedding
                doc_embedding = doc.get("embedding")
                if not doc_embedding:
                    continue
                
                # Calculate cosine similarity
                doc_vector = np.array(doc_embedding)
                doc_norm = np.linalg.norm(doc_vector)
                
                if doc_norm == 0:
                    continue
                
                # Cosine similarity = dot product / (norm1 * norm2)
                similarity = np.dot(query_vector, doc_vector) / (query_norm * doc_norm)
                
                # Create search result
                result = SearchResult(
                    document_id=doc["_id"],
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    source=doc.get("source", ""),
                    category=doc.get("category", ""),
                    similarity_score=float(similarity),
                    metadata=doc.get("metadata", {})
                )
                
                results.append(result)
                
            except Exception as e:
                logger.warning(f"Error calculating similarity for document {doc.get('_id', 'unknown')}: {e}")
                continue
        
        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        logger.debug(f"Calculated similarities for {len(results)} documents")
        return results
    
    async def search_conversation_history(
        self, 
        user_id: str, 
        query_text: str, 
        limit: int = 5,
        min_similarity: float = 0.6
    ) -> List[Dict[str, Any]]:
        """Search user's conversation history for similar content."""
        await self.initialize()
        
        try:
            # Generate embedding for query
            embedding_result = await self.embeddings_service.get_embedding(query_text)
            if not embedding_result:
                return []
            
            query_embedding = embedding_result.embedding
            
            # Get user's conversation embeddings
            collection = self.mongodb_manager.db[self.mongodb_manager.collections["conversation_embeddings"]]
            cursor = collection.find(
                {"user_id": user_id},
                {"conversation_id": 1, "message_text": 1, "embedding": 1, "metadata": 1, "created_at": 1}
            ).sort("created_at", -1).limit(1000)  # Recent conversations first
            
            conversations = await cursor.to_list(length=1000)
            
            # Calculate similarities
            query_vector = np.array(query_embedding)
            query_norm = np.linalg.norm(query_vector)
            
            if query_norm == 0:
                return []
            
            results = []
            for conv in conversations:
                try:
                    conv_embedding = conv.get("embedding")
                    if not conv_embedding:
                        continue
                    
                    conv_vector = np.array(conv_embedding)
                    conv_norm = np.linalg.norm(conv_vector)
                    
                    if conv_norm == 0:
                        continue
                    
                    similarity = np.dot(query_vector, conv_vector) / (query_norm * conv_norm)
                    
                    if similarity >= min_similarity:
                        results.append({
                            "conversation_id": conv["conversation_id"],
                            "message_text": conv["message_text"],
                            "similarity_score": float(similarity),
                            "metadata": conv.get("metadata", {}),
                            "created_at": conv["created_at"]
                        })
                
                except Exception as e:
                    logger.warning(f"Error processing conversation similarity: {e}")
                    continue
            
            # Sort by similarity and return top results
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            final_results = results[:limit]
            
            logger.info(f"Found {len(final_results)} similar conversations for user {user_id}")
            return final_results
            
        except Exception as e:
            logger.error(f"Error searching conversation history: {e}")
            return []
    
    async def add_knowledge_document(
        self, 
        document_id: str,
        title: str,
        content: str,
        source: str,
        category: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Add a new knowledge document with embedding."""
        await self.initialize()
        
        try:
            # Generate embedding for content
            full_text = f"{title}\n\n{content}"
            embedding_result = await self.embeddings_service.get_embedding(full_text)
            
            if not embedding_result:
                logger.error(f"Failed to generate embedding for document: {document_id}")
                return False
            
            # Store document in MongoDB
            from .mongodb_manager import KnowledgeDocument
            document = KnowledgeDocument(
                id=document_id,
                title=title,
                content=content,
                source=source,
                category=category,
                embedding=embedding_result.embedding,
                metadata=metadata or {}
            )
            
            success = await self.mongodb_manager.store_knowledge_document(document)
            if success:
                logger.info(f"Added knowledge document with embedding: {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding knowledge document {document_id}: {e}")
            return False
    
    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search engine statistics."""
        await self.initialize()
        
        try:
            mongodb_stats = await self.mongodb_manager.get_collection_stats()
            embeddings_stats = self.embeddings_service.get_cache_stats()
            
            return {
                "mongodb_collections": mongodb_stats,
                "embeddings_service": embeddings_stats,
                "vector_dimension": self.embeddings_service.get_embedding_dimension()
            }
            
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {}


# Global vector search engine instance
_vector_search_engine: Optional[VectorSearchEngine] = None


async def get_vector_search_engine() -> VectorSearchEngine:
    """Get global vector search engine instance."""
    global _vector_search_engine
    if _vector_search_engine is None:
        _vector_search_engine = VectorSearchEngine()
        await _vector_search_engine.initialize()
    return _vector_search_engine