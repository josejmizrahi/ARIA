# 📊 Bases del Presupuesto - Fuentes de Datos

## 🎯 Resumen Ejecutivo

Los presupuestos se construyen a partir de **datos históricos reales** de Odoo, específicamente:

- **Ingresos**: Facturas de cliente (`account.move` con `move_type="out_invoice"`)
- **Gastos**: Pagos realizados (`account.payment`) y movimientos contables (`account.move.line`)
- **Categorización**: Plan de cuentas (`account.account`) para agrupar por tipo

## 📋 Modelos de Odoo Utilizados

### 1. Ingresos (Revenue)

**Modelo:** `account.move`

**Filtros:**
```python
[
    ("move_type", "=", "out_invoice"),      # Solo facturas de cliente
    ("state", "=", "posted"),               # Solo facturas publicadas
    ("invoice_date", ">=", month_start),    # Rango de fechas
    ("invoice_date", "<=", month_end),
    ("company_id", "=", company_id),        # Filtro por compañía
]
```

**Campos utilizados:**
- `amount_total`: Monto total de la factura
- `invoice_date`: Fecha de la factura (para agrupar por mes)
- `state`: Estado (solo "posted" = publicadas)
- `move_type`: Tipo de movimiento ("out_invoice" = factura de cliente)

**Ejemplo de consulta:**
```python
invoices = odoo_client.search_read(
    "account.move",
    [
        ("move_type", "=", "out_invoice"),
        ("state", "=", "posted"),
        ("invoice_date", ">=", "2026-01-01"),
        ("invoice_date", "<=", "2026-01-31"),
        ("company_id", "=", 1),
    ],
    ["amount_total"]
)

# Suma total de ingresos del mes
revenue = sum(i["amount_total"] for i in invoices)
```

### 2. Gastos Totales (Total Expenses)

**Modelo:** `account.payment`

**Filtros:**
```python
[
    ("payment_type", "=", "outbound"),      # Solo pagos salientes
    ("state", "=", "posted"),                # Solo pagos confirmados
    ("date", ">=", month_start),            # Rango de fechas
    ("date", "<=", month_end),
    ("company_id", "=", company_id),
]
```

**Campos utilizados:**
- `amount`: Monto del pago
- `date`: Fecha del pago
- `payment_type`: Tipo ("outbound" = saliente/pago a proveedores)
- `state`: Estado ("posted" = confirmado)

**Ejemplo:**
```python
payments = odoo_client.search_read(
    "account.payment",
    [
        ("payment_type", "=", "outbound"),
        ("state", "=", "posted"),
        ("date", ">=", "2026-01-01"),
        ("date", "<=", "2026-01-31"),
        ("company_id", "=", 1),
    ],
    ["amount"]
)

# Suma total de gastos del mes
expenses = sum(p["amount"] for p in payments)
```

### 3. Gastos por Categoría (Expenses by Category)

**Modelos:** `account.account` + `account.move.line`

**Paso 1: Obtener cuentas de gastos**
```python
expense_accounts = odoo_client.search_read(
    "account.account",
    [
        ("account_type", "in", [
            "expense",                    # Gastos operativos
            "expense_depreciation",       # Depreciaciones
            "expense_direct_cost"         # Costos directos
        ]),
        ("company_id", "=", company_id),
    ],
    ["id", "name"]
)
```

**Tipos de cuenta utilizados:**
- `expense`: Gastos operativos generales
- `expense_depreciation`: Depreciaciones y amortizaciones
- `expense_direct_cost`: Costos directos de producción

**Paso 2: Obtener movimientos por cuenta**
```python
for account in expense_accounts:
    lines = odoo_client.search_read(
        "account.move.line",
        [
            ("account_id", "=", account["id"]),
            ("parent_state", "=", "posted"),    # Solo asientos publicados
            ("date", ">=", month_start),
            ("date", "<=", month_end),
            ("company_id", "=", company_id),
        ],
        ["balance"]
    )
    
    # Suma movimientos de esta cuenta
    total = abs(sum(l["balance"] for l in lines))
    
    # Agrupa por nombre de cuenta (categoría)
    expenses_by_category[account["name"]] = total
```

**Ejemplo de categorías resultantes:**
```json
{
  "Gastos de Ventas": 500000,
  "Gastos Administrativos": 300000,
  "Marketing": 200000,
  "Depreciación": 100000,
  "Costos de Producción": 800000
}
```

## 🔄 Proceso de Cálculo Automático

### Paso 1: Obtener Datos Históricos

