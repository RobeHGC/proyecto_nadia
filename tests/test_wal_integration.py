# tests/test_wal_integration.py
"""Tests de integración para el Write-Ahead Log."""
import asyncio
import json

import pytest
import redis.asyncio as redis

from utils.config import Config


@pytest.mark.asyncio
class TestWALIntegration:
    """Tests para verificar la robustez del WAL."""

    @pytest.fixture
    async def redis_client(self, redis_cleanup):
        """Cliente Redis para tests."""
        config = Config.from_env()
        r = await redis.from_url(config.redis_url)
        yield r
        # Limpiar después del test
        await r.flushdb()
        await r.aclose()

    async def test_message_enqueue(self, redis_client):
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

        await redis_client.lpush(queue_key, json.dumps(message_data))

        # Verificar que el mensaje está en la cola
        queue_length = await redis_client.llen(queue_key)
        assert queue_length == 1

        # Recuperar y verificar el mensaje
        result = await redis_client.brpop(queue_key, timeout=1)
        assert result is not None

        _, message_json = result
        recovered_data = json.loads(message_json)
        assert recovered_data == message_data

    async def test_multiple_messages_order(self, redis_client):
        """Verifica que múltiples mensajes mantengan el orden FIFO."""
        queue_key = "nadia_message_queue"

        # Encolar varios mensajes
        messages = []
        for i in range(5):
            msg = {
                'user_id': f'user_{i}',
                'message': f'Mensaje {i}',
                'chat_id': -1001234567890,
                'message_id': i,
                'timestamp': f'2024-01-01T12:00:0{i}'
            }
            messages.append(msg)
            await redis_client.lpush(queue_key, json.dumps(msg))

        # Verificar que se recuperan en orden FIFO
        for i in range(5):
            result = await redis_client.brpop(queue_key, timeout=1)
            assert result is not None

            _, message_json = result
            recovered_data = json.loads(message_json)
            assert recovered_data['message'] == f'Mensaje {i}'

    async def test_processing_marker(self, redis_client):
        """Verifica el marcador de procesamiento."""
        processing_key = "nadia_processing:user123"

        # Marcar como en procesamiento
        message_data = {'user_id': 'user123', 'message': 'Test'}
        await redis_client.set(
            processing_key,
            json.dumps(message_data),
            ex=300  # 5 minutos
        )

        # Verificar que existe
        exists = await redis_client.exists(processing_key)
        assert exists == 1

        # Verificar TTL
        ttl = await redis_client.ttl(processing_key)
        assert 290 < ttl <= 300  # Aproximadamente 5 minutos

        # Limpiar
        await redis_client.delete(processing_key)
        exists = await redis_client.exists(processing_key)
        assert exists == 0

    async def test_concurrent_processing(self, redis_client):
        """Simula procesamiento concurrente de mensajes."""
        queue_key = "nadia_message_queue"
        processed_messages = []

        async def process_worker(worker_id: int):
            """Worker que procesa mensajes."""
            while True:
                result = await redis_client.brpop(queue_key, timeout=1)
                if result is None:
                    break

                _, message_json = result
                data = json.loads(message_json)
                processed_messages.append({
                    'worker_id': worker_id,
                    'message': data['message']
                })
                await asyncio.sleep(0.1)  # Simular procesamiento

        # Encolar mensajes
        for i in range(10):
            msg = {'message': f'Msg-{i}', 'user_id': f'user_{i}'}
            await redis_client.lpush(queue_key, json.dumps(msg))

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
