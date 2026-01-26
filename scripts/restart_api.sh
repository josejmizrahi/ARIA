#!/bin/bash
# Script para reiniciar la API de ARIA
# Libera el puerto 8000 si está en uso y luego inicia la API

echo "🔄 Reiniciando ARIA API..."

# Primero, intentar liberar el puerto 8000
echo "📌 Verificando puerto 8000..."
PID=$(lsof -ti :8000 2>/dev/null)

if [ -n "$PID" ]; then
    echo "⚠️  Puerto 8000 en uso por proceso $PID"
    echo "🛑 Deteniendo proceso..."
    kill -9 $PID 2>/dev/null
    sleep 2
    
    # Verificar que se detuvo
    if lsof -ti :8000 >/dev/null 2>&1; then
        echo "❌ No se pudo detener el proceso. Intenta manualmente:"
        echo "   kill -9 $PID"
        exit 1
    else
        echo "✅ Puerto 8000 liberado"
    fi
else
    echo "✅ Puerto 8000 está libre"
fi

# Esperar un momento para asegurar que el puerto se liberó completamente
sleep 1

# Iniciar la API
echo ""
echo "🚀 Iniciando ARIA API..."
echo ""

cd /workspace || cd "$(dirname "$0")/.." || exit 1
aria api
