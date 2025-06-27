# tests/test_resource_exhaustion.py
"""Resource exhaustion and system limits testing."""
import asyncio
import time
import psutil
import gc
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import redis.asyncio as redis

from database.models import DatabaseManager
from memory.user_memory import UserMemoryManager


class ResourceExhaustionSimulator:
    """Simulate various resource exhaustion scenarios."""
    
    def __init__(self):
        self.initial_memory = None
        self.memory_samples = []
        self.cpu_samples = []
        self.connection_counts = {}
        
    def start_monitoring(self):
        """Start monitoring system resources."""
        self.initial_memory = psutil.virtual_memory().used
        self.memory_samples = []
        self.cpu_samples = []
        
    def sample_resources(self):
        """Take a snapshot of current resource usage."""
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        
        sample = {
            'timestamp': time.time(),
            'memory_used_mb': memory.used / 1024 / 1024,
            'memory_percent': memory.percent,
            'cpu_percent': cpu,
            'process_count': len(psutil.pids())
        }
        
        self.memory_samples.append(sample)
        self.cpu_samples.append(cpu)
        
        return sample
    
    async def simulate_memory_exhaustion(self, target_mb: int, increment_mb: int = 10) -> Dict[str, Any]:
        """Simulate gradual memory consumption up to target."""
        memory_consumers = []
        results = {
            'target_mb': target_mb,
            'achieved_mb': 0,
            'memory_errors': [],
            'samples': [],
            'peak_memory': 0,
            'system_impact': {}
        }
        
        try:
            current_mb = 0
            while current_mb < target_mb:
                try:
                    # Allocate memory in chunks
                    chunk_size = min(increment_mb, target_mb - current_mb)
                    memory_chunk = bytearray(chunk_size * 1024 * 1024)  # MB to bytes
                    memory_consumers.append(memory_chunk)
                    current_mb += chunk_size
                    
                    # Sample resources
                    sample = self.sample_resources()
                    results['samples'].append(sample)
                    results['peak_memory'] = max(results['peak_memory'], sample['memory_used_mb'])
                    
                    # Check system impact
                    if sample['memory_percent'] > 90:
                        results['system_impact']['critical_memory'] = True
                        break
                    
                    # Small delay to observe system behavior
                    await asyncio.sleep(0.1)
                    
                except MemoryError as e:
                    results['memory_errors'].append(f"MemoryError at {current_mb}MB: {str(e)}")
                    break
                except Exception as e:
                    results['memory_errors'].append(f"Unexpected error at {current_mb}MB: {str(e)}")
                    break
            
            results['achieved_mb'] = current_mb
            
        finally:
            # Clean up allocated memory
            memory_consumers.clear()
            gc.collect()
            
        return results
    
    async def simulate_connection_exhaustion(self, max_connections: int, connection_type: str = "redis") -> Dict[str, Any]:
        """Simulate connection pool exhaustion."""
        connections = []
        results = {
            'max_connections': max_connections,
            'successful_connections': 0,
            'connection_errors': [],
            'connection_times': [],
            'exhaustion_detected': False
        }
        
        try:
            for i in range(max_connections):
                try:
                    start_time = time.time()
                    
                    if connection_type == "redis":
                        # Mock Redis connection creation
                        with patch('redis.asyncio.from_url') as mock_redis:
                            mock_conn = AsyncMock()
                            mock_redis.return_value = mock_conn
                            
                            # Simulate connection overhead
                            await asyncio.sleep(0.01)  # Connection establishment time
                            
                            conn = await redis.from_url("redis://localhost:6379")
                            connections.append(conn)
                            
                    elif connection_type == "database":
                        # Mock database connection
                        with patch('database.models.DatabaseManager') as mock_db:
                            db_instance = AsyncMock()
                            mock_db.return_value = db_instance
                            
                            await asyncio.sleep(0.02)  # DB connection time
                            connections.append(db_instance)
                    
                    connection_time = time.time() - start_time
                    results['connection_times'].append(connection_time)
                    results['successful_connections'] += 1
                    
                    # Check for performance degradation
                    if connection_time > 1.0:  # Slow connection indicates exhaustion
                        results['exhaustion_detected'] = True
                        results['connection_errors'].append(
                            f"Connection {i} took {connection_time:.2f}s (performance degradation)"
                        )
                    
                except Exception as e:
                    results['connection_errors'].append(f"Connection {i} failed: {str(e)}")
                    if "pool" in str(e).lower() or "limit" in str(e).lower():
                        results['exhaustion_detected'] = True
                    break
        
        finally:
            # Clean up connections
            for conn in connections:
                try:
                    if hasattr(conn, 'aclose'):
                        await conn.aclose()
                    elif hasattr(conn, 'close'):
                        await conn.close()
                except:
                    pass
        
        return results
    
    async def simulate_cpu_exhaustion(self, duration_seconds: int, cpu_threads: int = 4) -> Dict[str, Any]:
        """Simulate high CPU usage."""
        results = {
            'duration_seconds': duration_seconds,
            'cpu_threads': cpu_threads,
            'cpu_samples': [],
            'peak_cpu': 0,
            'avg_cpu': 0,
            'system_impact': {}
        }
        
        def cpu_intensive_task(task_id: int, stop_event: threading.Event):
            """CPU-intensive task for load simulation."""
            counter = 0
            while not stop_event.is_set():
                # Busy work to consume CPU
                for _ in range(10000):
                    counter += 1
                # Small break to allow monitoring
                time.sleep(0.001)
        
        # Start CPU-intensive threads
        stop_event = threading.Event()
        threads = []
        
        try:
            for i in range(cpu_threads):
                thread = threading.Thread(
                    target=cpu_intensive_task, 
                    args=(i, stop_event)
                )
                thread.start()
                threads.append(thread)
            
            # Monitor CPU usage
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                cpu_sample = psutil.cpu_percent(interval=0.5)
                results['cpu_samples'].append({
                    'timestamp': time.time(),
                    'cpu_percent': cpu_sample
                })
                results['peak_cpu'] = max(results['peak_cpu'], cpu_sample)
                
                # Check system impact
                if cpu_sample > 95:
                    results['system_impact']['critical_cpu'] = True
                
                await asyncio.sleep(0.5)
        
        finally:
            # Stop CPU threads
            stop_event.set()
            for thread in threads:
                thread.join(timeout=1)
        
        # Calculate average CPU
        if results['cpu_samples']:
            results['avg_cpu'] = sum(s['cpu_percent'] for s in results['cpu_samples']) / len(results['cpu_samples'])
        
        return results
    
    async def simulate_disk_space_exhaustion(self, target_mb: int, temp_dir: str = "/tmp") -> Dict[str, Any]:
        """Simulate disk space consumption."""
        results = {
            'target_mb': target_mb,
            'files_created': 0,
            'disk_errors': [],
            'disk_samples': []
        }
        
        created_files = []
        
        try:
            for i in range(target_mb):
                try:
                    # Create 1MB files
                    filename = f"{temp_dir}/test_exhaustion_{i}.tmp"
                    with open(filename, 'wb') as f:
                        f.write(b'0' * (1024 * 1024))  # 1MB of zeros
                    
                    created_files.append(filename)
                    results['files_created'] += 1
                    
                    # Sample disk usage
                    disk_usage = psutil.disk_usage(temp_dir)
                    results['disk_samples'].append({
                        'timestamp': time.time(),
                        'free_mb': disk_usage.free / 1024 / 1024,
                        'used_percent': (disk_usage.used / disk_usage.total) * 100
                    })
                    
                    # Check if disk is getting full
                    if disk_usage.free < 100 * 1024 * 1024:  # Less than 100MB free
                        results['disk_errors'].append("Disk space critically low, stopping test")
                        break
                    
                    await asyncio.sleep(0.01)  # Small delay
                    
                except IOError as e:
                    results['disk_errors'].append(f"File {i}: {str(e)}")
                    break
        
        finally:
            # Clean up created files
            for filename in created_files:
                try:
                    import os
                    os.remove(filename)
                except:
                    pass
        
        return results


