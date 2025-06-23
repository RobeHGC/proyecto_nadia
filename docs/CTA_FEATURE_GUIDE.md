# 🎯 CTA Feature Guide - NADIA HITL

## 📝 Overview

Esta extensión añade la capacidad de insertar CTAs (Call-to-Action) manualmente durante el proceso de revisión humana, sin modificar la lógica core del sistema HITL.

## 🚀 Quick Start

### 1. Aplicar Migración de Base de Datos

```bash
# Ejecutar la migración para añadir soporte CTA
psql -d nadia_hitl -f database/migrations/add_cta_support.sql
```

### 2. Usar el Dashboard

1. **Abrir dashboard**: `http://localhost:3000`
2. **Seleccionar mensaje** de la cola de revisión
3. **Insertar CTA** usando los botones:
   - 💬 **Soft CTA**: CTAs suaves/indirectos
   - 👀 **Medium CTA**: CTAs medios/sugestivos  
   - 🔥 **Direct CTA**: CTAs directos
4. **Editar si necesario** el texto del CTA
5. **Aprobar** normalmente

## 🎨 CTA Templates

### Soft CTAs (💬)
- "btw tengo unas fotos que no puedo mandar aquí 🙈"
- "ojalá pudiéramos hablar en otro lado más privado..."
- "me da penita mandarte ciertas cositas por aquí 😳"

### Medium CTAs (👀)
- "tengo contenido exclusivo en otro lado 👀"
- "si quieres ver más de mí ya sabes dónde 😏"
- "hay cositas que solo muestro en privado 🤫"

### Direct CTAs (🔥)
- "pásate a mi Fanvue para más contenido 💕"
- "link en mi bio para cositas exclusivas 🔥"
- "sígueme para contenido que no puedo subir aquí 🔞"

## 🗄️ Datos Almacenados

Cuando se inserta un CTA, se guarda automáticamente:

```json
{
  "inserted": true,
  "type": "soft|medium|direct",
  "conversation_depth": 1,
  "timestamp": "2025-06-20T10:00:00Z",
  "tags": ["CTA_SOFT"]
}
```

## 📊 Analytics Disponibles

```python
from analytics.cta_analytics import CTAAnalytics

# Métricas básicas
metrics = await CTAAnalytics.get_cta_metrics(db_conn)

# Análisis de calidad
quality = await CTAAnalytics.get_cta_quality_analysis(db_conn)

# Exportar datos de entrenamiento
training_data = await CTAAnalytics.export_cta_training_data(db_conn)
```

## 🏷️ Tags Automáticos

Cuando se inserta un CTA, se añaden automáticamente estos tags:

- `CTA_SOFT` - Para CTAs suaves
- `CTA_MEDIUM` - Para CTAs medios
- `CTA_DIRECT` - Para CTAs directos

## 🎯 Testing

Para probar la funcionalidad:

1. **Enviar mensaje** al bot de prueba
2. **Abrir dashboard** y seleccionar el mensaje
3. **Click en botón CTA** deseado
4. **Verificar** que aparece la burbuja con borde rojo
5. **Aprobar** y verificar confirmación
6. **Verificar en BD** que `cta_data` se guardó correctamente

## 🔍 Monitoring

### Query útiles para monitoring:

```sql
-- CTAs insertados hoy
SELECT 
    cta_data->>'type' as type,
    COUNT(*) as count
FROM interactions 
WHERE cta_data IS NOT NULL 
  AND DATE(created_at) = CURRENT_DATE
GROUP BY 1;

-- Calidad promedio por tipo de CTA
SELECT 
    cta_data->>'type' as cta_type,
    AVG(quality_score) as avg_quality
FROM interactions 
WHERE cta_data IS NOT NULL
GROUP BY 1;

-- CTAs vs no-CTAs (tiempo de revisión)
SELECT 
    CASE WHEN cta_data IS NOT NULL THEN 'with_cta' ELSE 'without_cta' END,
    AVG(review_time_seconds) as avg_time
FROM interactions 
WHERE review_status = 'approved'
GROUP BY 1;
```

## ⚠️ Notas Importantes

1. **No rompe funcionalidad existente** - Todo el flujo HITL sigue funcionando igual
2. **CTA es opcional** - Se puede revisar sin insertar CTAs
3. **Visual feedback** - Las burbujas CTA tienen borde rojo distintivo
4. **Datos para entrenamiento** - Todo se almacena para análisis posterior
5. **Templates editables** - Se puede modificar el texto del CTA después de insertarlo

## 🐛 Troubleshooting

### CTA no se guarda
- Verificar que la migración se aplicó correctamente
- Verificar logs del API server
- Verificar que el tag `CTA_*` está en edit_tags

### Botones no responden
- Verificar que JavaScript se cargó correctamente
- Verificar console del browser para errores
- Verificar que dashboard variable está inicializada

### Templates no aparecen
- Verificar que ctaTemplates está definido en HITLDashboard constructor
- Verificar que tipo de CTA es válido (soft/medium/direct)

## 📈 Future Enhancements

- [ ] CTAs contextuales basados en el contenido del mensaje
- [ ] A/B testing de templates
- [ ] Métricas de conversion (cuando tengamos datos de outcome)
- [ ] Templates personalizables via dashboard
- [ ] Analytics en tiempo real en el dashboard