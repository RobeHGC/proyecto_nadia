entro al dashboard del dataanalytics en la sección donde dice data integrity
veo un "warning" que dice
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

otro que dice en la parte derecha del dashboard de la misma sección
Type Mismatches (2):
llm1_model
Expected: text
Actual: character varying
llm2_model
Expected: text
Actual: character varying

quiero hacer un export del 22/06/2025 a 24/06/2025 (tal vez ese sea el error) y me manda a una pagina en blanco con {"detail":"Not authenticated"}.
ademas veo en la terminal esto:
INFO:     127.0.0.1:33552 - "GET /api/analytics/export?format=csv&date_from=2025-06-22&date_to=2025-06-24 HTTP/1.1" 403 Forbidden

quiero crear el backup pero en la terminal me pide la password y no me la se
Error creating backup: API Error: 500 - {"detail":"Backup error: pg_dump failed: pg_dump: error: connection to server at \"localhost\" (127.0.0.1), port 5432 failed: fe_sendauth: no password supplied\n"}

algo preocupante es que en la sección del data explorer veo la columna user message y a la derecha final bubbles pero no veo el mensaje del LLM2 que es el que voy a usar para futuros entrenamientos. Me da pendiente que en el sql tampoco salga y creo que ese dato de la respuesta del llm2 y la respuesta final (editada por mi) son imperativos para futuros experimentos.