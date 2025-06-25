#!/bin/bash

# NADIA Health Check Script
# Run this periodically to monitor system health

echo "🔧 Preparando entorno..."
source fix_env.sh > /dev/null 2>&1

echo ""
echo "🏥 Ejecutando health check..."
python monitoring/health_check.py

# Store result
HEALTH_RESULT=$?

if [ $HEALTH_RESULT -eq 0 ]; then
    echo ""
    echo "🎉 Sistema saludable - No se requiere acción"
else
    echo ""
    echo "⚠️  Se detectaron problemas - Revisar arriba"
    echo "💡 Sugerencias:"
    echo "   - Si review queue > 50: Revisar dashboard para aprobar mensajes"
    echo "   - Si Redis > 200MB: Considerar limpiar datos antiguos"
    echo "   - Si CPU/RAM alto: Verificar procesos en segundo plano"
fi

exit $HEALTH_RESULT