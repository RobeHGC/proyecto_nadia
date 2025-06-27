# PENDING IMPROVEMENTS - December 21, 2024

## 🔴 HIGH PRIORITY IMPROVEMENTS

### 1. Typing Indicator y Cadencia Natural
**Status**: Not Implemented  
**Priority**: Critical for UX  
**Description**: Agregar typing indicator y delays realistas entre envío de burbujas
**Technical Details**:
- Modificar `_process_approved_messages()` en `userbot.py`
- Agregar `await self.client.action(user_id, 'typing')` antes de cada burbuja
- Implementar delays variables (2-5 segundos) basados en longitud del mensaje
- Cancelar typing antes de enviar cada burbuja

**Impact**: Crítico para realismo de conversación

### 2. Fanvue Link Integration
**Status**: Missing  
**Priority**: Business Critical  
**Description**: Integrar https://www.fanvue.com/nadiagarc en templates de CTA
**Technical Details**:
- Modificar templates en `dashboard/frontend/app.js` ctaTemplates
- Agregar link en CTAs medium y direct
- Asegurar tracking de clicks para métricas

**Impact**: Métrica principal de conversión del negocio

### 3. Quality Score Repositioning
**Status**: Functional but Confusing  
**Priority**: High for User Experience  
**Description**: Clarificar que quality score evalúa humanización de LLM2
**Technical Details**:
- Mover quality score section después de LLM2 bubbles
- Cambiar label a "LLM2 Humanization Quality"
- Agregar tooltip explicativo
- Considerar separar quality scores para LLM1 creativity y LLM2 humanization

**Impact**: Mejora claridad para reviewers humanos

## 🟡 MEDIUM PRIORITY IMPROVEMENTS

### 4. Tag Taxonomy Updates
**Status**: Partially Complete  
**Priority**: Medium  
**Description**: Agregar CONTENT_EMOJI_CUT, remover MORE_CASUAL
**Technical Details**:
- Modificar database/migrations o agregar nueva migración
- Actualizar `edit_taxonomy` table
- Actualizar dashboard para mostrar nuevos tags

### 5. Delete Buttons for Bubbles
**Status**: Missing  
**Priority**: Medium  
**Description**: Agregar botones para eliminar burbujas individuales en editor
**Technical Details**:
- Agregar botón "X" a cada textarea en `renderBubbles()`
- Implementar función `deleteBubble(index)`
- Mantener al menos 1 burbuja obligatoria

### 6. Delete Buttons for CTAs
**Status**: Missing  
**Priority**: Medium  
**Description**: Permitir eliminar CTAs insertados accidentalmente
**Technical Details**:
- Identificar burbujas CTA por clase CSS `cta-bubble`
- Agregar botón delete específico para CTAs
- Limpiar metadata de CTA al eliminar

### 7. Constitution Flagging Display
**Status**: Data Available, UI Missing  
**Priority**: Medium  
**Description**: Mostrar análisis detallado de Constitution en dashboard
**Technical Details**:
- Agregar sección para mostrar `constitution_flags` y `risk_score`
- Color-coding basado en recommendation (approve/review/flag)
- Expandir detalles de por qué fue flaggeado

## 🟢 LOW PRIORITY IMPROVEMENTS

### 8. Gemini Quota Real-time Updates
**Status**: Working but Could Be Better  
**Priority**: Low  
**Description**: Mejorar actualización visual de quota usage
**Technical Details**:
- Verificar si updates en tiempo real funcionan correctamente
- Posible issue con cálculo de tokens pequeños
- Considerar batch updates cada 10-15 mensajes

### 9. Sticky Dashboard Sections
**Status**: Not Implemented  
**Priority**: Low  
**Description**: Hacer que secciones importantes permanezcan visibles al scroll
**Technical Details**:
- Aplicar `position: sticky` a headers de LLM sections
- Mantener action buttons visibles
- Responsive design considerations

### 10. Group Message Filtering
**Status**: Unknown Status  
**Priority**: Low  
**Description**: Verificar que bot solo procesa mensajes privados
**Technical Details**:
- Revisar filtro `lambda e: e.is_private` en userbot.py
- Testing con grupos para confirmar filtrado
- Logs para debugging si recibe mensajes de grupo

## 🔧 TECHNICAL DEBT

### Code Quality Improvements
- Remover console.logs de debug del quality score
- Agregar proper error handling en approved messages worker
- Considerar timeout handling para typing indicators
- Documentar nuevas funciones en código

### Testing Improvements
- Tests para approved messages worker
- Integration tests para typing indicators
- UI tests para nuevos delete buttons

### Performance Optimizations
- Consider message queuing optimization
- Redis connection pooling review
- Database query optimization para customer_status

---

## 📋 IMPLEMENTATION ORDER RECOMMENDATION

1. **Week 1**: Typing indicator + Fanvue link (business critical)
2. **Week 2**: Quality score repositioning + tag updates
3. **Week 3**: Delete buttons + Constitution display
4. **Week 4**: Low priority UI improvements

Esta priorización asegura que los aspectos más críticos para UX y negocio se implementen primero.