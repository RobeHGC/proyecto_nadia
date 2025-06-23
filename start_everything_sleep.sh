#!/bin/bash
# 🌙 SCRIPT COMPLETO PARA SLEEP MODE
# Inicia todos los servicios necesarios + sistema de perfección nocturna

echo "🌙 NADIA COMPLETE SLEEP MODE SETUP"
echo "=================================="
echo "🚀 Iniciando todos los servicios necesarios..."
echo ""

# Verificar archivos necesarios
required_files=(".env" ".env.testing" "userbot.py" "api/server.py")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Archivo faltante: $file"
        exit 1
    fi
done

echo "✅ Todos los archivos necesarios encontrados"
echo ""

# Función para limpiar procesos al salir
cleanup() {
    echo ""
    echo "🛑 Deteniendo todos los servicios..."
    
    # Matar procesos por nombre si existen
    pkill -f "python userbot.py" 2>/dev/null
    pkill -f "python api/server.py" 2>/dev/null  
    pkill -f "python dashboard/backend/static_server.py" 2>/dev/null
    pkill -f "automated_e2e_tester.py" 2>/dev/null
    
    echo "✅ Servicios detenidos"
    echo "🌅 ¡Buenos días! Revisa los reportes en ./sleep_reports/"
    exit 0
}

# Configurar trap para cleanup al salir
trap cleanup INT TERM EXIT

echo "🔧 PASO 1: Iniciando servicios principales..."
echo "============================================"

# Configurar PYTHONPATH para que encuentre los módulos
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 1. Iniciar UserBot en background
echo "🤖 Iniciando UserBot..."
PYTHONPATH="$(pwd)" python userbot.py > ./sleep_reports/userbot_$(date +%Y%m%d_%H%M%S).log 2>&1 &
USERBOT_PID=$!
sleep 3

# Verificar que UserBot inició correctamente
if ! kill -0 $USERBOT_PID 2>/dev/null; then
    echo "❌ Error: UserBot no pudo iniciar"
    echo "💡 Revisa el log en ./sleep_reports/"
    exit 1
fi
echo "✅ UserBot iniciado (PID: $USERBOT_PID)"

# 2. Iniciar API Server en background  
echo "🌐 Iniciando API Server..."
PYTHONPATH="$(pwd)" python api/server.py > ./sleep_reports/api_server_$(date +%Y%m%d_%H%M%S).log 2>&1 &
API_PID=$!
sleep 3

# Verificar que API Server inició correctamente
if ! kill -0 $API_PID 2>/dev/null; then
    echo "❌ Error: API Server no pudo iniciar"
    echo "💡 Revisa el log en ./sleep_reports/"
    cleanup
    exit 1
fi
echo "✅ API Server iniciado (PID: $API_PID)"

# 3. Opcional: Static Server para dashboard web
read -p "📊 ¿Iniciar Dashboard Web? (y/n, default: n): " start_dashboard
if [[ $start_dashboard == [yY] ]]; then
    echo "📊 Iniciando Dashboard Web..."
    PYTHONPATH="$(pwd)" python dashboard/backend/static_server.py > ./sleep_reports/dashboard_$(date +%Y%m%d_%H%M%S).log 2>&1 &
    DASHBOARD_PID=$!
    sleep 2
    echo "✅ Dashboard Web iniciado (PID: $DASHBOARD_PID)"
    echo "🌐 Accesible en: http://localhost:3000"
fi

echo ""
echo "⏳ PASO 2: Esperando que servicios se estabilicen..."
echo "================================================="
sleep 10

# Verificar que servicios responden
echo "🔍 Verificando conectividad..."

# Test API Server
if curl -s -f "http://localhost:8000/api/health" > /dev/null 2>&1; then
    echo "✅ API Server responde correctamente"
else
    echo "⚠️ API Server no responde (continuando de todas formas)"
fi

# Test UserBot (verificar que el proceso sigue vivo)
if kill -0 $USERBOT_PID 2>/dev/null; then
    echo "✅ UserBot funcionando correctamente"
else
    echo "❌ UserBot dejó de funcionar"
    cleanup
    exit 1
fi

echo ""
echo "🌙 PASO 3: Iniciando Sistema de Perfección Nocturna..."
echo "===================================================="

