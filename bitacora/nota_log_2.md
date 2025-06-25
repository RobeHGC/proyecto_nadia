Te dire lo que esta pasando. Hay un mensaje de un usuario, anteriormente ya habia aprovado uno y lo coloque sin etiquetas, sin ediciones al mensaje del llm2 porque me pareció bueno, lo mande con calificación de 5 estrellas sin problemas. Luego el usuario contestó mi respuesta, seleccione el mensaje, veo que ahora si me toca editar el mensaje, son 3 burbujas de mensajes, edito la primera, segunda y tercera, le añado 4 etiquetas, CONTENT_REWRITE, TONE_CASUAL, TONE_ENERGY_UP, TONE_LESS_IA, veo que dice prospect asi que lo vuelvo a colocar en LEAD_QUALIFIED como lo habia hecho en el primer mensaje que mando (de hecho este es un error porque el dashboard no refleja el CUSTOMER_STATUS actual y algo me dice que tampoco pasa en el sql. Luego pongo 2 estrellas, y presiono approve and send y acepto lo que dice en la ventana emergente y luego sale el error [object:object]

Se me ha recomendado abordar el problema de la siguiente manera. Si tienes alguna otra sugerencia porfavor dimelo y modifica el plan segun veas las posibilidades)
Actualiza ReviewApprovalRequest en api/server.py:
- Agrega customer_status con validación de valores permitidos
- Agrega ltv_amount con validación de rango
- Asegúrate de que estos campos se procesen en approve_review

En dashboard/frontend/review-interface.js:
1. Cuando se carga un review, debe obtener el customer_status actual del usuario
2. El dropdown debe mostrar el estado real, no siempre "PROSPECT"
3. Agrega una llamada API para obtener el estado actual antes de mostrar el review


En database/models.py, verifica que:
1. La función approve_review actualice el customer_status si se proporciona
2. Haya un método para obtener el customer_status actual de un usuario
3. Se registre el cambio en la tabla customer_status_transitions

Para verificar si el customer_status se está guardando correctamente:
Necesito que agregues logs de depuración en:
1. api/server.py en la función approve_review - imprime el customer_status recibido
2. database/models.py en approve_review - imprime si se está actualizando el customer_status
3. Verifica si existe una función para obtener el customer_status actual de un usuario