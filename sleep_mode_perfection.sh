#!/bin/bash
# 🌙 NADIA SLEEP MODE PERFECTION SYSTEM
# Sistema de auto-reparación nocturna - Déjalo corriendo mientras duermes

echo "🌙 NADIA SLEEP MODE PERFECTION SYSTEM"
echo "===================================="
echo "🛠️  Auto-repara bugs de testing humano"
echo "🔄 Loop continuo cada 30 minutos"
echo "🤖 Funciona sin supervisión"
echo "📊 Genera reportes detallados"
echo ""

# Verificar configuración
if [ ! -f ".env.testing" ]; then
    echo "❌ .env.testing no encontrado"
    echo "🔧 Ejecuta: python setup_perfection_loop.py"
    exit 1
fi

echo "✅ Configuración verificada"
echo ""
echo "🌙 MODO NOCTURNO ACTIVADO"
echo "========================"
echo "El sistema funcionará automáticamente mientras duermes:"
echo "• 🔍 Detecta bugs de testing humano"
echo "• 🔧 Aplica reparaciones automáticas"
echo "• 📊 Optimiza cache y rendimiento" 
echo "• 🧹 Limpieza preventiva de sistema"
echo "• 📈 Mejora continua hacia perfección"
echo ""
echo "💤 Para detener: Ctrl+C (o cierra la terminal)"
echo "📄 Reportes se guardan automáticamente"
echo ""

read -p "🚀 ¿Activar modo nocturno? (y/n): " confirm
if [[ ! $confirm == [yY] && ! $confirm == [yY][eE][sS] ]]; then
    echo "❌ Modo nocturno cancelado"
    exit 0
fi

echo ""
echo "🌙 INICIANDO SISTEMA NOCTURNO..."
echo "==============================="

# Configurar variables para modo nocturno
export PERFECTION_CYCLE_MINUTES=30  # Cada 30 minutos
export AUTO_FIX_ENABLED=true        # Habilitar auto-fixes
export CRITICAL_ALERTS_ENABLED=true # Alertas críticas
export LOG_LEVEL=INFO               # Logging informativo

# Crear directorio para reportes nocturnos
mkdir -p ./sleep_reports
timestamp=$(date +"%Y%m%d_%H%M%S")
log_file="./sleep_reports/sleep_perfection_${timestamp}.log"

echo "📝 Log guardándose en: $log_file"
echo "🌙 Sistema nocturno iniciado - ¡Buenas noches!"
echo ""

# Ejecutar en modo nocturno con logging
python -c "
import asyncio
import sys
import os
import logging
from datetime import datetime

# Configurar logging para modo nocturno
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SLEEP MODE - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('$log_file'),
        logging.StreamHandler(sys.stdout)
    ]
)

sys.path.append('.')
from tests.automated_e2e_tester import PerfectionLoop

async def sleep_mode():
    \"\"\"Modo nocturno con auto-reparación.\"\"\"
    loop = PerfectionLoop()
    
    # Configuración nocturna
    loop.success_rate_target = 0.98  # Más estricto en modo nocturno
    loop.response_time_target = 8.0  # Más exigente
    loop.cache_hit_rate_target = 0.80 # Mayor eficiencia
    
    try:
        await loop.initialize()
        
        logging.info('🌙 SLEEP MODE ACTIVADO')
        logging.info('🎯 Objetivos nocturnos más estrictos configurados')
        logging.info('🔧 Auto-reparación habilitada para bugs de testing')
        logging.info('⏰ Ciclos cada 30 minutos hasta alcanzar perfección')
        
        # Loop nocturno (menos verboso, más eficiente)
        cycle = 0
        while True:
            cycle += 1
            logging.info(f'🔄 CICLO NOCTURNO #{cycle} - {datetime.now().strftime(\"%H:%M:%S\")}')
            
            # Ejecutar suite con auto-reparación
            results = await loop.run_perfection_suite()
            
            # Aplicar todas las reparaciones automáticas
            fixes = await loop._apply_automatic_fixes()
            
            # Log resumen del ciclo
            metrics = results['overall_metrics']
            logging.info(f'📊 Success: {metrics[\"success_rate\"]:.1%} | Time: {metrics[\"avg_duration\"]:.1f}s | Cache: {metrics[\"avg_cache_ratio\"]:.1%} | Fixes: {fixes}')
            
            # Verificar si alcanzó perfección
            if loop._check_perfection_achieved(results):
                logging.info('🏆 ¡PERFECCIÓN ALCANZADA EN MODO NOCTURNO!')
                logging.info('✨ Sistema optimizado mientras dormías')
                
                # Generar reporte final nocturno
                loop._generate_final_perfection_report(results)
                
                # En modo nocturno, continuar monitoreando menos frecuentemente
                logging.info('💤 Cambiando a monitoreo de mantenimiento (cada 2 horas)')
                await asyncio.sleep(7200)  # 2 horas
            else:
                # Esperar 30 minutos hasta próximo ciclo
                await asyncio.sleep(1800)  # 30 minutos
                
    except KeyboardInterrupt:
        logging.info('🛑 Sleep mode interrumpido')
        logging.info('📊 Resumen de la noche:')
        logging.info(f'   • Ciclos ejecutados: {cycle}')
        logging.info(f'   • Mejoras aplicadas: {loop.fixes_applied}')
        logging.info(f'   • Tests realizados: {len(loop.test_results)}')
    except Exception as e:
        logging.error(f'❌ Error en sleep mode: {e}')
    finally:
        if loop.client:
            await loop.client.disconnect()
        logging.info('🌅 Sleep mode finalizado - ¡Buenos días!')

# Ejecutar modo nocturno
asyncio.run(sleep_mode())
" 2>&1 | tee -a "$log_file"

echo ""
echo "🌅 SLEEP MODE FINALIZADO"
echo "======================"
echo "📄 Log completo en: $log_file"
echo "📊 Revisa los reportes en: ./sleep_reports/"
echo "🎯 ¡El sistema trabajó toda la noche por ti!"