Para cada uno de los últimos **6 meses**:

```python
for i in range(6):  # Últimos 6 meses
    month_start = (datetime.now() - timedelta(days=30*(i+1))).strftime("%Y-%m-%d")
    month_end = (datetime.now() - timedelta(days=30*i)).strftime("%Y-%m-%d")
    
    # 1. Ingresos del mes
    invoices = get_invoices(month_start, month_end)
    revenue = sum(invoice["amount_total"] for invoice in invoices)
    monthly_revenues.append(revenue)
    
    # 2. Gastos totales del mes
    payments = get_payments(month_start, month_end)
    expenses = sum(payment["amount"] for payment in payments)
    monthly_expenses.append(expenses)
    
    # 3. Gastos por categoría del mes
    for account in expense_accounts:
        lines = get_account_lines(account, month_start, month_end)
        category_total = sum(line["balance"] for line in lines)
        expenses_by_category[account["name"]].append(category_total)
```

### Paso 2: Calcular Promedios

```python
# Promedio de ingresos mensuales
avg_revenue = sum(monthly_revenues) / len(monthly_revenues)

# Promedio de gastos mensuales
avg_expenses = sum(monthly_expenses) / len(monthly_expenses)

# Promedio por categoría
avg_by_category = {
    category: sum(amounts) / len(amounts)
    for category, amounts in expenses_by_category.items()
}
```

### Paso 3: Retornar Presupuesto

```python
return {
    "source": "calculated",
    "monthly_revenue": avg_revenue,
    "monthly_expenses": avg_expenses,
    "by_category": avg_by_category,
    "calculated_at": datetime.now().isoformat(),
    "months_used": 6,
}
```

## 📊 Estructura de Datos del Presupuesto

### Presupuesto Completo

```json
{
  "source": "calculated",                    // Fuente: "odoo", "manual", "calculated"
  "monthly_revenue": 24500000,               // Presupuesto mensual de ingresos
  "monthly_expenses": 17150000,             // Presupuesto mensual de gastos
  "by_category": {                           // Presupuestos por categoría
    "Gastos de Ventas": 5000000,
    "Marketing": 2000000,
    "Operaciones": 5000000,
    "RRHH": 3000000,
    "Administración": 2150000
  },
  "calculated_at": "2026-01-26T10:30:00",   // Cuándo se calculó
  "months_used": 6                           // Meses históricos usados
}
```

## 🎯 Clasificación de Cuentas

### Tipos de Cuenta para Ingresos

El sistema identifica ingresos usando:
- `account_type = "income"`: Ingresos operativos
- `account_type = "income_other"`: Otros ingresos

### Tipos de Cuenta para Gastos

El sistema identifica gastos usando:
- `account_type = "expense"`: Gastos operativos
- `account_type = "expense_depreciation"`: Depreciaciones
- `account_type = "expense_direct_cost"`: Costos directos

### Ejemplo de Clasificación

```python
# Al leer una línea de presupuesto de Odoo:
account_info = odoo_client.read("account.account", [account_id], ["account_type"])
account_type = account_info[0]["account_type"]

if account_type in ["income", "income_other"]:
    # Es un ingreso → suma a monthly_revenue
    monthly_revenue += planned_amount
    
elif account_type in ["expense", "expense_depreciation", "expense_direct_cost"]:
    # Es un gasto → suma a monthly_expenses y by_category
    monthly_expenses += planned_amount
    by_category[account_name] = planned_amount
```

## 🔍 Filtros y Consideraciones

### Solo Datos Publicados

**Importante:** El sistema solo considera movimientos con `state="posted"`:
- Facturas publicadas (no borradores)
- Pagos confirmados (no pendientes)
- Asientos contables publicados

### Filtro por Compañía

Todos los datos se filtran por `company_id` para:
- Multi-empresa: Cada empresa tiene su propio presupuesto
- Seguridad: Solo datos de la compañía configurada

### Límites de Consulta

Para evitar sobrecarga:
- Máximo 1000 facturas por mes
- Máximo 1000 pagos por mes
- Máximo 50 cuentas de gastos
- Máximo 1000 líneas por cuenta

## 📈 Ejemplo Práctico Completo

### Escenario: Calcular Presupuesto para Enero 2026

