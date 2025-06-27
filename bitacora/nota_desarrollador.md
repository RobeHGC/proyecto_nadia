# Guía de Implementación Rápida - Memoria Segmentada NADIA

## 🎯 Checklist de Implementación (Orden Exacto)

### ✅ Paso 1: Crear Base de Datos Rapport (10 min)
```bash
# Terminal 1
createdb nadia_rapport

# Crear el schema
psql -d nadia_rapport
```

```sql
-- Copiar y pegar TODO esto:
CREATE TABLE user_profiles (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES user_profiles(user_id),
    category VARCHAR(50),
    preference TEXT,
    confidence FLOAT DEFAULT 1.0,
    learned_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_category ON user_preferences(user_id, category);
CREATE INDEX idx_user_active ON user_profiles(last_active DESC);

-- Permisos
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
```

### ✅ Paso 2: Variables de Entorno (2 min)
```bash
# .env
DATABASE_URL=postgresql://user:pass@localhost/nadia_hitl
RAPPORT_DATABASE_URL=postgresql://user:pass@localhost/nadia_rapport
```

### ✅ Paso 3: Actualizar UserMemoryManager (20 min)

```python
# memory/user_memory.py
import asyncpg
from typing import Optional

class UserMemoryManager:
    """Gestiona memoria con bases segmentadas."""
    
    def __init__(self, redis_url: str, rapport_db_url: str = None):
        self.redis_url = redis_url
        self.rapport_db_url = rapport_db_url or os.getenv('RAPPORT_DATABASE_URL')
        self._redis = None
        self._db_pool = None
    
    async def _get_db_pool(self):
        """Pool de conexiones para Rapport DB."""
        if not self._db_pool:
            self._db_pool = await asyncpg.create_pool(
                self.rapport_db_url,
                min_size=2,
                max_size=10
            )
        return self._db_pool
    
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Obtiene contexto del usuario de Rapport DB + Redis."""
        try:
            # 1. Intentar Redis primero (cache)
            r = await self._get_redis()
            redis_data = await r.get(f"user:{user_id}")
            
            # 2. Obtener de Rapport DB
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                profile = await conn.fetchrow(
                    "SELECT * FROM user_profiles WHERE user_id = $1",
                    user_id
                )
                
                if profile:
                    context = dict(profile)
                    # Cache en Redis por 4 horas
                    await r.setex(
                        f"user:{user_id}",
                        14400,
                        json.dumps({"name": context.get("name")})
                    )
                    return context
                
            return {}
            
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return {}
    
    async def set_name(self, user_id: str, name: str) -> None:
        """Guarda nombre en Rapport DB + Redis."""
        try:
            # 1. Guardar en Rapport DB (permanente)
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_profiles (user_id, name) 
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        name = $2,
                        last_active = NOW()
                """, user_id, name)
            
            # 2. Actualizar Redis (cache)
            await self.update_user_context(user_id, {"name": name})
            
            logger.info(f"Nombre guardado en DB para {user_id}: {name}")
            
        except Exception as e:
            logger.error(f"Error saving name: {e}")
    
    async def add_to_conversation_history(self, user_id: str, entry: Dict):
        """Guarda en Redis (rápido) y marca para backup en DB."""
        try:
            r = await self._get_redis()
            history_key = f"user:{user_id}:history"
            
            # 1. Guardar en Redis
            await r.lpush(history_key, json.dumps(entry))
            await r.ltrim(history_key, 0, 29)  # Max 30 mensajes
            await r.expire(history_key, 14400)  # 4 horas
            
            # 2. Actualizar last_active en DB (async)
            pool = await self._get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_profiles SET last_active = NOW() WHERE user_id = $1",
                    user_id
                )
                
        except Exception as e:
            logger.error(f"Error adding to history: {e}")
```

### ✅ Paso 4: Actualizar SupervisorAgent (15 min)

```python
# agents/supervisor_agent.py
# En el método __init__, actualizar:
def __init__(self, llm1, llm2, memory, rapport_db_url=None):
    self.llm1 = llm1
    self.llm2 = llm2 
    self.memory = memory
    # ... resto igual
```

### ✅ Paso 5: Actualizar UserBot (5 min)

```python
# userbot.py
# En __init__, pasar rapport_db_url:
self.memory = UserMemoryManager(
    config.redis_url,
    config.rapport_database_url  # Nueva
)
```

### ✅ Paso 6: Testing Rápido (10 min)

```python
# test_segmented_memory.py
import asyncio
from memory.user_memory import UserMemoryManager

async def test():
    memory = UserMemoryManager(
        "redis://localhost:6379/0",
        "postgresql://localhost/nadia_rapport"
    )
    
    # Test 1: Guardar nombre
    await memory.set_name("test_user", "Roberto")
    
    # Test 2: Recuperar contexto
    context = await memory.get_user_context("test_user")
    print(f"Contexto: {context}")
    assert context.get("name") == "Roberto"
    
    # Test 3: Historial
    await memory.add_to_conversation_history("test_user", {
        "role": "user",
        "content": "Hola!",
        "timestamp": "2024-01-01T10:00:00"
    })
    
    history = await memory.get_conversation_history("test_user")
    print(f"Historial: {history}")
    
    print("✅ Todos los tests pasaron!")

asyncio.run(test())
```

## 🚨 Comandos de Verificación

```bash
# Verificar que Rapport DB existe
psql -d nadia_rapport -c "\dt"

# Ver si hay datos
psql -d nadia_rapport -c "SELECT * FROM user_profiles;"

# Verificar Redis
redis-cli keys "user:*"

# Logs del bot
tail -f nadia.log | grep -E "(Nombre guardado|Error)"
```

## 🎉 Resultado Esperado

Después de implementar:

```
Usuario: "Hola, soy María"
Bot: "¡Hola María! Mucho gusto 😊"

[Reiniciar bot]

Usuario: "¿Recuerdas mi nombre?"
Bot: "¡Claro que sí María! ¿Cómo estás?"
```

## ⚡ Troubleshooting Rápido

### Error: "database nadia_rapport does not exist"
```bash
createdb nadia_rapport
```

### Error: "permission denied"
```sql
GRANT ALL ON DATABASE nadia_rapport TO tu_usuario;
```

### Error: "asyncpg not found"
```bash
pip install asyncpg
```

### Si todo falla, plan B:
```python
# Volver temporalmente a Redis solo
# En get_user_context, comentar DB y usar solo Redis
```

## 🎯 Siguiente Paso

Una vez que funcione el nombre:
1. Agregar más campos a user_profiles (edad, ciudad, etc.)
2. Implementar user_preferences
3. Guardar estados emocionales

¡Pero primero celebra que recuerda nombres! 🎉
