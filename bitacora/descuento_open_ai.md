────────────────────────────────────────────────────────────────────────
      ⬇️  GPT-4o-nano  PROMPT-CACHING  PLAYBOOK  (23-jun-2025)  ⬇️
────────────────────────────────────────────────────────────────────────
1.  PREFIJO FIJO  (Stable Prefix)
    • Mínimo 1 024 tokens.  
    • 100 % inmutable: NADA de variables, timestamps ni saltos de línea
      añadidos por linters.  
    • Guárdalo en 1 solo archivo, p. ej.  persona/nadia_v1.md

2.  ORDEN DEL PROMPT  —  ¡Clave!
      [0] system   [prompt]              ←  BLOQUE CACHEADO
      [1] system   reglas_seguridad.md   ←  (opcional) otro bloque fijo
      [2] system   resumen_conv …        ←  dinámico
      [3] user     mensaje_actual        ←  dinámico

3.  PAD HASTA EL UMBRAL  
    Si el prefijo pesa <1 024 t, añade comentarios  `<!-- pad -->` 
    hasta rebasarlo; pagarás solo 25 % de esos tokens vs. 100 % si
    los metes en cada llamada.

4.  DESPLIEGUE SIN SORPRESAS  
    • 1ª llamada tras cambiar el prefijo        → paga completo  
    • Haz un **warm-up** de 1 request canary    → llena la caché  
    • Dirige el resto del tráfico cuando  
      `cached_tokens / prompt_tokens  ≈ 0.75`

5.  MONITORIZACIÓN  
    ```python
    ratio = resp.usage["prompt_tokens_details"]["cached_tokens"] \
            / resp.usage["prompt_tokens"]
    if ratio < 0.7:  alert("cache miss – prefijo cambió o TTL expiró")
    ```
    TTL ~5-60 min sin tráfico; programa un *ping* horario si tu bot
    puede estar ocioso.

6.  PATCHES RÁPIDOS  
    No edites el prefijo: agrega un segundo `system` corto  
    (“Hot-patch: evita ‘babe’ hoy”). Así la clave cacheada sigue viva.

7.  RESÚMENES  ≠  PREFIJO  
    El buffer de Redis (últimos 10-15 turnos) y cualquier resumen
    largo **van después**; pagan precio normal, pero no afectan el
    descuento del bloque fijo.

8.  COSTO RULE-OF-THUMB  
    • 1 024 t cacheados  ⇒  facturan como 256 t  
    • Prefijo de 1 600 t  ⇒  pagas solo 400 t + tokens dinámicos  
    • Vale la pena siempre que reutilices el mismo prefijo ≥2 veces.

────────────────────────────────────────────────────────────────────────
💡  Mantén este archivo versionado (git tag  persona_v1, persona_v2…).
    Cualquier cambio →  nuevo warm-up  →  luego full rollout.
────────────────────────────────────────────────────────────────────────
