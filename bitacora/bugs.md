Los badges funcionan bien por ahora, posiblemente encuentre bugs al forzar las funcionalidades pero esta pendiente.
Ahora quiero ver otra cosa y es que en la terminal del static server veo esto: INFO:     127.0.0.1:32770 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:45580 - "GET / HTTP/1.1" 200 OK
INFO:     127.0.0.1:45580 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:45586 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:45586 - "GET /index.html HTTP/1.1" 200 OK
INFO:     127.0.0.1:45586 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:47834 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:47842 - "GET /index.html HTTP/1.1" 200 OK
INFO:     127.0.0.1:47842 - "GET /app.js HTTP/1.1" 200 OK
INFO:     127.0.0.1:47842 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:47842 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:37006 - "GET /index.html HTTP/1.1" 200 OK
INFO:     127.0.0.1:37006 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:37006 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:32914 - "GET /index.html HTTP/1.1" 200 OK
INFO:     127.0.0.1:32914 - "GET /api/config HTTP/1.1" 200 OK
INFO:     127.0.0.1:33598 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:53348 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:53348 - "GET /index.html HTTP/1.1" 200 OK
INFO:     127.0.0.1:53348 - "GET /app.js HTTP/1.1" 200 OK
INFO:     127.0.0.1:53348 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found

Ahora ese es un problema
El otro problema es que creo que el customer status cambia, me explico:
    cuando selecciono la tarjeta en el review queue section pone prospect pero si selecciono otra tarjeta (quito la selección y pongo otra) en la tarjeta que habia seleccionado previamente cambia a lead_exhausted 
Actualmente mande mensaje desde dos dispositivos. No se si la manera en que solicita la información los endpoints podría ser la causa de esta confusión
Por otra parte no estoy seguro si el customer status dentro de la sección "review editor" este aplicando la logica que necesita para reflejar el customer_status del: id con el ultimo timestamp guardado de la ultima interaccion. ¿no se si tal vez haya problema en la logica.   



nuevos errores en la consola de chrome:
:8000/edit-taxonomy:1 
            Failed to load resource: net::ERR_CONNECTION_REFUSED
app.js:88  Failed to load edit taxonomy: TypeError: Failed to fetch
    at HITLDashboard.loadEditTaxonomy (app.js:82:36)
    at HITLDashboard.init (app.js:67:20)
