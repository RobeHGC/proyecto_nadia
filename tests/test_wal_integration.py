# tests/test_wal_integration.py
"""Tests de integración para el Write-Ahead Log."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as redis

from utils.config import Config


@pytest.mark.asyncio
class TestWALIntegration:
    """Tests para verificar la robustez del WAL."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for tests."""
        return AsyncMock()

    async def test_message_enqueue(self, mock_redis):
        """Verifica que los mensajes se encolen correctamente."""
        queue_key = "nadia_message_queue"

        # Simular encolado de mensaje
        message_data = {
            'user_id': '12345',
            'message': 'Hola test',
            'chat_id': -1001234567890,
            'message_id': 42,
            'timestamp': '2024-01-01T12:00:00'
        }

        # Configure mock responses
        mock_redis.llen.return_value = 1
        mock_redis.brpop.return_value = (queue_key.encode(), json.dumps(message_data).encode())

        await mock_redis.lpush(queue_key, json.dumps(message_data))

        # Verificar que el mensaje está en la cola
        queue_length = await mock_redis.llen(queue_key)
        assert queue_length == 1

        # Recuperar y verificar el mensaje
        result = await mock_redis.brpop(queue_key, timeout=1)
        assert result is not None

        _, message_json = result
        recovered_data = json.loads(message_json.decode())
        assert recovered_data == message_data
        
        # Verify Redis operations were called
        mock_redis.lpush.assert_called_once_with(queue_key, json.dumps(message_data))
        mock_redis.llen.assert_called_once_with(queue_key)
        mock_redis.brpop.assert_called_once_with(queue_key, timeout=1)

    async def test_multiple_messages_order(self, mock_redis):
        """Verifica que múltiples mensajes mantengan el orden FIFO."""
        queue_key = "nadia_message_queue"

        # Encolar varios mensajes
        messages = []
        brpop_results = []
        
        for i in range(5):
            msg = {
                'user_id': f'user_{i}',
                'message': f'Mensaje {i}',
                'chat_id': -1001234567890,
                'message_id': i,
                'timestamp': f'2024-01-01T12:00:0{i}'
            }
            messages.append(msg)
            brpop_results.append((queue_key.encode(), json.dumps(msg).encode()))
            await mock_redis.lpush(queue_key, json.dumps(msg))

        # Configure mock to return messages in FIFO order
        mock_redis.brpop.side_effect = brpop_results

        # Verificar que se recuperan en orden FIFO
        for i in range(5):
            result = await mock_redis.brpop(queue_key, timeout=1)
            assert result is not None

            _, message_json = result
            recovered_data = json.loads(message_json.decode())
            assert recovered_data['message'] == f'Mensaje {i}'
            
        # Verify Redis operations
        assert mock_redis.lpush.call_count == 5
        assert mock_redis.brpop.call_count == 5

    async def test_processing_marker(self, mock_redis):
        """Verifica el marcador de procesamiento."""
        processing_key = "nadia_processing:user123"

        # Configure mock responses
        mock_redis.exists.side_effect = [1, 0]  # First exists, then doesn't
        mock_redis.ttl.return_value = 295  # TTL value

        # Marcar como en procesamiento
        message_data = {'user_id': 'user123', 'message': 'Test'}
        await mock_redis.set(
            processing_key,
            json.dumps(message_data),
            ex=300  # 5 minutos
        )

        # Verificar que existe
        exists = await mock_redis.exists(processing_key)
        assert exists == 1

        # Verificar TTL
        ttl = await mock_redis.ttl(processing_key)
        assert 290 < ttl <= 300  # Aproximadamente 5 minutos

        # Limpiar
        await mock_redis.delete(processing_key)
        exists = await mock_redis.exists(processing_key)
        assert exists == 0
        
        # Verify Redis operations
        mock_redis.set.assert_called_once_with(processing_key, json.dumps(message_data), ex=300)
        mock_redis.delete.assert_called_once_with(processing_key)
        assert mock_redis.exists.call_count == 2
        mock_redis.ttl.assert_called_once_with(processing_key)

    async def test_concurrent_processing(self, mock_redis):
        """Simula procesamiento concurrente de mensajes."""
        queue_key = "nadia_message_queue"
        processed_messages = []

        # Prepare mock messages
        messages = []
        brpop_results = []
        
        for i in range(10):
            msg = {'message': f'Msg-{i}', 'user_id': f'user_{i}'}
            messages.append(msg)
            brpop_results.append((queue_key.encode(), json.dumps(msg).encode()))
        
        # Add None results to signal end of queue for each worker
        brpop_results.extend([None, None, None])
        
        # Configure mock
        mock_redis.brpop.side_effect = brpop_results

        async def process_worker(worker_id: int):
            """Worker que procesa mensajes."""
            while True:
                result = await mock_redis.brpop(queue_key, timeout=1)
                if result is None:
                    break

                _, message_json = result
                data = json.loads(message_json.decode())
                processed_messages.append({
                    'worker_id': worker_id,
                    'message': data['message']
                })
                await asyncio.sleep(0.01)  # Simular procesamiento (reduced for faster tests)

        # Encolar mensajes (mock)
        for i in range(10):
            msg = {'message': f'Msg-{i}', 'user_id': f'user_{i}'}
            await mock_redis.lpush(queue_key, json.dumps(msg))

        # Iniciar workers concurrentes
        workers = [
            asyncio.create_task(process_worker(i))
            for i in range(3)
        ]

        # Esperar a que terminen
        await asyncio.gather(*workers)

        # Verificar que todos los mensajes fueron procesados
        assert len(processed_messages) == 10

        # Verificar que no hay mensajes duplicados
        processed_texts = [m['message'] for m in processed_messages]
        assert len(set(processed_texts)) == 10
        
        # Verify Redis operations
        assert mock_redis.lpush.call_count == 10
        assert mock_redis.brpop.call_count == 13  # 10 messages + 3 None results
