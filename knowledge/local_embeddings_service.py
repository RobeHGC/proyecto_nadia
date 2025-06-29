# knowledge/local_embeddings_service.py
"""Local embeddings service using sentence-transformers (CPU-optimized for Ryzen 7 5700)."""
import logging
import time
import threading
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of text embedding operation (compatible with OpenAI service)."""
    text: str
    embedding: List[float]
    token_count: int
    model: str


class LocalEmbeddingsService:
    """Local embeddings service optimized for AMD Ryzen 7 5700 (8 cores, 16GB RAM)."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize local embeddings service."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name
        self.model = None
        self._model_lock = threading.Lock()
        
        # Hardware-optimized settings for Ryzen 7 5700
        self.batch_size = 32  # Optimal for 16GB RAM
        self.max_workers = 8  # Match CPU cores
        self.max_seq_length = 256  # Good for conversational text
        
        # Cache for recent embeddings
        self._embedding_cache: Dict[str, EmbeddingResult] = {}
        self._cache_max_size = 2000  # Higher cache due to 16GB RAM
        
        # Performance tracking
        self._stats = {
            "embeddings_generated": 0,
            "cache_hits": 0,
            "total_time": 0.0,
            "avg_time_per_embedding": 0.0
        }
        
        logger.info(f"Initializing LocalEmbeddingsService with model: {model_name}")
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the sentence transformer model."""
        try:
            start_time = time.time()
            
            # Load model with CPU optimization
            self.model = SentenceTransformer(
                self.model_name,
                device="cpu"  # Explicit CPU usage
            )
            
            # Configure for optimal performance
            self.model.max_seq_length = self.max_seq_length
            
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f}s. Embedding dimension: {self.get_embedding_dimension()}")
            
            # Warm up with a test embedding
            test_result = self._generate_single_embedding("test")
            logger.info(f"Model warmed up. Test embedding time: {test_result.token_count}ms equivalent")
            
        except Exception as e:
            logger.error(f"Failed to initialize model {self.model_name}: {e}")
            raise
    
    def _generate_single_embedding(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            raise ValueError("Empty text provided for embedding")
        
        start_time = time.time()
        
        # Generate embedding
        embedding = self.model.encode(
            text.strip(),
            convert_to_numpy=True,
            normalize_embeddings=True  # Normalize for cosine similarity
        )
        
        elapsed_time = time.time() - start_time
        
        # Estimate token count (rough approximation)
        estimated_tokens = len(text.split()) * 1.3  # Approximate tokens
        
        result = EmbeddingResult(
            text=text.strip(),
            embedding=embedding.tolist(),
            token_count=int(estimated_tokens),
            model=self.model_name
        )
        
        # Update stats
        self._stats["embeddings_generated"] += 1
        self._stats["total_time"] += elapsed_time
        self._stats["avg_time_per_embedding"] = (
            self._stats["total_time"] / self._stats["embeddings_generated"]
        )
        
        logger.debug(f"Generated embedding in {elapsed_time*1000:.1f}ms for text: {text[:50]}...")
        return result
    
    def _generate_batch_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts efficiently."""
        if not texts:
            return []
        
        # Filter and prepare texts
        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            return []
        
        start_time = time.time()
        
        # Generate embeddings in batch (much more efficient)
        embeddings = self.model.encode(
            valid_texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False  # Disable progress bar for cleaner logs
        )
        
        elapsed_time = time.time() - start_time
        
        # Create results
        results = []
        for i, (text, embedding) in enumerate(zip(valid_texts, embeddings)):
            estimated_tokens = len(text.split()) * 1.3
            
            result = EmbeddingResult(
                text=text,
                embedding=embedding.tolist(),
                token_count=int(estimated_tokens),
                model=self.model_name
            )
            results.append(result)
        
        # Update stats
        self._stats["embeddings_generated"] += len(results)
        self._stats["total_time"] += elapsed_time
        self._stats["avg_time_per_embedding"] = (
            self._stats["total_time"] / self._stats["embeddings_generated"]
        )
        
        logger.info(f"Generated {len(results)} embeddings in {elapsed_time*1000:.1f}ms "
                   f"({elapsed_time*1000/len(results):.1f}ms per embedding)")
        
        return results
    
    async def get_embedding(self, text: str) -> Optional[EmbeddingResult]:
        """Get embedding for a single text (async interface compatible with OpenAI service)."""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        text_key = text.strip()
        
        # Check cache first
        if text_key in self._embedding_cache:
            self._stats["cache_hits"] += 1
            logger.debug(f"Using cached embedding for text: {text_key[:50]}...")
            return self._embedding_cache[text_key]
        
        try:
            with self._model_lock:
                result = self._generate_single_embedding(text_key)
            
            # Cache the result
            self._cache_embedding(text_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    async def get_embeddings_batch(self, texts: List[str]) -> List[Optional[EmbeddingResult]]:
        """Get embeddings for multiple texts efficiently (async interface)."""
        if not texts:
            return []
        
        # Check cache and separate uncached texts
        results = [None] * len(texts)
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            text_key = text.strip() if text else ""
            if not text_key:
                results[i] = None
                continue
            
            if text_key in self._embedding_cache:
                results[i] = self._embedding_cache[text_key]
                self._stats["cache_hits"] += 1
            else:
                uncached_texts.append(text_key)
                uncached_indices.append(i)
        
        # Generate embeddings for uncached texts
        if uncached_texts:
            try:
                with self._model_lock:
                    batch_results = self._generate_batch_embeddings(uncached_texts)
                
                # Place results back in correct positions and cache them
                for j, result in enumerate(batch_results):
                    original_index = uncached_indices[j]
                    results[original_index] = result
                    
                    # Cache the result
                    self._cache_embedding(result.text, result)
                    
            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")
                # Set failed embeddings to None
                for idx in uncached_indices:
                    if results[idx] is None:
                        results[idx] = None
        
        return results
    
    def _cache_embedding(self, text_key: str, result: EmbeddingResult):
        """Cache embedding result with LRU-like management."""
        # Simple cache size management
        if len(self._embedding_cache) >= self._cache_max_size:
            # Remove oldest entries (first 200)
            items = list(self._embedding_cache.items())
            for key, _ in items[:200]:
                del self._embedding_cache[key]
            logger.debug(f"Cache cleanup: removed 200 old entries")
        
        self._embedding_cache[text_key] = result
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by current model."""
        if self.model is None:
            return 384  # Default for all-MiniLM-L6-v2
        
        # Get actual dimension from model
        try:
            test_embedding = self.model.encode("test", convert_to_numpy=True)
            return len(test_embedding)
        except Exception:
            return 384  # Fallback
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache and performance statistics."""
        cache_hit_rate = 0
        if self._stats["embeddings_generated"] + self._stats["cache_hits"] > 0:
            cache_hit_rate = self._stats["cache_hits"] / (
                self._stats["embeddings_generated"] + self._stats["cache_hits"]
            )
        
        return {
            "cache_size": len(self._embedding_cache),
            "cache_max_size": self._cache_max_size,
            "cache_hit_rate": cache_hit_rate,
            "model": self.model_name,
            "embedding_dimension": self.get_embedding_dimension(),
            "embeddings_generated": self._stats["embeddings_generated"],
            "cache_hits": self._stats["cache_hits"],
            "avg_time_per_embedding_ms": self._stats["avg_time_per_embedding"] * 1000,
            "total_time_seconds": self._stats["total_time"]
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "model_loaded": self.model is not None,
            "embedding_dimension": self.get_embedding_dimension(),
            "max_seq_length": self.max_seq_length,
            "batch_size": self.batch_size,
            "device": "cpu",
            "hardware_optimized_for": "AMD Ryzen 7 5700 (8 cores, 16GB RAM)"
        }


# Global local embeddings service instance
_local_embeddings_service: Optional[LocalEmbeddingsService] = None


def get_local_embeddings_service(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> LocalEmbeddingsService:
    """Get global local embeddings service instance."""
    global _local_embeddings_service
    if _local_embeddings_service is None or _local_embeddings_service.model_name != model_name:
        _local_embeddings_service = LocalEmbeddingsService(model_name)
    return _local_embeddings_service


async def embed_text_local(text: str) -> Optional[List[float]]:
    """Convenience function to get embedding vector for text using local model."""
    service = get_local_embeddings_service()
    result = await service.get_embedding(text)
    return result.embedding if result else None


async def embed_texts_local(texts: List[str]) -> List[Optional[List[float]]]:
    """Convenience function to get embedding vectors for multiple texts using local model."""
    service = get_local_embeddings_service()
    results = await service.get_embeddings_batch(texts)
    return [result.embedding if result else None for result in results]