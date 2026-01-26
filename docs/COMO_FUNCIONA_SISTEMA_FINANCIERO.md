# 📊 Cómo Funciona el Sistema de Planeación Financiera

## 🏗️ Arquitectura General

El sistema de planeación financiera de ARIA está compuesto por varios componentes que trabajan juntos:

```
┌─────────────────────────────────────────────────────────────┐
│                    ARIA - Sistema Financiero                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Finance Agent │───▶│ Budget Mgr  │───▶│   Odoo ERP   │  │
│  │  (Análisis)   │    │ (Presup.)   │    │  (Datos)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Tareas     │    │   Archivo    │    │   API REST   │  │
│  │ Programadas  │    │   JSON       │    │  Endpoints   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         └────────────────────┴────────────────────┘          │
│                            │                                  │
│                            ▼                                  │
│                   ┌──────────────┐                           │
│                   │  Dashboard   │                           │
│                   │     Web      │                           │
│                   └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Flujo de Datos

### 1. Carga de Presupuestos (BudgetManager)

El sistema carga presupuestos siguiendo esta prioridad:

```
┌─────────────────────────────────────────────────────────┐
│  ¿Existe account.budget en Odoo?                        │
│  ─────────────────────────────────────────────────────  │
│  SÍ → Cargar desde Odoo (account.budget)               │
│  NO ↓                                                   │
│  ¿Existe crossovered.budget en Odoo?                   │
│  ─────────────────────────────────────────────────────  │
│  SÍ → Cargar desde Odoo (crossovered.budget)           │
│  NO ↓                                                   │
│  ¿Existe budgets.json?                                  │
│  ─────────────────────────────────────────────────────  │
│  SÍ → Cargar desde archivo JSON                        │
│  NO ↓                                                   │
│  Calcular automáticamente desde histórico (6 meses)    │
└─────────────────────────────────────────────────────────┘
```

**Ejemplo práctico:**

```python
# El BudgetManager verifica automáticamente:
budget_manager = BudgetManager(company_id=1)

# 1. Intenta cargar desde Odoo
budgets = budget_manager._load_budgets_from_odoo(odoo_client)
# Si account.budget existe → carga presupuestos
# Si no existe → intenta crossovered.budget
# Si ninguno existe → retorna None

# 2. Si no hay en Odoo, intenta archivo
if not budgets:
    budgets = budget_manager._load_budgets_from_file()

# 3. Si no hay archivo, calcula desde histórico
if not budgets:
    budgets = budget_manager._calculate_budgets_from_history(odoo_client)
```

### 2. Ejecución de Tareas Programadas

El agente de finanzas tiene tareas que se ejecutan automáticamente:

| Tarea | Horario | Qué hace |
|-------|---------|----------|
| `cash_flow_projection` | Diario 7:00 AM | Proyecta flujo de caja 4 semanas |
| `bank_balances` | Diario 8:00 AM | Reporta saldos bancarios |
| `upcoming_payments` | Diario 9:00 AM | Verifica pagos próximos |
| `financial_analysis` | Lunes 10:00 AM | Análisis de ratios financieros |
| `budget_comparison` | Lunes 8:00 AM | Compara real vs presupuestado |
| `profitability_analysis` | Lunes 11:00 AM | Análisis de rentabilidad |
| `annual_forecast` | Día 1 del mes | Proyecciones anuales |
| `weekly_report` | Viernes 5:00 PM | Reporte semanal |
| `monthly_executive_report` | Día 1 del mes | Reporte ejecutivo |

**Ejemplo de ejecución:**

```python
# El scheduler ejecuta automáticamente:
# Lunes 8:00 AM → Ejecuta budget_comparison

async def compare_vs_budget(self):
    # 1. Obtiene presupuestos (desde BudgetManager)
    monthly_budget = self.monthly_budget  # Propiedad que carga automáticamente
    
    # 2. Obtiene datos reales del mes
    invoices = self.search_read("account.move", [...])
    actual_revenue = sum(i["amount_total"] for i in invoices)
    
    # 3. Calcula variaciones
    variance = actual_revenue - expected_revenue
    
    # 4. Crea alertas si hay desviaciones
    if variance < -10%:
        await self.propose(...)  # Propuesta de acción
