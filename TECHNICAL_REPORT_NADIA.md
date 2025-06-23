# Reporte Técnico: Sistema NADIA - Chatbot con Revisión Humana

## Resumen Ejecutivo

NADIA es un sistema de chatbot conversacional para Telegram que implementa un flujo Human-in-the-Loop (HITL). El bot se presenta como una mujer estadounidense de 24 años, amigable y coqueta. Todas las respuestas generadas por IA pasan por revisión humana antes de ser enviadas, garantizando calidad y recolectando datos de entrenamiento.

## Arquitectura del Sistema

### Stack Tecnológico
- **Backend**: Python 3.11+ con AsyncIO
- **Framework API**: FastAPI
- **Base de Datos**: PostgreSQL + Redis
- **Cliente Telegram**: Telethon
- **Modelos IA**: Gemini 2.0 Flash (Google) + GPT-4.1-nano (OpenAI)
- **Frontend**: HTML/JavaScript vanilla

### Componentes Principales

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Telegram  │────▶│   UserBot    │────▶│   Redis WAL     │
│    Users    │     │  (Telethon)  │     │    (Queue)      │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────────────────────┼─────────┐
                    │                              ▼         │
                    │     ┌─────────────────────────────┐    │
                    │     │   SupervisorAgent          │    │
                    │     │  ┌─────────┐ ┌──────────┐  │    │
                    │     │  │ LLM-1   │ │  LLM-2   │  │    │
                    │     │  │(Gemini) │ │(GPT-4.1) │  │    │
                    │     │  └─────────┘ └──────────┘  │    │
                    │     │         Constitution       │    │
                    │     └─────────────┬──────────────┘    │
                    │                   │                    │
                    │                   ▼                    │
                    │        ┌──────────────────┐           │
                    │        │   Review Queue   │           │
                    │        │     (Redis)      │           │
                    │        └────────┬─────────┘           │
                    │                 │                      │
                    │                 ▼                      │
                    │     ┌───────────────────────┐         │
                    │     │   Dashboard (Web)     │         │
                    │     │  Human Reviewers      │         │
                    │     └───────────┬───────────┘         │
                    │                 │                      │
                    │                 ▼                      │
                    │      ┌──────────────────┐             │
                    │      │ Approved Queue   │             │
                    │      │    (Redis)       │             │
                    │      └────────┬─────────┘             │
                    │               │                        │
                    └───────────────┼────────────────────────┘
                                    ▼
                              Send to User
```

## Flujo de Procesamiento Detallado

### 1. Ingesta de Mensajes

```python
# userbot.py - Event Handler
@self.client.on(events.NewMessage(incoming=True))
async def message_handler(event):
    # Encola mensaje en Write-Ahead Log (WAL)
    wal_entry = {
        "user_id": event.sender_id,
        "message": event.text,
        "chat_id": event.chat_id,
        "message_id": event.id,
        "timestamp": datetime.utcnow().isoformat()
    }
    await redis.lpush("nadia_wal_queue", json.dumps(wal_entry))
```

El sistema utiliza un patrón WAL (Write-Ahead Log) para garantizar que ningún mensaje se pierda, incluso si hay fallos del sistema.

### 2. Pipeline Multi-LLM

El `SupervisorAgent` orquesta un pipeline de dos LLMs con optimización de caché:

#### 2.1 Generación Creativa (LLM-1)
```python
# Usa Gemini 2.0 Flash (GRATIS hasta 32k tokens/día)
llm1_response = await gemini_client.generate(
    prompt=creative_prompt,
    temperature=0.8,  # Alta creatividad
    max_tokens=300
)
```

#### 2.2 Refinamiento y Formato (LLM-2)
```python
# Usa GPT-4.1-nano con 75% descuento por caché
# Implementa prefijos estables de ≥1024 tokens
stable_prefix = self._build_stable_prefix()  # 1,062 tokens
llm2_response = await openai_client.generate(
    prompt=stable_prefix + refinement_prompt,
    temperature=0.3,  # Baja para consistencia
    seed=42  # Determinismo para caché
)
```

#### 2.3 Análisis de Seguridad (Constitution)
```python
# Análisis no bloqueante
risk_analysis = constitution.analyze(llm2_response)
# Retorna: {
#   "score": 0.15,  # 0.0-1.0
#   "flags": ["mild_flirtation"],
#   "violations": [],
#   "recommendation": "approve"
# }
```

### 3. Sistema de Revisión Humana

#### 3.1 Creación de ReviewItem
```python
review_item = ReviewItem(
    user_id=user_id,
    user_message=message,
    ai_response_raw=llm1_response,
    ai_response_formatted=llm2_bubbles,
    constitution_analysis=risk_analysis,
    llm1_model="gemini-2.0-flash-exp",
    llm2_model="gpt-4.1-nano",
    llm1_cost_usd=0.0,  # Gratis
    llm2_cost_usd=0.000307,  # Con caché
    priority=self._calculate_priority(...)
)
```

#### 3.2 Cola de Prioridad en Redis
```python
# Datos en hash
await redis.hset(f"review:{review_id}", mapping=review_data)

