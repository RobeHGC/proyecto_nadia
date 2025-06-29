#!/usr/bin/env python3
"""
Performance benchmarking and optimization tool for hybrid memory system.
Measures latency, throughput, memory usage, and provides optimization recommendations.
"""

import asyncio
import logging
import time
import psutil
import statistics
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import matplotlib.pyplot as plt
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import hybrid memory components
try:
    from memory.hybrid_memory_manager import HybridMemoryManager, MemoryItem, MemoryTier
    from memory.user_memory import UserMemoryManager
    from agents.memory_strategies import AgentConfigurationManager, AgentType
    from knowledge.rag_manager import RAGManager
    HYBRID_MEMORY_AVAILABLE = True
except ImportError as e:
    logger.error(f"Hybrid memory system not available: {e}")
    HYBRID_MEMORY_AVAILABLE = False

@dataclass
class BenchmarkResult:
    """Container for benchmark results."""
    operation: str
    latency_ms: float
    throughput_ops_per_sec: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success_rate: float
    error_count: int
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class BenchmarkSuite:
    """Complete benchmark suite results."""
    memory_storage: List[BenchmarkResult]
    memory_retrieval: List[BenchmarkResult]
    memory_consolidation: List[BenchmarkResult]
    rag_integration: List[BenchmarkResult]
    agent_configuration: List[BenchmarkResult]
    system_metrics: Dict[str, Any]
    recommendations: List[str]
    total_duration_seconds: float

