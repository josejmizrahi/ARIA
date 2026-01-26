#!/bin/bash
# Script para ejecutar ARIA con Docker
# Funciona con docker-compose y docker compose

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Iniciando ARIA con Docker...${NC}"

# Detectar si usar docker-compose o docker compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo "✓ Usando docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
    echo "✓ Usando docker compose"
else
    echo -e "${RED}❌ Error: Docker Compose no encontrado${NC}"
    echo "Por favor instala Docker Compose:"
    echo "  - Docker Desktop incluye docker compose"
    echo "  - O instala docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.prod.yml" ]; then
    echo -e "${YELLOW}⚠️  No se encontró docker-compose.prod.yml${NC}"
    echo "Cambiando al directorio docker..."
    cd "$(dirname "$0")" || exit 1
fi

# Verificar que existe el archivo .env en la raíz
if [ ! -f "../.env" ]; then
    echo -e "${YELLOW}⚠️  No se encontró archivo .env${NC}"
    echo "Creando desde env.example..."
    if [ -f "../env.example" ]; then
        cp ../env.example ../.env
        echo -e "${YELLOW}⚠️  Por favor edita ../.env con tus credenciales de Odoo${NC}"
    else
        echo -e "${RED}❌ Error: No se encontró env.example${NC}"
        exit 1
    fi
fi

# Verificar que Docker está corriendo
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Error: Docker no está corriendo${NC}"
    echo "Por favor inicia Docker Desktop o el servicio de Docker"
    exit 1
fi

echo ""
echo -e "${GREEN}📦 Construyendo imágenes...${NC}"
$DOCKER_COMPOSE -f docker-compose.prod.yml build

echo ""
echo -e "${GREEN}🚀 Iniciando servicios...${NC}"
$DOCKER_COMPOSE -f docker-compose.prod.yml up -d

echo ""
echo -e "${GREEN}✅ Servicios iniciados!${NC}"
echo ""
echo "📊 Ver estado:"
echo "   $DOCKER_COMPOSE -f docker-compose.prod.yml ps"
echo ""
echo "📋 Ver logs:"
echo "   $DOCKER_COMPOSE -f docker-compose.prod.yml logs -f"
echo ""
echo "🌐 Acceder a:"
echo "   - Dashboard: http://localhost:5173"
echo "   - API: http://localhost:8000"
echo "   - Docs: http://localhost:8000/docs"
echo ""

# Esperar un momento y mostrar estado
sleep 2
echo -e "${GREEN}Estado de los contenedores:${NC}"
$DOCKER_COMPOSE -f docker-compose.prod.yml ps
