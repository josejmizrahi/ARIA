#!/bin/bash
# Script para reiniciar el dashboard y limpiar caché

echo "🔄 Reiniciando dashboard de ARIA..."

# Ir al directorio del dashboard
cd "$(dirname "$0")/../dashboard" || exit 1

# Limpiar caché de node_modules/.vite
echo "🧹 Limpiando caché de Vite..."
rm -rf node_modules/.vite
rm -rf dist

# Verificar si hay un proceso corriendo en el puerto 5173
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
    echo "🛑 Deteniendo proceso en puerto 5173..."
    lsof -ti :5173 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Instalar dependencias si es necesario
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependencias..."
    npm install
fi

# Iniciar el servidor de desarrollo
echo "🚀 Iniciando servidor de desarrollo..."
echo ""
echo "✅ Dashboard disponible en: http://localhost:5173"
echo "💡 Presiona Ctrl+C para detener el servidor"
echo ""

npm run dev
