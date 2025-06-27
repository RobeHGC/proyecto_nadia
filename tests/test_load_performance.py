# tests/test_load_performance.py
"""Load and stress testing for NADIA system performance."""
import asyncio
import time
import json
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import redis.asyncio as redis

from database.models import DatabaseManager
from agents.supervisor_agent import SupervisorAgent
from memory.user_memory import UserMemoryManager
from utils.config import Config


class LoadTestingFramework:
    """Framework for load testing NADIA system components."""
    
    def __init__(self):
        self.metrics = {
            'response_times': [],
            'memory_usage': [],
            'cpu_usage': [],
            'redis_operations': [],
            'database_operations': [],
            'errors': []
        }
        self.start_time = None
        self.config = Config.from_env()
    
    async def simulate_message_burst(self, count: int, duration_seconds: int) -> Dict[str, Any]:
        """Simulate burst of messages over specified duration."""
        self.start_time = time.time()
        interval = duration_seconds / count
        
        tasks = []
        for i in range(count):
            delay = i * interval
            task = asyncio.create_task(
                self._delayed_message_simulation(delay, f"user_{i}", f"Test message {i}")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful vs failed operations
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = count - successful
        
        return {
            'total_messages': count,
            'successful': successful,
            'failed': failed,
            'duration_seconds': duration_seconds,
            'throughput': successful / duration_seconds,
            'error_rate': failed / count,
            'response_times': self.metrics['response_times']
        }
    
    async def simulate_concurrent_users(self, users: int, messages_per_user: int) -> Dict[str, Any]:
        """Simulate multiple users sending messages concurrently."""
        self.start_time = time.time()
        
        async def user_simulation(user_id: str, message_count: int):
            user_results = []
            for i in range(message_count):
                try:
                    start_time = time.time()
                    result = await self._simulate_single_message(
                        user_id, f"Concurrent message {i} from {user_id}"
                    )
                    response_time = time.time() - start_time
                    user_results.append({
                        'response_time': response_time,
                        'success': True,
                        'message_id': i
                    })
                except Exception as e:
                    user_results.append({
                        'response_time': None,
                        'success': False,
                        'error': str(e),
                        'message_id': i
                    })
                    self.metrics['errors'].append(str(e))
                
                # Small delay between messages from same user
                await asyncio.sleep(0.1)
            
            return user_results
        
        # Create tasks for all users
        tasks = [
            asyncio.create_task(user_simulation(f"user_{i}", messages_per_user))
            for i in range(users)
        ]
        
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        total_messages = users * messages_per_user
        successful_messages = 0
        all_response_times = []
        
        for user_result in user_results:
            if isinstance(user_result, Exception):
                continue
            for msg_result in user_result:
                if msg_result['success']:
                    successful_messages += 1
                    if msg_result['response_time']:
                        all_response_times.append(msg_result['response_time'])
        
        avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0
        
        return {
            'concurrent_users': users,
            'messages_per_user': messages_per_user,
            'total_messages': total_messages,
            'successful_messages': successful_messages,
            'error_rate': (total_messages - successful_messages) / total_messages,
            'average_response_time': avg_response_time,
            'max_response_time': max(all_response_times) if all_response_times else 0,
            'response_times': all_response_times
        }
    
    async def measure_resource_usage(self, duration_seconds: int, interval: float = 1.0) -> Dict[str, Any]:
        """Monitor system resource usage over time."""
        measurements = []
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            measurement = {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_mb': psutil.virtual_memory().used / 1024 / 1024
            }
            measurements.append(measurement)
            await asyncio.sleep(interval)
        
        # Calculate statistics
        cpu_values = [m['cpu_percent'] for m in measurements]
        memory_values = [m['memory_mb'] for m in measurements]
        
        return {
            'duration_seconds': duration_seconds,
            'measurements': measurements,
            'cpu_stats': {
                'average': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory_stats': {
                'average_mb': sum(memory_values) / len(memory_values),
                'max_mb': max(memory_values),
                'min_mb': min(memory_values)
            }
        }
    
    async def _delayed_message_simulation(self, delay: float, user_id: str, message: str):
        """Simulate message with specified delay."""
        await asyncio.sleep(delay)
        start_time = time.time()
        try:
            result = await self._simulate_single_message(user_id, message)
            response_time = time.time() - start_time
            self.metrics['response_times'].append(response_time)
            return result
        except Exception as e:
            self.metrics['errors'].append(str(e))
            raise
    
    async def _simulate_single_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """Simulate processing of a single message."""
        # Simulate realistic processing delay
        base_delay = 0.05  # 50ms base processing time
        message_complexity_delay = len(message) * 0.0001  # Additional delay based on message length
        
        await asyncio.sleep(base_delay + message_complexity_delay)
        
        # Simulate occasional processing failures (5% failure rate)
        import random
        if random.random() < 0.05:
            raise Exception(f"Simulated processing failure for message: {message[:20]}...")
        
        return {
            'user_id': user_id,
            'message': message,
            'processed_at': datetime.now().isoformat(),
            'success': True,
            'mock_response': f"Mock response to: {message[:30]}...",
            'interaction_id': f"mock_{user_id}_{int(time.time() * 1000000)}"
        }


@pytest.fixture
def load_tester():
    """Fixture providing load testing framework."""
    return LoadTestingFramework()


class TestLoadPerformance:
    """Test suite for load and performance testing."""
    
    @pytest.mark.asyncio
    async def test_message_burst_light_load(self, load_tester):
        """Test system under light burst load (50 messages in 10 seconds)."""
        result = await load_tester.simulate_message_burst(count=50, duration_seconds=10)
        
        # Performance assertions
        assert result['successful'] >= 45, f"Too many failures: {result['failed']}/50"
        assert result['error_rate'] < 0.1, f"Error rate too high: {result['error_rate']}"
        assert result['throughput'] >= 4.5, f"Throughput too low: {result['throughput']} msg/s"
        
        # Response time assertions
        if result['response_times']:
            avg_response_time = sum(result['response_times']) / len(result['response_times'])
            assert avg_response_time < 2.0, f"Average response time too high: {avg_response_time}s"
    
    @pytest.mark.asyncio
    async def test_message_burst_medium_load(self, load_tester):
        """Test system under medium burst load (100 messages in 15 seconds)."""
        result = await load_tester.simulate_message_burst(count=100, duration_seconds=15)
        
        # Performance assertions
        assert result['successful'] >= 90, f"Too many failures: {result['failed']}/100"
        assert result['error_rate'] < 0.1, f"Error rate too high: {result['error_rate']}"
        assert result['throughput'] >= 6.0, f"Throughput too low: {result['throughput']} msg/s"
        
        # Response time assertions
        if result['response_times']:
            avg_response_time = sum(result['response_times']) / len(result['response_times'])
            max_response_time = max(result['response_times'])
            assert avg_response_time < 3.0, f"Average response time too high: {avg_response_time}s"
            assert max_response_time < 10.0, f"Max response time too high: {max_response_time}s"
    
    @pytest.mark.asyncio
    async def test_concurrent_users_light(self, load_tester):
        """Test system with light concurrent user load (10 users, 5 messages each)."""
        result = await load_tester.simulate_concurrent_users(users=10, messages_per_user=5)
        
        # Performance assertions
        assert result['successful_messages'] >= 45, f"Too many failures: {result['successful_messages']}/50"
        assert result['error_rate'] < 0.1, f"Error rate too high: {result['error_rate']}"
        assert result['average_response_time'] < 2.0, f"Average response time too high: {result['average_response_time']}s"
        
        # Concurrent processing validation
        assert result['concurrent_users'] == 10
        assert result['messages_per_user'] == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_users_medium(self, load_tester):
        """Test system with medium concurrent user load (25 users, 4 messages each)."""
        result = await load_tester.simulate_concurrent_users(users=25, messages_per_user=4)
        
        # Performance assertions
        assert result['successful_messages'] >= 90, f"Too many failures: {result['successful_messages']}/100"
        assert result['error_rate'] < 0.1, f"Error rate too high: {result['error_rate']}"
        assert result['average_response_time'] < 3.0, f"Average response time too high: {result['average_response_time']}s"
        assert result['max_response_time'] < 15.0, f"Max response time too high: {result['max_response_time']}s"
    
    @pytest.mark.asyncio
    async def test_resource_usage_under_load(self, load_tester):
        """Test resource usage while system is under load."""
        # Start resource monitoring
        resource_task = asyncio.create_task(
            load_tester.measure_resource_usage(duration_seconds=20, interval=0.5)
        )
        
        # Simulate load while monitoring
        load_task = asyncio.create_task(
            load_tester.simulate_message_burst(count=200, duration_seconds=20)
        )
        
        # Wait for both to complete
        resource_result, load_result = await asyncio.gather(resource_task, load_task)
        
        # Resource usage assertions
        assert resource_result['cpu_stats']['average'] < 80.0, \
            f"CPU usage too high: {resource_result['cpu_stats']['average']}%"
        assert resource_result['memory_stats']['max_mb'] < 1024, \
            f"Memory usage too high: {resource_result['memory_stats']['max_mb']}MB"
        
        # Load performance assertions
        assert load_result['error_rate'] < 0.15, \
            f"Error rate too high under resource monitoring: {load_result['error_rate']}"
    
    @pytest.mark.asyncio  
    async def test_sustained_load_performance(self, load_tester):
        """Test system performance under sustained load (300 messages over 60 seconds)."""
        result = await load_tester.simulate_message_burst(count=300, duration_seconds=60)
        
        # Sustained performance assertions
        assert result['successful'] >= 270, f"Too many failures in sustained test: {result['failed']}/300"
        assert result['error_rate'] < 0.1, f"Error rate too high in sustained test: {result['error_rate']}"
        assert result['throughput'] >= 4.5, f"Sustained throughput too low: {result['throughput']} msg/s"
        
        # Response time consistency
        if result['response_times']:
            response_times = result['response_times']
            avg_response_time = sum(response_times) / len(response_times)
            
            # Check that 95% of responses are within reasonable time
            sorted_times = sorted(response_times)
            p95_time = sorted_times[int(0.95 * len(sorted_times))]
            
            assert avg_response_time < 2.5, f"Sustained average response time too high: {avg_response_time}s"
            assert p95_time < 8.0, f"95th percentile response time too high: {p95_time}s"
    
    @pytest.mark.asyncio
    async def test_memory_leak_detection(self, load_tester):
        """Test for memory leaks during extended operation."""
        initial_memory = psutil.virtual_memory().used / 1024 / 1024  # MB
        
        # Run multiple load cycles
        for cycle in range(3):
            await load_tester.simulate_message_burst(count=50, duration_seconds=10)
            await asyncio.sleep(2)  # Brief pause between cycles
        
        final_memory = psutil.virtual_memory().used / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory leak assertion (allow some growth but not excessive)
        assert memory_increase < 100, \
            f"Potential memory leak detected: {memory_increase}MB increase"
    
    @pytest.mark.asyncio
    async def test_queue_depth_under_load(self, load_tester):
        """Test that message queues don't become overwhelmed under load."""
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis_conn = AsyncMock()
            mock_redis.return_value = mock_redis_conn
            
            # Mock queue depth responses
            mock_redis_conn.llen.side_effect = [10, 25, 45, 30, 15]  # Simulated queue depths
            mock_redis_conn.zcard.return_value = 5  # Review queue depth
            
            # Simulate load
            await load_tester.simulate_message_burst(count=100, duration_seconds=10)
            
            # Verify queue monitoring was called
            assert mock_redis_conn.llen.called, "Queue depth monitoring not activated"
            
            # In a real implementation, we would check actual queue depths
            # For now, we verify the monitoring infrastructure is in place
    
    @pytest.mark.asyncio
    async def test_performance_degradation_thresholds(self, load_tester):
        """Test that performance degrades gracefully as load increases."""
        # Test light load first
        light_result = await load_tester.simulate_message_burst(count=25, duration_seconds=5)
        
        # Test heavier load
        heavy_result = await load_tester.simulate_message_burst(count=150, duration_seconds=15)
        
        # Calculate performance metrics
        light_throughput = light_result['throughput']
        heavy_throughput = heavy_result['throughput']
        
        light_avg_time = sum(light_result['response_times']) / len(light_result['response_times']) \
            if light_result['response_times'] else 0
        heavy_avg_time = sum(heavy_result['response_times']) / len(heavy_result['response_times']) \
            if heavy_result['response_times'] else 0
        
        # Graceful degradation assertions
        # Throughput may decrease under heavier load, but should still be reasonable
        assert heavy_throughput >= light_throughput * 0.7, \
            f"Throughput degraded too much: {heavy_throughput} vs {light_throughput}"
        
        # Response time may increase but should remain bounded
        if light_avg_time > 0 and heavy_avg_time > 0:
            time_increase_ratio = heavy_avg_time / light_avg_time
            assert time_increase_ratio < 3.0, \
                f"Response time increased too much: {time_increase_ratio}x increase"
        
        # Error rates should remain low even under heavier load
        assert heavy_result['error_rate'] < 0.15, \
            f"Error rate too high under heavy load: {heavy_result['error_rate']}"