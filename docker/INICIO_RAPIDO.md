# 🚀 Inicio Rápido con Docker

## Pasos para Ejecutar ARIA con Docker

### 1. Verificar Docker

```bash
# Verificar que Docker está instalado
docker --version
docker-compose --version
```

### 2. Configurar Variables de Entorno

Asegúrate de tener un archivo `.env` en la raíz del proyecto con tus credenciales:

```bash
# Desde la raíz del proyecto
cp env.example .env
# Editar .env con tus credenciales de Odoo
```

### 3. Iniciar ARIA con Docker Compose

```bash
# Ir al directorio docker
cd docker

# Iniciar todos los servicios (Redis, API, Dashboard)
docker-compose -f docker-compose.prod.yml up -d

# Ver logs en tiempo real
docker-compose -f docker-compose.prod.yml logs -f

# Ver solo logs de la API
docker-compose -f docker-compose.prod.yml logs -f api

# Ver solo logs del Dashboard
docker-compose -f docker-compose.prod.yml logs -f dashboard
```

### 4. Verificar que Todo Está Funcionando

```bash
# Ver estado de los contenedores
docker-compose -f docker-compose.prod.yml ps

# Deberías ver algo como:
# NAME                  STATUS          PORTS
# aria-api-prod         Up 30 seconds   0.0.0.0:8000->8000/tcp
# aria-dashboard-prod   Up 30 seconds   0.0.0.0:5173->5173/tcp
# aria-redis-prod       Up 30 seconds   0.0.0.0:6379->6379/tcp
```

### 5. Acceder a la Aplicación

Una vez que los contenedores estén corriendo:

- **Dashboard**: http://localhost:5173
- **API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

## Comandos Útiles

### Detener Servicios
```bash
docker-compose -f docker-compose.prod.yml stop
```

### Detener y Eliminar Contenedores
```bash
docker-compose -f docker-compose.prod.yml down
```

### Reiniciar un Servicio
```bash
docker-compose -f docker-compose.prod.yml restart api
docker-compose -f docker-compose.prod.yml restart dashboard
```

### Reconstruir Imágenes (si cambias código)
```bash
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

### Ver Logs de Errores
```bash
# Ver últimos 100 líneas de logs
docker-compose -f docker-compose.prod.yml logs --tail=100 api

# Ver logs en tiempo real
docker-compose -f docker-compose.prod.yml logs -f api
```

### Entrar al Contenedor (para debugging)
```bash
# Entrar al contenedor de la API
docker exec -it aria-api-prod bash

# Entrar al contenedor del Dashboard
docker exec -it aria-dashboard-prod sh
```

## Solución de Problemas Comunes

### Error: "Port already in use"

Si los puertos 8000 o 5173 ya están en uso:

```bash
# Opción 1: Detener procesos locales
lsof -ti :8000 | xargs kill -9
lsof -ti :5173 | xargs kill -9

# Opción 2: Cambiar puertos en docker-compose.prod.yml
# Editar los puertos en el archivo:
ports:
  - "8001:8000"  # Cambiar 8000 a 8001
  - "5174:5173"  # Cambiar 5173 a 5174
```

### Error: "Cannot connect to Odoo"

1. Verificar que `.env` tenga las credenciales correctas
2. Verificar variables de entorno en el contenedor:
   ```bash
   docker exec aria-api-prod env | grep ODOO
   ```
3. Verificar que el contenedor tenga acceso a internet:
   ```bash
   docker exec aria-api-prod ping -c 3 google.com
   ```

### Error: "Module not found" o "Command not found"

Reconstruir las imágenes:
```bash
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

### Limpiar Todo y Empezar de Nuevo

```bash
# Detener y eliminar contenedores
docker-compose -f docker-compose.prod.yml down -v

# Limpiar imágenes no usadas
docker system prune -a

# Reconstruir y reiniciar
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

## Próximos Pasos

1. **Verificar que la API funciona**: Visita http://localhost:8000/docs
2. **Verificar que el Dashboard funciona**: Visita http://localhost:5173
3. **Revisar logs** si hay problemas: `docker-compose -f docker-compose.prod.yml logs -f`

## Notas Importantes

- Los logs se guardan en `../logs/` (relativo al directorio docker)
- El archivo `.env` se monta como solo lectura en el contenedor
- Redis persiste datos en un volumen Docker
- Los cambios en el código requieren reconstruir las imágenes
