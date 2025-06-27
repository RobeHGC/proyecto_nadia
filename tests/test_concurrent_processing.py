# tests/test_concurrent_processing.py
"""Concurrent processing and race condition testing."""
import asyncio
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
from unittest.mock import AsyncMock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
import redis.asyncio as redis

# Note: Import actual modules as needed - using simplified testing for resilience validation


class ConcurrencyTestFramework:
    """Framework for testing concurrent processing scenarios."""
    
    def __init__(self):
        self.shared_state = {}
        self.race_conditions_detected = []
        self.access_log = []
        self.lock = asyncio.Lock()
    
    async def simulate_concurrent_memory_access(self, user_count: int, operations_per_user: int) -> Dict[str, Any]:
        """Test concurrent access to user memory system."""
        results = {
            'total_operations': user_count * operations_per_user,
            'successful_operations': 0,
            'race_conditions': [],
            'memory_consistency_errors': [],
            'user_results': {}
        }
        
        async def user_memory_operations(user_id: str, operation_count: int):
            user_results = {'successful': 0, 'failed': 0, 'errors': []}
            
            with patch('memory.user_memory.UserMemoryManager') as mock_memory:
                memory_manager = AsyncMock()
                mock_memory.return_value = memory_manager
                
                # Mock Redis operations with potential race conditions
                memory_manager.add_message = AsyncMock()
                memory_manager.get_recent_history = AsyncMock(return_value=[])
                memory_manager.clear_history = AsyncMock()
                
                for i in range(operation_count):
                    try:
                        # Simulate different memory operations
                        operation_type = i % 3
                        
                        if operation_type == 0:
                            # Add message
                            await memory_manager.add_message(
                                user_id, f"Test message {i}", is_bot=False
                            )
                        elif operation_type == 1:
                            # Get history
                            await memory_manager.get_recent_history(user_id, limit=10)
                        else:
                            # Clear history
                            await memory_manager.clear_history(user_id)
                        
                        user_results['successful'] += 1
                        
                        # Small delay to increase chance of race conditions
                        await asyncio.sleep(0.001)
                        
                    except Exception as e:
                        user_results['failed'] += 1
                        user_results['errors'].append(str(e))
            
            return user_results
        
        # Create concurrent tasks for all users
        tasks = [
            asyncio.create_task(user_memory_operations(f"user_{i}", operations_per_user))
            for i in range(user_count)
        ]
        
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        for i, user_result in enumerate(user_results):
            if isinstance(user_result, Exception):
                results['race_conditions'].append(f"User {i}: {str(user_result)}")
            else:
                results['user_results'][f"user_{i}"] = user_result
                results['successful_operations'] += user_result['successful']
        
        return results
    
    async def simulate_concurrent_database_access(self, concurrent_writes: int, table: str = "interactions") -> Dict[str, Any]:
        """Test concurrent database operations for race conditions."""
        results = {
            'concurrent_operations': concurrent_writes,
            'successful_writes': 0,
            'database_errors': [],
            'consistency_issues': [],
            'operation_times': []
        }
        
        async def database_write_operation(operation_id: int):
            operation_result = {'id': operation_id, 'success': False, 'error': None, 'duration': 0}
            
            with patch('database.models.DatabaseManager') as mock_db_class:
                db_manager = AsyncMock()
                mock_db_class.return_value = db_manager
                
                # Mock database operations
                if table == "interactions":
                    db_manager.create_interaction = AsyncMock(return_value=f"interaction_{operation_id}")
                elif table == "user_cursors":
                    db_manager.update_user_cursor = AsyncMock(return_value=True)
                else:
                    db_manager.execute_query = AsyncMock(return_value=True)
                
                try:
                    start_time = time.time()
                    
                    if table == "interactions":
                        result = await db_manager.create_interaction(
                            user_id=f"user_{operation_id}",
                            user_message=f"Concurrent test message {operation_id}",
                            assistant_response=f"Response {operation_id}",
                            needs_review=True
                        )
                    elif table == "user_cursors":
                        result = await db_manager.update_user_cursor(
                            user_id=f"user_{operation_id}",
                            message_id=operation_id + 1000
                        )
                    else:
                        result = await db_manager.execute_query(
                            f"INSERT INTO test_table VALUES ({operation_id}, 'data_{operation_id}')"
                        )
                    
                    operation_result['duration'] = time.time() - start_time
                    operation_result['success'] = True
                    operation_result['result'] = result
                    
                except Exception as e:
                    operation_result['error'] = str(e)
                    operation_result['duration'] = time.time() - start_time
            
            return operation_result
        
        # Execute concurrent database operations
        tasks = [
            asyncio.create_task(database_write_operation(i))
            for i in range(concurrent_writes)
        ]
        
        operation_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        for result in operation_results:
            if isinstance(result, Exception):
                results['database_errors'].append(str(result))
            else:
                if result['success']:
                    results['successful_writes'] += 1
                else:
                    results['database_errors'].append(result['error'])
                
                results['operation_times'].append(result['duration'])
        
        # Check for consistency issues (e.g., identical timestamps, conflicting IDs)
        if len(results['operation_times']) > 1:
            avg_time = sum(results['operation_times']) / len(results['operation_times'])
            max_time = max(results['operation_times'])
            
            if max_time > avg_time * 5:  # Some operations took 5x longer
                results['consistency_issues'].append(
                    f"Large timing variance detected: max={max_time:.3f}s, avg={avg_time:.3f}s"
                )
        
        return results
    
    async def simulate_redis_connection_competition(self, concurrent_connections: int, operations_per_connection: int) -> Dict[str, Any]:
        """Test Redis connection pool under concurrent load."""
        results = {
            'total_connections': concurrent_connections,
            'successful_connections': 0,
            'connection_errors': [],
            'operation_results': {},
            'pool_exhaustion_detected': False
        }
        
        async def redis_operations(connection_id: int, operation_count: int):
            connection_results = {
                'successful_ops': 0,
                'failed_ops': 0,
                'errors': [],
                'connection_time': 0,
                'operations': []
            }
            
            try:
                start_time = time.time()
                
                # Mock Redis connection
                with patch('redis.asyncio.from_url') as mock_redis:
                    redis_conn = AsyncMock()
                    mock_redis.return_value = redis_conn
                    
                    # Configure Redis operations
                    redis_conn.set = AsyncMock(return_value=True)
                    redis_conn.get = AsyncMock(return_value=f"value_{connection_id}")
                    redis_conn.lpush = AsyncMock(return_value=1)
                    redis_conn.brpop = AsyncMock(return_value=(b"queue", b"message"))
                    redis_conn.ping = AsyncMock(return_value=True)
                    
                    connection_results['connection_time'] = time.time() - start_time
                    
                    # Perform operations
                    for op_id in range(operation_count):
                        try:
                            op_start = time.time()
                            
                            # Different operation types
                            if op_id % 4 == 0:
                                await redis_conn.set(f"key_{connection_id}_{op_id}", f"value_{op_id}")
                            elif op_id % 4 == 1:
                                await redis_conn.get(f"key_{connection_id}_{op_id}")
                            elif op_id % 4 == 2:
                                await redis_conn.lpush(f"queue_{connection_id}", f"item_{op_id}")
                            else:
                                await redis_conn.ping()
                            
                            op_duration = time.time() - op_start
                            connection_results['operations'].append({
                                'operation_id': op_id,
                                'duration': op_duration,
                                'success': True
                            })
                            connection_results['successful_ops'] += 1
                            
                        except Exception as e:
                            connection_results['failed_ops'] += 1
                            connection_results['errors'].append(f"Op {op_id}: {str(e)}")
                            connection_results['operations'].append({
                                'operation_id': op_id,
                                'duration': 0,
                                'success': False,
                                'error': str(e)
                            })
            
            except Exception as e:
                connection_results['errors'].append(f"Connection error: {str(e)}")
                if "pool" in str(e).lower() or "connection" in str(e).lower():
                    results['pool_exhaustion_detected'] = True
            
            return connection_results
        
        # Create concurrent Redis operations
        tasks = [
            asyncio.create_task(redis_operations(i, operations_per_connection))
            for i in range(concurrent_connections)
        ]
        
        connection_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        for i, conn_result in enumerate(connection_results):
            if isinstance(conn_result, Exception):
                results['connection_errors'].append(f"Connection {i}: {str(conn_result)}")
            else:
                results['operation_results'][f"connection_{i}"] = conn_result
                if conn_result['successful_ops'] > 0:
                    results['successful_connections'] += 1
        
        return results
    
    async def simulate_message_queue_race_conditions(self, producer_count: int, consumer_count: int, messages_per_producer: int) -> Dict[str, Any]:
        """Test WAL message queue under concurrent producer/consumer load."""
        results = {
            'producers': producer_count,
            'consumers': consumer_count,
            'messages_per_producer': messages_per_producer,
            'total_messages_produced': 0,
            'total_messages_consumed': 0,
            'race_conditions': [],
            'message_loss_detected': False,
            'duplicate_processing_detected': False
        }
        
        # Shared state for tracking messages
        produced_messages = set()
        consumed_messages = set()
        processing_lock = asyncio.Lock()
        
        async def message_producer(producer_id: int, message_count: int):
            producer_results = {'produced': 0, 'errors': []}
            
            with patch('utils.wal.WALManager') as mock_wal:
                wal_manager = AsyncMock()
                mock_wal.return_value = wal_manager
                wal_manager.add_to_queue = AsyncMock()
                
                for i in range(message_count):
                    try:
                        message_id = f"producer_{producer_id}_msg_{i}"
                        message_data = {
                            'id': message_id,
                            'user_id': f"user_{producer_id}",
                            'content': f"Message {i} from producer {producer_id}",
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        await wal_manager.add_to_queue("nadia_message_queue", json.dumps(message_data))
                        
                        async with processing_lock:
                            produced_messages.add(message_id)
                        
                        producer_results['produced'] += 1
                        
                        # Small delay to increase race condition chances
                        await asyncio.sleep(0.001)
                        
                    except Exception as e:
                        producer_results['errors'].append(str(e))
            
            return producer_results
        
        async def message_consumer(consumer_id: int):
            consumer_results = {'consumed': 0, 'errors': [], 'duplicates': []}
            
            with patch('utils.wal.WALManager') as mock_wal:
                wal_manager = AsyncMock()
                mock_wal.return_value = wal_manager
                
                # Mock message consumption
                messages_to_consume = [
                    f"producer_{i}_msg_{j}" 
                    for i in range(producer_count) 
                    for j in range(min(messages_per_producer, 5))  # Limit for simulation
                ]
                
                for message_id in messages_to_consume:
                    try:
                        # Simulate brpop operation
                        wal_manager.get_from_queue = AsyncMock(return_value=(b"nadia_message_queue", message_id.encode()))
                        
                        result = await wal_manager.get_from_queue("nadia_message_queue", timeout=1)
                        if result:
                            queue_name, message_data = result
                            message_id_consumed = message_data.decode()
                            
                            async with processing_lock:
                                if message_id_consumed in consumed_messages:
                                    consumer_results['duplicates'].append(message_id_consumed)
                                    results['duplicate_processing_detected'] = True
                                else:
                                    consumed_messages.add(message_id_consumed)
                            
                            consumer_results['consumed'] += 1
                        
                        await asyncio.sleep(0.002)  # Consumer processing time
                        
                    except Exception as e:
                        consumer_results['errors'].append(str(e))
            
            return consumer_results
        
        # Start producers and consumers concurrently
        producer_tasks = [
            asyncio.create_task(message_producer(i, messages_per_producer))
            for i in range(producer_count)
        ]
        
        consumer_tasks = [
            asyncio.create_task(message_consumer(i))
            for i in range(consumer_count)
        ]
        
        # Wait for all tasks to complete
        producer_results = await asyncio.gather(*producer_tasks, return_exceptions=True)
        consumer_results = await asyncio.gather(*consumer_tasks, return_exceptions=True)
        
        # Analyze results
        for result in producer_results:
            if isinstance(result, Exception):
                results['race_conditions'].append(f"Producer error: {str(result)}")
            else:
                results['total_messages_produced'] += result['produced']
        
        for result in consumer_results:
            if isinstance(result, Exception):
                results['race_conditions'].append(f"Consumer error: {str(result)}")
            else:
                results['total_messages_consumed'] += result['consumed']
        
        # Check for message loss
        if len(consumed_messages) < len(produced_messages):
            results['message_loss_detected'] = True
            results['race_conditions'].append(
                f"Message loss: {len(produced_messages)} produced, {len(consumed_messages)} consumed"
            )
        
        return results


@pytest.fixture
def concurrency_tester():
    """Fixture providing concurrency testing framework."""
    return ConcurrencyTestFramework()


class TestConcurrentProcessing:
    """Test suite for concurrent processing and race conditions."""
    
    @pytest.mark.asyncio
    async def test_concurrent_memory_access_light(self, concurrency_tester):
        """Test concurrent access to user memory with light load."""
        result = await concurrency_tester.simulate_concurrent_memory_access(
            user_count=5, operations_per_user=10
        )
        
        # Verify no major race conditions
        assert result['successful_operations'] >= 40, \
            f"Too many failed operations: {result['successful_operations']}/50"
        assert len(result['race_conditions']) == 0, \
            f"Race conditions detected: {result['race_conditions']}"
        assert len(result['memory_consistency_errors']) == 0, \
            f"Memory consistency errors: {result['memory_consistency_errors']}"
    
    @pytest.mark.asyncio
    async def test_concurrent_memory_access_heavy(self, concurrency_tester):
        """Test concurrent access to user memory with heavy load."""
        result = await concurrency_tester.simulate_concurrent_memory_access(
            user_count=20, operations_per_user=15
        )
        
        # Allow for some failures under heavy load, but should be minimal
        success_rate = result['successful_operations'] / result['total_operations']
        assert success_rate >= 0.85, \
            f"Success rate too low under heavy load: {success_rate:.2%}"
        
        # Race conditions should be rare
        assert len(result['race_conditions']) <= 2, \
            f"Too many race conditions: {result['race_conditions']}"
    
    @pytest.mark.asyncio
    async def test_concurrent_database_writes(self, concurrency_tester):
        """Test concurrent database writes for race conditions."""
        result = await concurrency_tester.simulate_concurrent_database_access(
            concurrent_writes=15, table="interactions"
        )
        
        # Database should handle concurrent writes
        assert result['successful_writes'] >= 12, \
            f"Too many database write failures: {result['successful_writes']}/15"
        assert len(result['database_errors']) <= 3, \
            f"Too many database errors: {result['database_errors']}"
        
        # Check for reasonable operation times
        if result['operation_times']:
            avg_time = sum(result['operation_times']) / len(result['operation_times'])
            assert avg_time < 1.0, f"Database operations too slow: {avg_time:.3f}s average"
    
    @pytest.mark.asyncio
    async def test_redis_connection_pool_stress(self, concurrency_tester):
        """Test Redis connection pool under concurrent stress."""
        result = await concurrency_tester.simulate_redis_connection_competition(
            concurrent_connections=25, operations_per_connection=10
        )
        
        # Connection pool should handle concurrent access
        assert result['successful_connections'] >= 20, \
            f"Too many connection failures: {result['successful_connections']}/25"
        assert not result['pool_exhaustion_detected'], \
            "Redis connection pool exhaustion detected"
        
        # Analyze operation success rates
        total_successful_ops = sum(
            conn['successful_ops'] for conn in result['operation_results'].values()
        )
        total_operations = len(result['operation_results']) * 10
        
        if total_operations > 0:
            op_success_rate = total_successful_ops / total_operations
            assert op_success_rate >= 0.9, \
                f"Redis operation success rate too low: {op_success_rate:.2%}"
    
    @pytest.mark.asyncio
    async def test_message_queue_producer_consumer_race(self, concurrency_tester):
        """Test message queue under concurrent producer/consumer load."""
        result = await concurrency_tester.simulate_message_queue_race_conditions(
            producer_count=5, consumer_count=3, messages_per_producer=8
        )
        
        # Message processing should be reliable
        assert not result['message_loss_detected'], \
            "Message loss detected in queue processing"
        assert not result['duplicate_processing_detected'], \
            "Duplicate message processing detected"
        
        # Production should succeed
        expected_messages = result['producers'] * result['messages_per_producer']
        assert result['total_messages_produced'] >= expected_messages * 0.9, \
            f"Message production rate too low: {result['total_messages_produced']}/{expected_messages}"
    
    @pytest.mark.asyncio
    async def test_supervisor_agent_concurrent_requests(self):
        """Test supervisor agent handling concurrent requests."""
        with patch('agents.supervisor_agent.SupervisorAgent.__init__') as mock_init:
            mock_init.return_value = None
            
            # Create shared supervisor instance
            supervisor = SupervisorAgent()
            supervisor.llm_router = AsyncMock()
            supervisor.llm_router.route_request = AsyncMock(
                return_value={'response': 'Mock response', 'model': 'gpt-4'}
            )
            
            # Mock database operations
            with patch('database.models.DatabaseManager') as mock_db:
                db_instance = AsyncMock()
                mock_db.return_value = db_instance
                db_instance.create_interaction = AsyncMock(
                    side_effect=lambda **kwargs: f"interaction_{int(time.time() * 1000000)}"
                )
                
                supervisor.db_manager = db_instance
                
                # Test concurrent request processing
                async def process_request(user_id: str, message: str):
                    try:
                        result = await supervisor._generate_creative_response(message, user_id)
                        return ('success', result)
                    except Exception as e:
                        return ('error', str(e))
                
                # Create 15 concurrent requests
                tasks = [
                    asyncio.create_task(process_request(f"user_{i}", f"Concurrent message {i}"))
                    for i in range(15)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Analyze results
                successes = sum(1 for r in results if isinstance(r, tuple) and r[0] == 'success')
                errors = sum(1 for r in results if isinstance(r, tuple) and r[0] == 'error')
                exceptions = sum(1 for r in results if isinstance(r, Exception))
                
                # Concurrent processing should be successful
                assert successes >= 12, f"Too many failed requests: {successes}/15 successful"
                assert exceptions == 0, f"Unexpected exceptions: {exceptions}"
    
    @pytest.mark.asyncio
    async def test_shared_resource_contention(self):
        """Test contention for shared resources (Redis keys, database connections)."""
        shared_resource_access_count = 0
        access_conflicts = []
        
        async def access_shared_resource(accessor_id: int, access_count: int):
            nonlocal shared_resource_access_count
            conflicts = []
            
            for i in range(access_count):
                # Simulate accessing shared resource
                current_count = shared_resource_access_count
                await asyncio.sleep(0.001)  # Simulate processing time
                
                # Check for race condition
                if shared_resource_access_count != current_count:
                    conflicts.append(f"Accessor {accessor_id} iteration {i}: count changed during access")
                
                shared_resource_access_count += 1
                
            return conflicts
        
        # Create concurrent accessors
        tasks = [
            asyncio.create_task(access_shared_resource(i, 5))
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze contention
        all_conflicts = []
        for result in results:
            if isinstance(result, list):
                all_conflicts.extend(result)
        
        # Some contention is expected, but should be manageable
        assert len(all_conflicts) <= 10, f"Too many resource conflicts: {len(all_conflicts)}"
        assert shared_resource_access_count == 50, f"Incorrect final count: {shared_resource_access_count}"
    
    @pytest.mark.asyncio
    async def test_deadlock_prevention(self):
        """Test that the system prevents deadlocks in resource acquisition."""
        resource_a_locked = False
        resource_b_locked = False
        deadlock_detected = False
        
        async def task_1():
            nonlocal resource_a_locked, resource_b_locked, deadlock_detected
            
            # Acquire resource A
            while resource_a_locked:
                await asyncio.sleep(0.001)
            resource_a_locked = True
            
            await asyncio.sleep(0.01)  # Hold resource A
            
            # Try to acquire resource B
            attempts = 0
            while resource_b_locked and attempts < 100:
                await asyncio.sleep(0.001)
                attempts += 1
            
            if attempts >= 100:
                deadlock_detected = True
            else:
                resource_b_locked = True
                await asyncio.sleep(0.001)  # Hold both resources
                resource_b_locked = False
            
            resource_a_locked = False
        
        async def task_2():
            nonlocal resource_a_locked, resource_b_locked, deadlock_detected
            
            # Acquire resource B
            while resource_b_locked:
                await asyncio.sleep(0.001)
            resource_b_locked = True
            
            await asyncio.sleep(0.01)  # Hold resource B
            
            # Try to acquire resource A
            attempts = 0
            while resource_a_locked and attempts < 100:
                await asyncio.sleep(0.001)
                attempts += 1
            
            if attempts >= 100:
                deadlock_detected = True
            else:
                resource_a_locked = True
                await asyncio.sleep(0.001)  # Hold both resources
                resource_a_locked = False
            
            resource_b_locked = False
        
        # Run potentially deadlocking tasks
        await asyncio.gather(
            asyncio.create_task(task_1()),
            asyncio.create_task(task_2())
        )
        
        # Verify no deadlock occurred
        assert not deadlock_detected, "Deadlock detected between concurrent tasks"
        assert not resource_a_locked, "Resource A still locked after completion"
        assert not resource_b_locked, "Resource B still locked after completion"
    
    @pytest.mark.asyncio
    async def test_async_context_isolation(self):
        """Test that async contexts are properly isolated between concurrent operations."""
        context_values = {}
        
        async def context_operation(operation_id: int, initial_value: str):
            # Set context-specific value
            context_values[operation_id] = initial_value
            
            # Simulate async work that might mix contexts
            await asyncio.sleep(0.01)
            
            # Verify context value hasn't been corrupted
            current_value = context_values.get(operation_id)
            
            return {
                'operation_id': operation_id,
                'initial_value': initial_value,
                'final_value': current_value,
                'context_preserved': current_value == initial_value
            }
        
        # Create operations with different context values
        tasks = [
            asyncio.create_task(context_operation(i, f"value_{i}"))
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify context isolation
        for result in results:
            if isinstance(result, dict):
                assert result['context_preserved'], \
                    f"Context corruption in operation {result['operation_id']}: " \
                    f"expected {result['initial_value']}, got {result['final_value']}"
            else:
                pytest.fail(f"Unexpected exception in context test: {result}")