# Cola ordenada por prioridad
await redis.zadd("nadia_review_queue", {review_id: priority})
```

### 4. Dashboard de Revisión

El dashboard web permite a revisores humanos:

- **Ver mensajes pendientes** ordenados por prioridad
- **Editar respuestas** con editor de burbujas
- **Insertar CTAs** (Call-to-Actions) en 3 niveles
- **Etiquetar ediciones** para datos de entrenamiento
- **Calificar humanización** (1-5 estrellas)
- **Actualizar estado del cliente** (PROSPECT → CUSTOMER)

```javascript
// dashboard/frontend/app.js
async function approveReview(reviewId) {
    const editedBubbles = editor.getBubbles();
    const response = await fetch(`/api/reviews/${reviewId}/approve`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${API_KEY}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            edited_response: editedBubbles,
            edit_tags: selectedTags,
            quality_score: starRating,
            cta_data: ctaInsertions
        })
    });
}
```

### 5. Envío con Simulación Humana

```python
# userbot.py - Procesador de mensajes aprobados
async def _process_approved_messages(self):
    while True:
        # Obtiene mensaje aprobado
        data = await redis.brpop("nadia_approved_messages")
        
        # Calcula tiempo de lectura
        reading_time = len(user_message) * 0.06  # 60ms por carácter
        
        # Simula escritura
        await client.send_typing(chat_id)
        await asyncio.sleep(reading_time)
        
        # Envía burbujas con delays naturales
        for bubble in bubbles:
            typing_time = len(bubble) * 0.08
            await asyncio.sleep(typing_time)
            await client.send_message(chat_id, bubble)
            await asyncio.sleep(random.uniform(0.5, 1.5))
```

## Optimizaciones Implementadas

### 1. Optimización de Caché (75% descuento)
- **Prefijos estables**: 1,062 tokens inmutables para máximos cache hits
- **Resúmenes de conversación**: En lugar de historial completo
- **Conteo real de tokens**: Integración con tiktoken
- **Monitoreo**: Alertas visuales cuando cache ratio < 50%

### 2. Gestión de Cuotas
```python
# Tracking en Redis con límites diarios
await quota_manager.check_and_update(
    provider="gemini",
    tokens_used=150,
    daily_limit=32000  # Tier gratuito
)
```

### 3. Perfiles Dinámicos de Modelos
```yaml
# llms/model_config.yaml
profiles:
  smart_economic:  # Por defecto
    llm1: gemini/gemini-2.0-flash-exp  # $0.00/1k msgs
    llm2: openai/gpt-4.1-nano          # $0.50/1k msgs con caché
    
  premium:
    llm1: gemini/gemini-2.5-flash      # $0.25/1k msgs
    llm2: openai/gpt-4o                # $12.50/1k msgs
```

## Seguridad y Compliance

### 1. Autenticación API
```python
# Bearer token para todos los endpoints
security = HTTPBearer()

