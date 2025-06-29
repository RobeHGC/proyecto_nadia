"""
Local RAG Manager - Works without MongoDB by using direct file system access.
This is a simplified version for immediate deployment without database dependencies.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import pickle

from .local_embeddings_service import get_local_embeddings_service
from .rag_manager import RAGContext, RAGResponse

logger = logging.getLogger(__name__)


@dataclass
class LocalKnowledgeDoc:
    """Local knowledge document for file-based RAG."""
    id: str
    title: str
    content: str
    category: str
    embedding: List[float]
    metadata: Dict[str, Any]


class LocalRAGManager:
    """Local file-based RAG manager without MongoDB dependency."""
    
    def __init__(self, knowledge_docs_path: str = None):
        """Initialize local RAG manager."""
        self.knowledge_docs_path = Path(knowledge_docs_path or 
                                      Path(__file__).parent.parent / "knowledge_documents")
        self.embeddings_service = None
        self._initialized = False
        self._knowledge_cache = {}
        self._embeddings_cache_file = self.knowledge_docs_path.parent / "cache" / "embeddings.pkl"
        
        # Ensure cache directory exists
        self._embeddings_cache_file.parent.mkdir(exist_ok=True)
        
        # RAG configuration
        self.config = {
            "max_context_length": 2000,
            "min_similarity_threshold": 0.05,  # Adjusted threshold for sentence-transformers model
            "max_documents": 3,
            "context_weight": 0.3
        }
        
        # Document categories mapping
        self.doc_categories = {
            "nadia_biografia_familiar.md": "family",
            "nadia_vida_estudiantil.md": "education", 
            "nadia_personalidad_hobbies.md": "personality",
            "nadia_fanvue_backstory.md": "backstory",
            "nadia_austin_texas.md": "travel",
            "nadia_monterrey_montanismo.md": "hobbies",
            "nadia_conocimiento_medico.md": "medical_knowledge"
        }
    
    async def initialize(self):
        """Initialize embeddings service and load knowledge base."""
        if self._initialized:
            return
        
        logger.info("Initializing Local RAG Manager...")
        
        # Initialize embeddings service
        self.embeddings_service = get_local_embeddings_service()
        
        # Load or generate knowledge base embeddings
        await self._load_or_generate_knowledge_base()
        
        self._initialized = True
        logger.info(f"Local RAG Manager initialized with {len(self._knowledge_cache)} documents")
    
    async def _load_or_generate_knowledge_base(self):
        """Load existing embeddings cache or generate new ones."""
        # Try to load from cache first
        if self._embeddings_cache_file.exists():
            try:
                with open(self._embeddings_cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    self._knowledge_cache = cache_data.get('knowledge_cache', {})
                    logger.info(f"Loaded {len(self._knowledge_cache)} documents from cache")
                    
                    # Verify cache is still valid (check if files changed)
                    if await self._is_cache_valid(cache_data.get('file_hashes', {})):
                        return
                    else:
                        logger.info("Cache is outdated, regenerating embeddings...")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        # Generate new embeddings
        await self._generate_knowledge_embeddings()
        await self._save_embeddings_cache()
    
    async def _is_cache_valid(self, cached_hashes: Dict[str, str]) -> bool:
        """Check if the embeddings cache is still valid."""
        try:
            md_files = list(self.knowledge_docs_path.glob("*.md"))
            for file_path in md_files:
                # Simple hash based on file modification time and size
                file_hash = f"{file_path.stat().st_mtime}_{file_path.stat().st_size}"
                if cached_hashes.get(file_path.name) != file_hash:
                    return False
            return True
        except Exception:
            return False
    
    async def _generate_knowledge_embeddings(self):
        """Generate embeddings for all knowledge documents."""
        logger.info("Generating embeddings for knowledge documents...")
        
        md_files = list(self.knowledge_docs_path.glob("*.md"))
        self._knowledge_cache = {}
        
        for i, file_path in enumerate(md_files):
            try:
                # Load document
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract title
                lines = content.split('\n')
                title = lines[0].strip('#').strip() if lines[0].startswith('#') else file_path.stem
                
                # Generate embedding
                logger.info(f"Generating embedding for {file_path.name} ({i+1}/{len(md_files)})")
                embedding_result = await self.embeddings_service.get_embedding(content)
                
                if embedding_result and embedding_result.embedding:
                    doc = LocalKnowledgeDoc(
                        id=f"local_{file_path.stem}",
                        title=title,
                        content=content,
                        category=self.doc_categories.get(file_path.name, "general"),
                        embedding=embedding_result.embedding,
                        metadata={
                            "filename": file_path.name,
                            "content_length": len(content),
                            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
                        }
                    )
                    self._knowledge_cache[doc.id] = doc
                    logger.info(f"✅ Generated embedding for {file_path.name}")
                else:
                    logger.warning(f"❌ Failed to generate embedding for {file_path.name}")
                    
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
        
        logger.info(f"Generated embeddings for {len(self._knowledge_cache)} documents")
    
    async def _save_embeddings_cache(self):
        """Save embeddings cache to disk."""
        try:
            # Generate file hashes for validation
            file_hashes = {}
            md_files = list(self.knowledge_docs_path.glob("*.md"))
            for file_path in md_files:
                file_hashes[file_path.name] = f"{file_path.stat().st_mtime}_{file_path.stat().st_size}"
            
            cache_data = {
                'knowledge_cache': self._knowledge_cache,
                'file_hashes': file_hashes,
                'cache_version': '1.0'
            }
            
            with open(self._embeddings_cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"Saved embeddings cache to {self._embeddings_cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to save embeddings cache: {e}")
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def _find_similar_documents(self, query_embedding: List[float]) -> List[Tuple[LocalKnowledgeDoc, float]]:
        """Find documents similar to the query embedding."""
        similarities = []
        
        for doc in self._knowledge_cache.values():
            similarity = self._cosine_similarity(query_embedding, doc.embedding)
            if similarity >= self.config["min_similarity_threshold"]:
                similarities.append((doc, similarity))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top results
        return similarities[:self.config["max_documents"]]
    
    async def enhance_prompt_with_context(
        self, 
        user_message: str, 
        user_id: str,
        conversation_context: Dict[str, Any] = None
    ) -> RAGResponse:
        """Enhance prompt with relevant context from local knowledge base."""
        await self.initialize()
        
        try:
            # Generate embedding for user message
            embedding_result = await self.embeddings_service.get_embedding(user_message)
            if not embedding_result or not embedding_result.embedding:
                logger.warning("Failed to generate embedding for user message")
                return RAGResponse(
                    enhanced_prompt=user_message,
                    context_used=RAGContext([], None, [], "", 0.0),
                    success=False,
                    error_message="Failed to generate query embedding"
                )
            
            # Find similar documents
            similar_docs = await self._find_similar_documents(embedding_result.embedding)
            
            if not similar_docs:
                logger.debug(f"No relevant documents found for query: {user_message[:50]}...")
                return RAGResponse(
                    enhanced_prompt=user_message,
                    context_used=RAGContext([], None, [], "", 0.0),
                    success=True
                )
            
            # Build context summary
            context_parts = ["Relevant Knowledge:"]
            confidence_scores = []
            
            for doc, similarity in similar_docs:
                confidence_scores.append(similarity)
                # Truncate long content
                content_preview = doc.content[:300] + "..." if len(doc.content) > 300 else doc.content
                context_parts.append(f"- {doc.title} (relevance: {similarity:.2f}): {content_preview}")
            
            context_summary = "\n".join(context_parts)
            
            # Calculate confidence score
            confidence_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            # Create enhanced prompt if confidence is high enough
            if confidence_score >= 0.3:
                enhanced_prompt = f"""User Message: {user_message}

