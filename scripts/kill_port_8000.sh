#!/bin/bash
# Script para liberar el puerto 8000
# Uso: ./kill_port_8000.sh [--force] para detener sin confirmación

FORCE=false
if [ "$1" == "--force" ] || [ "$1" == "-f" ]; then
    FORCE=true
fi

echo "🔍 Buscando procesos en el puerto 8000..."

# En macOS/Linux
PID=$(lsof -ti :8000 2>/dev/null)

if [ -z "$PID" ]; then
    echo "✅ El puerto 8000 está libre"
    exit 0
fi

echo "⚠️  Proceso encontrado: PID $PID"
echo "📋 Información del proceso:"
lsof -i :8000

if [ "$FORCE" = true ]; then
    REPLY="y"
else
    echo ""
    read -p "¿Deseas detener este proceso? (y/n) " -n 1 -r
    echo ""
fi

if [[ $REPLY =~ ^[Yy]$ ]] || [ "$FORCE" = true ]; then
    echo "🛑 Deteniendo proceso $PID..."
    kill -9 $PID 2>/dev/null
    sleep 2
    
    # Verificar que se detuvo
    if lsof -ti :8000 >/dev/null 2>&1; then
        echo "❌ No se pudo detener el proceso. Intenta manualmente:"
        echo "   kill -9 $PID"
        exit 1
    else
        echo "✅ Puerto 8000 liberado correctamente"
        exit 0
    fi
else
    echo "ℹ️  Proceso no detenido. Puedes detenerlo manualmente con:"
    echo "   kill -9 $PID"
    exit 0
fi
