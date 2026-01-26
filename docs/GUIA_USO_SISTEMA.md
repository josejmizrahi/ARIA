# 🚀 Guía de Uso del Sistema - Cómo Empezar

## 📋 Requisitos Previos

Antes de empezar, asegúrate de tener:

- ✅ Python 3.11+ instalado
- ✅ Node.js 18+ instalado (para el dashboard)
- ✅ Redis corriendo (para almacenamiento de propuestas)
- ✅ Acceso a servidor Odoo configurado
- ✅ Archivo `.env` configurado con tus credenciales

## 🔧 Paso 1: Configuración Inicial

### 1.1 Configurar Variables de Entorno

Copia el archivo de ejemplo y edítalo:

```bash
cp env.example .env
```

Edita `.env` con tus datos:

```env
# Conexión a Odoo
ODOO_URL=http://tu-servidor-odoo:8069
ODOO_DB=nombre_base_datos
ODOO_USER=usuario
ODOO_PASSWORD=contraseña
ODOO_COMPANY_ID=1
ODOO_DEFAULT_CURRENCY=MXN

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram (opcional pero recomendado)
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_ADMIN_CHAT_ID=tu_chat_id

# ARIA Settings
ARIA_ENV=development
ARIA_DEBUG=true
ARIA_LOG_LEVEL=INFO
```

### 1.2 Instalar Dependencias Python

```bash
# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -e .
```

### 1.3 Instalar Dependencias del Dashboard

```bash
cd dashboard
npm install
cd ..
```

### 1.4 Iniciar Redis

```bash
# Con Docker (recomendado)
cd docker
docker-compose -f docker-compose.dev.yml up -d

# Verificar que está corriendo
docker-compose -f docker-compose.dev.yml ps
```

## 🚀 Paso 2: Iniciar el Sistema

Necesitas **2 terminales** abiertas:

### Terminal 1: API Backend

```bash
# Activar entorno virtual si lo creaste
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Iniciar API
aria api

# O si prefieres con scheduler (tareas automáticas):
aria serve
```

Deberías ver algo como:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**La API estará disponible en:** http://localhost:8000

**Documentación API (Swagger):** http://localhost:8000/docs

### Terminal 2: Dashboard Frontend

```bash
cd dashboard
npm run dev
```

Deberías ver algo como:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

**El dashboard estará disponible en:** http://localhost:5173

## 🎯 Paso 3: Acceder al Dashboard

### 3.1 Abrir en el Navegador

Abre tu navegador y ve a:
```
http://localhost:5173
```

### 3.2 Pantalla Principal

Verás el dashboard principal con:

- **KPIs Principales:**
  - Propuestas pendientes
  - Agentes activos
  - Saldo bancario
  - CxC vencidas

- **Tarjetas de Agentes:**
  - Estado de cada agente
  - Métricas principales
  - Click para ver detalles

- **Propuestas Pendientes:**
  - Lista de acciones propuestas
  - Botones para aprobar/rechazar

### 3.3 Dashboard Financiero

Para acceder al dashboard financiero completo:

1. **Opción 1:** Click en la tarjeta "Saldo Bancario" en el dashboard principal
2. **Opción 2:** Navegar directamente (si implementas routing)

El dashboard financiero tiene **5 pestañas**:

#### 📊 Resumen
- Saldo disponible y runway
- Ingresos del mes vs presupuesto
- Pagos próximos y cobranza esperada
- Posición neta

#### 🧮 Ratios
- Margen neto
- Ratio gastos/ingresos
- Liquidez corriente
- Crecimiento de ingresos
- Gráficos de tendencias

#### 🎯 Presupuesto
- Comparativo real vs presupuestado
- Proyecciones al final del mes
- Desviaciones y alertas

#### 📈 Rentabilidad
- Margen de contribución
- Punto de equilibrio
- Gastos por categoría
- Ingresos por producto/servicio

#### 🔮 Proyecciones
- Escenarios optimista, realista y pesimista
- Proyecciones anuales
- Promedios históricos

## ⚙️ Paso 4: Configurar Presupuestos

### Opción 1: Desde el Dashboard (Recomendado)

1. Ve al **Dashboard Financiero**
2. Click en **"Configurar Presupuestos"** (botón arriba a la derecha)
3. Ingresa los valores:
   - Presupuesto mensual de ingresos
   - Presupuesto mensual de gastos
   - Presupuestos por categoría (opcional)
4. Click en **"Guardar"**

Los presupuestos se guardan automáticamente en `logs/budgets.json`

### Opción 2: Desde Odoo

Si tienes el módulo `account_budget` instalado en Odoo:

1. Configura presupuestos normalmente en Odoo
2. El sistema los detectará automáticamente
3. Se usarán sin configuración adicional

### Opción 3: Automático

Si no configuras nada:
- El sistema calculará automáticamente desde histórico (últimos 6 meses)
- Funciona como referencia inicial
- Puedes ajustar después desde el dashboard

## 🔍 Paso 5: Ver Métricas y Análisis

### Desde el Dashboard

1. **Dashboard Principal:**
   - Ve KPIs en tiempo real
   - Estado de agentes
   - Propuestas pendientes

2. **Dashboard Financiero:**
   - Click en diferentes pestañas para ver análisis
   - Los datos se actualizan automáticamente cada minuto

### Desde la API

Puedes consultar directamente la API:

