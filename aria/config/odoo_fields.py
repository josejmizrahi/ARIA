"""
ARIA - Configuración de Campos Odoo.

Mapeo completo de modelos y campos utilizados por los agentes ARIA.
Basado en introspección de Odoo 19.

Este archivo sirve como referencia central para:
- Campos disponibles por modelo
- Campos requeridos vs opcionales
- Filtros y dominios estándar
"""

from typing import Any

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================

# Campos comunes que siempre están disponibles
COMMON_FIELDS = ["id", "display_name", "create_date", "write_date"]

# Estados de facturas
INVOICE_STATES = {
    "draft": "Borrador",
    "posted": "Publicado",
    "cancel": "Cancelado",
}

# Tipos de movimiento contable
MOVE_TYPES = {
    "out_invoice": "Factura de cliente",
    "out_refund": "Nota de crédito cliente",
    "in_invoice": "Factura de proveedor",
    "in_refund": "Nota de crédito proveedor",
    "entry": "Asiento contable",
}

# Estados de pago
PAYMENT_STATES = {
    "not_paid": "No pagado",
    "in_payment": "En proceso",
    "paid": "Pagado",
    "partial": "Pago parcial",
    "reversed": "Reversado",
}


# ============================================================
# CLIENTES Y PROVEEDORES (res.partner)
# ============================================================
PARTNER_FIELDS = {
    # Identificación
    "id": "ID",
    "name": "Nombre",
    "display_name": "Nombre completo",
    "ref": "Referencia interna",
    "vat": "RFC/NIT",
    "company_type": "Tipo (persona/empresa)",
    "is_company": "Es empresa",
    
    # Contacto
    "email": "Email",
    "phone": "Teléfono",
    "mobile": "Móvil",
    "website": "Sitio web",
    
    # Dirección
    "street": "Calle",
    "street2": "Calle 2",
    "city": "Ciudad",
    "state_id": "Estado/Provincia",
    "zip": "Código postal",
    "country_id": "País",
    
    # Clasificación
    "customer_rank": "Ranking cliente",
    "supplier_rank": "Ranking proveedor",
    "category_id": "Etiquetas",
    "user_id": "Vendedor asignado",
    "team_id": "Equipo de ventas",
    
    # Crédito
    "credit_limit": "Límite de crédito",
    "total_due": "Total adeudado",
    "total_invoiced": "Total facturado",
    "total_overdue": "Total vencido",
    
    # Términos
    "property_payment_term_id": "Plazo de pago cliente",
    "property_supplier_payment_term_id": "Plazo de pago proveedor",
    
    # Estado
    "active": "Activo",
    "parent_id": "Empresa relacionada",
}

PARTNER_FILTERS = {
    "customers": [("customer_rank", ">", 0), ("active", "=", True)],
    "suppliers": [("supplier_rank", ">", 0), ("active", "=", True)],
    "active": [("active", "=", True)],
    "with_credit": [("total_due", ">", 0)],
    "overdue": [("total_overdue", ">", 0)],
}


# ============================================================
# VENTAS (sale.order, sale.order.line)
# ============================================================
SALE_ORDER_FIELDS = {
    # Identificación
    "id": "ID",
    "name": "Número de pedido",
    "client_order_ref": "Referencia cliente",
    "origin": "Documento origen",
    
    # Cliente
    "partner_id": "Cliente",
    "partner_invoice_id": "Dirección facturación",
    "partner_shipping_id": "Dirección entrega",
    
    # Fechas
    "date_order": "Fecha del pedido",
    "validity_date": "Fecha de validez",
    "commitment_date": "Fecha compromiso entrega",
    "expected_date": "Fecha esperada",
    
    # Montos
    "amount_untaxed": "Subtotal",
    "amount_tax": "Impuestos",
    "amount_total": "Total",
    "currency_id": "Moneda",
    
    # Márgenes
    "margin": "Margen ($)",
    "margin_percent": "Margen (%)",
    
    # Estado
    "state": "Estado",
    "invoice_status": "Estado facturación",
    "delivery_status": "Estado entrega",
    
    # Responsables
    "user_id": "Vendedor",
    "team_id": "Equipo de ventas",
    "company_id": "Compañía",
    
    # Condiciones
    "pricelist_id": "Lista de precios",
    "payment_term_id": "Plazo de pago",
}

