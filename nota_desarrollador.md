nota del desarrollador 22/06/2025 18:41 domingo hora de mexico
ya funciona
esto me sale en el api server al "jugar" con los filtros
INFO:     127.0.0.1:43460 - "GET /api/analytics/data?page=1&limit=25&sort_by=customer_status&sort_order=desc&search=&date_from=2025-06-21&date_to=2025-06-22&user_id=7730855562%20&_=1750637208603 HTTP/1.1" 500 Internal Server Error
me salió cuando filtre por customer_status
también al seleccionar la casilla cta filters
también al seleccionar la casilla de "necesita revision"
son los mismos errores: 500 internal server error
no veo la respuesta del LLM2 que se supone que quiero comparar contra la final, pero no se si tenga que aplicar un filtro
solo veo la columna "final bubbles" 
parece que los filtros de date from: y date to: no funcionan ni el de user ID funciona. Les pongo apply y no cambia nada
voy a tratar de exportar: no pasa nada
voy a tratar de "clear all": no pasa nada
revisaré la pestaña analytics: todo parece bien, ssolo veo graficas, ningún botón interactivo.
pesaña de backups: veo el botón create backup pero le hago click y no hace nada
ahora la pestaña management: hago click en "export data" pero nada, no se si los filtros aquí sirvan.
data clean up: presionare el botón de "execute cleanup" 	nada
ahora data integrity: veo una alerta

Missing Database Fields
3 expected fields not found in database
[
  {
    "field": "ai_response_raw",
    "expected_type": "text",
    "required": false
  },
  {
    "field": "ai_response_formatted",
    "expected_type": "text",
    "required": false
  },
  {
    "field": "human_edited_response",
    "expected_type": "text",
    "required": false
  }
]

ahora Data type mismatches:

Data Type Mismatches
2 fields have unexpected data types
[
  {
    "field": "llm1_model",
    "expected_type": "text",
    "actual_type": "character varying"
  },
  {
    "field": "llm2_model",
    "expected_type": "text",
    "actual_type": "character varying"
  }
]

se ve que dice 
Stale Reviews
1 reviews stuck in 'reviewing' state for >24h

Recommendation: Reset these reviews to pending status

veo secciones donde dice issues found, good, active alerts pero no se si sean botones interactivos y debería pasar algo al hacer click
