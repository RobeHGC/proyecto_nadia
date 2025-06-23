🔍 Descripción del Problema
¿Qué está pasando?
GPT-4o-nano (LLM2) está interpretando el mensaje del LLM1 fuera parte de la conversación, por lo que le contesta al LLM1 como si fuera la persona que hay que devolverle una respuesta en lugar de modificar esa respuesta para humanizarla. 
¿Por qué es crítico?

Los usuarios reciben respuestas sin sentido que no se relacionan con su mensaje
El bot parece "roto" o "loco"
Se pierden tokens y dinero en respuestas inútiles

¿Cuál es el desafío?
Tu sistema usa un StablePrefixManager para mantener un prefijo cacheable y aprovechar el 75% de descuento de OpenAI manteniendo el prefijo menor a 1024 tokens. NO podemos cambiar drásticamente la estructura sin perder este beneficio.

CONTEXTO CRÍTICO: Tenemos un playbook de prompt-caching que explica cómo mantener el 75% de descuento con GPT-4o-nano.

PROBLEMA: GPT-4o-nano está respondiendo a las instrucciones como si fueran conversación porque el prefijo estable no está bien estructurado.

INVESTIGA Y SOLUCIONA:

1. BUSCA EL PREFIJO ACTUAL:
   - Busca en llms/stable_prefix_manager.py el método build_messages_for_cache
   - Identifica cuál es el "prefijo estable" actual (debe ser >1024 tokens)
   - Verifica si está guardado en un archivo como sugiere el playbook (persona/nadia_v1.md)

2. ANALIZA LA ESTRUCTURA ACTUAL:
   Según el playbook, el orden correcto es:
   [0] system [prefijo fijo de >1024 tokens] ← CACHEADO
   [1] system [reglas adicionales] ← opcional
   [2] system [resumen conversación] ← dinámico
   [3] user [mensaje a refinar] ← dinámico

   VERIFICA: ¿Se está respetando este orden?

3. EL PROBLEMA PROBABLE:
   El contenido a refinar (raw_response de LLM1) probablemente se está metiendo DENTRO del prefijo estable en lugar de ir en un mensaje "user" separado.

4. SOLUCIÓN PROPUESTA:
   
   A) Si NO existe un archivo persona/nadia_v1.md, CRÉALO:
   ```markdown
   <!-- STABLE PREFIX FOR GPT-4o-nano - DO NOT MODIFY -->
   You are Nadia, a friendly and flirty 24-year-old woman chatting on Telegram.
   
   YOUR TASK: Refine messages to sound more natural and human-like.
   
   INSTRUCTIONS:
   1. Make responses sound casual and natural
   2. Add 2-3 appropriate emojis naturally
   3. Split into short message bubbles using [GLOBO]
   4. Use American slang and text speak when appropriate
   5. Keep flirty but not over the top
   
   IMPORTANT: You will receive a message to refine. DO NOT respond to it as if it were directed at you. Instead, REFINE it to match the style described above.
   
   <!-- padding to reach 1024 tokens minimum for cache -->
   <!-- pad pad pad pad pad pad pad pad pad pad pad pad -->
   [... agregar más padding hasta alcanzar 1024 tokens ...]

   validar si es buena idea Modificar build_messages_for_cache para usar la estructura correcta:: 
   def build_messages_for_cache(self, user_context, conversation_summary, current_message):
    # Cargar prefijo estable desde archivo
    with open('persona/nadia_v1.md', 'r') as f:
        stable_prefix = f.read()
    
    # Construir mensajes en el orden correcto
    messages = [
        {"role": "system", "content": stable_prefix},  # >1024 tokens, CACHEADO
        {"role": "system", "content": f"Current conversation summary: {conversation_summary}"},  # dinámico
        {"role": "user", "content": f"Please refine this message: {current_message}"}  # dinámico
    ]
    
    # Calcular tokens del prefijo estable
    stable_tokens = len(stable_prefix.split()) * 1.3  # aproximación
    
    return messages, stable_tokens



VERIFICACIÓN POST-CAMBIO:
Agrega logging para monitorear el cache ratio


if hasattr(response, 'usage'):
    cached = response.usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)
    total = response.usage.get('prompt_tokens', 1)
    cache_ratio = cached / total
    logger.info(f"Cache hit ratio: {cache_ratio:.2%}")
    
WARM-UP DESPUÉS DEL CAMBIO:
Según el playbook, después de cambiar el prefijo:

Primera llamada paga completo
Hacer 1 request de prueba antes de dirigir todo el tráfico
Verificar que cache_ratio ≈ 0.75

## 🎯 **Resumen para Claude-code**

1. **El prefijo estable debe ser >1024 tokens e inmutable**
2. **Debe ir en el primer mensaje con role="system"**
3. **El contenido a refinar debe ir en un mensaje separado con role="user"**
4. **Monitorear cache_ratio para confirmar el descuento**