SALE_ORDER_LINE_FIELDS = {
    "id": "ID",
    "order_id": "Pedido",
    "product_id": "Producto",
    "name": "Descripción",
    
    # Cantidades
    "product_uom_qty": "Cantidad pedida",
    "qty_delivered": "Cantidad entregada",
    "qty_invoiced": "Cantidad facturada",
    "qty_to_invoice": "Cantidad por facturar",
    
    # Precios
    "price_unit": "Precio unitario",
    "discount": "Descuento (%)",
    "price_subtotal": "Subtotal",
    "price_total": "Total",
    
    # Márgenes
    "purchase_price": "Costo",
    "margin": "Margen ($)",
    "margin_percent": "Margen (%)",
    
    # Estado
    "state": "Estado",
    "invoice_status": "Estado facturación",
}

SALE_ORDER_STATES = {
    "draft": "Cotización",
    "sent": "Cotización enviada",
    "sale": "Pedido de venta",
    "done": "Bloqueado",
    "cancel": "Cancelado",
}


# ============================================================
# FACTURACIÓN (account.move, account.move.line)
# ============================================================
ACCOUNT_MOVE_FIELDS = {
    # Identificación
    "id": "ID",
    "name": "Número",
    "ref": "Referencia",
    "move_type": "Tipo",
    "invoice_origin": "Origen",
    
    # Cliente/Proveedor
    "partner_id": "Cliente/Proveedor",
    "commercial_partner_id": "Entidad comercial",
    
    # Fechas
    "date": "Fecha contable",
    "invoice_date": "Fecha factura",
    "invoice_date_due": "Fecha vencimiento",
    
    # Montos
    "amount_untaxed": "Subtotal",
    "amount_tax": "Impuestos",
    "amount_total": "Total",
    "amount_residual": "Saldo pendiente",
    "amount_paid": "Monto pagado",
    
    # Montos con signo
    "amount_untaxed_signed": "Subtotal (firmado)",
    "amount_total_signed": "Total (firmado)",
    "amount_residual_signed": "Saldo (firmado)",
    
    # Moneda
    "currency_id": "Moneda",
    "company_currency_id": "Moneda compañía",
    
    # Estado
    "state": "Estado",
    "payment_state": "Estado de pago",
    
    # Responsables
    "invoice_user_id": "Vendedor",
    "journal_id": "Diario",
    "company_id": "Compañía",
    
    # Condiciones
    "invoice_payment_term_id": "Plazo de pago",
    "fiscal_position_id": "Posición fiscal",
    "payment_reference": "Referencia de pago",
}

ACCOUNT_MOVE_LINE_FIELDS = {
    "id": "ID",
    "move_id": "Asiento",
    "name": "Etiqueta",
    
    # Cuenta
    "account_id": "Cuenta contable",
    "journal_id": "Diario",
    
    # Entidad
    "partner_id": "Cliente/Proveedor",
    "product_id": "Producto",
    
    # Montos
    "quantity": "Cantidad",
    "price_unit": "Precio unitario",
    "price_subtotal": "Subtotal",
    "price_total": "Total",
    
    # Débito/Crédito
    "debit": "Debe",
    "credit": "Haber",
    "balance": "Balance",
    "amount_currency": "Monto en moneda",
    "amount_residual": "Saldo residual",
    
    # Fechas
    "date": "Fecha",
    "date_maturity": "Fecha vencimiento",
    
    # Conciliación
    "reconciled": "Conciliado",
    "full_reconcile_id": "Conciliación",
    
    # Moneda
    "currency_id": "Moneda",
    "company_id": "Compañía",
    
    # Analítica
    "analytic_distribution": "Distribución analítica",
}


# ============================================================
# COMPRAS (purchase.order, purchase.order.line)
# ============================================================
PURCHASE_ORDER_FIELDS = {
    "id": "ID",
    "name": "Referencia",
    "partner_ref": "Referencia proveedor",
    "origin": "Documento origen",
    
    # Proveedor
    "partner_id": "Proveedor",
    
    # Fechas
    "date_order": "Fecha orden",
    "date_approve": "Fecha aprobación",
    "date_planned": "Fecha planeada",
    "effective_date": "Fecha efectiva",
    
    # Montos
    "amount_untaxed": "Subtotal",
    "amount_tax": "Impuestos",
    "amount_total": "Total",
    "currency_id": "Moneda",
    
    # Estado
    "state": "Estado",
    "receipt_status": "Estado recepción",
    "invoice_status": "Estado facturación",
    
    # Responsables
    "user_id": "Comprador",
    "company_id": "Compañía",
    
    # Condiciones
    "payment_term_id": "Plazo de pago",
    "fiscal_position_id": "Posición fiscal",
    "incoterm_id": "Incoterm",
    
    # Contadores
    "picking_count": "Recepciones",
    "invoice_count": "Facturas",
}

