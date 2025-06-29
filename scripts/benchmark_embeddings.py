#!/usr/bin/env python3
"""Benchmark script to compare local vs OpenAI embeddings quality and performance."""
import asyncio
import json
import time
import sys
import os
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from knowledge.embeddings_service import EmbeddingsService, get_embeddings_service
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from knowledge.local_embeddings_service import LocalEmbeddingsService, get_local_embeddings_service
    LOCAL_AVAILABLE = True
except ImportError:
    LOCAL_AVAILABLE = False

import numpy as np


@dataclass
class BenchmarkResult:
    """Result of embedding benchmark."""
    service_name: str
    avg_time_ms: float
    total_time_ms: float
    embeddings_count: int
    success_rate: float
    embedding_dimension: int
    cache_hit_rate: float = 0.0
    errors: List[str] = None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def calculate_embedding_similarities(embeddings1: List[List[float]], embeddings2: List[List[float]]) -> List[float]:
    """Calculate cosine similarities between corresponding embeddings."""
    similarities = []
    for emb1, emb2 in zip(embeddings1, embeddings2):
        if emb1 and emb2:
            sim = cosine_similarity(np.array(emb1), np.array(emb2))
            similarities.append(sim)
    return similarities


class EmbeddingsBenchmark:
    """Benchmark local vs OpenAI embeddings."""
    
    def __init__(self):
        """Initialize benchmark."""
        self.test_texts = [
            # Short conversational texts
            "hello how are you",
            "i'm doing great thanks",
            "what did you do today",
            "just work and study",
            "that sounds boring lol",
            
            # Medium length responses
            "i had such a long day at work today, my boss was being super demanding",
            "oh no that sucks! what happened? tell me more about it",
            "btw have you seen the new movie that came out? everyone's talking about it",
            "yeah i watched it last weekend, it was actually pretty good surprisingly",
            "we should hang out soon, it's been way too long since we last met up",
            
            # NADIA-style responses
            "hey babe 😘 how was your day? mine was pretty crazy with classes and stuff",
            "aww you're so sweet for asking! studying medicine is tough but i love it",
            "haha you always know how to make me smile 💕 you're the best",
            "i wish we could hang out in person sometime, chatting here is fun but...",
            "tell me something interesting about yourself, i want to know you better",
            
            # Technical/medical content
            "studying anatomy today, learning about the cardiovascular system",
            "medical school is challenging but i'm passionate about helping people",
            "the human body is so fascinating, especially neurological connections",
            
            # Emotional content
            "feeling a bit stressed about exams coming up next week",
            "sometimes i wonder if i made the right choice with my major",
            "thanks for always being there to listen, it means so much to me",
        ]
    
    async def benchmark_service(self, service, service_name: str) -> BenchmarkResult:
        """Benchmark a specific embeddings service."""
        print(f"\n🔄 Benchmarking {service_name}...")
        
        start_time = time.time()
        successful_embeddings = 0
        errors = []
        embeddings = []
        
        # Test individual embeddings
        for i, text in enumerate(self.test_texts):
            try:
                result = await service.get_embedding(text)
                if result and result.embedding:
                    embeddings.append(result.embedding)
                    successful_embeddings += 1
                else:
                    embeddings.append(None)
                    errors.append(f"Failed to get embedding for text {i}")
            except Exception as e:
                embeddings.append(None)
                errors.append(f"Error with text {i}: {str(e)}")
        
        # Test batch embeddings
        try:
            batch_results = await service.get_embeddings_batch(self.test_texts[:5])
            print(f"  ✅ Batch processing: {len([r for r in batch_results if r])} successful")
        except Exception as e:
            errors.append(f"Batch processing error: {str(e)}")
        
        total_time = time.time() - start_time
        
        # Get service stats
        embedding_dim = 0
        cache_hit_rate = 0
        try:
            stats = service.get_cache_stats()
            cache_hit_rate = stats.get('cache_hit_rate', 0)
            embedding_dim = stats.get('embedding_dimension', 0)
        except:
            pass
        
        result = BenchmarkResult(
            service_name=service_name,
            avg_time_ms=(total_time * 1000) / len(self.test_texts),
            total_time_ms=total_time * 1000,
            embeddings_count=successful_embeddings,
            success_rate=successful_embeddings / len(self.test_texts),
            embedding_dimension=embedding_dim,
            cache_hit_rate=cache_hit_rate,
            errors=errors
        )
        
        print(f"  ⏱️  Avg time: {result.avg_time_ms:.1f}ms per embedding")
        print(f"  ✅ Success rate: {result.success_rate:.1%}")
        print(f"  📊 Dimension: {result.embedding_dimension}")
        if cache_hit_rate > 0:
            print(f"  💾 Cache hit rate: {cache_hit_rate:.1%}")
        
        return result, embeddings
    
    async def compare_embedding_quality(self, openai_embeddings: List, local_embeddings: List):
        """Compare the quality between OpenAI and local embeddings."""
        print(f"\n🔍 Comparing embedding quality...")
        
        # Filter out None embeddings
        valid_pairs = [
            (oa, local) for oa, local in zip(openai_embeddings, local_embeddings)
            if oa is not None and local is not None
        ]
        
        if not valid_pairs:
            print("  ❌ No valid embeddings to compare")
            return
        
        openai_valid = [pair[0] for pair in valid_pairs]
        local_valid = [pair[1] for pair in valid_pairs]
        
        # Calculate similarities
        similarities = calculate_embedding_similarities(openai_valid, local_valid)
        
        if similarities:
            avg_similarity = np.mean(similarities)
            min_similarity = np.min(similarities)
            max_similarity = np.max(similarities)
            
            print(f"  📈 Average similarity: {avg_similarity:.3f}")
            print(f"  📉 Min similarity: {min_similarity:.3f}")
            print(f"  📊 Max similarity: {max_similarity:.3f}")
            
            # Quality assessment
            if avg_similarity >= 0.85:
                quality = "Excellent (≥85%)"
            elif avg_similarity >= 0.75:
                quality = "Good (75-85%)"
            elif avg_similarity >= 0.65:
                quality = "Fair (65-75%)"
            else:
                quality = "Poor (<65%)"
            
            print(f"  🎯 Quality assessment: {quality}")
            
            return {
                "avg_similarity": avg_similarity,
                "min_similarity": min_similarity,
                "max_similarity": max_similarity,
                "quality_rating": quality,
                "valid_comparisons": len(similarities)
            }
    
    def print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary."""
        print(f"\n" + "="*60)
        print(f"📊 EMBEDDING BENCHMARK SUMMARY")
        print(f"="*60)
        
        for service_name, (result, _) in results.items():
            print(f"\n{service_name.upper()}:")
            print(f"  ⏱️  Performance: {result.avg_time_ms:.1f}ms avg")
            print(f"  ✅ Reliability: {result.success_rate:.1%}")
            print(f"  📊 Dimension: {result.embedding_dimension}")
            
            if result.errors:
                print(f"  ❌ Errors: {len(result.errors)}")
        
        # Performance comparison
        if len(results) >= 2:
            times = [(name, result.avg_time_ms) for name, (result, _) in results.items()]
            times.sort(key=lambda x: x[1])
            
            print(f"\n🏆 PERFORMANCE RANKING:")
            for i, (name, time_ms) in enumerate(times, 1):
                print(f"  {i}. {name}: {time_ms:.1f}ms")
        
        # Cost analysis
        print(f"\n💰 COST ANALYSIS:")
        for service_name, (result, _) in results.items():
            if "openai" in service_name.lower():
                daily_cost = (result.embeddings_count / len(self.test_texts)) * 50 * 0.00002  # Assume 50 embeddings/day
                print(f"  {service_name}: ~${daily_cost:.4f}/day")
            else:
                print(f"  {service_name}: $0.00/day (after setup)")
    
    async def run_benchmark(self):
        """Run the complete benchmark."""
        print("🚀 Starting Embeddings Benchmark for NADIA RAG System")
        print(f"📝 Testing {len(self.test_texts)} sample texts")
        
        results = {}
        
        # Benchmark OpenAI if available
        if OPENAI_AVAILABLE:
            try:
                openai_service = get_embeddings_service()
                result, embeddings = await self.benchmark_service(openai_service, "OpenAI")
                results["OpenAI"] = (result, embeddings)
            except Exception as e:
                print(f"❌ OpenAI benchmark failed: {e}")
                results["OpenAI"] = (None, None)
        else:
            print("⚠️  OpenAI service not available")
        
        # Benchmark Local if available
        if LOCAL_AVAILABLE:
            try:
                local_service = get_local_embeddings_service()
                result, embeddings = await self.benchmark_service(local_service, "Local (sentence-transformers)")
                results["Local"] = (result, embeddings)
            except Exception as e:
                print(f"❌ Local benchmark failed: {e}")
                results["Local"] = (None, None)
        else:
            print("⚠️  Local service not available")
        
        # Compare quality if both services worked
        if "OpenAI" in results and "Local" in results:
            if results["OpenAI"][1] and results["Local"][1]:
                quality_comparison = await self.compare_embedding_quality(
                    results["OpenAI"][1], 
                    results["Local"][1]
                )
                if quality_comparison:
                    results["quality_comparison"] = quality_comparison
        
        # Print summary
        self.print_summary(results)
        
        return results


async def main():
    """Main benchmark execution."""
    benchmark = EmbeddingsBenchmark()
    results = await benchmark.run_benchmark()
    
    # Save results to file
    output_file = "benchmark_results.json"
    with open(output_file, 'w') as f:
        # Convert results to JSON-serializable format
        json_results = {}
        for name, (result, embeddings) in results.items():
            if result:
                json_results[name] = {
                    "service_name": result.service_name,
                    "avg_time_ms": result.avg_time_ms,
                    "total_time_ms": result.total_time_ms,
                    "embeddings_count": result.embeddings_count,
                    "success_rate": result.success_rate,
                    "embedding_dimension": result.embedding_dimension,
                    "cache_hit_rate": result.cache_hit_rate,
                    "error_count": len(result.errors) if result.errors else 0
                }
        
        if "quality_comparison" in results:
            json_results["quality_comparison"] = results["quality_comparison"]
        
        json.dump(json_results, f, indent=2)
    
    print(f"\n💾 Results saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())