```

### 3. Análisis Financiero

Cada análisis sigue este flujo:

```
┌─────────────────┐
│  Consulta Odoo  │ → Obtiene datos históricos
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Calcula Métricas│ → Ratios, tendencias, proyecciones
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Detecta Issues │ → Compara con umbrales
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Crea Propuestas│ → Si hay problemas críticos
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Envía Notif.   │ → Telegram/Dashboard
└─────────────────┘
```

**Ejemplo: Análisis de Ratios**

```python
async def analyze_financial_ratios(self):
    # 1. Obtiene datos últimos 3 meses
    months_data = []
    for i in range(3):
        revenue = self._get_monthly_revenue(i)
        expenses = self._get_monthly_expenses(i)
        months_data.append({"revenue": revenue, "expenses": expenses})
    
    # 2. Calcula ratios
    current_month = months_data[0]
    net_margin = (current_month["net"] / current_month["revenue"]) * 100
    revenue_growth = calculate_growth(months_data)
    
    # 3. Detecta problemas
    if net_margin < 10:
        await self.propose(
            title="Margen neto bajo",
            priority=Priority.HIGH,
            ...
        )
    
    # 4. Notifica resultados
    await self.notify(
        title="Análisis Financiero",
        message=f"Margen: {net_margin}%, Crecimiento: {revenue_growth}%"
    )
```

## 📊 Sistema de Presupuestos

### Carga Automática desde Odoo

Si tienes el módulo `account.budget` instalado:

```python
# El sistema detecta automáticamente:
available_models = budget_manager._check_budget_models_available(odoo_client)
# {"account.budget": True, "account.budget.line": True, ...}

# Luego carga los presupuestos:
budget = odoo_client.read("account.budget", [budget_id], [
    "name", "date_from", "date_to", "budget_line_ids"
])

# Procesa las líneas:
for line in budget_lines:
    account_type = get_account_type(line["account_id"])
    if account_type == "income":
        monthly_revenue += line["planned_amount"]
    elif account_type == "expense":
        monthly_expenses += line["planned_amount"]
```

### Configuración Manual desde Dashboard

1. Usuario accede al dashboard financiero
2. Click en "Configurar Presupuestos"
3. Ingresa valores:
   - Presupuesto mensual de ingresos
   - Presupuesto mensual de gastos
   - Presupuestos por categoría
4. Se guarda en `logs/budgets.json`
5. El sistema los usa automáticamente

```json
{
  "source": "manual",
  "monthly_revenue": 24500000,
  "monthly_expenses": 17150000,
  "by_category": {
    "Ventas": 20000000,
    "Marketing": 2000000,
    "Operaciones": 5000000
  },
  "updated_at": "2026-01-26T10:30:00"
}
```

### Cálculo Automático

Si no hay presupuestos configurados:

```python
# Calcula promedio de últimos 6 meses
for i in range(6):
    month_revenue = get_revenue_for_month(i)
    month_expenses = get_expenses_for_month(i)
    revenues.append(month_revenue)
    expenses.append(month_expenses)

# Retorna promedios
return {
    "source": "calculated",
    "monthly_revenue": sum(revenues) / 6,
    "monthly_expenses": sum(expenses) / 6,
    "by_category": calculate_category_averages()
}
```

## 🌐 API REST y Dashboard

### Endpoints Disponibles

```
GET  /api/finance/metrics          → Métricas consolidadas
GET  /api/finance/ratios           → Ejecuta análisis de ratios
GET  /api/finance/budget           → Comparación vs presupuesto
GET  /api/finance/profitability    → Análisis de rentabilidad
GET  /api/finance/forecast         → Proyecciones anuales
GET  /api/finance/budgets          → Obtiene presupuestos actuales
POST /api/finance/budgets          → Actualiza presupuestos
```

### Flujo Dashboard → API → Odoo

```
Usuario en Dashboard
    │
    ▼
Click "Ver Análisis de Ratios"
    │
    ▼
Frontend llama: GET /api/finance/ratios
    │
    ▼
API ejecuta: agent.run_task("financial_analysis")
    │
    ▼
Agente consulta Odoo: search_read("account.move", ...)
    │
    ▼
Odoo retorna datos
    │
    ▼
Agente calcula ratios
    │
    ▼
Agente retorna TaskResult
    │
    ▼
API retorna JSON al frontend
    │
    ▼
Dashboard muestra gráficos y métricas
```

## 🔍 Ejemplo Completo: Comparación vs Presupuesto

### Paso 1: Tarea se ejecuta automáticamente

```python
# Lunes 8:00 AM - Scheduler ejecuta:
await finance_agent.run_task("budget_comparison")
```

### Paso 2: Obtiene presupuestos

```python
# El agente usa propiedades que cargan automáticamente:
monthly_budget = self.monthly_budget  # → BudgetManager.get_budgets()
# Si hay account.budget en Odoo → lo usa
# Si no → busca en budgets.json
# Si no → calcula desde histórico
```

### Paso 3: Obtiene datos reales

```python
# Consulta Odoo para facturas del mes actual
invoices = self.search_read(
    "account.move",
    [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("invoice_date", ">=", month_start),
        ("company_id", "=", self.company_id),
    ],
    ["amount_total"]
)

