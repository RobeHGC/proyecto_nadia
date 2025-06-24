Abordemos este problema con profesionalidad, tomando en cuenta que soy "vibe-coder", no programador y tu eres mi asesor experto en programación y lead development.

Quiero añadir nuevas funcionalidades. Para eso vamos a abrir un nuevo branch con la fecha de hoy 24/06/2025 
Introduzco dudas: 
Preguntas
1. ¿el dashboard cuando muestra el id del usuario hace un request al sql?
2. ¿El dashboard actualmente solo pide el user_id del sql?
    4.1 yo se que pide mas cosas pero el que pide mas cosas es la pagina de "data analytics"

Explicación de problema y propuestas.
2. Noto que el dashboard falla en mostrar el estado actual del CUSTOMER STATUS del mensaje seleccionado en la sección de revisión. A veces no falla pero a veces si
    2.1 ¿el dashboard hace el request al sql para pedir el customer status del usario seleccionado en el dashboard para saber su estado actual?     
3. propuestas: 
    3.1 El dashboard haría un request al sql: pediría el customer status del ultimo mensaje del usuario seleccionado en el dashboard para mostrarlo. 
        3.1.1 asi podríamos mostrar ese "estado" para cambiarlo/ignorarlo desde el dahsboard y mandarlo al sql segun corresponda
            3.1.1.2 esto permitiría que el dashboard muestre actualizaciones que ocurrieron en el ultimo mensaje. Asi mostraría el customer status en "tiempo real" del usuario mediante el ultimo mensaje guardado en el sql.
    3.2 Añadir "badges" a las tarjetas/filas de los mensajes de los usuarios en la sección de "review queue"
        3.2 "statusbadge" junto al userid en cada tarjeta/fila de la sección "review queue" del dashboard que muestre el "customer status" del ultimo mensaje registrado en el sql
        3.3 ¿que tal si añadimos la funcionalidad de ponerle un "nicknamebagde" al lado de userid (o al lado del statusbadge")
            3.3.1 Estoy teniendo dificultades para saber a quien le contesto, ya que solo veo el id de cada tarjeta en el review queue del dashboard 
            3.3.2 Enviar ese nicknamebadge al sql ligado al user_id (como lo hemos hecho con los demas datos) y cada que el ese user_id mande un mensaje y el supervisor lo mande a request y esa respuesta llegue al dashboard, el dashboard solicite al sql el nicknamebadge del ultimo mensaje de ese id para poder mostrar/cambiar el nicknamebadge en en tiempo real. 
5. Tengo otro problema 
    5.1 a veces al finalizar la revisión y hacer el "aproval", se me olvida comentar 
        5.1.1 es importante porque actualmente el bot falla en cosas que hay que comentar y se me olvida ponerlo al hacer click rapido 
            5.1.1.1 Me gustaría tener la opción de ir al data analytics, buscar ese mensaje enviado y poder añadir ese comentario que me faltó.
            5.1.1.2 el problema de poder añadir el comentario en data anylitics es que no estoy seguro de si actualmente muestra comentarios añadidos a las revisiones. 
6. voy al data analytics en la sección de overview donde dice "messages over the last 30 days" y veo en la grafica que dice:
    6.1 en el dia 23/06/2025 hubo 17 mensajes 
        6.1.1 estoy seguro de que ese dato esta mal o al menos es cuestionable
    6.2 el dia 22/06/2025 hubo 77 mensajes
        6.1.1 cuestionable, hay que revisarlo 
    6.3 estoy a 24/06/2025 y no muestra el numero de mensajes que contesté hoy 
    6.4. en la parte de la derecha superior del data analytics dice: "last updated" 12:49:22 pm y podría ser parte del problema 
Espero tu feedback y propuestas