PURCHASE_ORDER_STATES = {
    "draft": "RFQ",
    "sent": "RFQ enviada",
    "to approve": "Por aprobar",
    "purchase": "Orden de compra",
    "done": "Bloqueado",
    "cancel": "Cancelado",
}


# ============================================================
# INVENTARIO (product, stock)
# ============================================================
PRODUCT_TEMPLATE_FIELDS = {
    "id": "ID",
    "name": "Nombre",
    "default_code": "Referencia interna",
    "barcode": "Código de barras",
    "type": "Tipo de producto",
    
    # Categoría
    "categ_id": "Categoría",
    
    # Precios
    "list_price": "Precio de venta",
    "standard_price": "Costo",
    
    # Unidades
    "uom_id": "Unidad de medida",
    "uom_po_id": "Unidad de compra",
    
    # Peso/Volumen
    "weight": "Peso",
    "volume": "Volumen",
    
    # Configuración
    "sale_ok": "Se vende",
    "purchase_ok": "Se compra",
    "active": "Activo",
    
    # Trazabilidad
    "tracking": "Seguimiento (lote/serie)",
    
    # Responsable
    "responsible_id": "Responsable",
}

STOCK_QUANT_FIELDS = {
    "id": "ID",
    "product_id": "Producto",
    "location_id": "Ubicación",
    "lot_id": "Lote/Serie",
    "package_id": "Paquete",
    "owner_id": "Propietario",
    
    # Cantidades
    "quantity": "Cantidad disponible",
    "reserved_quantity": "Cantidad reservada",
    "available_quantity": "Disponible real",
    
    # Inventario
    "inventory_quantity": "Cantidad contada",
    "inventory_diff_quantity": "Diferencia",
}

STOCK_MOVE_FIELDS = {
    "id": "ID",
    "reference": "Referencia",
    "product_id": "Producto",
    "product_uom_qty": "Cantidad",
    "quantity": "Cantidad real",
    
    # Ubicaciones
    "location_id": "Origen",
    "location_dest_id": "Destino",
    
    # Fechas
    "date": "Fecha",
    "date_deadline": "Fecha límite",
    
    # Estado
    "state": "Estado",
    
    # Relaciones
    "picking_id": "Transferencia",
    "origin": "Documento origen",
}

ORDERPOINT_FIELDS = {
    "id": "ID",
    "name": "Nombre",
    "product_id": "Producto",
    "warehouse_id": "Almacén",
    "location_id": "Ubicación",
    
    # Cantidades
    "product_min_qty": "Cantidad mínima",
    "product_max_qty": "Cantidad máxima",
    "qty_to_order": "Cantidad a ordenar",
    
    # Configuración
    "trigger": "Disparador",
    "active": "Activo",
    
    # Ruta
    "route_id": "Ruta de abastecimiento",
    "supplier_id": "Proveedor",
}


# ============================================================
# RRHH (hr.employee, hr.attendance, hr.leave)
# ============================================================
HR_EMPLOYEE_FIELDS = {
    "id": "ID",
    "name": "Nombre",
    "work_email": "Email trabajo",
    "work_phone": "Teléfono trabajo",
    "mobile_phone": "Móvil trabajo",
    
    # Puesto
    "job_id": "Puesto",
    "job_title": "Título del puesto",
    "department_id": "Departamento",
    
    # Jerarquía
    "parent_id": "Gerente",
    "coach_id": "Coach",
    
    # Personal
    "birthday": "Cumpleaños",
    "identification_id": "No. identificación",
    "gender": "Género",
    "marital": "Estado civil",
    
    # Emergencia
    "emergency_contact": "Contacto emergencia",
    "emergency_phone": "Teléfono emergencia",
    
    # Control
    "barcode": "Badge ID",
    "pin": "PIN",
    
    # Vacaciones
    "leave_manager_id": "Aprobador de ausencias",
    "allocation_remaining_display": "Días restantes",
    
    # Compañía
    "company_id": "Compañía",
    "resource_calendar_id": "Horario de trabajo",
}

HR_ATTENDANCE_FIELDS = {
    "id": "ID",
    "employee_id": "Empleado",
    "check_in": "Entrada",
    "check_out": "Salida",
    "date": "Fecha",
    
    # Horas
    "worked_hours": "Horas trabajadas",
    "expected_hours": "Horas esperadas",
    "overtime_hours": "Horas extra",
    "validated_overtime_hours": "Horas extra validadas",
    "overtime_status": "Estado horas extra",
    
    # Ubicación entrada
    "in_latitude": "Latitud entrada",
    "in_longitude": "Longitud entrada",
    "in_location": "Ubicación entrada",
    "in_mode": "Modo entrada",
    
    # Ubicación salida
    "out_latitude": "Latitud salida",
    "out_longitude": "Longitud salida",
    "out_location": "Ubicación salida",
    "out_mode": "Modo salida",
}

