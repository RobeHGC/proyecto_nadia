#!/bin/bash
# 🎯 NADIA PERFECTION SYSTEM LAUNCHER
# Lanzador rápido para el sistema de perfección continua

echo "🎯 NADIA PERFECTION SYSTEM LAUNCHER"
echo "=================================="

# Verificar que estamos en el directorio correcto
if [ ! -f "userbot.py" ]; then
    echo "❌ Error: No estás en el directorio del proyecto NADIA"
    echo "💡 Cambia al directorio: cd /ruta/a/chatbot_nadia"
    exit 1
fi

# Verificar archivo de configuración
if [ ! -f ".env.testing" ]; then
    echo "❌ .env.testing no encontrado"
    echo "🔧 Ejecuta primero: python setup_perfection_loop.py"
    echo "📋 O copia .env.testing.example a .env.testing y configúralo"
    exit 1
fi

# Verificar dependencias
python -c "import telethon, aiohttp, rich, questionary" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencias faltantes"
    echo "📦 Ejecuta: pip install -r requirements.txt"
    exit 1
fi

echo "✅ Configuración verificada"
echo ""
echo "🚀 Opciones disponibles:"
echo "1. 🔄 Loop de Perfección Continua (Recomendado)"
echo "2. 🖥️ Monitor Visual Interactivo"
echo "3. 🧪 Test Individual Comprensivo"
echo "4. 📊 Suite de Perfección Completa"
echo "5. 🛠️ Configuración y Diagnóstico"

read -p "👉 Elige opción (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🔄 INICIANDO LOOP DE PERFECCIÓN CONTINUA"
        echo "======================================="
        echo "🎯 Objetivo: Alcanzar la perfección absoluta del sistema"
        echo "⏱️ El sistema ejecutará tests automáticos cada 10 minutos"
        echo "🔧 Aplicará mejoras automáticas cuando sea posible"
        echo "📊 Generará reportes de progreso hacia la perfección"
        echo ""
        echo "💡 Tip: Deja esto corriendo en background mientras desarrollas"
        echo "🛑 Para detener: Ctrl+C"
        echo ""
        read -p "🚀 ¿Continuar? (y/n): " confirm
        if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
            python tests/automated_e2e_tester.py
        else
            echo "❌ Operación cancelada"
        fi
        ;;
    2)
        echo ""
        echo "🖥️ INICIANDO MONITOR VISUAL INTERACTIVO"
        echo "======================================"
        echo "📊 Dashboard en tiempo real con métricas visuales"
        echo "🎨 Interface rica con tablas, gráficos y progreso"
        echo "👀 Observa el sistema funcionando en vivo"
        echo ""
        python tests/visual_test_monitor.py
        ;;
    3)
        echo ""
        read -p "📝 Mensaje de prueba: " message
        if [ -z "$message" ]; then
            message="Hello! Test message from perfection system"
        fi
        echo ""
        echo "🧪 EJECUTANDO TEST INDIVIDUAL COMPRENSIVO"
        echo "========================================"
        echo "📝 Mensaje: '$message'"
        echo "🔍 Verificará todo el pipeline E2E"
        echo ""
        python -c "
import asyncio
import sys
sys.path.append('.')
from tests.automated_e2e_tester import PerfectionLoop

async def run():
    try:
        loop = PerfectionLoop()
        await loop.initialize()
        result = await loop.run_comprehensive_test('$message')
        print(f'\\n🎯 Resultado: {result.status.value.upper()}')
        print(f'⏱️ Duración: {result.duration:.2f}s')
        print(f'✅ Pasos exitosos: {sum(result.steps.values())}/{len(result.steps)}')
        if result.errors:
            print(f'❌ Errores: {len(result.errors)}')
        await loop.client.disconnect()
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(run())
"
        ;;
    4)
        echo ""
        echo "📊 EJECUTANDO SUITE DE PERFECCIÓN COMPLETA"
        echo "========================================="
        echo "🧪 Tests múltiples con análisis comprehensivo"
        echo "📈 Métricas detalladas de rendimiento"
        echo "🚨 Detección automática de problemas"
        echo "📄 Reporte completo de perfección"
        echo ""
        python -c "
import asyncio
import sys
sys.path.append('.')
from tests.automated_e2e_tester import PerfectionLoop

async def run():
    try:
        loop = PerfectionLoop()
        await loop.initialize()
        results = await loop.run_perfection_suite()
        metrics = results['overall_metrics']
        print(f'\\n🎯 RESUMEN DE PERFECCIÓN:')
        print(f'✅ Success Rate: {metrics[\"success_rate\"]:.1%}')
        print(f'⏱️ Tiempo Promedio: {metrics[\"avg_duration\"]:.2f}s')
        print(f'💾 Cache Ratio: {metrics[\"avg_cache_ratio\"]:.1%}')
        print(f'🚨 Problemas: {len(results[\"issues_found\"])}')
        await loop.client.disconnect()
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(run())
"
        ;;
    5)
        echo ""
        echo "🛠️ CONFIGURACIÓN Y DIAGNÓSTICO"
        echo "=============================="
        echo ""
        echo "📋 Información del sistema:"
        echo "   • Directorio: $(pwd)"
        echo "   • Python: $(python --version)"
        echo "   • Usuario: $(whoami)"
        echo ""
        
        if [ -f ".env.testing" ]; then
            echo "✅ .env.testing encontrado"
            echo "📱 API ID: $(grep TEST_API_ID .env.testing | cut -d'=' -f2)"
            echo "🤖 Bot objetivo: $(grep TARGET_BOT_USERNAME .env.testing | cut -d'=' -f2)"
            echo "🌐 Dashboard: $(grep DASHBOARD_URL .env.testing | cut -d'=' -f2)"
        else
            echo "❌ .env.testing no encontrado"
        fi
        
        echo ""
        echo "📦 Verificando dependencias:"
        python -c "
import sys
deps = ['telethon', 'aiohttp', 'rich', 'questionary', 'dotenv']
for dep in deps:
    try:
        __import__(dep)
        print(f'   ✅ {dep}')
    except ImportError:
        print(f'   ❌ {dep} - No instalado')
"
        
        echo ""
        echo "📁 Archivos del sistema:"
        files=("tests/automated_e2e_tester.py" "tests/visual_test_monitor.py" "setup_perfection_loop.py")
        for file in "${files[@]}"; do
            if [ -f "$file" ]; then
                echo "   ✅ $file"
            else
                echo "   ❌ $file - No encontrado"
            fi
        done
        
        echo ""
        echo "🔧 Para reconfigurar:"
        echo "   python setup_perfection_loop.py"
        ;;
    *)
        echo "❌ Opción inválida"
        echo "💡 Elige un número del 1 al 5"
        exit 1
        ;;
esac

echo ""
echo "🎯 NADIA Perfection System - Fin de ejecución"