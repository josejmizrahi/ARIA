#!/bin/bash
# Script para iniciar ARIA en modo nube/producción

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "☁️  Iniciando ARIA en modo nube..."
echo ""

# Verificar que existe .env
if [ ! -f .env ]; then
    echo "❌ Error: Archivo .env no encontrado"
    echo "   Copia env.example a .env y configura tus credenciales"
    exit 1
fi

# Cargar variables de entorno
set -a
source .env
set +a

# Verificar variables críticas
if [ -z "$ODOO_URL" ] || [ -z "$ODOO_DB" ] || [ -z "$ODOO_USER" ]; then
    echo "❌ Error: Variables de Odoo no configuradas en .env"
    exit 1
fi

# Obtener IP del servidor
SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")

echo "📋 Configuración:"
echo "   Entorno: ${ARIA_ENV:-production}"
echo "   API: http://${SERVER_IP}:8000"
echo "   Dashboard: http://${SERVER_IP}:5173"
echo ""

# Verificar si Redis está disponible
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis disponible"
    else
        echo "⚠️  Redis no responde. Iniciando Redis con Docker..."
        docker run -d --name aria-redis -p 6379:6379 redis:7-alpine 2>/dev/null || echo "   Redis ya está corriendo o Docker no disponible"
    fi
else
    echo "⚠️  Redis CLI no encontrado. Asegúrate de que Redis esté corriendo."
fi

echo ""
echo "🚀 Iniciando servicios..."
echo ""

# Función para limpiar procesos al salir
cleanup() {
    echo ""
    echo "🛑 Deteniendo servicios..."
    kill $API_PID $DASHBOARD_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Iniciar API
echo "📡 Iniciando API..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi

aria api --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!
echo "   API iniciada (PID: $API_PID)"
echo "   Logs: tail -f logs/api.log"

# Esperar a que la API esté lista
sleep 3

# Iniciar Dashboard
echo "🎨 Iniciando Dashboard..."
cd dashboard

# Configurar API URL si no está configurada
if [ -z "$VITE_API_URL" ]; then
    export VITE_API_URL="http://${SERVER_IP}:8000"
fi

npm run dev -- --host 0.0.0.0 > ../logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "   Dashboard iniciado (PID: $DASHBOARD_PID)"
echo "   Logs: tail -f logs/dashboard.log"

cd ..

echo ""
echo "✅ ARIA está corriendo en modo nube!"
echo ""
echo "📍 Accesos:"
echo "   API:        http://${SERVER_IP}:8000"
echo "   Dashboard: http://${SERVER_IP}:5173"
echo "   Docs:       http://${SERVER_IP}:8000/docs"
echo ""
echo "📊 Ver logs:"
echo "   API:        tail -f logs/api.log"
echo "   Dashboard: tail -f logs/dashboard.log"
echo ""
echo "🛑 Presiona Ctrl+C para detener"
echo ""

# Esperar
wait
