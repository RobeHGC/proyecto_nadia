# knowledge/embeddings_service.py
"""Embeddings service for text-to-vector conversion using OpenAI."""
import logging
import os
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import openai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of text embedding operation."""
    text: str
    embedding: List[float]
    token_count: int
    model: str


class EmbeddingsService:
    """Service for generating text embeddings using OpenAI."""
    
    def __init__(self, api_key: str = None):
        """Initialize embeddings service."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required for embeddings service")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "text-embedding-3-small"  # Cost-effective embedding model
        self.max_tokens = 8191  # Token limit for embedding model
        
        # Cache for recent embeddings to avoid duplicate API calls
        self._embedding_cache: Dict[str, EmbeddingResult] = {}
        self._cache_max_size = 1000
    
    async def get_embedding(self, text: str) -> Optional[EmbeddingResult]:
        """Get embedding for a single text."""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        # Check cache first
        text_key = text.strip()
        if text_key in self._embedding_cache:
            logger.debug(f"Using cached embedding for text: {text_key[:50]}...")
            return self._embedding_cache[text_key]
        
        try:
            # Truncate text if too long
            truncated_text = self._truncate_text(text_key)
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=truncated_text
            )
            
            embedding_data = response.data[0]
            result = EmbeddingResult(
                text=truncated_text,
                embedding=embedding_data.embedding,
                token_count=response.usage.total_tokens,
                model=self.model
            )
            
            # Cache the result
            self._cache_embedding(text_key, result)
            
            logger.debug(f"Generated embedding for text ({result.token_count} tokens): {text_key[:50]}...")
            return result
            
        except openai.RateLimitError:
            logger.warning("OpenAI rate limit hit for embedding generation")
            return None
        except openai.APIError as e:
            logger.error(f"OpenAI API error for embedding: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            return None
    
    async def get_embeddings_batch(self, texts: List[str]) -> List[Optional[EmbeddingResult]]:
        """Get embeddings for multiple texts efficiently."""
        if not texts:
            return []
        
        # Filter out empty texts and check cache
        text_results = []
        texts_to_embed = []
        indices_to_embed = []
        
        for i, text in enumerate(texts):
            text_key = text.strip() if text else ""
            if not text_key:
                text_results.append(None)
                continue
            
            # Check cache
            if text_key in self._embedding_cache:
                text_results.append(self._embedding_cache[text_key])
            else:
                text_results.append(None)  # Placeholder
                texts_to_embed.append(self._truncate_text(text_key))
                indices_to_embed.append(i)
        
        # Generate embeddings for uncached texts
        if texts_to_embed:
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=texts_to_embed
                )
                
                # Process results
                for j, embedding_data in enumerate(response.data):
                    original_index = indices_to_embed[j]
                    original_text = texts[original_index].strip()
                    
                    result = EmbeddingResult(
                        text=texts_to_embed[j],
                        embedding=embedding_data.embedding,
                        token_count=response.usage.total_tokens // len(texts_to_embed),  # Approximate
                        model=self.model
                    )
                    
                    # Cache and store result
                    self._cache_embedding(original_text, result)
                    text_results[original_index] = result
                
                logger.info(f"Generated {len(texts_to_embed)} embeddings in batch")
                
            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")
                # Set failed embeddings to None
                for idx in indices_to_embed:
                    if text_results[idx] is None:
                        text_results[idx] = None
        
        return text_results
    
    def _truncate_text(self, text: str) -> str:
        """Truncate text to fit within token limits."""
        # Simple approximation: ~4 characters per token
        max_chars = self.max_tokens * 4
        if len(text) > max_chars:
            truncated = text[:max_chars]
            logger.debug(f"Truncated text from {len(text)} to {len(truncated)} characters")
            return truncated
        return text
    
    def _cache_embedding(self, text_key: str, result: EmbeddingResult):
        """Cache embedding result with size limit."""
        # Simple LRU-like cache management
        if len(self._embedding_cache) >= self._cache_max_size:
            # Remove oldest entries (first 100)
            items = list(self._embedding_cache.items())
            for key, _ in items[:100]:
                del self._embedding_cache[key]
        
        self._embedding_cache[text_key] = result
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by current model."""
        # text-embedding-3-small produces 1536-dimensional vectors
        return 1536
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._embedding_cache),
            "cache_max_size": self._cache_max_size,
            "model": self.model,
            "embedding_dimension": self.get_embedding_dimension()
        }


# Global embeddings service instance
_embeddings_service: Optional[EmbeddingsService] = None


def get_embeddings_service() -> EmbeddingsService:
    """Get global embeddings service instance."""
    global _embeddings_service
    if _embeddings_service is None:
        _embeddings_service = EmbeddingsService()
    return _embeddings_service


async def embed_text(text: str) -> Optional[List[float]]:
    """Convenience function to get embedding vector for text."""
    service = get_embeddings_service()
    result = await service.get_embedding(text)
    return result.embedding if result else None


async def embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """Convenience function to get embedding vectors for multiple texts."""
    service = get_embeddings_service()
    results = await service.get_embeddings_batch(texts)
    return [result.embedding if result else None for result in results]