# Crear directorio para reportes si no existe
mkdir -p ./sleep_reports

echo "📋 SERVICIOS ACTIVOS:"
echo "   🤖 UserBot (PID: $USERBOT_PID)"
echo "   🌐 API Server (PID: $API_PID)"
if [[ -n $DASHBOARD_PID ]]; then
    echo "   📊 Dashboard (PID: $DASHBOARD_PID)"
fi
echo ""

echo "🎯 CONFIGURACIÓN NOCTURNA:"
echo "   • Tests cada 30 minutos"
echo "   • Auto-reparación habilitada"
echo "   • Objetivos estrictos (98% success)"
echo "   • Monitoreo hasta perfección"
echo ""

echo "💤 PARA DETENER TODO:"
echo "   • Ctrl+C en esta terminal"
echo "   • O cierra la terminal completa"
echo ""

read -p "🚀 ¿Iniciar modo nocturno completo? (y/n): " confirm
if [[ ! $confirm == [yY] && ! $confirm == [yY][eE][sS] ]]; then
    echo "❌ Modo nocturno cancelado"
    cleanup
    exit 0
fi

echo ""
echo "🌙 INICIANDO MODO NOCTURNO COMPLETO..."
echo "===================================="

# Configurar variables para modo nocturno
export PERFECTION_CYCLE_MINUTES=30
export AUTO_FIX_ENABLED=true
export CRITICAL_ALERTS_ENABLED=true
export LOG_LEVEL=INFO

# Timestamp para logs
timestamp=$(date +"%Y%m%d_%H%M%S")
log_file="./sleep_reports/complete_sleep_${timestamp}.log"

echo "📝 Log completo en: $log_file"
echo "🌙 ¡Todos los servicios corriendo! Modo nocturno iniciado..."
echo "💤 Buenas noches - el sistema trabajará por ti"
echo ""

# Ejecutar sistema de perfección nocturna
python -c "
import asyncio
import sys
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - COMPLETE SLEEP - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('$log_file'),
        logging.StreamHandler(sys.stdout)
    ]
)

sys.path.append('.')
from tests.automated_e2e_tester import PerfectionLoop

async def complete_sleep_mode():
    loop = PerfectionLoop()
    
    # Configuración nocturna estricta
    loop.success_rate_target = 0.98
    loop.response_time_target = 8.0  
    loop.cache_hit_rate_target = 0.80
    
    try:
        await loop.initialize()
        
        logging.info('🌙 COMPLETE SLEEP MODE ACTIVADO')
        logging.info('🎯 Todos los servicios corriendo + perfección nocturna')
        logging.info('🔧 Auto-reparación completa habilitada')
        
        cycle = 0
        while True:
            cycle += 1
            logging.info(f'🔄 COMPLETE CYCLE #{cycle} - {datetime.now().strftime(\"%H:%M:%S\")}')
            
            # Suite completa con auto-reparación
            results = await loop.run_perfection_suite()
            fixes = await loop._apply_automatic_fixes()
            
            # Resumen
            metrics = results['overall_metrics']
            logging.info(f'📊 Complete: {metrics[\"success_rate\"]:.1%} | {metrics[\"avg_duration\"]:.1f}s | {metrics[\"avg_cache_ratio\"]:.1%} | Fixes: {fixes}')
            
            # Verificar perfección
            if loop._check_perfection_achieved(results):
                logging.info('🏆 ¡PERFECCIÓN COMPLETA ALCANZADA!')
                loop._generate_final_perfection_report(results)
                logging.info('💤 Monitoreo de mantenimiento cada 2h')
                await asyncio.sleep(7200)
            else:
                await asyncio.sleep(1800)  # 30 min
                
    except KeyboardInterrupt:
        logging.info('🛑 Complete sleep mode interrumpido')
        logging.info(f'📊 Ciclos: {cycle} | Mejoras: {loop.fixes_applied} | Tests: {len(loop.test_results)}')
    except Exception as e:
        logging.error(f'❌ Error: {e}')
    finally:
        if loop.client:
            await loop.client.disconnect()
        logging.info('🌅 Complete sleep mode finalizado')

asyncio.run(complete_sleep_mode())
" 2>&1 | tee -a "$log_file"

# Al terminar, limpiar automáticamente
cleanup