```bash
# Ver presupuestos actuales
curl http://localhost:8000/api/finance/budgets

# Ejecutar análisis de ratios
curl http://localhost:8000/api/finance/ratios

# Ver resumen del agente de finanzas
curl http://localhost:8000/api/agents/finanzas/summary

# Ver todas las métricas financieras
curl http://localhost:8000/api/finance/metrics
```

### Desde Swagger (Interfaz Web)

1. Ve a http://localhost:8000/docs
2. Explora los endpoints disponibles
3. Prueba las llamadas directamente desde el navegador

## 📊 Paso 6: Ejecutar Análisis Manualmente

### Desde la API

```bash
# Ejecutar análisis de ratios
curl -X GET http://localhost:8000/api/finance/ratios

# Ejecutar comparación vs presupuesto
curl -X GET http://localhost:8000/api/finance/budget

# Ejecutar análisis de rentabilidad
curl -X GET http://localhost:8000/api/finance/profitability

# Generar proyecciones anuales
curl -X GET http://localhost:8000/api/finance/forecast
```

### Desde CLI

```bash
# Ejecutar tarea específica del agente de finanzas
aria agent run finanzas -t financial_analysis
aria agent run finanzas -t budget_comparison
aria agent run finanzas -t profitability_analysis

# Ver estado del agente
aria agent status finanzas

# Ver todas las tareas programadas
aria scheduler list
```

## 🔔 Paso 7: Configurar Notificaciones (Opcional)

### Telegram Bot

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram
2. Crea un bot: `/newbot`
3. Copia el token al `.env` como `TELEGRAM_BOT_TOKEN`
4. Envía un mensaje a tu bot
5. Visita: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Busca `"chat":{"id":` y copia el número al `.env` como `TELEGRAM_ADMIN_CHAT_ID`
7. Inicia el bot en otra terminal:

```bash
aria bot
```

Ahora recibirás notificaciones en Telegram cuando:
- Se detecten problemas financieros
- Haya propuestas pendientes
- Se generen reportes automáticos

## 📱 Uso del Dashboard

### Navegación

- **Dashboard Principal:** Vista general de todos los agentes
- **Dashboard Financiero:** Análisis financiero detallado
- **Propuestas:** Lista de acciones pendientes de aprobación

### Acciones Disponibles

1. **Aprobar Propuestas:**
   - Click en el botón verde ✅ en cada propuesta
   - O desde Telegram con `/aprobar <id>`

2. **Rechazar Propuestas:**
   - Click en el botón rojo ⚠️ en cada propuesta
   - O desde Telegram con `/rechazar <id>`

3. **Configurar Presupuestos:**
   - Dashboard Financiero → "Configurar Presupuestos"
   - Ingresa valores y guarda

4. **Ver Detalles:**
   - Click en cualquier tarjeta de agente
   - Explora las diferentes pestañas del dashboard financiero

### Actualización Automática

- El dashboard se actualiza automáticamente cada **30 segundos**
- El dashboard financiero se actualiza cada **1 minuto**
- Puedes forzar actualización con el botón de refresh 🔄

## 🐛 Solución de Problemas

### El dashboard no carga

1. Verifica que la API esté corriendo: http://localhost:8000/health
2. Verifica que el dashboard esté corriendo: http://localhost:5173
3. Revisa la consola del navegador (F12) para errores
4. Verifica que el proxy en `vite.config.js` apunte a `http://localhost:8000`

### No se ven datos

1. Verifica conexión a Odoo: `aria check`
2. Verifica que Redis esté corriendo
3. Ejecuta una tarea manualmente: `aria agent run finanzas -t bank_balances`
4. Revisa los logs en `logs/aria.log`

### Error de conexión a Odoo

1. Verifica credenciales en `.env`
2. Verifica que Odoo esté accesible desde tu máquina
3. Prueba conexión: `aria check --verbose`

### Los presupuestos no se cargan

1. Verifica que tengas datos en Odoo (facturas, pagos)
2. Si usas Odoo Budget: verifica que el módulo esté instalado
3. Si configuraste manualmente: verifica `logs/budgets.json`
4. El sistema calculará automáticamente si no hay configuración

## 📚 Recursos Adicionales

### Documentación

- `docs/COMO_FUNCIONA_SISTEMA_FINANCIERO.md` - Cómo funciona el sistema
- `docs/BASES_PRESUPUESTO.md` - Bases de datos del presupuesto
- `README.md` - Documentación general

### Comandos Útiles

```bash
# Verificar configuración
aria check

# Ver agentes disponibles
aria agent list

# Ver estado de un agente
aria agent status finanzas

# Ejecutar tarea específica
aria agent run finanzas -t cash_flow_projection

# Ver propuestas pendientes
aria proposal list

# Ver logs
tail -f logs/aria.log
```

### URLs Importantes

- **Dashboard:** http://localhost:5173
- **API:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/docs
- **API Docs (ReDoc):** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

## 🎯 Próximos Pasos

1. ✅ Configura tus presupuestos desde el dashboard
2. ✅ Explora las diferentes pestañas del dashboard financiero
3. ✅ Revisa las propuestas pendientes y aprueba/rechaza según corresponda
4. ✅ Configura Telegram para recibir notificaciones
5. ✅ Revisa los análisis automáticos que se ejecutan según horarios

¡El sistema está listo para usar! 🚀
