# ARIA - Campos Odoo Verificados

Este documento lista todos los modelos y campos de Odoo utilizados por los agentes ARIA.
Verificado contra Odoo 19.

## Resumen

| Métrica | Valor |
|---------|-------|
| Agentes activos | 11 |
| Tareas programadas | 64 |
| Modelos verificados | 34 |
| Campos disponibles | ~1,200 |

---

## 1. Clientes y Proveedores (`res.partner`)

**Campos disponibles:** 124

### Campos clave para análisis:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Nombre |
| `email` | char | Email |
| `phone` | char | Teléfono |
| `vat` | char | RFC/NIT |
| `credit_limit` | float | Límite de crédito |
| `total_due` | monetary | Total adeudado |
| `total_invoiced` | monetary | Total facturado |
| `total_overdue` | monetary | Total vencido |
| `customer_rank` | integer | Ranking cliente |
| `supplier_rank` | integer | Ranking proveedor |
| `user_id` | many2one | Vendedor asignado |
| `team_id` | many2one | Equipo de ventas |
| `property_payment_term_id` | many2one | Plazo de pago |

---

## 2. Ventas (`sale.order`, `sale.order.line`)

### sale.order - **96 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Número de pedido |
| `partner_id` | many2one | Cliente |
| `date_order` | datetime | Fecha del pedido |
| `amount_untaxed` | monetary | Subtotal |
| `amount_tax` | monetary | Impuestos |
| `amount_total` | monetary | Total |
| `margin` | monetary | Margen ($) |
| `margin_percent` | float | Margen (%) |
| `state` | selection | Estado (draft, sent, sale, done, cancel) |
| `invoice_status` | selection | Estado facturación |
| `delivery_status` | selection | Estado entrega |
| `user_id` | many2one | Vendedor |
| `team_id` | many2one | Equipo |

### sale.order.line - **69 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | many2one | Producto |
| `product_uom_qty` | float | Cantidad pedida |
| `qty_delivered` | float | Cantidad entregada |
| `qty_invoiced` | float | Cantidad facturada |
| `price_unit` | float | Precio unitario |
| `discount` | float | Descuento (%) |
| `price_subtotal` | monetary | Subtotal |
| `purchase_price` | float | Costo |
| `margin` | float | Margen ($) |
| `margin_percent` | float | Margen (%) |

---

## 3. Facturación (`account.move`, `account.move.line`)

### account.move - **122 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Número |
| `ref` | char | Referencia |
| `move_type` | selection | Tipo (out_invoice, in_invoice, etc.) |
| `partner_id` | many2one | Cliente/Proveedor |
| `invoice_date` | date | Fecha factura |
| `invoice_date_due` | date | Fecha vencimiento |
| `amount_total` | monetary | Total |
| `amount_residual` | monetary | Saldo pendiente |
| `state` | selection | Estado (draft, posted, cancel) |
| `payment_state` | selection | Estado pago (not_paid, paid, partial) |
| `invoice_user_id` | many2one | Vendedor |
| `journal_id` | many2one | Diario |

### account.move.line - **77 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `account_id` | many2one | Cuenta contable |
| `debit` | monetary | Debe |
| `credit` | monetary | Haber |
| `balance` | monetary | Balance |
| `date_maturity` | date | Fecha vencimiento |
| `reconciled` | boolean | Conciliado |
| `amount_residual` | monetary | Saldo residual |

---

## 4. Compras (`purchase.order`)

**Campos disponibles:** 47

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Referencia |
| `partner_id` | many2one | Proveedor |
| `date_order` | datetime | Fecha orden |
| `date_planned` | datetime | Fecha planeada |
| `amount_total` | monetary | Total |
| `state` | selection | Estado |
| `receipt_status` | selection | Estado recepción |
| `invoice_status` | selection | Estado facturación |

---

## 5. Inventario (`product`, `stock`)

### product.template - **75 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Nombre |
| `default_code` | char | Referencia interna |
| `type` | selection | Tipo (consu, product, service) |
| `categ_id` | many2one | Categoría |
| `list_price` | float | Precio de venta |
| `standard_price` | float | Costo |
| `qty_available` | float | Cantidad disponible |
| `tracking` | selection | Seguimiento (none, lot, serial) |

### stock.quant - **17 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | many2one | Producto |
| `location_id` | many2one | Ubicación |
| `lot_id` | many2one | Lote/Serie |
| `quantity` | float | Cantidad |
| `reserved_quantity` | float | Reservado |

### stock.warehouse.orderpoint - **19 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | many2one | Producto |
| `product_min_qty` | float | Cantidad mínima |
| `product_max_qty` | float | Cantidad máxima |
| `qty_to_order` | float | Cantidad a ordenar |

---

## 6. RRHH (`hr.employee`, `hr.attendance`)

### hr.employee - **79 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Nombre |
| `work_email` | char | Email trabajo |
| `department_id` | many2one | Departamento |
| `job_id` | many2one | Puesto |
| `parent_id` | many2one | Gerente |
| `birthday` | date | Cumpleaños |
| `allocation_remaining_display` | char | Días vacaciones restantes |

### hr.attendance - **22 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `employee_id` | many2one | Empleado |
| `check_in` | datetime | Entrada |
| `check_out` | datetime | Salida |
| `worked_hours` | float | Horas trabajadas |
| `overtime_hours` | float | Horas extra |
| `in_location` | char | Ubicación entrada |

---

## 7. Manufactura (`mrp`)

### mrp.production - **53 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Referencia |
| `product_id` | many2one | Producto |
| `product_qty` | float | Cantidad a producir |
| `qty_produced` | float | Cantidad producida |
| `state` | selection | Estado |
| `date_start` | datetime | Inicio |
| `date_deadline` | datetime | Fecha límite |
| `bom_id` | many2one | Lista de materiales |

### mrp.workcenter - **24 campos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Nombre |
| `time_efficiency` | float | Eficiencia |
| `working_state` | selection | Estado operativo |
| `oee_target` | float | OEE objetivo |
| `costs_hour` | float | Costo por hora |

---

## 8. CRM (`crm.lead`)

**Campos disponibles:** 67

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | char | Nombre oportunidad |
| `partner_id` | many2one | Contacto |
| `stage_id` | many2one | Etapa |
| `expected_revenue` | monetary | Ingreso esperado |
| `probability` | float | Probabilidad (%) |
| `date_deadline` | date | Cierre esperado |
| `user_id` | many2one | Vendedor |
| `team_id` | many2one | Equipo |
| `won_status` | selection | Ganado/Perdido |
| `source_id` | many2one | Fuente |
| `campaign_id` | many2one | Campaña |

---

## Archivos de Configuración

- `docs/odoo_full_fields.json` - Todos los campos por modelo
- `docs/odoo_fields_mapping.json` - Mapeo de campos para agentes
- `aria/fields_config/odoo_fields.py` - Configuración Python de campos

---

## Comandos Útiles

```bash
# Introspección de campos
python scripts/odoo_introspection.py

# Introspección con salida JSON
python scripts/odoo_introspection.py --json

# Guardar reporte
python scripts/odoo_introspection.py -o reporte.json

# Diagnóstico del sistema
aria diagnose
aria diagnose --agent cobranza
```
