# 🔧 Solución de Problemas Comunes

## ❌ Error: Puerto 8000 ya en uso

### Problema
```
ERROR: [Errno 48] error while attempting to bind on address ('0.0.0.0', 8000): address already in use
```

### Solución 1: Encontrar y detener el proceso

**En macOS/Linux:**
```bash
# Encontrar qué proceso usa el puerto 8000
lsof -ti:8000

# O más detallado
lsof -i:8000

# Detener el proceso (reemplaza PID con el número que aparezca)
kill -9 PID

# O en una línea
kill -9 $(lsof -ti:8000)
```

**En Windows:**
```bash
# Encontrar proceso
netstat -ano | findstr :8000

# Detener proceso (reemplaza PID)
taskkill /PID PID /F
```

### Solución 2: Usar otro puerto

Edita el archivo `.env` o usa variable de entorno:
```bash
# Cambiar puerto de la API
export ARIA_API_PORT=8001

# O editar en código (no recomendado)
```

### Solución 3: Reiniciar completamente

```bash
# Detener todos los procesos Python relacionados
pkill -f "aria api"
pkill -f "uvicorn"

# Esperar unos segundos
sleep 2

# Reiniciar
aria api
```

## ❌ Error: Redis no disponible

### Problema
```
Error conectando a Redis
```

### Solución

**Con Docker:**
```bash
cd docker
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml ps
```

**Verificar Redis:**
```bash
redis-cli ping
# Debe responder: PONG
```

## ❌ Error: No se conecta a Odoo

### Problema
```
Error conectando a Odoo
```

### Solución

1. **Verificar configuración en `.env`:**
   ```bash
   cat .env | grep ODOO
   ```

2. **Verificar conexión:**
   ```bash
   aria check
   ```

3. **Verificar que Odoo esté accesible:**
   ```bash
   curl http://tu-servidor-odoo:8069/web/health
   ```

## ❌ Dashboard no carga datos

### Problema
El dashboard carga pero muestra "Sin datos" o errores.

### Solución

1. **Verificar que la API esté corriendo:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verificar proxy en `dashboard/vite.config.js`:**
   ```javascript
   proxy: {
     '/api': {
       target: 'http://localhost:8000',  // Debe coincidir con tu API
     },
   }
   ```

3. **Revisar consola del navegador (F12):**
   - Busca errores en la pestaña "Console"
   - Verifica errores de red en "Network"

4. **Ejecutar tarea manualmente para generar datos:**
   ```bash
   aria agent run finanzas -t bank_balances
   ```

## ❌ Los clicks no funcionan

### Problema
Los botones y tarjetas no responden al click.

### Solución

1. **Recargar la página:**
   - Ctrl+R (Windows/Linux)
   - Cmd+R (Mac)

2. **Limpiar cache del navegador:**
   - Ctrl+Shift+R (hard reload)
   - O abrir en modo incógnito

3. **Verificar que estés usando la versión más reciente:**
   ```bash
   cd dashboard
   npm run dev
   ```

## ❌ No aparecen conversaciones entre agentes

### Problema
El dashboard de conversaciones está vacío.

### Solución

Las conversaciones aparecen cuando los agentes se comunican. Para generarlas:

```bash
# Ejecutar tarea que genera comunicación
aria agent run finanzas -t cash_flow_projection

# Ejecutar tarea del agente de cobranza (procesa mensajes)
aria agent run cobranza -t check_overdue

# Luego recargar el dashboard y ver "Conversaciones"
```

## ❌ Inventario muestra 0 productos

### Problema
El agente de inventario muestra 0 productos.

### Solución

1. **Verificar que haya productos en Odoo:**
   ```bash
   # Desde Odoo o usando el cliente
   ```

2. **Verificar logs:**
   ```bash
   tail -f logs/aria.log | grep inventario
   ```

3. **Ejecutar tarea manualmente:**
   ```bash
   aria agent run inventario -t check_stock_levels
   ```

## ❌ No se cargan presupuestos

### Problema
Los presupuestos no aparecen o están en 0.

### Solución

1. **Verificar fuente de presupuestos:**
   ```bash
   curl http://localhost:8000/api/finance/budgets
   ```

2. **Configurar manualmente desde dashboard:**
   - Dashboard Financiero → "Configurar Presupuestos"

3. **Verificar módulo de Odoo:**
   - Si tienes `account_budget` instalado, debería cargarse automáticamente

4. **El sistema calculará automáticamente:**
   - Si no hay configuración, calculará desde histórico (últimos 6 meses)

## ❌ Error: Módulo no encontrado

### Problema
```
ModuleNotFoundError: No module named 'X'
```

### Solución

```bash
# Reinstalar dependencias
pip install -e .

# O específicamente
pip install nombre-modulo
```

## ❌ Error: Campo no existe en Odoo

### Problema
```
Campo 'X' no existe en modelo 'Y'
```

### Solución

El sistema ahora valida automáticamente y usa solo campos válidos. Si persiste:

1. **Verificar en Odoo:**
   - Ir a Configuración → Técnico → Base de Datos → Estructura → Modelos
   - Buscar el modelo y verificar campos disponibles

2. **El sistema aprenderá automáticamente:**
   - La próxima vez usará solo campos válidos
   - Revisa logs para ver sugerencias

## 🔍 Comandos de Diagnóstico

```bash
# Ver estado de git
git status

# Ver logs en tiempo real
tail -f logs/aria.log

# Verificar configuración
aria check

# Ver agentes disponibles
aria agent list

# Ver estado de un agente
aria agent status finanzas

# Ejecutar tarea específica
aria agent run finanzas -t bank_balances

# Ver propuestas pendientes
aria proposal list
```

## 📞 Obtener Ayuda

Si el problema persiste:

1. **Revisar logs:**
   ```bash
   tail -100 logs/aria.log
   ```

2. **Verificar configuración:**
   ```bash
   aria check --verbose
   ```

3. **Probar endpoints directamente:**
   ```bash
   curl http://localhost:8000/api/dashboard
   curl http://localhost:8000/api/agents/finanzas/summary
   ```
