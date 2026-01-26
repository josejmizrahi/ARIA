# Solución: Puerto 8000 en Uso

## Problema
Al intentar iniciar la API de ARIA, aparece el error:
```
ERROR: [Errno 48] error while attempting to bind on address ('0.0.0.0', 8000): address already in use
```

Esto significa que otro proceso está usando el puerto 8000.

## Soluciones Rápidas

### Opción 1: Usar el script automático (Recomendado)

```bash
# Desde el directorio raíz del proyecto
./scripts/restart_api.sh
```

Este script:
- Detecta si el puerto 8000 está en uso
- Detiene el proceso automáticamente
- Inicia la API de ARIA

### Opción 2: Liberar el puerto manualmente

#### En macOS:
```bash
# 1. Encontrar el proceso que usa el puerto 8000
lsof -ti :8000

# 2. Detener el proceso (reemplaza PID con el número que apareció)
kill -9 PID

# 3. Verificar que se detuvo
lsof -ti :8000

# 4. Iniciar la API
aria api
```

#### En Linux:
```bash
# 1. Encontrar el proceso que usa el puerto 8000
sudo lsof -ti :8000
# O alternativamente:
sudo netstat -tlnp | grep :8000

# 2. Detener el proceso
sudo kill -9 PID

# 3. Iniciar la API
aria api
```

### Opción 3: Usar el script de liberación de puerto

```bash
# Con confirmación interactiva
./scripts/kill_port_8000.sh

# Sin confirmación (fuerza)
./scripts/kill_port_8000.sh --force
```

## Verificar Procesos de Python/ARIA

Si sospechas que hay múltiples instancias de la API corriendo:

```bash
# Ver todos los procesos relacionados con ARIA
ps aux | grep -E "(uvicorn|aria|python.*api)" | grep -v grep

# Detener todos los procesos de Python relacionados con ARIA
pkill -f "aria api"
```

## Prevención

Para evitar este problema en el futuro:

1. **Siempre detén la API correctamente**: Usa `Ctrl+C` en la terminal donde está corriendo
2. **Verifica antes de iniciar**: Ejecuta `lsof -ti :8000` para verificar que el puerto está libre
3. **Usa el script de reinicio**: `./scripts/restart_api.sh` maneja todo automáticamente

## Solución Alternativa: Cambiar el Puerto

Si necesitas ejecutar múltiples instancias, puedes cambiar el puerto:

```bash
# Usar puerto 8001 en lugar de 8000
aria api --port 8001
```

O modificar la configuración en `aria/api/app.py` o variables de entorno.