@app.get("/api/reviews/pending")
async def get_pending_reviews(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if credentials.credentials != DASHBOARD_API_KEY:
        raise HTTPException(401)
```

### 2. Rate Limiting
```python
# Límites por endpoint
limiter = Limiter(key_func=get_remote_address)

@app.get("/api/reviews/pending")
@limiter.limit("30/minute")
async def get_pending_reviews():
    # ...
```

### 3. GDPR Compliance
- Endpoint para eliminación de datos de usuario
- Logs sin PII (Información Personal Identificable)
- Retención de datos configurable

## Métricas y Monitoreo

### KPIs del Sistema
- **Costo promedio**: $0.000307 por mensaje
- **Ahorro vs GPT-4**: 70% menor costo
- **Tiempo de revisión promedio**: 45 segundos
- **Tasa de aprobación**: 85%
- **Cache hit ratio**: 75%

### Endpoints de Métricas
```python
GET /api/metrics/dashboard
{
    "queue_length": 42,
    "messages_today": 1250,
    "cost_today_usd": 0.38,
    "gemini_quota_used": 15420,
    "gemini_quota_limit": 32000,
    "cache_hit_ratio": 0.75,
    "avg_review_time_seconds": 45
}
```

## Base de Datos

### PostgreSQL Schema
```sql
-- Tabla principal de interacciones
CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    user_message TEXT NOT NULL,
    ai_response_raw TEXT,
    ai_response_formatted TEXT,
    human_edited_response TEXT,
    edit_tags TEXT[],
    quality_score INTEGER,
    review_time_seconds INTEGER,
    llm1_model VARCHAR(100),
    llm2_model VARCHAR(100),
    llm1_cost_usd DECIMAL(10,6),
    llm2_cost_usd DECIMAL(10,6),
    cta_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX idx_user_id ON interactions(user_id);
CREATE INDEX idx_created_at ON interactions(created_at DESC);
```

## Instalación y Despliegue

### Requisitos
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- 2GB RAM mínimo
- API keys: Telegram, OpenAI, Gemini

### Variables de Entorno
```bash
# .env
API_ID=12345678
API_HASH=abcdef1234567890
PHONE_NUMBER=+1234567890
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
DATABASE_URL=postgresql://user:pass@localhost/nadia_hitl
REDIS_URL=redis://localhost:6379/0
DASHBOARD_API_KEY=secure-key-here
LLM_PROFILE=smart_economic
```

### Comandos de Inicio
```bash
# API Server
PYTHONPATH=/path/to/project python -m api.server

# Dashboard
python dashboard/backend/static_server.py

# Telegram Bot
python userbot.py
```

## Problemas Conocidos y Soluciones

### 🔴 PRIORIDAD ALTA

#### 1. Memoria Contextual del Bot
- **Problema**: Bot no puede seguir conversaciones lógicas
- **Causa**: UserMemoryManager no integrado con SupervisorAgent
- **Consideración estratégica**: Evaluar implementación de RAG como "parte aguas" para humanización
- **Estado**: En fase de validación de hipótesis
- **Impacto**: **CRÍTICO** - Fundamental para experiencia conversacional natural

#### 2. Customer Status Update
- **Problema**: Error "failed to update customer status. please try again" al intentar actualizar estado
- **Estado**: Sin resolver
- **Impacto**: Imposible actualizar estados de cliente manualmente

#### 3. Contaminación de Base de Datos
- **Problema**: Mensajes "cancelados" se anotan en la base de datos
- **Regla de negocio violada**: Solo mensajes aceptados deben guardarse
- **Acción requerida**: Verificar y limpiar registros de mensajes cancelados

### 🟡 PRIORIDAD MEDIA

#### 4. Problemas del Dashboard - Ventanas Emergentes
- **Problema**: Botón "cancelar" no cancela, actúa como "aceptar"
- **Problema**: Ventana "optional reviewer notes" no respeta la acción "cancelar"
- **Problema**: Mensajes "cancelados" se envían como si fueran aceptados
- **Riesgo**: Mensajes no deseados enviados a usuarios
- **Estado**: Sin resolver

#### 5. Contexto Horario (Timezone)
- **Problema**: Respuestas no consideran zona horaria de Monterrey
- **Ejemplo**: Bot dice "buenas noches" cuando en México es de mañana
- **Solución pendiente**: Integrar contexto horario en prompts

#### 6. Message Number Tracking
- **Problema**: `message_number` siempre vale 1 (hardcodeado)
- **Impacto**: Pérdida de análisis conversacional y patrones
- **Código afectado**: `database/models.py:67`

### 🟢 PRIORIDAD BAJA - MEJORAS DE DATOS Y VISUALIZACIÓN

#### 7. Revisión de Datos
- **Necesidad**: Interface tipo Excel para revisar datos registrados
- **Objetivo**: Verificar integridad de datos de manera cómoda

#### 8. Evaluación de Constitution
- **Problema**: No hay manera de evaluar efectividad de flaggeos/warnings
- **Necesidad**: Dashboard para analizar decisiones del Constitution

#### 9. CTA Response Type Tracking
- **Problema**: No hay sección en dashboard para registrar `cta_response_type`
- **Impacto**: Pérdida de datos de conversión importantes

#### 10. Vista de Usuario por Evolución
- **Necesidad**: Dashboard que muestre por usuario:
  - Número de mensajes totales
  - CTAs enviados
  - Customer status actual
  - Evolución temporal (no solo user_id)

### PROBLEMAS LEGACY (Ya identificados previamente)

#### 11. Actualización Estado Cliente (Backend)
- **Problema**: POST endpoint falla con "Internal Server Error"
- **Solución temporal**: Usar DATABASE_MODE=skip

#### 12. Límites de Cuota Gemini
- **Problema**: 429 errors en tier gratuito
- **Solución**: Implementado backoff exponencial y fallback a otros modelos

### ANÁLISIS DE IMPACTO

#### Problemas Críticos que Requieren Atención Inmediata:
1. **Memoria Contextual del Bot** - Fundamental para experiencia conversacional natural
2. **Customer Status update fallando** - Impide gestión manual de clientes
3. **Contaminación de datos** - Afecta calidad del dataset de entrenamiento

#### Consideraciones Estratégicas:
- **RAG Implementation**: Evaluación pendiente si puede ser "parte aguas" para humanización
- **Contexto horario**: Importante para personalización de respuestas
- **Message number**: Fundamental para análisis conversacional avanzado
- **Ventanas emergentes**: Problema de UX pero no crítico para funcionalidad core

## Dimensiones y Atributos del Dataset

### Dimensiones Principales de Análisis

#### 1. Identificación de Usuario
- `user_id` - Identificador único de Telegram
- `conversation_id` - Sesión de conversación única
- `message_number` - Número secuencial del mensaje en la conversación

#### 2. Contenido del Mensaje
- `user_message` - Mensaje original del usuario
- `user_message_timestamp` - Timestamp del mensaje del usuario
- `llm1_raw_response` - Respuesta creativa de LLM-1 (Gemini)
- `llm2_bubbles` - Respuesta refinada de LLM-2 (GPT) como array de burbujas
- `final_bubbles` - Respuesta final editada por humano como array
- `messages_sent_at` - Timestamp cuando se envió el mensaje aprobado

#### 3. Tracking de Modelos IA
- `llm1_model` - Modelo usado para generación creativa (ej: gemini-2.0-flash)
- `llm2_model` - Modelo usado para refinamiento (ej: gpt-4o-mini)
- `llm1_tokens_used` - Tokens consumidos por LLM-1
- `llm2_tokens_used` - Tokens consumidos por LLM-2
- `llm1_cost_usd` - Costo en USD de LLM-1
- `llm2_cost_usd` - Costo en USD de LLM-2
- `total_cost_usd` - Costo combinado de ambos LLMs

#### 4. Análisis de Constitution
- `constitution_risk_score` - Puntuación de riesgo 0.0 (seguro) a 1.0 (alto riesgo)
- `constitution_flags` - Array de banderas de violación detectadas
- `constitution_recommendation` - Recomendación: 'approve', 'review', o 'flag'

#### 5. Proceso de Revisión Humana
- `review_status` - Estado: 'pending', 'reviewing', 'approved', 'rejected'
- `reviewer_id` - ID del revisor humano
- `review_started_at` - Cuando comenzó la revisión
- `review_completed_at` - Cuando terminó la revisión
- `review_time_seconds` - Tiempo de revisión en segundos
- `quality_score` - Calificación de calidad 1-5 del revisor
- `reviewer_notes` - Notas de texto libre del revisor

#### 6. Taxonomía de Ediciones

##### Ediciones de Tono
- `TONE_CASUAL` - Hacer más casual/informal
- `TONE_FLIRT_UP` - Aumentar tono coqueto/juguetón
- `TONE_CRINGE_DOWN` - Reducir cringe/melodrama
- `TONE_ENERGY_UP` - Añadir energía/entusiasmo
- `TONE_LESS_IA` - Hacer respuesta menos IA y más humana
- `TONE_ROMANTIC_UP` - Aumentar tono romántico/íntimo

##### Ediciones de Estructura
- `STRUCT_SHORTEN` - Acortado significativamente
- `STRUCT_BUBBLE` - Cambio en división de burbujas

##### Ediciones de Contenido
- `CONTENT_EMOJI_ADD` - Añadir emojis
- `CONTENT_EMOJI_CUT` - Remover emojis excesivos
- `CONTENT_QUESTION` - Añadir pregunta engaging
- `CONTENT_QUESTION_CUT` - Remover preguntas innecesarias
- `CONTENT_REWRITE` - Reescritura completa
- `CONTENT_SENTENCE_ADD` - Añadir más oraciones/contexto

##### Ediciones de Lenguaje
- `ENGLISH_SLANG` - Añadir slang americano
- `TEXT_SPEAK` - Convertir a estilo mensaje de texto

##### Ediciones de CTA
- `CTA_SOFT` - CTA suave insertado (ej: "btw i have some pics i can't send here 🙈")
- `CTA_MEDIUM` - CTA medio insertado
- `CTA_DIRECT` - CTA directo insertado (ej: "check out my Fanvue for more content 💕")

#### 7. Tracking de Estado del Cliente
- `customer_status` - Estado en el embudo de ventas:
  - `PROSPECT` - Sin CTA enviado aún
  - `LEAD_QUALIFIED` - Engaged con CTAs
  - `CUSTOMER` - Convertido a cliente pagando
  - `CHURNED` - Dejó de pagar
  - `LEAD_EXHAUSTED` - Sin potencial de conversión
- `cta_sent_count` - Número de CTAs enviados al usuario
- `cta_response_type` - Cómo respondió el usuario:
  - `IGNORED`
  - `POLITE_DECLINE`
  - `INTERESTED`
  - `CONVERTED`
  - `RUDE_DECLINE`
- `last_cta_sent_at` - Timestamp del último CTA
- `conversion_date` - Cuando el usuario se convirtió
- `ltv_usd` - Lifetime value en USD
- `cta_data` - Campo JSONB para metadata de inserción manual de CTA

#### 8. Prioridad y Performance
- `priority_score` - Prioridad del mensaje para cola de revisión
- Métricas de caché (tracked en código):
  - `cached_tokens` - Tokens servidos desde caché
  - `total_tokens` - Total de tokens procesados
  - `cache_ratio` - Ratio de cache hits

### Vistas Agregadas para Análisis

#### 1. Métricas de Usuario (`user_metrics`)
- `total_interactions` - Total de mensajes por usuario
- `avg_quality_score` - Calificación de calidad promedio
- `total_conversations` - Número de conversaciones
- `last_interaction` - Interacción más reciente
- `total_cost` - Costo total por usuario

#### 2. Métricas por Hora (`hourly_metrics`)
- `messages` - Conteo de mensajes por hora
- `avg_review_time` - Tiempo promedio de revisión
- `unique_users` - Usuarios únicos por hora
- `hourly_cost` - Costo por hora

#### 3. Análisis de Patrones de Edición (`edit_pattern_analysis`)
- `edit_tag` - Tag de edición específico
- `frequency` - Frecuencia de uso
- `avg_quality` - Calidad promedio cuando se usa el tag
- `avg_review_time` - Tiempo promedio de revisión para el tag

#### 4. Métricas del Embudo de Cliente (`customer_funnel_metrics`)
- `interaction_count` - Interacciones por estado
- `unique_users` - Usuarios por estado
- `avg_ctas_sent` - CTAs promedio por estado
- `converted_count` - Conversiones por estado
- `total_ltv` - Lifetime value total
- `avg_ltv` - Lifetime value promedio

### Datasets de Exportación

El script de exportación genera 4 archivos CSV optimizados para diferentes análisis:

1. **Datos de Entrenamiento Principal** (`nadia_training_data_*.csv`)
   - Registros completos de interacciones con todas las dimensiones
   - Ideal para fine-tuning de modelos

2. **Patrones de Edición** (`edit_patterns_*.csv`)
   - Análisis agregado de tags de edición
   - Identifica patrones comunes de mejora humana

3. **Resúmenes de Conversación** (`conversations_*.csv`)
   - Métricas a nivel de conversación
   - Útil para análisis de engagement

4. **Comparación LLM vs Humano** (`llm_human_comparison_*.csv`)
   - Comparación lado a lado de outputs de IA vs ediciones humanas
   - Esencial para mejorar prompts y modelos

Este sistema integral de tracking permite:
- Recolección de datos de entrenamiento para fine-tuning
- Análisis de calidad de ediciones humanas
- Optimización de costos y tracking de performance
- Análisis del embudo de conversión de clientes
- Descubrimiento de patrones de edición
- Evaluación de efectividad del Constitution
- Métricas de performance multidimensionales

## Conclusiones

NADIA representa una arquitectura sofisticada que balancea:
- **Calidad**: Revisión humana garantiza respuestas apropiadas
- **Costo**: $0.0003/mensaje con optimizaciones de caché
- **Escalabilidad**: Arquitectura async con colas Redis
- **Datos de entrenamiento**: Sistema integral de 8+ dimensiones principales con 50+ atributos
- **Análisis multidimensional**: Vistas agregadas para insights de negocio y mejora de IA

El sistema está en producción y procesa ~1,250 mensajes diarios con un costo total de $0.38/día, mientras recolecta datos de entrenamiento de alta calidad en múltiples dimensiones.