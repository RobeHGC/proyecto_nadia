#!/bin/bash

# NADIA System Check Script
# Runs both health check and async issues detection

echo "🔧 Preparando entorno..."
source fix_env.sh > /dev/null 2>&1

echo ""
echo "=================================================================================="
echo "🏥 HEALTH CHECK"
echo "=================================================================================="
python monitoring/health_check.py
HEALTH_RESULT=$?

echo ""
echo "=================================================================================="
echo "🔍 ASYNC/AWAIT ISSUES CHECK"
echo "=================================================================================="
python check_async_issues.py
ASYNC_RESULT=$?

echo ""
echo "=================================================================================="
echo "📋 RESUMEN"
echo "=================================================================================="

if [ $HEALTH_RESULT -eq 0 ] && [ $ASYNC_RESULT -eq 0 ]; then
    echo "✅ Sistema completamente saludable"
    echo "   - Health check: OK"
    echo "   - Async issues: OK"
    exit 0
else
    echo "⚠️  Se detectaron problemas:"
    if [ $HEALTH_RESULT -ne 0 ]; then
        echo "   - Health check: FAILED"
    else
        echo "   - Health check: OK"
    fi
    
    if [ $ASYNC_RESULT -ne 0 ]; then
        echo "   - Async issues: FOUND"
    else
        echo "   - Async issues: OK"
    fi
    exit 1
fi