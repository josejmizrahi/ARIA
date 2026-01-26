# 🐳 Docker para ARIA

Guía completa para ejecutar ARIA con Docker.

## 📋 Requisitos Previos

1. **Docker instalado**: https://docs.docker.com/get-docker/
2. **Docker Compose instalado**: Viene con Docker Desktop o instalar por separado
3. **Archivo `.env` configurado** en la raíz del proyecto

## 🚀 Inicio Rápido

### Opción 1: Docker Compose (Recomendado)

```bash
# 1. Ir al directorio docker
cd docker

# 2. Copiar y configurar .env si no existe
cp ../env.example ../.env
# Editar ../.env con tus credenciales

# 3. Iniciar todos los servicios
docker-compose -f docker-compose.prod.yml up -d

# 4. Ver logs
docker-compose -f docker-compose.prod.yml logs -f

# 5. Verificar que estén corriendo
docker-compose -f docker-compose.prod.yml ps
```

### Opción 2: Construir y Ejecutar Manualmente

**Construir imagen de API:**
```bash
cd /ruta/a/ARIA
docker build -f docker/Dockerfile.api -t aria-api:latest .
```

**Construir imagen de Dashboard:**
```bash
cd /ruta/a/ARIA/dashboard
docker build -f ../docker/Dockerfile.dashboard -t aria-dashboard:latest .
```

**Ejecutar contenedores:**
```bash
# Redis
docker run -d --name aria-redis -p 6379:6379 redis:7-alpine

# API
docker run -d --name aria-api \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  aria-api:latest

# Dashboard
docker run -d --name aria-dashboard \
  -p 5173:5173 \
  -e VITE_API_URL=http://TU_IP:8000 \
  aria-dashboard:latest
```

## 🔧 Solución de Problemas

### Error: "Cannot find module" al construir API

**Solución:**
```bash
# Verificar que requirements.txt existe
ls -la requirements.txt

# Verificar que pyproject.toml existe
ls -la pyproject.toml

# Construir con más contexto
docker build -f docker/Dockerfile.api -t aria-api:latest .
```

### Error: "npm ci failed" al construir Dashboard

**Solución:**
```bash
# Usar npm install en lugar de npm ci
# Ya está configurado en el Dockerfile con fallback
```

### Error: "aria: command not found"

**Solución:**
El Dockerfile necesita instalar el paquete en modo editable:
```bash
# Verificar que el Dockerfile tenga:
RUN pip install -e .
```

### Error: "Port already in use"

**Solución:**
```bash
# Cambiar puertos en docker-compose.prod.yml
ports:
  - "8001:8000"  # Cambiar 8000 a 8001
```

### Error: "Cannot connect to Odoo"

**Solución:**
1. Verificar que `.env` tenga las credenciales correctas
2. Verificar que el contenedor tenga acceso a internet
3. Verificar variables de entorno:
   ```bash
   docker exec aria-api-prod env | grep ODOO
   ```

## 📊 Comandos Útiles

```bash
# Ver logs de un servicio
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f dashboard

# Detener servicios
docker-compose -f docker-compose.prod.yml down

# Reiniciar un servicio
docker-compose -f docker-compose.prod.yml restart api

# Ver estado
docker-compose -f docker-compose.prod.yml ps

# Entrar al contenedor
docker exec -it aria-api-prod bash
docker exec -it aria-dashboard-prod sh

# Reconstruir imágenes
docker-compose -f docker-compose.prod.yml build --no-cache

# Limpiar todo
docker-compose -f docker-compose.prod.yml down -v
docker system prune -a
```

## 🌐 Acceso

Una vez iniciado:

- **API**: http://TU_IP:8000
- **Dashboard**: http://TU_IP:5173
- **Docs**: http://TU_IP:8000/docs

## 🔒 Variables de Entorno Necesarias

Asegúrate de tener en `.env`:

```env
ODOO_URL=https://tu-instancia.odoo.com
ODOO_DB=tu_base_datos
ODOO_USER=tu_usuario
ODOO_PASSWORD=tu_contraseña
ODOO_COMPANY_ID=1
REDIS_URL=redis://redis:6379/0
API_URL=http://TU_IP:8000
```
