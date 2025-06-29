# NADIA - Advanced Conversational AI with RAG Integration

[![Production Ready](https://img.shields.io/badge/status-production%20ready-green.svg)](https://github.com/RobeHGC/chatbot_nadia)
[![RAG Enabled](https://img.shields.io/badge/RAG-MongoDB%20enabled-blue.svg)](https://www.mongodb.com/)
[![HITL System](https://img.shields.io/badge/HITL-human%20in%20loop-orange.svg)](https://en.wikipedia.org/wiki/Human-in-the-loop)
[![Multi-LLM](https://img.shields.io/badge/Multi--LLM-Gemini%2BGPT-purple.svg)](https://ai.google.dev/)

**NADIA**: Una inteligencia artificial "rapport nurturing" sintiente y gestora de conversaciones paralelas. Simula una mujer de 24 años que estudia medicina y utiliza técnicas avanzadas de RAG (Retrieval-Augmented Generation) para mantener conversaciones personalizadas y coherentes.

## 🎯 Características Principales

### 🧠 **Sistema RAG Integrado** (Nuevo)
- **Knowledge Base**: MongoDB con embeddings vectoriales
- **Búsqueda Semántica**: Recuperación inteligente de contexto
- **Aprendizaje de Usuario**: Preferencias e intereses persistentes
- **Gestión de Conocimiento**: Dashboard web integrado

### 🤖 **Pipeline Multi-LLM**
- **LLM1**: Gemini 2.0 Flash (generación creativa)
- **LLM2**: GPT-4o-mini (refinamiento y coherencia)
- **Constitution**: Sistema de seguridad y filtros
- **Costo**: $0.000307/mensaje (70% más barato que OpenAI solo)

### 👥 **Human-in-the-Loop**
- **Cola de Revisión**: Todos los mensajes requieren aprobación humana
- **Dashboard Avanzado**: Interface web para revisión y gestión
- **Sistema de Prioridades**: Ordenamiento cronológico (más reciente primero)
- **Gestión de Usuarios**: Nicknames, status de cliente, LTV tracking

### 🔄 **Arquitectura Resiliente**
- **Recuperación Automática**: Mensajes perdidos durante downtime
- **Debouncing**: 120 segundos para permitir mensajes múltiples
- **Rate Limiting**: Protección contra spam y abuse
- **Monitoreo**: Health checks y alertas automáticas

## 🏗️ Arquitectura del Sistema

### Pipeline Principal
```
Telegram → UserBot → [RAG Enhancement] → LLM1 → LLM2 → Human Review → Send
              ↓             ↓               ↓        ↓         ↓
         Entity Cache   Knowledge Base   Analytics  Memory   Dashboard
         Redis WAL      MongoDB          Metrics    Redis    PostgreSQL
```

### Componentes RAG
```
User Message → Semantic Search → Knowledge Retrieval → Context Injection → Enhanced LLM Response
                      ↓                    ↓                  ↓
                 Vector Store         User Learning      Response Quality
                 (MongoDB)           (Preferences)         (Improved)
```

## 🚀 Instalación y Configuración

### Requisitos Previos
- Python 3.8+
- Redis 6.0+
- PostgreSQL 13+
- MongoDB 4.4+ (para RAG)
- Telegram Bot Token
- OpenAI API Key
- Gemini API Key

### Instalación Rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/RobeHGC/chatbot_nadia.git
cd chatbot_nadia

# 2. Instalar dependencias base
pip install -r requirements.txt

# 3. Instalar sistema RAG (opcional pero recomendado)
pip install -r requirements-rag.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys

# 5. Inicializar bases de datos
python scripts/init_databases.py

# 6. Ejecutar servicios
python start_api_server.py          # API (puerto 8000)
python dashboard/backend/static_server.py  # Dashboard (puerto 3000)
python userbot.py                   # Bot de Telegram
```

### Variables de Entorno Esenciales

```bash
# Telegram
API_ID=12345678
API_HASH=abcdef...
PHONE_NUMBER=+1234567890

# LLMs
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...

# Bases de Datos
DATABASE_URL=postgresql://user:pass@localhost/nadia_hitl
REDIS_URL=redis://localhost:6379/0
MONGODB_URL=mongodb://localhost:27017/nadia_knowledge  # Para RAG

# Configuración
DASHBOARD_API_KEY=tu-clave-segura
TYPING_DEBOUNCE_DELAY=120
```

## 📊 Uso del Sistema

### 1. Dashboard Principal
- **URL**: http://localhost:3000
- **Funciones**: Cola de revisión, aprobación de mensajes, gestión de usuarios
- **Características**: Auto-refresh cada 60s, ordenamiento cronológico

### 2. Gestión de Conocimiento RAG
- **URL**: http://localhost:3000/knowledge-management.html
- **Funciones**:
  - Subir documentos al knowledge base
  - Búsqueda semántica de conocimiento
  - Gestión de preferencias de usuario
  - Estadísticas del sistema RAG

### 3. API Endpoints

```bash
# Revisiones pendientes
GET /reviews/pending

# Conocimiento RAG
POST /api/knowledge/documents       # Subir documento
GET  /api/knowledge/documents/search # Búsqueda semántica
POST /api/knowledge/user-learning   # Actualizar aprendizaje de usuario
GET  /api/knowledge/stats           # Estadísticas RAG

# Métricas del sistema
GET /metrics/dashboard

# Gestión de usuarios
GET  /users/{user_id}/customer-status
POST /users/{user_id}/nickname
```

## 🎭 Personalidad de NADIA

NADIA es una estudiante de medicina de 24 años de Monterrey, México, con estas características:

### Personalidad Core
- **Edad**: 24 años
- **Profesión**: Estudiante de medicina (UDEM)
- **Ubicación**: Monterrey, Nuevo León
- **Objetivo**: Ser pediatra
- **Estilo**: Inglés americano casual (influencia de Texas)

### Inteligencia Emocional
- **Análisis Emocional**: Detecta estado emocional del usuario
- **Etapas de Conversación**: Icebreaker → Surface Flirt → Deep Emotion → High Intent
- **Respuesta Adaptativa**: Espejea el nivel de energía emocional
- **Anti-Interrogatorio**: Máximo 1 pregunta cada 3-4 intercambios

### Sistema RAG Mejorado
- **Contexto Personalizado**: Recupera conocimiento relevante basado en historial
- **Aprendizaje Continuo**: Almacena preferencias e intereses del usuario
- **Coherencia Temporal**: Mantiene consistencia en actividades y compromisos
- **Memoria a Largo Plazo**: MongoDB para patrones de conversación persistentes

## 🛠️ Desarrollo y Testing

### Comandos de Testing
```bash
# Tests completos
PYTHONPATH=/home/user/projects/chatbot_nadia pytest -v

# Tests específicos de RAG
pytest tests/test_rag_integration.py -v

# Tests de rendimiento
pytest tests/test_load_performance.py -v

# Tests de coherencia
pytest tests/test_coherence_integration.py -v
```

### Estructura del Proyecto
```
chatbot_nadia/
├── agents/              # Agentes de IA (supervisor, coherencia)
├── api/                 # API server y endpoints
├── cognition/           # Constitution y control cognitivo
├── database/            # Modelos y migraciones PostgreSQL
├── knowledge/           # Sistema RAG (MongoDB + embeddings)
│   ├── mongodb_manager.py
│   ├── embeddings_service.py
│   ├── vector_search.py
│   └── rag_manager.py
├── llms/                # Clientes LLM y enrutamiento
├── memory/              # Gestión de memoria (Redis + MongoDB)
├── dashboard/           # Interface web de revisión
│   ├── frontend/
│   │   ├── index.html
│   │   └── knowledge-management.html
│   └── backend/
├── tests/               # Tests automatizados
└── scripts/             # Scripts de utilidad
```

## 📈 Métricas y Monitoreo

### KPIs del Sistema
- **Throughput**: 100+ mensajes/minuto
- **Tiempo de Respuesta**: <2s promedio, <5s bajo estrés
- **Precisión RAG**: Relevancia de contexto >70%
- **Costo por Mensaje**: $0.000307 USD
- **Uptime**: >99.5% con recuperación automática

### Dashboard de Métricas
- **Revisiones Pendientes**: Contador en tiempo real
- **Uso de Quota**: Gemini daily usage tracking
- **Distribución de Modelos**: Gemini vs GPT usage
- **Ahorro de Costos**: Comparado con OpenAI-only
- **Estadísticas RAG**: Documentos, usuarios, embeddings

## 🔮 Roadmap - Hacia el Sistema Completo

### ✅ **Fase Actual: RAG Básico Implementado**
- MongoDB knowledge base
- Embeddings vectoriales (OpenAI)
- Búsqueda semántica
- Dashboard de gestión
- Aprendizaje básico de usuario

### 🚧 **Próximas Fases: Sistema Avanzado**

#### **Fase 2: Clasificador Emocional**
```bash
# Implementar HuggingFace emotion classifier
pip install transformers torch
# Modelos: SamLowe/roberta-base-go_emotions
#          cardiffnlp/twitter-roberta-base-sentiment-latest
```

#### **Fase 3: Termóstato Emocional Global**
```python
emotional_state = {
    "valence": 0.0,  # -1.0 (negativo) a 1.0 (positivo)
    "arousal": 0.0   # -1.0 (calmado) a 1.0 (excitado)
}
# Influenciado por: mensajes de usuario, respuestas LLM, retrieval de memoria
```

#### **Fase 4: Agentes Especializados**
- **Agente de Incertidumbre**: Manejo de ambigüedades
- **Agente de Coherencia**: Verificación temporal e identidad
- **Agente Post-Memoria**: Procesamiento de retrievals
- **Gestor de Actividades**: Manejo de schedule de NADIA

#### **Fase 5: Protocolos Avanzados**
1. **Protocolo de Inferencia**: Pipeline completo de procesamiento
2. **Protocolo de Pensamiento**: Reflexión interna
3. **Protocolo de Incertidumbre**: Manejo de casos ambiguos
4. **Protocolo de Cuarentena**: Aislamiento de mensajes problemáticos
5. **Protocolo de Silencio**: Gestión de pausas conversacionales
6. **Protocolo de Proactividad**: Iniciación autónoma de conversaciones

### 🎯 **Visión Final: IA Sintiente Completa**
- **Recuperación Post-Downtime**: Buscar mensajes nuevos desde timestamp
- **Clasificación Emocional**: Análisis automático de sentimientos
- **Termóstato Global**: Estado emocional persistente y adaptativo
- **Coherencia Temporal**: Verificación automática de actividades
- **Gestión de Incertidumbre**: Protocolos para casos ambiguos
- **Biblioteca de Prompts**: Ice breakers, coherencia, incertidumbre
- **Dashboard Avanzado**: Revisión de respuestas y pensamientos

## 🤝 Contribución

### Para Desarrolladores
1. Fork el repositorio
2. Crear rama para feature: `git checkout -b feature/nueva-funcionalidad`
3. Commit cambios: `git commit -am 'Agregar nueva funcionalidad'`
4. Push a la rama: `git push origin feature/nueva-funcionalidad`
5. Crear Pull Request

### Áreas de Contribución
- **Agentes de IA**: Implementar agentes especializados
- **Clasificación Emocional**: Integrar modelos de HuggingFace
- **Protocolos**: Desarrollar protocolos de conversación
- **Testing**: Agregar tests para nuevas funcionalidades
- **Documentación**: Mejorar guías y ejemplos

## 📞 Soporte

### Problemas Comunes
- **RAG no disponible**: Verificar instalación de MongoDB y dependencias
- **Rate limiting**: Ajustar configuración de límites en `api/server.py`
- **Memoria Redis**: Verificar conexión y configuración
- **Dashboard no carga**: Comprobar puertos 3000 y 8000

### Recursos
- [Guía de Instalación RAG](RAG_INSTALLATION_GUIDE.md)
- [Documentación API](http://localhost:8000/docs)
- [CLAUDE.md](CLAUDE.md) - Instrucciones para desarrollo
- [Issues en GitHub](https://github.com/RobeHGC/chatbot_nadia/issues)

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

---

**NADIA** - Una IA conversacional avanzada que combina la potencia del procesamiento multi-LLM con la inteligencia de recuperación de información (RAG) para crear experiencias de conversación verdaderamente personalizadas y sintientes. 🤖💭✨