HR_LEAVE_FIELDS = {
    "id": "ID",
    "employee_id": "Empleado",
    "holiday_status_id": "Tipo de ausencia",
    
    # Fechas
    "date_from": "Desde",
    "date_to": "Hasta",
    "number_of_days": "Días",
    
    # Estado
    "state": "Estado",
    
    # Notas
    "name": "Descripción",
    "notes": "Notas",
}


# ============================================================
# MANUFACTURA (mrp)
# ============================================================
MRP_PRODUCTION_FIELDS = {
    "id": "ID",
    "name": "Referencia",
    "product_id": "Producto",
    "product_qty": "Cantidad a producir",
    "product_uom_id": "Unidad",
    
    # Producción
    "qty_producing": "Cantidad en proceso",
    "qty_produced": "Cantidad producida",
    
    # Fechas
    "date_start": "Fecha inicio",
    "date_finished": "Fecha fin",
    "date_deadline": "Fecha límite",
    
    # Estado
    "state": "Estado",
    "reservation_state": "Estado de reserva",
    
    # BOM y Routing
    "bom_id": "Lista de materiales",
    "picking_type_id": "Tipo de operación",
    
    # Ubicaciones
    "location_src_id": "Ubicación componentes",
    "location_dest_id": "Ubicación productos",
    
    # Responsable
    "user_id": "Responsable",
    "company_id": "Compañía",
    
    # Origen
    "origin": "Documento origen",
    "priority": "Prioridad",
    
    # Disponibilidad
    "components_availability": "Disponibilidad componentes",
    "components_availability_state": "Estado disponibilidad",
}

MRP_PRODUCTION_STATES = {
    "draft": "Borrador",
    "confirmed": "Confirmado",
    "progress": "En progreso",
    "to_close": "Por cerrar",
    "done": "Hecho",
    "cancel": "Cancelado",
}

MRP_WORKCENTER_FIELDS = {
    "id": "ID",
    "name": "Nombre",
    "code": "Código",
    "active": "Activo",
    
    # Eficiencia
    "time_efficiency": "Eficiencia de tiempo",
    "working_state": "Estado operativo",
    "oee_target": "OEE objetivo",
    
    # Tiempos
    "time_start": "Tiempo setup",
    "time_stop": "Tiempo cleanup",
    
    # Costos
    "costs_hour": "Costo por hora",
    "employee_costs_hour": "Costo empleado/hora",
    
    # Mantenimiento
    "maintenance_count": "Mantenimientos",
    "maintenance_open_count": "Mantenimientos abiertos",
    "expected_mtbf": "MTBF esperado",
    
    # Calendario
    "resource_calendar_id": "Horario de trabajo",
    "company_id": "Compañía",
}

MRP_WORKORDER_FIELDS = {
    "id": "ID",
    "name": "Nombre",
    "workcenter_id": "Centro de trabajo",
    "production_id": "Orden de producción",
    
    # Tiempos
    "duration": "Duración real",
    "duration_expected": "Duración esperada",
    "duration_percent": "% completado",
    
    # Estado
    "state": "Estado",
    "working_state": "Estado de trabajo",
    
    # Fechas
    "date_start": "Inicio",
    "date_finished": "Fin",
    "date_planned_start": "Inicio planeado",
    "date_planned_finished": "Fin planeado",
}


# ============================================================
# CRM (crm.lead)
# ============================================================
CRM_LEAD_FIELDS = {
    "id": "ID",
    "name": "Nombre oportunidad",
    "type": "Tipo (lead/oportunidad)",
    
    # Contacto
    "partner_id": "Contacto",
    "contact_name": "Nombre contacto",
    "email_from": "Email",
    "phone": "Teléfono",
    "mobile": "Móvil",
    
    # Equipo
    "user_id": "Vendedor",
    "team_id": "Equipo de ventas",
    "company_id": "Compañía",
    
    # Pipeline
    "stage_id": "Etapa",
    "priority": "Prioridad",
    "color": "Color",
    
    # Ingresos
    "expected_revenue": "Ingreso esperado",
    "prorated_revenue": "Ingreso prorrateado",
    "recurring_revenue": "Ingreso recurrente",
    "recurring_plan": "Plan recurrente",
    
    # Probabilidad
    "probability": "Probabilidad (%)",
    "automated_probability": "Probabilidad automática",
    
    # Fechas
    "date_deadline": "Cierre esperado",
    "date_open": "Fecha asignación",
    "date_conversion": "Fecha conversión",
    "date_closed": "Fecha cierre",
    
    # Resultado
    "won_status": "Estado ganado/perdido",
    "lost_reason_id": "Razón de pérdida",
    
    # Origen
    "source_id": "Fuente",
    "medium_id": "Medio",
    "campaign_id": "Campaña",
    
    # Estado
    "active": "Activo",
}