class HybridMemoryBenchmark:
    """Comprehensive benchmark suite for hybrid memory system."""
    
    def __init__(self, database_url: str = None, mongodb_uri: str = None):
        self.database_url = database_url
        self.mongodb_uri = mongodb_uri
        self.memory_manager: Optional[HybridMemoryManager] = None
        self.user_memory: Optional[UserMemoryManager] = None
        self.config_manager: Optional[AgentConfigurationManager] = None
        self.rag_manager: Optional[RAGManager] = None
        
        # Benchmark configuration
        self.benchmark_config = {
            "memory_operations_count": 100,
            "retrieval_queries_count": 50,
            "concurrent_users": 10,
            "memory_sizes": [10, 50, 100, 500],  # Number of memories per user
            "query_complexities": ["simple", "medium", "complex"],
            "consolidation_intervals": [100, 500, 1000],  # Number of memories before consolidation
        }
        
        # Results storage
        self.results: List[BenchmarkResult] = []
    
    async def initialize(self):
        """Initialize all components for benchmarking."""
        try:
            # Initialize hybrid memory manager
            if self.database_url:
                self.memory_manager = HybridMemoryManager(self.database_url, self.mongodb_uri)
                await self.memory_manager.initialize()
                logger.info("Hybrid memory manager initialized")
            
            # Initialize user memory
            self.user_memory = UserMemoryManager(enable_hybrid_memory=True)
            logger.info("User memory manager initialized")
            
            # Initialize agent configuration
            self.config_manager = AgentConfigurationManager(self.database_url)
            await self.config_manager.initialize()
            logger.info("Agent configuration manager initialized")
            
            # Initialize RAG manager
            self.rag_manager = RAGManager(enable_memory_integration=True)
            await self.rag_manager.initialize()
            logger.info("RAG manager initialized")
            
        except Exception as e:
            logger.warning(f"Partial initialization due to: {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        if self.memory_manager:
            await self.memory_manager.close()
        if self.user_memory:
            await self.user_memory.close()
        if self.config_manager:
            await self.config_manager.close()
    
    async def run_comprehensive_benchmark(self) -> BenchmarkSuite:
        """Run the complete benchmark suite."""
        logger.info("Starting comprehensive hybrid memory benchmark...")
        start_time = time.time()
        
        # Initialize system monitoring
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run benchmark categories
        storage_results = await self.benchmark_memory_storage()
        retrieval_results = await self.benchmark_memory_retrieval()
        consolidation_results = await self.benchmark_memory_consolidation()
        rag_results = await self.benchmark_rag_integration()
        config_results = await self.benchmark_agent_configuration()
        
        # Collect system metrics
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        system_metrics = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_growth_mb": final_memory - initial_memory,
            "cpu_cores": psutil.cpu_count(),
            "total_ram_gb": psutil.virtual_memory().total / 1024**3,
            "python_version": psutil.sys.version.split()[0]
        }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            storage_results + retrieval_results + consolidation_results + rag_results + config_results,
            system_metrics
        )
        
        total_duration = time.time() - start_time
        
        benchmark_suite = BenchmarkSuite(
            memory_storage=storage_results,
            memory_retrieval=retrieval_results,
            memory_consolidation=consolidation_results,
            rag_integration=rag_results,
            agent_configuration=config_results,
            system_metrics=system_metrics,
            recommendations=recommendations,
            total_duration_seconds=total_duration
        )
        
        logger.info(f"Benchmark completed in {total_duration:.2f} seconds")
        return benchmark_suite
    
    async def benchmark_memory_storage(self) -> List[BenchmarkResult]:
        """Benchmark memory storage operations."""
        logger.info("Benchmarking memory storage operations...")
        results = []
        
        if not self.memory_manager:
            logger.warning("Memory manager not available, skipping storage benchmark")
            return results
        
        for memory_size in self.benchmark_config["memory_sizes"]:
            # Create test memories
            memories = []
            for i in range(memory_size):
                memory = MemoryItem(
                    user_id=f"benchmark_user_{i % 10}",  # 10 different users
                    content=f"Benchmark memory content {i} with some additional text to simulate realistic memory size",
                    timestamp=datetime.utcnow() - timedelta(minutes=i),
                    memory_type="conversation" if i % 2 == 0 else "preference",
                    importance=0.3 + (i % 7) * 0.1,  # Vary importance
                    tier=MemoryTier.HOT,
                    metadata={
                        "benchmark_id": i,
                        "category": f"category_{i % 5}",
                        "source": "benchmark"
                    }
                )
                memories.append(memory)
            
            # Benchmark storage
            start_time = time.time()
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024
            initial_cpu = process.cpu_percent()
            
            success_count = 0
            error_count = 0
            
            for memory in memories:
                try:
                    await self.memory_manager.store_memory(memory)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    logger.debug(f"Storage error: {e}")
            
            end_time = time.time()
            final_memory = process.memory_info().rss / 1024 / 1024
            final_cpu = process.cpu_percent()
            
            duration = end_time - start_time
            throughput = memory_size / duration if duration > 0 else 0
            avg_latency = (duration * 1000) / memory_size if memory_size > 0 else 0
            success_rate = success_count / memory_size if memory_size > 0 else 0
            
            result = BenchmarkResult(
                operation=f"memory_storage_{memory_size}",
                latency_ms=avg_latency,
                throughput_ops_per_sec=throughput,
                memory_usage_mb=final_memory - initial_memory,
                cpu_usage_percent=(final_cpu + initial_cpu) / 2,
                success_rate=success_rate,
                error_count=error_count,
                timestamp=datetime.utcnow(),
                metadata={
                    "memory_count": memory_size,
                    "unique_users": min(10, memory_size),
                    "duration_seconds": duration
                }
            )
            
            results.append(result)
            logger.info(f"Storage {memory_size} memories: {avg_latency:.2f}ms avg, {throughput:.2f} ops/sec")
        
        return results
    
    async def benchmark_memory_retrieval(self) -> List[BenchmarkResult]:
        """Benchmark memory retrieval operations."""
        logger.info("Benchmarking memory retrieval operations...")
        results = []
        
        if not self.memory_manager:
            logger.warning("Memory manager not available, skipping retrieval benchmark")
            return results
        
        # Test different query complexities
        test_queries = {
            "simple": ["test", "memory", "conversation"],
            "medium": ["I love hiking in the mountains", "My work as a doctor", "Family gathering last weekend"],
            "complex": [
                "Tell me about the conversation where we discussed mountain climbing and photography",
                "What did I mention about my family and their preferences for outdoor activities",
                "Recall our discussion about work-life balance and stress management techniques"
            ]
        }
        
        for complexity, queries in test_queries.items():
            for user_count in [1, 5, 10]:
                start_time = time.time()
                process = psutil.Process()
                initial_memory = process.memory_info().rss / 1024 / 1024
                initial_cpu = process.cpu_percent()
                
                total_operations = 0
                success_count = 0
                error_count = 0
                
                for user_id in range(user_count):
                    for query in queries:
                        try:
                            memories = await self.memory_manager.retrieve_memories(
                                user_id=f"benchmark_user_{user_id}",
                                query=query,
                                memory_types=["conversation", "preference"],
                                limit=5,
                                min_importance=0.3
                            )
                            success_count += 1
                            total_operations += 1
                        except Exception as e:
                            error_count += 1
                            total_operations += 1
                            logger.debug(f"Retrieval error: {e}")
                
                end_time = time.time()
                final_memory = process.memory_info().rss / 1024 / 1024
                final_cpu = process.cpu_percent()
                
                duration = end_time - start_time
                throughput = total_operations / duration if duration > 0 else 0
                avg_latency = (duration * 1000) / total_operations if total_operations > 0 else 0
                success_rate = success_count / total_operations if total_operations > 0 else 0
                
                result = BenchmarkResult(
                    operation=f"memory_retrieval_{complexity}_{user_count}users",
                    latency_ms=avg_latency,
                    throughput_ops_per_sec=throughput,
                    memory_usage_mb=final_memory - initial_memory,
                    cpu_usage_percent=(final_cpu + initial_cpu) / 2,
                    success_rate=success_rate,
                    error_count=error_count,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "query_complexity": complexity,
                        "user_count": user_count,
                        "queries_per_user": len(queries),
                        "total_operations": total_operations
                    }
                )
                
                results.append(result)
                logger.info(f"Retrieval {complexity} x {user_count} users: {avg_latency:.2f}ms avg, {throughput:.2f} ops/sec")
        
        return results
    
    async def benchmark_memory_consolidation(self) -> List[BenchmarkResult]:
        """Benchmark memory consolidation operations."""
        logger.info("Benchmarking memory consolidation...")
        results = []
        
        if not self.memory_manager:
            logger.warning("Memory manager not available, skipping consolidation benchmark")
            return results
        
        for interval in self.benchmark_config["consolidation_intervals"]:
            start_time = time.time()
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024
            initial_cpu = process.cpu_percent()
            
            success_count = 0
            error_count = 0
            total_stats = {"promoted": 0, "demoted": 0, "archived": 0, "compressed": 0}
            
            # Test consolidation for multiple users
            for user_id in range(5):  # 5 test users
                try:
                    stats = await self.memory_manager.consolidate_memories(f"benchmark_user_{user_id}")
                    for key in total_stats:
                        total_stats[key] += stats.get(key, 0)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    logger.debug(f"Consolidation error: {e}")
            
            end_time = time.time()
            final_memory = process.memory_info().rss / 1024 / 1024
            final_cpu = process.cpu_percent()
            
            duration = end_time - start_time
            throughput = success_count / duration if duration > 0 else 0
            avg_latency = (duration * 1000) / success_count if success_count > 0 else 0
            success_rate = success_count / 5
            
            result = BenchmarkResult(
                operation=f"memory_consolidation_{interval}",
                latency_ms=avg_latency,
                throughput_ops_per_sec=throughput,
                memory_usage_mb=final_memory - initial_memory,
                cpu_usage_percent=(final_cpu + initial_cpu) / 2,
                success_rate=success_rate,
                error_count=error_count,
                timestamp=datetime.utcnow(),
                metadata={
                    "consolidation_interval": interval,
                    "users_processed": 5,
                    "consolidation_stats": total_stats
                }
            )
            
            results.append(result)
            logger.info(f"Consolidation {interval}: {avg_latency:.2f}ms avg, processed {total_stats}")
        
        return results
    
    async def benchmark_rag_integration(self) -> List[BenchmarkResult]:
        """Benchmark RAG system integration."""
        logger.info("Benchmarking RAG integration...")
        results = []
        
        if not self.rag_manager:
            logger.warning("RAG manager not available, skipping RAG benchmark")
            return results
        
        test_scenarios = [
            {"message": "Tell me about hiking", "context_size": "small"},
            {"message": "I want to learn about mountain climbing safety and equipment recommendations", "context_size": "medium"},
            {"message": "Can you help me understand the relationship between cardiovascular health, outdoor activities like hiking and rock climbing, and mental wellness, especially for medical students dealing with stress?", "context_size": "large"}
        ]
        
        for scenario in test_scenarios:
            start_time = time.time()
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024
            initial_cpu = process.cpu_percent()
            
            success_count = 0
            error_count = 0
            
            # Test RAG enhancement for multiple users
            for user_id in range(5):
                try:
                    response = await self.rag_manager.enhance_prompt_with_context(
                        user_message=scenario["message"],
                        user_id=f"benchmark_user_{user_id}",
                        conversation_context={"user_id": f"benchmark_user_{user_id}"}
                    )
                    if response.success:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    error_count += 1
                    logger.debug(f"RAG error: {e}")
            
            end_time = time.time()
            final_memory = process.memory_info().rss / 1024 / 1024
            final_cpu = process.cpu_percent()
            
            duration = end_time - start_time
            total_operations = success_count + error_count
            throughput = total_operations / duration if duration > 0 else 0
            avg_latency = (duration * 1000) / total_operations if total_operations > 0 else 0
            success_rate = success_count / total_operations if total_operations > 0 else 0
            
            result = BenchmarkResult(
                operation=f"rag_integration_{scenario['context_size']}",
                latency_ms=avg_latency,
                throughput_ops_per_sec=throughput,
                memory_usage_mb=final_memory - initial_memory,
                cpu_usage_percent=(final_cpu + initial_cpu) / 2,
                success_rate=success_rate,
                error_count=error_count,
                timestamp=datetime.utcnow(),
                metadata={
                    "context_size": scenario["context_size"],
                    "message_length": len(scenario["message"]),
                    "users_tested": 5
                }
            )
            
            results.append(result)
            logger.info(f"RAG {scenario['context_size']}: {avg_latency:.2f}ms avg, {success_rate:.2%} success")
        
        return results
    
    async def benchmark_agent_configuration(self) -> List[BenchmarkResult]:
        """Benchmark agent configuration operations."""
        logger.info("Benchmarking agent configuration...")
        results = []
        
        if not self.config_manager:
            logger.warning("Config manager not available, skipping configuration benchmark")
            return results
        
        start_time = time.time()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        initial_cpu = process.cpu_percent()
        
        success_count = 0
        error_count = 0
        
        # Test configuration operations for all agent types
        for agent_type in AgentType:
            try:
                # Get configuration
                config = await self.config_manager.get_agent_config(agent_type)
                
                # Test memory strategy selection
                strategy, params = await self.config_manager.get_memory_strategy_for_context(
                    agent_type=agent_type,
                    context_size=8000,
                    user_activity_level="normal",
                    conversation_complexity="medium"
                )
                
                success_count += 2  # Two operations
            except Exception as e:
                error_count += 2
                logger.debug(f"Config error for {agent_type}: {e}")
        
        end_time = time.time()
        final_memory = process.memory_info().rss / 1024 / 1024
        final_cpu = process.cpu_percent()
        
        duration = end_time - start_time
        total_operations = success_count + error_count
        throughput = total_operations / duration if duration > 0 else 0
        avg_latency = (duration * 1000) / total_operations if total_operations > 0 else 0
        success_rate = success_count / total_operations if total_operations > 0 else 0
        
        result = BenchmarkResult(
            operation="agent_configuration",
            latency_ms=avg_latency,
            throughput_ops_per_sec=throughput,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=(final_cpu + initial_cpu) / 2,
            success_rate=success_rate,
            error_count=error_count,
            timestamp=datetime.utcnow(),
            metadata={
                "agent_types_tested": len(AgentType),
                "operations_per_agent": 2
            }
        )
        
        results.append(result)
        logger.info(f"Agent config: {avg_latency:.2f}ms avg, {success_rate:.2%} success")
        
        return results
    
    def _generate_recommendations(self, results: List[BenchmarkResult], system_metrics: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations based on benchmark results."""
        recommendations = []
        
        # Analyze latency patterns
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        if latencies:
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)
            
            if avg_latency > 100:
                recommendations.append(f"High average latency ({avg_latency:.1f}ms). Consider enabling database connection pooling and optimizing queries.")
            
            if max_latency > 1000:
                recommendations.append(f"Very high maximum latency ({max_latency:.1f}ms). Implement query timeouts and circuit breakers.")
        
        # Analyze memory usage
        memory_usage = [r.memory_usage_mb for r in results if r.memory_usage_mb > 0]
        if memory_usage:
            total_memory_growth = sum(memory_usage)
            if total_memory_growth > 100:
                recommendations.append(f"High memory usage ({total_memory_growth:.1f}MB growth). Implement memory cleanup and connection pooling.")
        
        # Analyze success rates
        success_rates = [r.success_rate for r in results]
        if success_rates:
            avg_success_rate = statistics.mean(success_rates)
            if avg_success_rate < 0.95:
                recommendations.append(f"Low success rate ({avg_success_rate:.1%}). Improve error handling and add retry mechanisms.")
        
        # Analyze throughput
        throughputs = [r.throughput_ops_per_sec for r in results if r.throughput_ops_per_sec > 0]
        if throughputs:
            avg_throughput = statistics.mean(throughputs)
            if avg_throughput < 10:
                recommendations.append(f"Low throughput ({avg_throughput:.1f} ops/sec). Consider adding caching and batch operations.")
        
        # System-specific recommendations
        if system_metrics.get("memory_growth_mb", 0) > 50:
            recommendations.append("Significant memory growth detected. Monitor for memory leaks and implement periodic cleanup.")
        
        if system_metrics.get("total_ram_gb", 0) < 4:
            recommendations.append("Low system RAM. Consider optimizing memory usage or upgrading hardware.")
        
        if system_metrics.get("cpu_cores", 0) < 4:
            recommendations.append("Limited CPU cores. Consider async optimization and reducing CPU-intensive operations.")
        
        # Default recommendations if no issues found
        if not recommendations:
            recommendations.append("Performance looks good! Consider monitoring in production for optimization opportunities.")
        
        return recommendations
    
    def generate_report(self, benchmark_suite: BenchmarkSuite, output_file: str = None) -> str:
        """Generate a comprehensive benchmark report."""
        report_lines = []
        
        # Header
        report_lines.extend([
            "=" * 80,
            "HYBRID MEMORY SYSTEM PERFORMANCE BENCHMARK REPORT",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            f"Total Duration: {benchmark_suite.total_duration_seconds:.2f} seconds",
            ""
        ])
        
        # System Metrics
        report_lines.extend([
            "SYSTEM METRICS:",
            "-" * 40,
            f"Initial Memory: {benchmark_suite.system_metrics['initial_memory_mb']:.1f} MB",
            f"Final Memory: {benchmark_suite.system_metrics['final_memory_mb']:.1f} MB",
            f"Memory Growth: {benchmark_suite.system_metrics['memory_growth_mb']:.1f} MB",
            f"CPU Cores: {benchmark_suite.system_metrics['cpu_cores']}",
            f"Total RAM: {benchmark_suite.system_metrics['total_ram_gb']:.1f} GB",
            ""
        ])
        
        # Results by category
        categories = [
            ("Memory Storage", benchmark_suite.memory_storage),
            ("Memory Retrieval", benchmark_suite.memory_retrieval),
            ("Memory Consolidation", benchmark_suite.memory_consolidation),
            ("RAG Integration", benchmark_suite.rag_integration),
            ("Agent Configuration", benchmark_suite.agent_configuration)
        ]
        
        for category_name, results in categories:
            if not results:
                continue
                
            report_lines.extend([
                f"{category_name.upper()}:",
                "-" * 40
            ])
            
            for result in results:
                report_lines.extend([
                    f"Operation: {result.operation}",
                    f"  Latency: {result.latency_ms:.2f} ms",
                    f"  Throughput: {result.throughput_ops_per_sec:.2f} ops/sec",
                    f"  Memory Usage: {result.memory_usage_mb:.2f} MB",
                    f"  Success Rate: {result.success_rate:.1%}",
                    f"  Errors: {result.error_count}",
                    ""
                ])
        
        # Recommendations
        report_lines.extend([
            "OPTIMIZATION RECOMMENDATIONS:",
            "-" * 40
        ])
        
        for i, recommendation in enumerate(benchmark_suite.recommendations, 1):
            report_lines.append(f"{i}. {recommendation}")
        
        report_lines.extend(["", "=" * 80])
        
        # Write to file if specified
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            logger.info(f"Report written to {output_file}")
        
        return report_content
    
    def plot_performance_charts(self, benchmark_suite: BenchmarkSuite, output_dir: str = "benchmark_charts"):
        """Generate performance visualization charts."""
        try:
            import os
            os.makedirs(output_dir, exist_ok=True)
            
            # Collect all results
            all_results = (
                benchmark_suite.memory_storage + 
                benchmark_suite.memory_retrieval + 
                benchmark_suite.memory_consolidation + 
                benchmark_suite.rag_integration + 
                benchmark_suite.agent_configuration
            )
            
            if not all_results:
                logger.warning("No results to plot")
                return
            
            # Latency chart
            plt.figure(figsize=(12, 6))
            operations = [r.operation for r in all_results]
            latencies = [r.latency_ms for r in all_results]
            
            plt.subplot(1, 2, 1)
            plt.bar(range(len(operations)), latencies)
            plt.title("Operation Latency")
            plt.ylabel("Latency (ms)")
            plt.xticks(range(len(operations)), operations, rotation=45, ha='right')
            plt.tight_layout()
            
            # Throughput chart
            plt.subplot(1, 2, 2)
            throughputs = [r.throughput_ops_per_sec for r in all_results]
            plt.bar(range(len(operations)), throughputs)
            plt.title("Operation Throughput")
            plt.ylabel("Ops/sec")
            plt.xticks(range(len(operations)), operations, rotation=45, ha='right')
            plt.tight_layout()
            
            plt.savefig(f"{output_dir}/performance_overview.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            # Success rate chart
            plt.figure(figsize=(10, 6))
            success_rates = [r.success_rate * 100 for r in all_results]
            colors = ['green' if sr >= 95 else 'orange' if sr >= 80 else 'red' for sr in success_rates]
            
            plt.bar(range(len(operations)), success_rates, color=colors)
            plt.title("Operation Success Rates")
            plt.ylabel("Success Rate (%)")
            plt.ylim(0, 100)
            plt.axhline(y=95, color='green', linestyle='--', alpha=0.7, label='Target: 95%')
            plt.xticks(range(len(operations)), operations, rotation=45, ha='right')
            plt.legend()
            plt.tight_layout()
            
            plt.savefig(f"{output_dir}/success_rates.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Performance charts saved to {output_dir}/")
            
        except ImportError:
            logger.warning("matplotlib not available, skipping chart generation")
        except Exception as e:
            logger.error(f"Error generating charts: {e}")

async def main():
    """Main benchmark execution function."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Hybrid Memory System Benchmark")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="PostgreSQL database URL")
    parser.add_argument("--mongodb-uri", default=os.getenv("MONGODB_URI"), help="MongoDB connection URI")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory for results")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmark with reduced test sizes")
    parser.add_argument("--charts", action="store_true", help="Generate performance charts")
    
    args = parser.parse_args()
    
    if not HYBRID_MEMORY_AVAILABLE:
        logger.error("Hybrid memory system not available. Cannot run benchmark.")
        return 1
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize benchmark
    benchmark = HybridMemoryBenchmark(args.database_url, args.mongodb_uri)
    
    # Adjust configuration for quick benchmark
    if args.quick:
        benchmark.benchmark_config.update({
            "memory_operations_count": 20,
            "retrieval_queries_count": 10,
            "concurrent_users": 3,
            "memory_sizes": [10, 50],
            "consolidation_intervals": [100]
        })
        logger.info("Running quick benchmark with reduced test sizes")
    
    try:
        await benchmark.initialize()
        
        # Run benchmark suite
        results = await benchmark.run_comprehensive_benchmark()
        
        # Generate report
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = f"{args.output_dir}/benchmark_report_{timestamp}.txt"
        report = benchmark.generate_report(results, report_file)
        
        # Save JSON results
        json_file = f"{args.output_dir}/benchmark_results_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(asdict(results), f, indent=2, default=str)
        
        # Generate charts if requested
        if args.charts:
            benchmark.plot_performance_charts(results, f"{args.output_dir}/charts_{timestamp}")
        
        # Print summary
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        all_results = (
            results.memory_storage + results.memory_retrieval + 
            results.memory_consolidation + results.rag_integration + 
            results.agent_configuration
        )
        
        if all_results:
            avg_latency = statistics.mean([r.latency_ms for r in all_results if r.latency_ms > 0])
            avg_throughput = statistics.mean([r.throughput_ops_per_sec for r in all_results if r.throughput_ops_per_sec > 0])
            avg_success_rate = statistics.mean([r.success_rate for r in all_results])
            
            print(f"Average Latency: {avg_latency:.2f} ms")
            print(f"Average Throughput: {avg_throughput:.2f} ops/sec")
            print(f"Average Success Rate: {avg_success_rate:.1%}")
            print(f"Memory Growth: {results.system_metrics['memory_growth_mb']:.1f} MB")
        
        print(f"\nFull report: {report_file}")
        print(f"JSON results: {json_file}")
        
        if len(results.recommendations) > 0:
            print(f"\nTop Recommendation: {results.recommendations[0]}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return 1
        
    finally:
        await benchmark.cleanup()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)