{context_summary}

Instructions: Use the relevant knowledge above to provide a more informed and personalized response. Stay true to Nadia's personality while incorporating relevant details when appropriate."""
            else:
                enhanced_prompt = user_message
            
            # Create fake SearchResults for compatibility
            from .vector_search import SearchResult
            search_results = [
                SearchResult(
                    document_id=doc.id,
                    title=doc.title,
                    content=doc.content,
                    source="nadia_biography",
                    category=doc.category,
                    similarity_score=similarity,
                    metadata=doc.metadata
                ) for doc, similarity in similar_docs
            ]
            
            rag_context = RAGContext(
                relevant_documents=search_results,
                user_preferences=None,
                conversation_history=[],
                context_summary=context_summary,
                confidence_score=confidence_score
            )
            
            logger.info(f"Enhanced prompt with {len(similar_docs)} documents (confidence: {confidence_score:.2f})")
            
            return RAGResponse(
                enhanced_prompt=enhanced_prompt,
                context_used=rag_context,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error in local RAG enhancement: {e}")
            return RAGResponse(
                enhanced_prompt=user_message,
                context_used=RAGContext([], None, [], "", 0.0),
                success=False,
                error_message=str(e)
            )
    
    async def store_user_interaction(
        self, 
        user_id: str, 
        user_message: str, 
        ai_response: str,
        conversation_id: str = None
    ) -> bool:
        """Store user interaction (no-op for local version)."""
        # In local version, we don't store interactions
        # This could be extended to save to local files if needed
        logger.debug(f"Local RAG: Interaction logged for user {user_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get local RAG manager statistics."""
        return {
            "documents_loaded": len(self._knowledge_cache),
            "cache_file_exists": self._embeddings_cache_file.exists(),
            "embeddings_service": "local",
            "config": self.config,
            "status": "operational" if self._initialized else "not_initialized"
        }


# Global instance
_local_rag_manager: Optional[LocalRAGManager] = None


async def get_local_rag_manager() -> LocalRAGManager:
    """Get global local RAG manager instance."""
    global _local_rag_manager
    if _local_rag_manager is None:
        _local_rag_manager = LocalRAGManager()
        await _local_rag_manager.initialize()
    return _local_rag_manager