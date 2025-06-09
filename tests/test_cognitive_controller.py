# tests/test_cognitive_controller.py
"""Tests para el Controlador Cognitivo."""
import pytest

from cognition.cognitive_controller import CognitiveController


class TestCognitiveController:
    """Tests para la lógica de enrutamiento del controlador."""

    @pytest.fixture
    def controller(self):
        """Crea una instancia del controlador para tests."""
        return CognitiveController()

    def test_fast_path_commands(self, controller):
        """Verifica que los comandos se enruten a fast_path."""
        fast_commands = [
            "/ayuda",
            "/AYUDA",  # Mayúsculas
            "/help",
            "/start",
            "/stop",
            "/estado",
            "/status",
            "/version",
            "/comandos"
        ]

        for command in fast_commands:
            route = controller.route_message(command)
            assert route == 'fast_path', f"Comando {command} debería ir por fast_path"

    def test_slow_path_conversations(self, controller):
        """Verifica que las conversaciones normales vayan por slow_path."""
        conversations = [
            "Hola, ¿cómo estás?",
            "Me llamo Juan",
            "¿Qué puedes hacer?",
            "Cuéntame un chiste",
            "¿Cuál es el sentido de la vida?",
            "/comando_inexistente",
            "ayuda",  # Sin slash
            ""  # Mensaje vacío
        ]

        for message in conversations:
            route = controller.route_message(message)
            assert route == 'slow_path', f"Mensaje '{message}' debería ir por slow_path"

    def test_whitespace_handling(self, controller):
        """Verifica el manejo correcto de espacios en blanco."""
        # Comandos con espacios
        assert controller.route_message("  /ayuda  ") == 'fast_path'
        assert controller.route_message("/ayuda ") == 'fast_path'
        assert controller.route_message(" /ayuda") == 'fast_path'

        # Comandos con texto adicional van por slow_path
        assert controller.route_message("/ayuda algo más") == 'slow_path'
        assert controller.route_message("/help me please") == 'slow_path'

    def test_add_custom_pattern(self, controller):
        """Verifica que se puedan añadir nuevos patrones."""
        # Añadir patrón personalizado
        controller.add_fast_path_pattern(r'^/custom$')

        # Verificar que funciona
        assert controller.route_message("/custom") == 'fast_path'
        assert controller.route_message("/custom extra") == 'slow_path'

    def test_case_insensitive(self, controller):
        """Verifica que los comandos sean case-insensitive."""
        variations = ["/AYUDA", "/Ayuda", "/aYuDa", "/ayuda"]

        for variant in variations:
            assert controller.route_message(variant) == 'fast_path'