CRM_STAGE_FIELDS = {
    "id": "ID",
    "name": "Nombre",
    "sequence": "Secuencia",
    "is_won": "Etapa ganada",
    "probability": "Probabilidad default",
    "team_id": "Equipo de ventas",
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_fields_for_agent(agent_name: str) -> dict[str, list[str]]:
    """Retorna los campos recomendados para cada agente."""
    
    AGENT_FIELDS = {
        "cobranza": {
            "account.move": list(ACCOUNT_MOVE_FIELDS.keys()),
            "account.move.line": list(ACCOUNT_MOVE_LINE_FIELDS.keys()),
            "res.partner": ["id", "name", "email", "phone", "credit_limit", "total_due", "total_overdue", "user_id"],
        },
        "ventas": {
            "sale.order": list(SALE_ORDER_FIELDS.keys()),
            "sale.order.line": list(SALE_ORDER_LINE_FIELDS.keys()),
            "account.move": ["id", "name", "partner_id", "amount_total", "amount_residual", "state", "move_type", "invoice_date"],
            "res.partner": ["id", "name", "customer_rank", "user_id", "team_id", "credit_limit"],
            "crm.lead": list(CRM_LEAD_FIELDS.keys()),
        },
        "compras": {
            "purchase.order": list(PURCHASE_ORDER_FIELDS.keys()),
            "stock.picking": list(STOCK_MOVE_FIELDS.keys()),
            "stock.warehouse.orderpoint": list(ORDERPOINT_FIELDS.keys()),
            "res.partner": ["id", "name", "supplier_rank"],
        },
        "inventario": {
            "product.template": list(PRODUCT_TEMPLATE_FIELDS.keys()),
            "product.product": ["id", "name", "default_code", "qty_available", "type", "categ_id", "standard_price", "list_price"],
            "stock.quant": list(STOCK_QUANT_FIELDS.keys()),
            "stock.move": list(STOCK_MOVE_FIELDS.keys()),
            "stock.warehouse.orderpoint": list(ORDERPOINT_FIELDS.keys()),
        },
        "finanzas": {
            "account.move": list(ACCOUNT_MOVE_FIELDS.keys()),
            "account.move.line": list(ACCOUNT_MOVE_LINE_FIELDS.keys()),
            "account.payment": ["id", "name", "amount", "currency_id", "date", "partner_id", "state"],
            "account.account": ["id", "name", "code", "account_type"],
            "account.journal": ["id", "name", "type", "company_id"],
        },
        "rrhh": {
            "hr.employee": list(HR_EMPLOYEE_FIELDS.keys()),
            "hr.attendance": list(HR_ATTENDANCE_FIELDS.keys()),
            "hr.leave": list(HR_LEAVE_FIELDS.keys()),
            "hr.department": ["id", "name", "manager_id", "parent_id"],
        },
        "produccion": {
            "mrp.production": list(MRP_PRODUCTION_FIELDS.keys()),
            "mrp.workcenter": list(MRP_WORKCENTER_FIELDS.keys()),
            "mrp.workorder": list(MRP_WORKORDER_FIELDS.keys()),
            "mrp.bom": ["id", "product_id", "product_tmpl_id", "product_qty"],
            "stock.move": list(STOCK_MOVE_FIELDS.keys()),
        },
    }
    
    return AGENT_FIELDS.get(agent_name, {})


def get_domain_for_company(company_id: int) -> list:
    """Retorna dominio de filtro por compañía."""
    return [("company_id", "=", company_id)]


def get_invoice_domain(
    move_type: str | list = None,
    state: str | list = None,
    payment_state: str | list = None,
    company_id: int = None,
) -> list:
    """Genera dominio para filtrar facturas."""
    domain = []
    
    if move_type:
        if isinstance(move_type, list):
            domain.append(("move_type", "in", move_type))
        else:
            domain.append(("move_type", "=", move_type))
    
    if state:
        if isinstance(state, list):
            domain.append(("state", "in", state))
        else:
            domain.append(("state", "=", state))
    
    if payment_state:
        if isinstance(payment_state, list):
            domain.append(("payment_state", "in", payment_state))
        else:
            domain.append(("payment_state", "=", payment_state))
    
    if company_id:
        domain.append(("company_id", "=", company_id))
    
    return domain
