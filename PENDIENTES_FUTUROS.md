# PENDIENTES FUTUROS - NADIA HITL

## 🔍 INVESTIGACIÓN DE MEMORIA CONTEXTUAL (PRIORIDAD #1 - CRÍTICA)

### Problema Identificado:
- **CONFIRMADO POR USUARIO**: El bot no responde según el contexto de mensajes anteriores
- Ejemplo real: Después de conversación, responder "what" no tiene contexto
- **IMPACTA**: Naturalidad de la conversación y experiencia del usuario

### Áreas a Investigar (Dec 21, 2024):
1. **Redis Memory Manager Integration**
   - ✅ UserMemoryManager existe (`memory/user_memory.py`)
   - ❓ Verificar si está guardando conversaciones correctamente
   - ❓ Confirmar integración con SupervisorAgent
   
2. **LLM Access to Memory**
   - ❓ LLM1 (creative) debe recibir contexto para respuestas apropiadas
   - ❓ LLM2 (refinement) necesita contexto para mantener coherencia
   - ❓ Revisar cómo se pasa memoria en `supervisor_agent.py`
   
3. **Arquitectura Actual vs Deseada**
   - ❓ Redis suficiente para contexto conversacional
   - ❓ ¿Necesidad de RAG completo con embeddings?
   - ❓ ¿Cuántos mensajes de historial mantener?

### Plan de Investigación:
1. **Auditar flujo actual**: UserBot → SupervisorAgent → LLMs
2. **Verificar Redis**: ¿Se guarda y recupera contexto?
3. **Testing**: Conversación multi-mensaje para verificar memoria
4. **Documentar**: Estado actual vs requerimientos

### Impacto Negocio:
- **CRÍTICO**: Sin memoria contextual, conversaciones no son naturales
- **UX**: Usuarios notan que bot "olvida" contexto
- **Engagement**: Puede reducir tiempo de conversación

---

## 📊 ANÁLISIS DE ARQUITECTURA DE MEMORIA

### Estado Actual:
- `UserMemoryManager` existe pero puede no estar integrado correctamente
- Redis está funcionando para colas pero no está claro si para memoria

### Tareas Pendientes:
1. Auditar flujo de memoria actual
2. Verificar integración SupervisorAgent ↔ Memory
3. Implementar tests de continuidad conversacional
4. Documentar arquitectura de memoria actual vs deseada

---

## 💡 MEJORAS UX MENORES

### CTAs Soft sin Links Completos
- Algunos CTAs soft no tienen URL completa
- Decisión: Mantener algunos sutiles, otros con link
- Baja prioridad - funcional actualmente

---

## 🚀 OTRAS MEJORAS FUTURAS

1. **Métricas de Negocio**
   - Dashboard de conversión CTA
   - Análisis de engagement por tipo de respuesta
   
2. **Optimización de Costos**
   - Análisis de cache hits
   - Optimización de prompts para reducir tokens

3. **Calidad de Respuestas**
   - A/B testing de diferentes temperaturas
   - Análisis de rechazos por categoría