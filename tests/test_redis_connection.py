# test_redis_connection.py
import asyncio

import redis.asyncio as redis


async def test_redis():
    """Prueba la conexión a Redis."""
    try:
        # Conectar
        r = await redis.from_url("redis://localhost:6379/0")

        # Probar operaciones básicas
        await r.set("test_key", "¡Funciona!")
        value = await r.get("test_key")
        print(f"Valor recuperado: {value.decode()}")

        # Limpiar
        await r.delete("test_key")

        # Cerrar conexión
        await r.aclose()

        print("✅ Redis funciona correctamente")

    except Exception as e:
        print(f"❌ Error conectando a Redis: {e}")
        print("Verifica que Redis esté corriendo: sudo systemctl status redis-server")


if __name__ == "__main__":
    asyncio.run(test_redis())