```python
# 1. Definir período histórico (últimos 6 meses)
#    Julio 2025 - Diciembre 2025

# 2. Para cada mes, obtener datos:

# JULIO 2025
invoices_jul = [
    {"amount_total": 22000000},  # Factura 1
    {"amount_total": 5000000},   # Factura 2
]
revenue_jul = 27000000

payments_jul = [
    {"amount": 15000000},        # Pago proveedor 1
    {"amount": 2000000},         # Pago proveedor 2
]
expenses_jul = 17000000

# AGOSTO 2025
revenue_ago = 25000000
expenses_ago = 16500000

# ... (septiembre, octubre, noviembre, diciembre)

# 3. Calcular promedios
monthly_revenues = [27000000, 25000000, 24000000, 23000000, 24500000, 25000000]
monthly_expenses = [17000000, 16500000, 17000000, 17500000, 17000000, 16800000]

avg_revenue = sum(monthly_revenues) / 6  # = 24750000
avg_expenses = sum(monthly_expenses) / 6  # = 16966667

# 4. Presupuesto resultante
budget = {
    "monthly_revenue": 24750000,
    "monthly_expenses": 16966667,
    "by_category": {
        "Gastos de Ventas": 5000000,      # Promedio de 6 meses
        "Marketing": 2000000,
        # ...
    }
}
```

## 🎨 Visualización de las Bases

```
┌─────────────────────────────────────────────────────────┐
│              BASES DEL PRESUPUESTO                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  INGRESOS                                                │
│  ┌──────────────────────────────────────────────┐      │
│  │ account.move                                  │      │
│  │ • move_type = "out_invoice"                  │      │
│  │ • state = "posted"                           │      │
│  │ • Campo: amount_total                        │      │
│  │ • Agrupación: Por mes (invoice_date)         │      │
│  └──────────────────────────────────────────────┘      │
│                                                          │
│  GASTOS TOTALES                                          │
│  ┌──────────────────────────────────────────────┐      │
│  │ account.payment                              │      │
│  │ • payment_type = "outbound"                  │      │
│  │ • state = "posted"                           │      │
│  │ • Campo: amount                              │      │
│  │ • Agrupación: Por mes (date)                 │      │
│  └──────────────────────────────────────────────┘      │
│                                                          │
│  GASTOS POR CATEGORÍA                                    │
│  ┌──────────────────────────────────────────────┐      │
│  │ account.account (cuentas de gastos)          │      │
│  │ • account_type IN ["expense", ...]           │      │
│  │                                              │      │
│  │ account.move.line (movimientos)              │      │
│  │ • account_id = cuenta de gasto               │      │
│  │ • parent_state = "posted"                    │      │
│  │ • Campo: balance                             │      │
│  │ • Agrupación: Por cuenta (account.name)      │      │
│  └──────────────────────────────────────────────┘      │
│                                                          │
│  CÁLCULO                                                 │
│  ┌──────────────────────────────────────────────┐      │
│  │ 1. Obtener datos últimos 6 meses             │      │
│  │ 2. Calcular promedio mensual                  │      │
│  │ 3. Agrupar gastos por categoría              │      │
│  │ 4. Retornar presupuesto calculado            │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

## ⚠️ Consideraciones Importantes

### 1. Solo Movimientos Publicados

El sistema **NO** incluye:
- Facturas en borrador
- Pagos pendientes
- Asientos no publicados

### 2. Período de Cálculo

- Por defecto: **6 meses** históricos
- Configurable en el código: `months: int = 6`
- Más meses = más estable, menos reactivo
- Menos meses = más reactivo, menos estable

### 3. Divisa

- Todos los cálculos usan la divisa configurada (`ODOO_DEFAULT_CURRENCY`)
- Si hay múltiples divisas, se usa la divisa por defecto
- Los presupuestos se expresan en la divisa principal

### 4. Fechas

- **Ingresos**: Se usa `invoice_date` (fecha de factura)
- **Gastos**: Se usa `date` del pago o `date` de la línea contable
- **Agrupación**: Por mes calendario (1-31)

## 🔧 Personalización

Si necesitas cambiar las bases del presupuesto, puedes modificar:

1. **Período histórico**: Cambiar `months: int = 6` en `_calculate_budgets_from_history()`
2. **Tipos de cuenta**: Modificar filtros de `account_type`
3. **Modelos de datos**: Cambiar de `account.payment` a `account.move.line` si prefieres
4. **Filtros adicionales**: Agregar más condiciones en las consultas

## 📚 Referencias

- **Modelo account.move**: Facturas y asientos contables
- **Modelo account.payment**: Pagos y cobros
- **Modelo account.account**: Plan de cuentas
- **Modelo account.move.line**: Líneas de asientos contables

Todos estos modelos son parte del módulo `account` de Odoo (contabilidad).
