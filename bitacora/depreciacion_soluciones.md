Qué significan los warnings que ves
Mensaje	Causa	Consecuencia futura
DeprecationWarning: The event_loop fixture provided by pytest-asyncio has been redefined …	A partir de pytest-asyncio 1.0 (mayo 2025) se eliminó el fixture event_loop. Forzar tu propio fixture dejará de funcionar muy pronto.
thinhdanggroup.github.io
Tu suite seguirá pasando ahora, pero al actualizar a pytest-asyncio ≥1.0 dejará de arrancar.
Exception ignored in: StreamWriter.__del__ … RuntimeError: Event loop is closed	Bug introducido en Python 3.11.5. El destructor de StreamWriter imprime la traza si el loop ya está cerrado. Arreglado en 3.11.12.
docs.python.org
Solo “ensucia” la salida; no rompe los tests, pero es ruido y puede ocultar errores reales.

Solución paso a paso
1 Actualiza tus dependencias mínimas
toml
Copiar
Editar
# pyproject.toml
[tool.poetry.dependencies]     # o requirements.txt equivalente
python = ">=3.11.12,<3.12"     # incluye el fix de StreamWriter
pytest = "^8.2.0"
pytest-asyncio = "^1.0.1"       # versión ya sin 'event_loop'
<details> <summary>¿Por qué 1.0.1?</summary>
La rama 1.x estabilizó la API tras la eliminación de event_loop y es la que recibirá parches de aquí en adelante.
thinhdanggroup.github.io

</details>
2 Elimina tu fixture event_loop sobrescrito
diff
Copiar
Editar
-# tests/conftest.py
-@pytest.fixture(scope="session")
-def event_loop():
-    loop = asyncio.new_event_loop()
-    yield loop
-    loop.close()
En casi todos los casos no necesitas nada: llama a
asyncio.get_running_loop() dentro del propio test si te hace falta un
handle explícito.
thinhdanggroup.github.io

3 Configura el scope del loop sin sobrescribir fixtures
Si antes usabas el override solo para usar un loop de módulo o sesión,
cámbialo por el nuevo parámetro loop_scope:

python
Copiar
Editar
import pytest

@pytest.mark.asyncio(loop_scope="module")   # "function" | "class" | "module" | "package" | "session"
async def test_mi_rutina():
    ...
Para fixtures asíncronas:

python
Copiar
Editar
import pytest_asyncio as pa

@pa.fixture(loop_scope="module")
async def recurso_compartido():
    ...
4 Si realmente necesitas un loop distinto (p.ej. uvloop)
python
Copiar
Editar
# conftest.py
import asyncio, pytest

class UvloopPolicy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        import uvloop
        return uvloop.new_event_loop()

@pytest.fixture(scope="session")
def event_loop_policy():          # <-- NUEVO fixture admitido
    return UvloopPolicy()
pytest-asyncio creará los loops adecuados a cada loop_scope usando
esa política.
pytest-asyncio.readthedocs.io

5 Silenciar (o convertir en error) los avisos de depreciación mientras migras
Añade en pytest.ini:

ini
Copiar
Editar
[pytest]
filterwarnings =
    error::DeprecationWarning:pytest_asyncio.*
Así fallarás el CI si accidentalmente reintroduces un patrón obsoleto.

6 El traceback de StreamWriter.__del__
Mejor solución: actualiza a Python 3.11.12 —el bug ya está
parcheado.
docs.python.org

Mitigación temporal (si no puedes actualizar el intérprete):
cierra explícitamente los StreamWriter creados en tus tests:

python
Copiar
Editar
reader, writer = await asyncio.open_connection(...)
try:
    ...
finally:
    writer.close()
    await writer.wait_closed()
Checklist rápido para tu repositorio chatbot_nadia
☐ Sube la versión mínima de Python a 3.11.12.

☐ Actualiza pytest-asyncio a ≥1.0 y elimina cualquiera de estos
patrones:

def event_loop(...): ...

event_loop como argumento de tests/fixtures.

☐ Sustituye overrides de scope por loop_scope=….

☐ Si usas otro loop (uvloop, trio-run), implementa
event_loop_policy.

☐ Activa filterwarnings = error para no volver a introducir código
obsoleto.

☐ Confirma que tus tests siguen pasando sin warnings.

Con estos cambios te adelantas a las deprecaciones y tendrás una base
sólida para futuras versiones de pytest-asyncio y Python.