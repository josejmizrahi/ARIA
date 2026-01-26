#!/bin/bash
# Script para construir las imágenes Docker de ARIA

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "🐳 Construyendo imágenes Docker de ARIA..."
echo ""

# Verificar que Docker esté instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker no está instalado"
    echo "   Instala Docker desde: https://docs.docker.com/get-docker/"
    exit 1
fi

# Verificar que docker-compose esté disponible
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "⚠️  Advertencia: docker-compose no encontrado"
    echo "   Intentando construir manualmente..."
    BUILD_MANUAL=true
else
    BUILD_MANUAL=false
fi

# Verificar que existe .env
if [ ! -f .env ]; then
    echo "⚠️  Advertencia: Archivo .env no encontrado"
    echo "   Copiando env.example a .env..."
    cp env.example .env
    echo "   ⚠️  IMPORTANTE: Edita .env con tus credenciales antes de ejecutar"
fi

echo "📦 Construyendo imagen de API..."
docker build -f docker/Dockerfile.api -t aria-api:latest . || {
    echo "❌ Error construyendo imagen de API"
    exit 1
}

echo ""
echo "🎨 Construyendo imagen de Dashboard..."
cd dashboard
docker build -f ../docker/Dockerfile.dashboard -t aria-dashboard:latest . || {
    echo "❌ Error construyendo imagen de Dashboard"
    exit 1
}
cd ..

echo ""
echo "✅ Imágenes construidas exitosamente!"
echo ""
echo "📋 Imágenes disponibles:"
docker images | grep -E "(aria-api|aria-dashboard|REPOSITORY)" | head -3
echo ""
echo "🚀 Para ejecutar con Docker Compose:"
echo "   cd docker"
echo "   docker-compose -f docker-compose.prod.yml up -d"
echo ""
echo "🚀 O ejecutar manualmente:"
echo "   # Redis"
echo "   docker run -d --name aria-redis -p 6379:6379 redis:7-alpine"
echo ""
echo "   # API"
echo "   docker run -d --name aria-api -p 8000:8000 --env-file .env aria-api:latest"
echo ""
echo "   # Dashboard"
echo "   docker run -d --name aria-dashboard -p 5173:5173 -e VITE_API_URL=http://TU_IP:8000 aria-dashboard:latest"
