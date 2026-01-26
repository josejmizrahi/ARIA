"""
Inspector Contextual de Ventas.

Analiza la gestión comercial en 4 niveles:
1. Vista general: Ventas vs presupuesto, pipeline, conversión
2. Por categorías: Por vendedor, categoría, región
3. Detalles: Cotizaciones vencidas, márgenes bajos, clientes inactivos
4. Anomalías: Pedidos sin vendedor, precios bajo costo
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class SalesInspector(BaseContextInspector):
    """Inspector contextual para Gestión Comercial."""
    
    AGENT_NAME = "ventas"
    AREA_NAME = "Gestión Comercial"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="inventario",
            dependency_type="upstream",
            data_flow="Disponibilidad de productos",
            criticality=ImpactLevel.CRITICAL,
            description="Ventas requiere stock disponible para vender"
        ),
        AgentDependency(
            agent_name="cobranza",
            dependency_type="upstream",
            data_flow="Estado crediticio de clientes",
            criticality=ImpactLevel.HIGH,
            description="Estado de crédito determina si se puede vender"
        ),
        AgentDependency(
            agent_name="costos",
            dependency_type="upstream",
            data_flow="Costo de productos",
            criticality=ImpactLevel.HIGH,
            description="Costo para calcular margen de venta"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="inventario",
            dependency_type="downstream",
            data_flow="Reservas y demanda",
            criticality=ImpactLevel.HIGH,
            description="Pedidos generan reservas de inventario"
        ),
        AgentDependency(
            agent_name="cobranza",
            dependency_type="downstream",
            data_flow="Facturas por cobrar",
            criticality=ImpactLevel.HIGH,
            description="Ventas genera facturas que cobra Cobranza"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="downstream",
            data_flow="Pedidos a fabricar",
            criticality=ImpactLevel.MEDIUM,
            description="Pedidos de productos fabricados generan OPs"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Proyección de ingresos",
            criticality=ImpactLevel.MEDIUM,
            description="Pipeline afecta proyección de flujo"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.inactive_days = 45
        self.quote_expiry_days = 30
        self.min_margin_pct = 15
        self.monthly_budget = 24_500_000  # Configurable
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de ventas."""
        
        # Ventas del mes (facturas)
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        invoices = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", first_day),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total_signed"],
            limit=5000
        )
        
        total_invoiced = sum(inv.get("amount_total_signed", 0) for inv in invoices)
        
        # Pedidos confirmados del mes
        orders = self._search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", first_day),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total"],
            limit=5000
        )
        
        total_orders = sum(o.get("amount_total", 0) for o in orders)
        
        # Calcular vs presupuesto
        budget_pct = (total_invoiced / self.monthly_budget * 100) if self.monthly_budget > 0 else 0
        
        # Health basado en cumplimiento de presupuesto
        day_of_month = datetime.now().day
        expected_pct = (day_of_month / 30) * 100  # Esperado linealmente
        
        if budget_pct >= expected_pct:
            health = 100
        else:
            health = (budget_pct / expected_pct) * 100 if expected_pct > 0 else 50
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=len(orders),
            total_value=total_invoiced,
            health_score=health,
            status=self._get_status_from_health(health),
            summary={
                "total_invoiced": total_invoiced,
                "total_orders": total_orders,
                "orders_count": len(orders),
                "budget": self.monthly_budget,
                "budget_pct": budget_pct,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de ventas."""
        
        summary = self._context.summary if self._context else {}
        
        # Comparativo vs presupuesto
        budget_pct = summary.get("budget_pct", 0)
        total_invoiced = summary.get("total_invoiced", 0)
        
        day_of_month = datetime.now().day
        expected_pct = (day_of_month / 30) * 100
        
        variance = budget_pct - expected_pct
        
        if variance < -20:
            self._add_finding(
                level=1,
                category="Presupuesto",
                title=f"🔴 Ventas {variance:.0f}% debajo de lo esperado",
                description=f"Facturado: {budget_pct:.0f}% vs esperado {expected_pct:.0f}% del presupuesto",
                severity=ImpactLevel.CRITICAL,
                affected_amount=self.monthly_budget * (expected_pct - budget_pct) / 100,
                impacts=[
                    self._increases_risk_for(
                        "ceo",
                        "Meta de ventas en riesgo",
                        f"A este ritmo no se alcanzará el presupuesto",
                        "Acciones comerciales urgentes"
                    ),
                    self._delays_agent(
                        "finanzas",
                        "Menor ingreso de efectivo",
                        "Flujo de caja afectado",
                        "Ajustar proyección"
                    ),
                ],
                solution="Implementar acciones comerciales urgentes"
            )
        elif variance < -10:
            self._add_finding(
                level=1,
                category="Presupuesto",
                title=f"⚠️ Ventas {variance:.0f}% debajo de lo esperado",
                description=f"Facturado: {budget_pct:.0f}% vs esperado {expected_pct:.0f}% del presupuesto",
                severity=ImpactLevel.HIGH,
                solution="Intensificar esfuerzos comerciales"
            )
        
        # Pipeline (cotizaciones)
        quotes = self._search_read(
            "sale.order",
            [
                ("state", "in", ["draft", "sent"]),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total", "date_order", "validity_date"],
            limit=1000
        )
        
        total_pipeline = sum(q.get("amount_total", 0) for q in quotes)
        
        if total_pipeline < self.monthly_budget * 0.5:
            self._add_finding(
                level=1,
                category="Pipeline",
                title=f"Pipeline bajo: {self._format_currency(total_pipeline)}",
                description=f"Pipeline < 50% del presupuesto mensual",
                severity=ImpactLevel.MEDIUM,
                affected_amount=total_pipeline,
                impacts=[
                    self._increases_risk_for(
                        "ceo",
                        "Pipeline insuficiente",
                        "No hay suficientes cotizaciones para alcanzar meta",
                        "Generar más oportunidades"
                    )
                ],
                solution="Aumentar prospección y cotizaciones"
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Análisis por vendedor y categoría."""
        
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        # Ventas por vendedor
        orders = self._search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", first_day),
                ("company_id", "=", self.company_id),
            ],
            ["user_id", "amount_total", "margin"],
            limit=5000
        )
        
        by_salesperson: dict[str, dict] = {}
        for order in orders:
            salesperson = self._safe_get_name(order, "user_id") or "Sin asignar"
            
            if salesperson not in by_salesperson:
                by_salesperson[salesperson] = {"sales": 0, "margin": 0, "count": 0}
            
            by_salesperson[salesperson]["sales"] += order.get("amount_total", 0)
            by_salesperson[salesperson]["margin"] += order.get("margin", 0)
            by_salesperson[salesperson]["count"] += 1
        
        # Vendedores sin ventas
        all_salespeople = self._search_read(
            "res.users",
            [("active", "=", True), ("share", "=", False)],
            ["name"],
            limit=100
        )
        
        active_sellers = set(by_salesperson.keys())
        inactive_sellers = [
            u.get("name") for u in all_salespeople
            if u.get("name") not in active_sellers
        ]
        
        if inactive_sellers and len(inactive_sellers) > 2:
            self._add_finding(
                level=2,
                category="Vendedores",
                title=f"{len(inactive_sellers)} vendedores sin ventas este mes",
                description="Usuarios activos sin pedidos confirmados",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(inactive_sellers),
                sample_data=[{"name": name} for name in inactive_sellers[:10]],
                solution="Revisar actividad y asignar cuentas"
            )
        
        # Margen por vendedor
        for salesperson, data in by_salesperson.items():
            if data["sales"] > 0:
                margin_pct = (data["margin"] / data["sales"]) * 100
                
                if margin_pct < self.min_margin_pct and data["sales"] > 100000:
                    self._add_finding(
                        level=2,
                        category="Margen",
                        title=f"Margen bajo para {salesperson}: {margin_pct:.1f}%",
                        description=f"Margen promedio por debajo del mínimo ({self.min_margin_pct}%)",
                        severity=ImpactLevel.HIGH,
                        affected_amount=data["sales"],
                        impacts=[
                            self._increases_cost_for(
                                "costos",
                                "Margen insuficiente",
                                f"Ventas de {salesperson} no son rentables",
                                "Revisar precios"
                            )
                        ],
                        solution=f"Revisar política de descuentos de {salesperson}"
                    )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Cotizaciones y clientes específicos."""
        
        # Cotizaciones por vencer
        today = datetime.now().strftime("%Y-%m-%d")
        soon = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        expiring_quotes = self._search_read(
            "sale.order",
            [
                ("state", "in", ["draft", "sent"]),
                ("validity_date", ">=", today),
                ("validity_date", "<=", soon),
                ("company_id", "=", self.company_id),
            ],
            ["name", "partner_id", "amount_total", "validity_date", "user_id"],
            limit=100,
            order="amount_total desc"
        )
        
        if expiring_quotes:
            total_expiring = sum(q.get("amount_total", 0) for q in expiring_quotes)
            
            self._add_finding(
                level=3,
                category="Cotizaciones",
                title=f"{len(expiring_quotes)} cotizaciones por vencer en 7 días",
                description=f"Pipeline en riesgo de perderse",
                severity=ImpactLevel.HIGH,
                affected_records=len(expiring_quotes),
                affected_amount=total_expiring,
                sample_data=[
                    {
                        "quote": q.get("name"),
                        "customer": self._safe_get_name(q, "partner_id"),
                        "amount": q.get("amount_total"),
                        "expires": q.get("validity_date"),
                        "salesperson": self._safe_get_name(q, "user_id"),
                    }
                    for q in expiring_quotes[:10]
                ],
                solution="Dar seguimiento urgente a cotizaciones",
                coordinated_actions=[
                    "VENTAS: Contactar clientes para cerrar",
                ]
            )
        
        # Clientes de alto valor inactivos
        days_ago = (datetime.now() - timedelta(days=self.inactive_days)).strftime("%Y-%m-%d")
        
        # Clientes con historial de compras
        top_customers = self._search_read(
            "res.partner",
            [
                ("customer_rank", ">", 0),
                ("active", "=", True),
            ],
            ["id", "name", "sale_order_count"],
            limit=500,
            order="sale_order_count desc"
        )
        
        inactive_valuable = []
        for customer in top_customers[:50]:  # Solo top 50
            # Verificar última orden
            last_order = self._search_read(
                "sale.order",
                [
                    ("partner_id", "=", customer["id"]),
                    ("state", "in", ["sale", "done"]),
                ],
                ["date_order"],
                limit=1,
                order="date_order desc"
            )
            
            if last_order:
                last_date = last_order[0].get("date_order", "")[:10]
                if last_date and last_date < days_ago:
                    customer["last_order"] = last_date
                    customer["days_inactive"] = self._days_between(last_date)
                    inactive_valuable.append(customer)
        
        if inactive_valuable:
            self._add_finding(
                level=3,
                category="Clientes",
                title=f"{len(inactive_valuable)} clientes top sin comprar en {self.inactive_days}+ días",
                description="Clientes de alto valor que no han comprado recientemente",
                severity=ImpactLevel.HIGH,
                affected_records=len(inactive_valuable),
                sample_data=[
                    {
                        "customer": c.get("name"),
                        "orders": c.get("sale_order_count"),
                        "last_order": c.get("last_order"),
                        "days": c.get("days_inactive"),
                    }
                    for c in sorted(inactive_valuable, key=lambda x: x.get("sale_order_count", 0), reverse=True)[:10]
                ],
                impacts=[
                    self._increases_risk_for(
                        "ceo",
                        "Pérdida de clientes valiosos",
                        "Clientes top sin actividad reciente",
                        "Reactivar relación"
                    )
                ],
                solution="Contactar para reactivar relación comercial"
            )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Pedidos sin vendedor
        no_salesperson = self._search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("user_id", "=", False),
                ("company_id", "=", self.company_id),
            ],
            ["name", "partner_id", "amount_total", "date_order"],
            limit=100
        )
        
        if no_salesperson:
            total_no_sales = sum(o.get("amount_total", 0) for o in no_salesperson)
            
            self._add_finding(
                level=4,
                category="Datos Faltantes",
                title=f"{len(no_salesperson)} pedidos sin vendedor asignado",
                description="Pedidos que no tienen vendedor responsable",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(no_salesperson),
                affected_amount=total_no_sales,
                solution="Asignar vendedor a pedidos huérfanos"
            )
        
        # Líneas con precio < costo
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        order_lines = self._search_read(
            "sale.order.line",
            [
                ("order_id.state", "in", ["sale", "done"]),
                ("order_id.date_order", ">=", first_day),
                ("price_unit", ">", 0),
                ("product_id", "!=", False),
            ],
            ["order_id", "product_id", "price_unit", "purchase_price", "margin"],
            limit=5000
        )
        
        negative_margin = [
            line for line in order_lines
            if line.get("margin", 0) < 0
        ]
        
        if negative_margin:
            total_loss = sum(abs(line.get("margin", 0)) for line in negative_margin)
            
            self._add_finding(
                level=4,
                category="Margen Negativo",
                title=f"🔴 {len(negative_margin)} líneas vendidas con pérdida",
                description="Productos vendidos por debajo del costo",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(negative_margin),
                affected_amount=total_loss,
                sample_data=[
                    {
                        "order": self._safe_get_name(line, "order_id"),
                        "product": self._safe_get_name(line, "product_id"),
                        "price": line.get("price_unit"),
                        "cost": line.get("purchase_price"),
                        "margin": line.get("margin"),
                    }
                    for line in sorted(negative_margin, key=lambda x: x.get("margin", 0))[:10]
                ],
                impacts=[
                    self._increases_cost_for(
                        "costos",
                        "Ventas a pérdida",
                        f"Se perdieron ${total_loss:,.0f} en margen negativo",
                        "Revisar precios mínimos"
                    )
                ],
                solution="Configurar precios mínimos y revisar descuentos",
                coordinated_actions=[
                    "COSTOS: Actualizar lista de precios mínimos",
                    "VENTAS: Capacitar sobre política de descuentos",
                ]
            )
        
        # Clientes sin vendedor asignado
        no_salesperson_customers = self._search_read(
            "res.partner",
            [
                ("customer_rank", ">", 0),
                ("active", "=", True),
                ("user_id", "=", False),
            ],
            ["name"],
            limit=500
        )
        
        if len(no_salesperson_customers) > 20:
            self._add_finding(
                level=4,
                category="Asignación",
                title=f"{len(no_salesperson_customers)} clientes sin vendedor asignado",
                description="Clientes que no tienen vendedor responsable",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(no_salesperson_customers),
                solution="Asignar vendedor a cada cliente"
            )
