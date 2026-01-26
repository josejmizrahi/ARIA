# 🐳 Comandos Docker para ARIA

## Detectar Versión de Docker Compose

En versiones recientes de Docker, el comando cambió de `docker-compose` a `docker compose` (sin guión).

### Verificar qué versión tienes:

```bash
# Intentar docker-compose (versión antigua)
docker-compose --version

# Intentar docker compose (versión nueva)
docker compose version
```

## Comandos según tu Versión

### Si tienes `docker-compose` (versión antigua):

```bash
cd docker
docker-compose -f docker-compose.prod.yml up -d
docker-compose -f docker-compose.prod.yml logs -f
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml stop
docker-compose -f docker-compose.prod.yml down
```

### Si tienes `docker compose` (versión nueva):

```bash
cd docker
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml stop
docker compose -f docker-compose.prod.yml down
```

## Script Automático (Recomendado)

Usa el script `ejecutar.sh` que detecta automáticamente tu versión:

```bash
cd docker
./ejecutar.sh
```

Este script:
- ✅ Detecta automáticamente si usar `docker-compose` o `docker compose`
- ✅ Verifica que Docker esté corriendo
- ✅ Verifica que exista el archivo `.env`
- ✅ Construye las imágenes
- ✅ Inicia los servicios
- ✅ Muestra el estado

## Solución de Problemas

### Error: "command not found: docker-compose"

**Solución 1**: Usar `docker compose` (sin guión)
```bash
docker compose -f docker-compose.prod.yml up -d
```

**Solución 2**: Instalar docker-compose
```bash
# macOS (con Homebrew)
brew install docker-compose

# Linux
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Error: "Docker daemon is not running"

**Solución**: Iniciar Docker Desktop o el servicio de Docker
```bash
# macOS: Abrir Docker Desktop desde Applications
# Linux:
sudo systemctl start docker
```

### Error: "Cannot connect to the Docker daemon"

**Solución**: Verificar permisos
```bash
# Agregar usuario al grupo docker (Linux)
sudo usermod -aG docker $USER
# Luego cerrar sesión y volver a entrar
```

## Comandos Útiles

### Ver logs en tiempo real
```bash
# Con docker-compose
docker-compose -f docker-compose.prod.yml logs -f

# Con docker compose
docker compose -f docker-compose.prod.yml logs -f

# Solo API
docker compose -f docker-compose.prod.yml logs -f api

# Solo Dashboard
docker compose -f docker-compose.prod.yml logs -f dashboard
```

### Ver estado de contenedores
```bash
docker compose -f docker-compose.prod.yml ps
# O simplemente:
docker ps
```

### Detener servicios
```bash
docker compose -f docker-compose.prod.yml stop
```

### Detener y eliminar contenedores
```bash
docker compose -f docker-compose.prod.yml down
```

### Reconstruir imágenes
```bash
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

### Entrar a un contenedor
```bash
# API
docker exec -it aria-api-prod bash

# Dashboard
docker exec -it aria-dashboard-prod sh
```