actual_revenue = sum(i["amount_total"] for i in invoices)
```

### Paso 4: Calcula variaciones

```python
# Calcula progreso del mes
days_elapsed = datetime.now().day
days_in_month = 30  # Simplificado
progress_pct = (days_elapsed / days_in_month) * 100

# Presupuesto esperado hasta hoy
expected_revenue = monthly_budget * (progress_pct / 100)

# Variación
variance = actual_revenue - expected_revenue
variance_pct = (variance / expected_revenue * 100) if expected_revenue > 0 else 0
```

### Paso 5: Detecta problemas y crea propuestas

```python
if variance_pct < -10:
    await self.propose(
        title="Desviación negativa en ingresos",
        description=f"Ingresos {variance_pct:.1f}% por debajo del presupuesto",
        priority=Priority.HIGH,
        situation_summary=f"""
        Presupuesto mensual: {format_currency(monthly_budget)}
        Ingresos reales: {format_currency(actual_revenue)}
        Esperado hasta hoy: {format_currency(expected_revenue)}
        Variación: {variance_pct:.1f}%
        """,
        proposed_action_detail="Acelerar ventas y revisar estrategia comercial"
    )
```

### Paso 6: Notifica resultados

```python
await self.notify(
    title="Comparativo vs Presupuesto",
    message=f"""
    *Ingresos:*
    • Real: {format_currency(actual_revenue)}
    • Esperado: {format_currency(expected_revenue)}
    • Variación: {format_currency(variance)} ({variance_pct:+.1f}%)
    """,
    priority=Priority.HIGH if variance_pct < -10 else Priority.MEDIUM
)
```

## 🎯 Casos de Uso

### Caso 1: Empresa con Odoo Budget Module

```
1. Instala módulo account_budget en Odoo
2. Configura presupuestos en Odoo
3. ARIA detecta automáticamente el módulo
4. Carga presupuestos desde Odoo
5. Compara real vs presupuestado automáticamente
6. Genera alertas si hay desviaciones
```

### Caso 2: Empresa sin Módulo de Presupuestos

```
1. No tiene módulo de presupuestos en Odoo
2. Configura presupuestos desde dashboard web
3. Se guardan en logs/budgets.json
4. ARIA los carga automáticamente
5. Funciona igual que con Odoo
```

### Caso 3: Empresa sin Configuración

```
1. No tiene presupuestos configurados
2. ARIA calcula automáticamente desde histórico
3. Usa promedio de últimos 6 meses
4. Funciona como referencia inicial
5. Puede configurar después desde dashboard
```

## 🔐 Seguridad y Aprobaciones

Todas las acciones importantes requieren aprobación:

```
Agente detecta problema
    │
    ▼
Crea Propuesta (Proposal)
    │
    ▼
Se registra en ApprovalEngine (Redis)
    │
    ▼
Se envía notificación (Telegram/Dashboard)
    │
    ▼
Humano revisa y decide
    │
    ├─→ Aprueba → ActionExecutor ejecuta en Odoo
    └─→ Rechaza → Se marca como rechazada
```

## 📈 Métricas y KPIs

El sistema calcula automáticamente:

- **Liquidez**: Saldo disponible, runway (días)
- **Ingresos**: Mensual, crecimiento, vs presupuesto
- **Gastos**: Por categoría, ratio sobre ingresos
- **Rentabilidad**: Margen neto, margen de contribución, punto de equilibrio
- **Flujo de caja**: Proyección 4 semanas, posición neta
- **Ratios**: Liquidez corriente, gastos/ingresos, crecimiento

Todos estos se actualizan automáticamente y están disponibles en:
- Dashboard web
- API REST
- Notificaciones Telegram
- Reportes PDF

## 🚀 Inicio Rápido

1. **Configurar conexión a Odoo** (`.env`)
2. **Iniciar ARIA**: `aria serve`
3. **Acceder al dashboard**: http://localhost:5173
4. **Configurar presupuestos** (opcional, desde dashboard)
5. **Las tareas se ejecutan automáticamente** según horarios programados

¡El sistema funciona automáticamente sin intervención manual!
