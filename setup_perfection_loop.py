#!/usr/bin/env python3
"""
Script de Configuración para el Sistema de Perfección Continua
Automatiza la instalación y configuración completa del loop de testing
"""
import os
import sys
import subprocess
import shutil
import asyncio
from pathlib import Path
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

class PerfectionSetup:
    """Configurador automático del sistema de perfección."""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.env_testing_file = self.project_root / ".env.testing"
        self.requirements_file = self.project_root / "requirements.txt"
        
    def show_welcome(self):
        """Muestra mensaje de bienvenida."""
        welcome_text = Text()
        welcome_text.append("🎯 NADIA PERFECTION LOOP SETUP\n", style="bold cyan")
        welcome_text.append("Configuración automática del sistema de testing E2E\n", style="white")
        welcome_text.append("con loop de mejora continua hacia la perfección\n", style="dim")
        
        console.print(Panel(
            welcome_text,
            title="🚀 SETUP WIZARD",
            border_style="cyan",
            padding=(1, 2)
        ))
        
    def check_prerequisites(self) -> bool:
        """Verifica prerequisitos del sistema."""
        console.print("\n🔍 Verificando prerequisitos...", style="bold blue")
        
        checks = []
        
        # Python version
        python_version = sys.version_info
        if python_version >= (3, 8):
            checks.append(("✅", "Python 3.8+", f"v{python_version.major}.{python_version.minor}"))
        else:
            checks.append(("❌", "Python 3.8+", f"v{python_version.major}.{python_version.minor} - UPGRADE NEEDED"))
            
        # pip
        try:
            subprocess.run(["pip", "--version"], capture_output=True, check=True)
            checks.append(("✅", "pip", "Available"))
        except:
            checks.append(("❌", "pip", "Not found"))
            
        # git (opcional)
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            checks.append(("✅", "git", "Available"))
        except:
            checks.append(("⚠️", "git", "Not found (optional)"))
            
        # Mostrar resultados
        for status, item, details in checks:
            console.print(f"   {status} {item}: {details}")
            
        failed = any(check[0] == "❌" for check in checks)
        if failed:
            console.print("\n❌ Algunos prerequisitos fallan. Por favor instálalos primero.", style="bold red")
            return False
            
        console.print("\n✅ Todos los prerequisitos verificados", style="bold green")
        return True
        
    async def install_dependencies(self):
        """Instala dependencias necesarias."""
        console.print("\n📦 Instalando dependencias...", style="bold blue")
        
        # Dependencias para testing E2E
        testing_deps = [
            "telethon>=1.24.0",
            "aiohttp>=3.8.0", 
            "rich>=13.0.0",
            "questionary>=1.10.0",
            "python-dotenv>=0.19.0"
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            
            for dep in testing_deps:
                task = progress.add_task(f"Instalando {dep}...", total=None)
                
                try:
                    subprocess.run(
                        ["pip", "install", dep], 
                        capture_output=True, 
                        check=True
                    )
                    progress.update(task, description=f"✅ {dep}")
                except subprocess.CalledProcessError as e:
                    progress.update(task, description=f"❌ {dep} - Error: {e}")
                    console.print(f"⚠️ Error instalando {dep}: {e}", style="yellow")
                    
        console.print("✅ Instalación de dependencias completada", style="bold green")
        
    def setup_environment_file(self):
        """Configura archivo .env.testing."""
        console.print("\n⚙️ Configurando archivo de testing...", style="bold blue")
        
        if self.env_testing_file.exists():
            overwrite = questionary.confirm(
                "📄 .env.testing ya existe. ¿Sobrescribir?",
                default=False
            ).ask()
            
            if not overwrite:
                console.print("⏭️ Omitiendo configuración de .env.testing", style="yellow")
                return
                
        # Recopilar información del usuario
        console.print("\n📋 Necesitamos configurar las credenciales de testing:")
        console.print("   (Obtener en: https://my.telegram.org)", style="dim")
        
        test_api_id = questionary.text(
            "📱 TEST_API_ID:",
            validate=lambda x: x.isdigit() or "Debe ser un número"
        ).ask()
        
        test_api_hash = questionary.text(
            "🔑 TEST_API_HASH:",
            validate=lambda x: len(x) == 32 or "Debe tener 32 caracteres"
        ).ask()
        
        test_phone = questionary.text(
            "📞 TEST_PHONE_NUMBER (formato: +1234567890):",
            validate=lambda x: x.startswith('+') and len(x) > 10 or "Formato: +1234567890"
        ).ask()
        
        target_bot = questionary.text(
            "🤖 TARGET_BOT_USERNAME:",
            default="@nadia_hitl_bot"
        ).ask()
        
        dashboard_url = questionary.text(
            "🌐 DASHBOARD_URL:",
            default="http://localhost:8000"
        ).ask()
        
        dashboard_key = questionary.text(
            "🔐 DASHBOARD_API_KEY:",
            default="miclavesegura45mil"
        ).ask()
        
        # Configuración avanzada opcional
        advanced = questionary.confirm(
            "⚙️ ¿Configurar opciones avanzadas?",
            default=False
        ).ask()
        
        success_target = 0.95
        response_target = 10.0
        cache_target = 0.75
        cycle_minutes = 10
        
        if advanced:
            success_target = float(questionary.text(
                "📊 SUCCESS_RATE_TARGET (0.0-1.0):",
                default="0.95"
            ).ask())
            
            response_target = float(questionary.text(
                "⏱️ RESPONSE_TIME_TARGET (segundos):",
                default="10.0"
            ).ask())
            
            cache_target = float(questionary.text(
                "💾 CACHE_HIT_RATE_TARGET (0.0-1.0):",
                default="0.75"
            ).ask())
            
            cycle_minutes = int(questionary.text(
                "🔄 PERFECTION_CYCLE_MINUTES:",
                default="10"
            ).ask())
            
        # Crear archivo .env.testing
        env_content = f"""# CONFIGURACIÓN DE TESTING E2E AUTOMATIZADO
# Generado automáticamente por setup_perfection_loop.py

# =============================================
# CREDENCIALES DEL CELULAR DE TESTING
# =============================================
TEST_API_ID={test_api_id}
TEST_API_HASH={test_api_hash}
TEST_PHONE_NUMBER={test_phone}

# =============================================
# CONFIGURACIÓN DEL SISTEMA DE TESTING
# =============================================
TARGET_BOT_USERNAME={target_bot}
DASHBOARD_URL={dashboard_url}
DASHBOARD_API_KEY={dashboard_key}

# =============================================
# CONFIGURACIÓN AVANZADA DE PERFECCIÓN
# =============================================
SUCCESS_RATE_TARGET={success_target}
RESPONSE_TIME_TARGET={response_target}
CACHE_HIT_RATE_TARGET={cache_target}
PERFECTION_CYCLE_MINUTES={cycle_minutes}
AUTO_FIX_ENABLED=true
CRITICAL_ALERTS_ENABLED=true

# =============================================
# CONFIGURACIÓN DE SEGURIDAD
# =============================================
NETWORK_TIMEOUT=30
MAX_RETRIES=5
TEST_INTERVAL=3
LOG_LEVEL=INFO
TELEGRAM_DEBUG=false
SAVE_SESSIONS=false

# =============================================
# CONFIGURACIÓN DE REPORTES
# =============================================
REPORTS_DIR=./perfection_reports
REPORTS_RETENTION_DAYS=30
REPORT_FORMAT=json
"""
        
        # Escribir archivo
        with open(self.env_testing_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
            
        # Configurar permisos seguros
        os.chmod(self.env_testing_file, 0o600)
        
        console.print(f"✅ Archivo .env.testing creado con permisos seguros", style="bold green")
        
    def setup_gitignore(self):
        """Configura .gitignore para seguridad."""
        console.print("\n🔒 Configurando .gitignore...", style="bold blue")
        
        gitignore_file = self.project_root / ".gitignore"
        
        # Entradas de seguridad para testing
        security_entries = [
            "# Testing E2E Security",
            ".env.testing",
            "*.session",
            "*.session-journal", 
            "perfection_reports/",
            "test_*.log",
            "testing_temp_*"
        ]
        
        if gitignore_file.exists():
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Verificar si ya tiene las entradas
            if ".env.testing" not in content:
                with open(gitignore_file, 'a', encoding='utf-8') as f:
                    f.write("\n\n" + "\n".join(security_entries) + "\n")
                console.print("✅ Entradas de seguridad añadidas a .gitignore", style="green")
            else:
                console.print("✅ .gitignore ya tiene configuración de seguridad", style="green")
        else:
            with open(gitignore_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(security_entries) + "\n")
            console.print("✅ .gitignore creado con configuración de seguridad", style="green")
            
    def create_directories(self):
        """Crea directorios necesarios."""
        console.print("\n📁 Creando directorios...", style="bold blue")
        
        directories = [
            "perfection_reports",
            "tests/logs",
            "tests/temp"
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            console.print(f"✅ {directory}/", style="green")
            
    def setup_launcher_script(self):
        """Crea scripts de lanzamiento convenientes."""
        console.print("\n🚀 Creando scripts de lanzamiento...", style="bold blue")
        
        # Script para launcher rápido
        launcher_content = '''#!/bin/bash
# Launcher para Sistema de Perfección NADIA

echo "🎯 NADIA PERFECTION SYSTEM LAUNCHER"
echo "=================================="

# Verificar archivo de configuración
if [ ! -f ".env.testing" ]; then
    echo "❌ .env.testing no encontrado"
    echo "🔧 Ejecuta: python setup_perfection_loop.py"
    exit 1
fi

echo "🚀 Opciones disponibles:"
echo "1. 🔄 Loop de Perfección Continua"
echo "2. 🖥️ Monitor Visual"
echo "3. 🧪 Test Individual"
echo "4. 📊 Solo Métricas"

read -p "Elige opción (1-4): " choice

case $choice in
    1)
        echo "🔄 Iniciando Loop de Perfección..."
        python tests/automated_e2e_tester.py
        ;;
    2)
        echo "🖥️ Iniciando Monitor Visual..."
        python tests/visual_test_monitor.py
        ;;
    3)
        read -p "📝 Mensaje de prueba: " message
        echo "🧪 Ejecutando test individual..."
        python -c "
import asyncio
from tests.automated_e2e_tester import PerfectionLoop
async def run():
    loop = PerfectionLoop()
    await loop.initialize()
    await loop.run_comprehensive_test('$message')
asyncio.run(run())
"
        ;;
    4)
        echo "📊 Mostrando métricas..."
        python -c "
import asyncio
from tests.visual_test_monitor import VisualPerfectionMonitor
async def run():
    monitor = VisualPerfectionMonitor()
    if await monitor.initialize():
        await monitor.update_data()
        print(f'Métricas: {monitor.current_metrics}')
asyncio.run(run())
"
        ;;
    *)
        echo "❌ Opción inválida"
        exit 1
        ;;
esac
'''
        
        launcher_file = self.project_root / "start_perfection.sh"
        with open(launcher_file, 'w', encoding='utf-8') as f:
            f.write(launcher_content)
            
        # Hacer ejecutable
        os.chmod(launcher_file, 0o755)
        
        console.print("✅ start_perfection.sh creado", style="green")
        
    def run_verification_test(self):
        """Ejecuta test de verificación básico."""
        console.print("\n🧪 Ejecutando test de verificación...", style="bold blue")
        
        # Test básico de importaciones
        try:
            console.print("📦 Verificando importaciones...", style="blue")
            
            # Test imports
            import telethon
            import aiohttp
            import rich
            import dotenv
            
            console.print("✅ Todas las importaciones exitosas", style="green")
            
            # Verificar archivos
            required_files = [
                "tests/automated_e2e_tester.py",
                "tests/visual_test_monitor.py",
                ".env.testing"
            ]
            
            for file_path in required_files:
                if (self.project_root / file_path).exists():
                    console.print(f"✅ {file_path}", style="green")
                else:
                    console.print(f"❌ {file_path} - No encontrado", style="red")
                    
            console.print("\n🎉 Verificación completada exitosamente!", style="bold green")
            
        except ImportError as e:
            console.print(f"❌ Error de importación: {e}", style="bold red")
            console.print("💡 Intenta: pip install -r requirements.txt", style="yellow")
            
    def show_completion_summary(self):
        """Muestra resumen de finalización."""
        summary_text = Text()
        summary_text.append("🎉 CONFIGURACIÓN COMPLETADA\n\n", style="bold green")
        summary_text.append("📁 Archivos creados:\n", style="bold white")
        summary_text.append("   • .env.testing (credenciales seguras)\n", style="white")
        summary_text.append("   • tests/automated_e2e_tester.py\n", style="white") 
        summary_text.append("   • tests/visual_test_monitor.py\n", style="white")
        summary_text.append("   • start_perfection.sh (launcher)\n", style="white")
        summary_text.append("   • perfection_reports/ (directorio)\n\n", style="white")
        
        summary_text.append("🚀 Para iniciar:\n", style="bold cyan")
        summary_text.append("   ./start_perfection.sh\n", style="cyan")
        summary_text.append("   O: python tests/automated_e2e_tester.py\n\n", style="cyan")
        
        summary_text.append("🎯 Loop de Perfección:\n", style="bold yellow")
        summary_text.append("   • Tests automáticos E2E\n", style="white")
        summary_text.append("   • Detección de problemas\n", style="white")
        summary_text.append("   • Mejoras automáticas\n", style="white")
        summary_text.append("   • Visualización en tiempo real\n", style="white")
        summary_text.append("   • Reportes de perfección\n", style="white")
        
        console.print(Panel(
            summary_text,
            title="✨ SETUP COMPLETADO",
            border_style="green",
            padding=(1, 2)
        ))

async def main():
    """Función principal del setup."""
    setup = PerfectionSetup()
    
    try:
        # Mostrar bienvenida
        setup.show_welcome()
        
        # Verificar prerequisitos
        if not setup.check_prerequisites():
            return 1
            
        # Preguntar si continuar
        if not questionary.confirm("¿Continuar con la configuración?", default=True).ask():
            console.print("❌ Configuración cancelada", style="yellow")
            return 0
            
        # Ejecutar pasos de configuración
        await setup.install_dependencies()
        setup.setup_environment_file()
        setup.setup_gitignore()
        setup.create_directories()
        setup.setup_launcher_script()
        
        # Verificación final
        setup.run_verification_test()
        
        # Mostrar resumen
        setup.show_completion_summary()
        
        console.print("\n🎯 ¡Sistema de Perfección listo para usar!", style="bold green")
        return 0
        
    except KeyboardInterrupt:
        console.print("\n❌ Configuración interrumpida", style="yellow")
        return 1
    except Exception as e:
        console.print(f"\n❌ Error durante configuración: {e}", style="bold red")
        return 1

if __name__ == "__main__":
    try:
        import questionary
        import rich
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except ImportError as e:
        print(f"❌ Dependencia faltante: {e}")
        print("💡 Instalar con: pip install questionary rich")
        sys.exit(1)