@pytest.fixture
def resource_simulator():
    """Fixture providing resource exhaustion simulator."""
    return ResourceExhaustionSimulator()


class TestResourceExhaustion:
    """Test suite for resource exhaustion scenarios."""
    
    @pytest.mark.asyncio
    async def test_memory_consumption_monitoring(self, resource_simulator):
        """Test memory consumption monitoring and limits."""
        # Test moderate memory consumption (50MB)
        result = await resource_simulator.simulate_memory_exhaustion(target_mb=50, increment_mb=5)
        
        # Should be able to allocate moderate memory
        assert result['achieved_mb'] >= 40, f"Could only allocate {result['achieved_mb']}MB of 50MB target"
        assert len(result['memory_errors']) == 0, f"Unexpected memory errors: {result['memory_errors']}"
        
        # Memory should increase during test
        if len(result['samples']) > 1:
            initial_memory = result['samples'][0]['memory_used_mb']
            peak_memory = result['peak_memory']
            assert peak_memory > initial_memory, "Memory consumption not detected"
    
    @pytest.mark.asyncio
    async def test_redis_connection_pool_limits(self, resource_simulator):
        """Test Redis connection pool exhaustion."""
        result = await resource_simulator.simulate_connection_exhaustion(
            max_connections=50, connection_type="redis"
        )
        
        # Should handle reasonable number of connections
        assert result['successful_connections'] >= 40, \
            f"Too few successful connections: {result['successful_connections']}/50"
        
        # Connection times should remain reasonable
        if result['connection_times']:
            avg_connection_time = sum(result['connection_times']) / len(result['connection_times'])
            assert avg_connection_time < 0.5, \
                f"Average connection time too high: {avg_connection_time:.3f}s"
        
        # Should detect exhaustion if it occurs
        if result['exhaustion_detected']:
            assert len(result['connection_errors']) > 0, \
                "Exhaustion detected but no error messages recorded"
    
    @pytest.mark.asyncio
    async def test_database_connection_limits(self, resource_simulator):
        """Test database connection pool exhaustion."""
        result = await resource_simulator.simulate_connection_exhaustion(
            max_connections=30, connection_type="database"
        )
        
        # Database should handle concurrent connections
        assert result['successful_connections'] >= 25, \
            f"Too few successful DB connections: {result['successful_connections']}/30"
        
        # Should not have excessive errors
        assert len(result['connection_errors']) <= 5, \
            f"Too many connection errors: {result['connection_errors']}"
    
    @pytest.mark.asyncio
    async def test_cpu_exhaustion_handling(self, resource_simulator):
        """Test system behavior under high CPU load."""
        result = await resource_simulator.simulate_cpu_exhaustion(
            duration_seconds=5, cpu_threads=2
        )
        
        # Should generate measurable CPU load
        assert result['peak_cpu'] > 50, f"CPU load too low: {result['peak_cpu']}%"
        assert result['avg_cpu'] > 30, f"Average CPU too low: {result['avg_cpu']}%"
        
        # System should remain responsive (not completely locked up)
        assert len(result['cpu_samples']) >= 8, \
            f"Too few CPU samples collected: {len(result['cpu_samples'])}"
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self):
        """Test for memory leaks in long-running operations."""
        # Record initial memory
        initial_memory = psutil.virtual_memory().used / 1024 / 1024  # MB
        
        # Simulate many operations that might leak memory
        with patch('memory.user_memory.UserMemoryManager') as mock_memory:
            memory_manager = AsyncMock()
            mock_memory.return_value = memory_manager
            memory_manager.add_message = AsyncMock()
            memory_manager.get_recent_history = AsyncMock(return_value=[])
            
            # Perform 1000 memory operations
            for i in range(1000):
                await memory_manager.add_message(f"user_{i % 10}", f"Message {i}", is_bot=False)
                await memory_manager.get_recent_history(f"user_{i % 10}", limit=50)
                
                # Force garbage collection periodically
                if i % 100 == 0:
                    gc.collect()
        
        # Check final memory
        final_memory = psutil.virtual_memory().used / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (allow some growth)
        assert memory_increase < 50, \
            f"Potential memory leak: {memory_increase:.1f}MB increase after 1000 operations"
    
    @pytest.mark.asyncio
    async def test_queue_overflow_handling(self):
        """Test message queue behavior when overwhelmed."""
        queue_sizes = []
        errors = []
        
        with patch('redis.asyncio.from_url') as mock_redis:
            redis_conn = AsyncMock()
            mock_redis.return_value = redis_conn
            
            # Mock queue operations
            current_queue_size = 0
            max_queue_size = 1000
            
            async def mock_lpush(queue_name, message):
                nonlocal current_queue_size
                if current_queue_size >= max_queue_size:
                    raise redis.exceptions.ResponseError("Queue overflow")
                current_queue_size += 1
                return current_queue_size
            
            async def mock_llen(queue_name):
                return current_queue_size
            
            redis_conn.lpush = AsyncMock(side_effect=mock_lpush)
            redis_conn.llen = AsyncMock(side_effect=mock_llen)
            
            # Try to overflow the queue
            for i in range(1200):  # Exceed max queue size
                try:
                    await redis_conn.lpush("test_queue", f"message_{i}")
                    queue_size = await redis_conn.llen("test_queue")
                    queue_sizes.append(queue_size)
                except Exception as e:
                    errors.append(str(e))
                    break
        
        # Should handle queue overflow gracefully
        assert len(errors) > 0, "Queue overflow not detected"
        assert "overflow" in errors[0].lower(), f"Unexpected error type: {errors[0]}"
        assert max(queue_sizes) <= max_queue_size, f"Queue size exceeded limit: {max(queue_sizes)}"
    
    @pytest.mark.asyncio
    async def test_large_message_handling(self):
        """Test handling of excessively large messages."""
        large_messages = [
            "A" * 1024,        # 1KB
            "B" * 10240,       # 10KB  
            "C" * 102400,      # 100KB
            "D" * 1048576,     # 1MB
        ]
        
        results = []
        
        with patch('agents.supervisor_agent.SupervisorAgent') as mock_supervisor:
            supervisor = AsyncMock()
            mock_supervisor.return_value = supervisor
            
            for i, large_message in enumerate(large_messages):
                try:
                    # Test message processing
                    supervisor._generate_creative_response = AsyncMock(
                        return_value={'response': f'Processed message {i}', 'needs_review': True}
                    )
                    
                    start_time = time.time()
                    result = await supervisor._generate_creative_response(large_message, f"user_{i}")
                    processing_time = time.time() - start_time
                    
                    results.append({
                        'message_size': len(large_message),
                        'processing_time': processing_time,
                        'success': True,
                        'result': result
                    })
                    
                except Exception as e:
                    results.append({
                        'message_size': len(large_message),
                        'processing_time': 0,
                        'success': False,
                        'error': str(e)
                    })
        
        # Analyze results
        successful_processing = [r for r in results if r['success']]
        failed_processing = [r for r in results if not r['success']]
        
        # Should handle reasonable message sizes
        small_messages = [r for r in results if r['message_size'] <= 10240]  # <= 10KB
        assert all(r['success'] for r in small_messages), \
            "Failed to process reasonable-sized messages"
        
        # May reject very large messages (this is acceptable)
        very_large_messages = [r for r in results if r['message_size'] >= 1048576]  # >= 1MB
        if any(not r['success'] for r in very_large_messages):
            # Verify error messages are appropriate
            for r in very_large_messages:
                if not r['success']:
                    assert any(keyword in r['error'].lower() for keyword in ['size', 'large', 'limit']), \
                        f"Unexpected error for large message: {r['error']}"
    
    @pytest.mark.asyncio
    async def test_concurrent_resource_exhaustion(self, resource_simulator):
        """Test system behavior when multiple resources are exhausted simultaneously."""
        # Start concurrent resource exhaustion
        memory_task = asyncio.create_task(
            resource_simulator.simulate_memory_exhaustion(target_mb=30, increment_mb=3)
        )
        
        cpu_task = asyncio.create_task(
            resource_simulator.simulate_cpu_exhaustion(duration_seconds=3, cpu_threads=2)
        )
        
        connection_task = asyncio.create_task(
            resource_simulator.simulate_connection_exhaustion(max_connections=20, connection_type="redis")
        )
        
        # Wait for all exhaustion tests to complete
        memory_result, cpu_result, connection_result = await asyncio.gather(
            memory_task, cpu_task, connection_task, return_exceptions=True
        )
        
        # System should handle multiple resource pressures
        if isinstance(memory_result, dict):
            assert memory_result['achieved_mb'] >= 20, \
                f"Memory allocation failed under multi-resource pressure: {memory_result['achieved_mb']}MB"
        
        if isinstance(cpu_result, dict):
            assert cpu_result['peak_cpu'] > 30, \
                f"CPU load generation failed under multi-resource pressure: {cpu_result['peak_cpu']}%"
        
        if isinstance(connection_result, dict):
            assert connection_result['successful_connections'] >= 15, \
                f"Connection handling failed under multi-resource pressure: {connection_result['successful_connections']}"
        
        # None of the tasks should have crashed with exceptions
        for result, task_name in [(memory_result, "memory"), (cpu_result, "cpu"), (connection_result, "connection")]:
            if isinstance(result, Exception):
                pytest.fail(f"{task_name} task crashed with exception: {result}")
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_under_pressure(self):
        """Test that system degrades gracefully under resource pressure."""
        degradation_metrics = {
            'response_times': [],
            'success_rates': [],
            'error_types': []
        }
        
        # Simulate system under increasing pressure
        pressure_levels = [10, 25, 50, 100]  # Number of concurrent operations
        
        for pressure in pressure_levels:
            successes = 0
            failures = 0
            response_times = []
            
            # Create concurrent load
            async def simulated_operation(op_id: int):
                start_time = time.time()
                try:
                    # Simulate system operation under pressure
                    await asyncio.sleep(0.01 + (pressure * 0.001))  # Simulate load-dependent delay
                    
                    # Simulate occasional failures under high pressure
                    if pressure > 75 and op_id % 10 == 0:
                        raise Exception("Service temporarily unavailable")
                    
                    return time.time() - start_time
                except Exception as e:
                    degradation_metrics['error_types'].append(str(e))
                    raise
            
            # Execute operations concurrently
            tasks = [
                asyncio.create_task(simulated_operation(i))
                for i in range(pressure)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results for this pressure level
            for result in results:
                if isinstance(result, Exception):
                    failures += 1
                else:
                    successes += 1
                    response_times.append(result)
            
            success_rate = successes / (successes + failures) if (successes + failures) > 0 else 0
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            degradation_metrics['success_rates'].append({
                'pressure': pressure,
                'success_rate': success_rate
            })
            
            degradation_metrics['response_times'].append({
                'pressure': pressure,
                'avg_response_time': avg_response_time
            })
        
        # Verify graceful degradation
        success_rates = [m['success_rate'] for m in degradation_metrics['success_rates']]
        response_times = [m['avg_response_time'] for m in degradation_metrics['response_times']]
        
        # Success rate should remain reasonable even under high pressure
        assert all(rate >= 0.7 for rate in success_rates[:3]), \
            f"Success rate degraded too quickly: {success_rates}"
        
        # Response times may increase but should remain bounded
        assert all(time < 1.0 for time in response_times), \
            f"Response times increased too much: {response_times}"
        
        # High pressure may cause some failures (this is acceptable)
        if success_rates[-1] < 0.9:  # Under highest pressure
            assert len(degradation_metrics['error_types']) > 0, \
                "Low success rate but no error messages recorded"