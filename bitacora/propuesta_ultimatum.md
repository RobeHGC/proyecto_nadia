El sistema debe
1.  USERBOT
    recibe mensajes 
    busca mensajes cada que se inicia
        utiliza el id_user
            utiliza el timestamp del mensaje mas reciente guardado en la base de datos
                compara los nuevos mensajes del chat con el timestamp y si los nuevos mensajes son mas recientes, los acomoda en batch con el id_user para encolarlos con los demas de los otros usuarios.

2. TENER UN CLASIFICADOR EMOCIONAL DE HUGGING FACE 
    clasifica mensajes de usuario 
        positivo
        negativo
        neutral
    clasifica las respuestas de nadia
        positivo
        negativo
        neutral

3. SUPERVISOR
    recibe el mensaje ya clasificado del usuario
    recibe el mensaje del llm 
        directa
        indirectamente
            del agente de coherencia
4. Gestor de memoria 
    RAG
    CAG
    MONGODB
        nombre
    REDIS
        se inyecta los ultimos 30 mensajes por usuario
5. LLM
    recibe prompt, mensaje, recuerdo y estado de animo
        genera respuestas
        genera toolcalls
    recibe json del agente de coherencia 

6. Agente de incertidumbre 
    6.1 evalua salidas de LLM

7. Agente de coherencia
    7.1 evalua salidas de LLM
8. Agente de verificador de coherencia (AVC)
    8.1 recibe la salida json del llm con prompt de coherencia
9. bibliotecas de prompts
    ice_breakers
        atiende user_id no conocidos 
        donde el Agente post memoria dice 
            nadia no tiene memorias de ellos 
        objetivo es conocerlos
    incertidumbre
        usado en el protocolo de incertidumbre
            analiza
            explica
            toolcall al agente de incertidumbre
    prompt de coherencia
    prompt para darse cuenta de inconcistencia y mejorar respuesta


10. Termostato emocional 
    su estado se inyecta a los prompts del LLM
    Se altera por:
        el mensaje del usuario dependiendo de su etiqueta dada por el clasificador
        el mensaje producido por el llm 
        por el "retrieval" en agente post memoria
    alcanza un thresold donde activa prompts de: 
        relajación 
        analisis 
        
11. agente post memoria 
    recibe el "retrieval" del rag
        altera el termostato emocional dependiendo de la etiquetea emocional del recuerdo 
        elige un prompt dependiendo de la etiqueta emocional 

12. constitution
    revisa los mensajes que el supervisor le envíe para darle el visto final
        rebota si no cumple seguridad 
            avisa al supervisor del error 
    

13. dashboard de revisión 
    parecido al actual pero
        revisa respuesta LLM 
        revisa pensamientos


protocolos 
1. protocolo de respuesta 
    recibe mensaje de userbot
    clasificador lo etiqueta 
    se altera el termostato
        (¿por que?)
    supervisor lo manda a memoria
    se evocan recuerdos 
    el agente post memoria (AP) recibe el output de RAG
    El AP solicita un prompt
    La memoria se inyecta prompt 
    LLM usa el prompt y responde
    Agente de coherencia (AC) formatea en json la respuesta del llm para compararla con la lista de actividades (itinerario) de nadia 
    se cambia de prompt a prompt de coherencia
    el llm compara la coherencia y manda una salida [inconcistencia_temporal(IT)/identidad/No_hay] JUNTO CON SUGERENCIA
        Si hay IT 
            el AVC recibe el input y decide 
                cambio de prompt del llm
                (el prompt es para darse cuenta de la inconcistenci)a y crear una mejor respuesta
                    enviar el json 
            


2. protocolo de pensamiento
3. protocolo de incertidumbre
4. protocolo de cuarentena 
5. protocolo de silencio
6. protocolo de proactividad 

Bases de datos
    Redis
    MongoDB
    PostGRESQL
