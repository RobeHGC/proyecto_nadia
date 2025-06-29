# 🏗️ PLAN ARQUITECTURA HÍBRIDA: PostgreSQL + MongoDB

## 📋 **SESIÓN ACTUAL - ESTADO**

**Fecha**: 2025-06-29  
**Contexto**: Evolucionando de RAG local a arquitectura híbrida completa  
**RAG Status**: ✅ Funcionando en producción con local embeddings  

---

## 🎯 **ARQUITECTURA DEFINITIVA APROBADA**

### **PostgreSQL** (Lo que ya dominas)
```
✅ user_current_status     - Usuarios, nicknames, customer status
✅ conversation_history    - Mensajes, timestamps, metadata conversacional  
✅ review_queue           - Human review, approval states
✅ analytics             - Métricas, costos, performance
🆕 procedural_knowledge   - Prompts, reglas, triggers por contexto
```

### **MongoDB** (Memorias complejas + Vector search)
```
🆕 semantic_memories     - Biografía Nadia + embeddings vectoriales
🆕 episodic_memories     - Recuerdos vividos complejos + contexto temporal/social
🆕 emotional_states      - Sentimientos asociados + intensidad + metadata
🆕 user_patterns         - Patrones conversacionales aprendidos
```

---

## 🚀 **PLAN DE IMPLEMENTACIÓN (90 min)**

### **FASE 1: MongoDB Setup** (30 min)
- [ ] **1.1** Configurar MongoDB local/Atlas connection
- [ ] **1.2** Crear database `nadia_memories` + colecciones
- [ ] **1.3** Configurar índices vectoriales para embeddings 384d
- [ ] **1.4** Migrar 7 documentos biográficos desde local files

### **FASE 2: Sistema Híbrido** (45 min)  
- [ ] **2.1** `HybridMemoryManager` - Coordinador PostgreSQL + MongoDB
- [ ] **2.2** RAG + CAG unificado - Router de búsquedas por tipo
- [ ] **2.3** Integración en `supervisor_agent.py` - Memoria híbrida automática
- [ ] **2.4** Fallback system - Local → MongoDB → PostgreSQL

### **FASE 3: Recuerdos Vividos** (15 min)
- [ ] **3.1** Episodic memory detection - Momentos importantes
- [ ] **3.2** Emotional context capture - Sentimientos + intensidad  
- [ ] **3.3** Memory linking system - Conectar recuerdos relacionados

---

## 📊 **FLUJO DE DATOS HÍBRIDO**

```
1. Usuario envía mensaje
   ↓ PostgreSQL
2. Guardar en conversation_history + metadata
   ↓ MongoDB  
3. Buscar recuerdos relevantes (RAG semantic + CAG episodic)
   ↓ HybridMemoryManager
4. Combinar historial PostgreSQL + memorias MongoDB
   ↓ Supervisor  
5. LLM genera respuesta con contexto completo
   ↓ PostgreSQL
6. Guardar respuesta + review_queue
   ↓ MongoDB (si importante)
7. Crear nuevo recuerdo episódico + emotional context
```

---

## 🗃️ **ESTRUCTURA DE DATOS**

### **MongoDB - Recuerdo Episódico Típico:**
```json
{
  "_id": "episodic_memory_123",
  "user_id": "user456", 
  "memory_type": "conversation_highlight",
  "content": "Usuario me contó sobre su divorcio reciente",
  "embedding": [0.23, -0.45, 0.67, ...], // 384 dims
  "temporal_context": {
    "happened_at": "2025-06-15T14:30:00Z",
    "conversation_turn": 23,
    "session_duration": "45min",
    "time_of_day": "afternoon"
  },
  "social_context": {
    "participants": ["nadia", "user456"],
    "relationship_stage": "getting_to_know", 
    "user_mood": "vulnerable",
    "conversation_topic": "personal_life"
  },
  "emotional_context": {
    "user_sentiment": "sad",
    "nadia_response_tone": "empathetic",
    "emotional_intensity": 0.8,
    "user_emotions": ["sadness", "relief", "hope"]
  },
  "memory_importance": 0.9,
  "retrieval_tags": ["personal", "relationships", "emotional_support"],
  "linked_memories": ["memory_120", "memory_125"],
  "created_at": "2025-06-15T14:35:00Z"
}
```

### **PostgreSQL - Conversación Estructurada:**
```sql
conversation_history:
- id, user_id, role, content, timestamp
- metadata_json (simple), review_status
- NO embeddings, NO complex objects
```

---

## 🎯 **VENTAJAS ARQUITECTURA HÍBRIDA**

### **PostgreSQL Strengths:**
- ✅ **ACID transactions** para datos críticos conversacionales
- ✅ **Queries familiares** SQL para analytics y reportes  
- ✅ **Performance predecible** para datos estructurados
- ✅ **Backup/recovery** robusto que ya conoces

### **MongoDB Strengths:**  
- ✅ **Vector search nativo** optimizado para embeddings
- ✅ **Documentos flexibles** para memorias complejas evolutivas
- ✅ **Agregations pipeline** para análisis de patrones
- ✅ **Escalabilidad horizontal** para crecimiento de memorias

### **Híbrido Benefits:**
- ✅ **Mejor de ambos mundos** - Estructura + Flexibilidad
- ✅ **Separation of concerns** - Cada base optimizada
- ✅ **Expertise leveraging** - PostgreSQL actual + MongoDB memorias
- ✅ **Independent scaling** - Escalar memorias sin afectar conversaciones

---

## 🚧 **RIESGOS & MITIGACIONES**

### **Riesgos:**
- ⚠️ **Complejidad operacional** - Dos bases de datos
- ⚠️ **Consistency challenges** - Sin ACID entre bases
- ⚠️ **MongoDB learning curve** - Nueva tecnología

### **Mitigaciones:**
- ✅ **Eventual consistency** aceptable para memorias
- ✅ **Fallback systems** - Local RAG si MongoDB falla
- ✅ **Incremental migration** - PostgreSQL continúa funcionando
- ✅ **Monitoring dual** - Health checks ambas bases

---

## 📈 **MÉTRICAS DE ÉXITO**

### **Performance Targets:**
- 🎯 **Memory retrieval**: <100ms para búsquedas híbridas
- 🎯 **Embedding generation**: <50ms promedio
- 🎯 **Context confidence**: >0.4 para memorias importantes
- 🎯 **System uptime**: 99.9% con fallbacks

### **Quality Metrics:**
- 🎯 **Memory relevance**: Usuario percibe mejores respuestas
- 🎯 **Context accuracy**: Recuerdos precisos y útiles
- 🎯 **Emotional intelligence**: Respuestas empáticas apropiadas
- 🎯 **Learning progression**: Mejora continua de memorias

---

## 🔄 **NEXT SESSION RESTART CHECKLIST**

- [ ] Revisar este documento
- [ ] Verificar estado RAG local actual (debe seguir funcionando)
- [ ] Confirmar MongoDB connection/setup
- [ ] Continuar desde todo list actual
- [ ] Validar PostgreSQL schemas existentes

**IMPORTANTE**: El RAG local actual debe seguir funcionando durante toda la migración como fallback.

---

**Última actualización**: 2025-06-29 - Plan aprobado para implementación híbrida