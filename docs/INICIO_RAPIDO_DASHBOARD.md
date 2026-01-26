# 🚀 Inicio Rápido - Ver Nuevas Funcionalidades en el Dashboard

## 📋 Requisitos Previos

Asegúrate de tener:
- ✅ Python 3.11+ instalado
- ✅ Node.js 18+ instalado
- ✅ Redis corriendo
- ✅ Odoo accesible y configurado en `.env`

## 🔧 Paso 1: Instalar Dependencias

### Backend (Python)

```bash
# Si no lo has hecho ya
pip install -e .

# O si tienes entorno virtual
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows
pip install -e .
```

### Frontend (Dashboard)

```bash
cd dashboard
npm install
cd ..
```

## 🚀 Paso 2: Iniciar el Sistema

Necesitas **2 terminales** abiertas:

### Terminal 1: API Backend

```bash
# Desde la raíz del proyecto
aria api

# O si prefieres con scheduler (tareas automáticas):
aria serve
```

**Deberías ver:**
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ **API disponible en:** http://localhost:8000

### Terminal 2: Dashboard Frontend

```bash
cd dashboard
npm run dev
```

**Deberías ver:**
```
VITE v5.x.x  ready in xxx ms
➜  Local:   http://localhost:5173/
```

✅ **Dashboard disponible en:** http://localhost:5173

## 🎯 Paso 3: Acceder al Dashboard

1. **Abre tu navegador** en: http://localhost:5173

2. **Verás el Dashboard Principal** con:
   - KPIs en tiempo real
   - Tarjetas de agentes
   - Propuestas pendientes
   - Selector de empresa (si hay múltiples)

## 🆕 Nuevas Funcionalidades Disponibles

### 1. Dashboard Financiero Completo

**Cómo acceder:**
- Click en la tarjeta **"Saldo Bancario"** en el dashboard principal
- O click en cualquier tarjeta del agente **"finanzas"**

**Qué verás:**
- **5 pestañas** con análisis financiero completo:
  1. **Resumen**: KPIs, saldos por divisa, saldos por cuenta bancaria
  2. **Ratios**: Margen neto, liquidez, crecimiento
  3. **Presupuesto**: Comparativo real vs presupuestado
  4. **Rentabilidad**: Márgenes, punto de equilibrio, gastos por categoría
  5. **Proyecciones**: Escenarios optimista, realista y pesimista

### 2. Saldos Bancarios Detallados

**En el Dashboard Financiero → Pestaña "Resumen":**

Verás:
- **Saldos por Divisa**: MXN, USD, EUR, etc.
- **Saldos por Cuenta Bancaria**: Detalle de cada cuenta con su saldo

### 3. Configurar Presupuestos

**En el Dashboard Financiero:**

1. Click en **"Configurar Presupuestos"** (botón arriba a la derecha)
2. Ingresa:
   - Presupuesto mensual de ingresos
   - Presupuesto mensual de gastos
   - Presupuestos por categoría (opcional)
3. Click en **"Guardar"**

Los presupuestos se guardan automáticamente y el sistema los usa.

### 4. Conversaciones entre Agentes

**Cómo acceder:**
- Click en botón **"Conversaciones"** (arriba a la derecha del dashboard principal)

**Qué verás:**
- Todas las conversaciones entre agentes
- Mensajes individuales con detalles
- Respuestas y colaboraciones
- Filtros por agente

**Ejemplo de conversación:**
```
Finanzas → Cobranza: "Consulta: Proyección de cobranza para 4 semanas"
Cobranza → Finanzas: "Proyección: $2,500,000"
```

### 5. Selector de Empresa (Multiempresa)

Si tienes múltiples empresas en Odoo:
- Aparece automáticamente un **selector** en el header
- Al cambiar de empresa, los datos se recargan automáticamente
- Todos los agentes filtran por la empresa seleccionada

## 🔍 Verificar que Todo Funciona

### 1. Verificar API

Abre en tu navegador:
- http://localhost:8000/health - Debe responder "healthy"
- http://localhost:8000/docs - Documentación interactiva de la API

### 2. Verificar Dashboard

- http://localhost:5173 - Debe cargar sin errores
- Revisa la consola del navegador (F12) por errores

### 3. Probar Funcionalidades

#### Probar Saldos Bancarios:

1. Ve al Dashboard Financiero
2. Pestaña "Resumen"
3. Deberías ver:
   - Saldos por divisa
   - Saldos por cuenta bancaria

#### Probar Conversaciones:

1. Ejecuta una tarea que genere comunicación:
   ```bash
   aria agent run finanzas -t cash_flow_projection
   ```

2. Ve a "Conversaciones" en el dashboard
3. Deberías ver mensajes entre agentes

#### Probar Configuración de Presupuestos:

1. Dashboard Financiero → "Configurar Presupuestos"
2. Ingresa valores y guarda
3. Ve a pestaña "Presupuesto"
4. Deberías ver tus presupuestos configurados

## 🐛 Solución de Problemas

### El dashboard no carga

1. Verifica que la API esté corriendo:
   ```bash
   curl http://localhost:8000/health
   ```

2. Verifica que el dashboard esté corriendo:
   ```bash
   # Debería estar en http://localhost:5173
   ```

3. Revisa la consola del navegador (F12) para errores

### No se ven datos

1. Verifica conexión a Odoo:
   ```bash
   aria check
   ```

2. Verifica que Redis esté corriendo:
   ```bash
   redis-cli ping
   # Debe responder: PONG
   ```

3. Ejecuta una tarea manualmente:
   ```bash
   aria agent run finanzas -t bank_balances
   ```

### Los clicks no funcionan

1. Recarga la página (Ctrl+R o Cmd+R)
2. Verifica que estés usando la versión más reciente del código
3. Limpia cache del navegador si es necesario

### No aparecen conversaciones

Las conversaciones aparecen cuando:
- Los agentes se comunican entre sí
- Ejecutas tareas que generan comunicación

Para generar conversaciones:
```bash
# Ejecutar proyección de flujo de caja (genera comunicación)
aria agent run finanzas -t cash_flow_projection

# Ejecutar análisis de cobranza (procesa mensajes)
aria agent run cobranza -t check_overdue
```

## 📊 URLs Importantes

- **Dashboard Principal:** http://localhost:5173
- **Dashboard Financiero:** Click en "Saldo Bancario" desde el principal
- **Conversaciones:** Click en "Conversaciones" desde el principal
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

## 🎯 Checklist de Verificación

- [ ] API corriendo en puerto 8000
- [ ] Dashboard corriendo en puerto 5173
- [ ] Puedo ver el dashboard principal
- [ ] Puedo hacer click en "Saldo Bancario" y ver dashboard financiero
- [ ] Veo saldos por divisa en el dashboard financiero
- [ ] Veo saldos por cuenta bancaria
- [ ] Puedo configurar presupuestos
- [ ] Puedo ver conversaciones (después de ejecutar tareas)
- [ ] Selector de empresa aparece (si hay múltiples empresas)
- [ ] Los datos se actualizan automáticamente

## 🚀 Próximos Pasos

1. **Explora el Dashboard Financiero:**
   - Ve todas las pestañas
   - Configura tus presupuestos
   - Revisa los análisis

2. **Genera Conversaciones:**
   - Ejecuta tareas que generen comunicación entre agentes
   - Observa cómo colaboran

3. **Configura Notificaciones:**
   - Configura Telegram para recibir alertas
   - Los agentes te notificarán cuando detecten problemas

¡Todo listo para usar! 🎉
