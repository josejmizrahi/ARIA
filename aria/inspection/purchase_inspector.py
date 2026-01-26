"""
Inspector Contextual de Compras.

Analiza aprovisionamiento en 4 niveles:
1. Vista general: OC abiertas, entregas esperadas, OTIF
2. Por categorías: Por proveedor, categoría, lead time
3. Detalles: OC pendientes, productos sin proveedor, variaciones
4. Anomalías: OC vencidas, duplicados posibles
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class PurchaseInspector(BaseContextInspector):
    """Inspector contextual para Aprovisionamiento."""
    
    AGENT_NAME = "compras"
    AREA_NAME = "Aprovisionamiento"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="inventario",
            dependency_type="upstream",
            data_flow="Necesidades de stock",
            criticality=ImpactLevel.HIGH,
            description="Inventario genera necesidades de reabastecimiento"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="upstream",
            data_flow="Materiales requeridos",
            criticality=ImpactLevel.HIGH,
            description="Producción requiere materiales"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="inventario",
            dependency_type="downstream",
            data_flow="Recepciones",
            criticality=ImpactLevel.HIGH,
            description="Compras genera recepciones de inventario"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Cuentas por pagar",
            criticality=ImpactLevel.HIGH,
            description="Compras genera CxP"
        ),
        AgentDependency(
            agent_name="costos",
            dependency_type="downstream",
            data_flow="Precios de compra",
            criticality=ImpactLevel.HIGH,
            description="Precios afectan costo de productos"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="downstream",
            data_flow="Materiales",
            criticality=ImpactLevel.CRITICAL,
            description="Producción espera materiales de OC"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.late_approval_days = 3
        self.single_supplier_threshold = 1
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de compras."""
        
        # OC abiertas
        open_orders = self._search_read(
            "purchase.order",
            [("state", "in", ["draft", "sent", "to approve", "purchase"])],
            ["amount_total", "state"],
            limit=1000
        )
        
        total_open = sum(o.get("amount_total", 0) for o in open_orders)
        
        # OC pendientes de aprobar > 3 días
        three_days_ago = (datetime.now() - timedelta(days=self.late_approval_days)).strftime("%Y-%m-%d")
        pending_approval = self._search_count(
            "purchase.order",
            [
                ("state", "in", ["draft", "sent", "to approve"]),
                ("date_order", "<", three_days_ago),
            ]
        )
        
        health = 100 - (pending_approval * 5)
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=len(open_orders),
            total_value=total_open,
            health_score=max(0, min(100, health)),
            status=self._get_status_from_health(max(0, min(100, health))),
            summary={
                "open_orders": len(open_orders),
                "total_open_value": total_open,
                "pending_approval": pending_approval,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de compras."""
        
        summary = self._context.summary if self._context else {}
        total_open = summary.get("total_open_value", 0)
        
        # OC abiertas
        self._add_finding(
            level=1,
            category="OC Abiertas",
            title=f"OC abiertas: {self._format_currency(total_open)}",
            description=f"{summary.get('open_orders', 0)} órdenes de compra pendientes",
            severity=ImpactLevel.INFO,
            affected_amount=total_open,
        )
        
        # Entregas esperadas esta semana
        week_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        deliveries = self._search_read(
            "purchase.order",
            [
                ("state", "=", "purchase"),
                ("date_planned", ">=", today),
                ("date_planned", "<=", week_end),
            ],
            ["name", "partner_id", "amount_total", "date_planned"],
            limit=100
        )
        
        total_deliveries = sum(d.get("amount_total", 0) for d in deliveries)
        
        if deliveries:
            self._add_finding(
                level=1,
                category="Entregas",
                title=f"{len(deliveries)} entregas esperadas esta semana",
                description=f"Valor: {self._format_currency(total_deliveries)}",
                severity=ImpactLevel.INFO,
                affected_records=len(deliveries),
                affected_amount=total_deliveries,
                sample_data=[
                    {
                        "po": d.get("name"),
                        "vendor": self._safe_get_name(d, "partner_id"),
                        "date": d.get("date_planned"),
                    }
                    for d in deliveries[:5]
                ],
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por proveedor y categoría."""
        
        # Compras por proveedor (concentración)
        orders = self._search_read(
            "purchase.order",
            [("state", "=", "purchase")],
            ["partner_id", "amount_total"],
            limit=1000
        )
        
        by_vendor: dict[str, float] = {}
        for o in orders:
            vendor = self._safe_get_name(o, "partner_id")
            by_vendor[vendor] = by_vendor.get(vendor, 0) + o.get("amount_total", 0)
        
        total = sum(by_vendor.values())
        
        if total > 0 and by_vendor:
            sorted_vendors = sorted(by_vendor.items(), key=lambda x: x[1], reverse=True)
            top_vendor = sorted_vendors[0]
            top_pct = (top_vendor[1] / total) * 100
            
            if top_pct > 50:
                self._add_finding(
                    level=2,
                    category="Concentración",
                    title=f"Alta dependencia: {top_vendor[0]} = {top_pct:.0f}%",
                    description="Un solo proveedor concentra más del 50% de las compras",
                    severity=ImpactLevel.HIGH,
                    affected_amount=top_vendor[1],
                    impacts=[
                        self._increases_risk_for(
                            "ceo",
                            "Riesgo de proveedor único",
                            "Problemas con este proveedor afectarían operación",
                            "Diversificar proveedores"
                        )
                    ],
                    solution="Desarrollar proveedores alternativos"
                )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: OC específicas con problemas."""
        
        # OC pendientes de aprobar > 3 días
        three_days_ago = (datetime.now() - timedelta(days=self.late_approval_days)).strftime("%Y-%m-%d")
        
        pending = self._search_read(
            "purchase.order",
            [
                ("state", "in", ["draft", "sent", "to approve"]),
                ("date_order", "<", three_days_ago),
            ],
            ["name", "partner_id", "amount_total", "date_order", "user_id"],
            limit=50,
            order="date_order asc"
        )
        
        if pending:
            total_pending = sum(p.get("amount_total", 0) for p in pending)
            
            self._add_finding(
                level=3,
                category="Aprobación",
                title=f"⚠️ {len(pending)} OC pendientes > {self.late_approval_days} días",
                description="Órdenes de compra sin aprobar por mucho tiempo",
                severity=ImpactLevel.HIGH,
                affected_records=len(pending),
                affected_amount=total_pending,
                sample_data=[
                    {
                        "po": p.get("name"),
                        "vendor": self._safe_get_name(p, "partner_id"),
                        "amount": p.get("amount_total"),
                        "date": p.get("date_order"),
                        "buyer": self._safe_get_name(p, "user_id"),
                    }
                    for p in pending[:10]
                ],
                impacts=[
                    self._delays_agent(
                        "inventario",
                        "Retraso en reabastecimiento",
                        "OC sin aprobar retrasan llegada de mercancía",
                        "Aprobar OC urgentes"
                    ),
                    self._delays_agent(
                        "produccion",
                        "Posible falta de material",
                        "Si son componentes, puede afectar producción",
                        "Verificar urgencia"
                    ),
                ],
                solution="Revisar y aprobar OC pendientes",
            )
        
        # Productos sin proveedor configurado
        products = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("active", "=", True),
                ("purchase_ok", "=", True),
            ],
            ["id", "name"],
            limit=1000
        )
        
        products_with_supplier = set()
        supplierinfo = self._search_read(
            "product.supplierinfo",
            [],
            ["product_id", "product_tmpl_id"],
            limit=5000
        )
        
        for si in supplierinfo:
            if si.get("product_id"):
                products_with_supplier.add(self._safe_get_id(si, "product_id"))
        
        no_supplier = [
            p for p in products
            if p["id"] not in products_with_supplier
        ]
        
        if len(no_supplier) > 10:
            self._add_finding(
                level=3,
                category="Proveedores",
                title=f"{len(no_supplier)} productos comprables sin proveedor",
                description="Productos marcados como comprables pero sin proveedor configurado",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(no_supplier),
                sample_data=[{"product": p.get("name")} for p in no_supplier[:10]],
                solution="Configurar proveedores para productos"
            )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # OC con fecha de entrega vencida
        late_orders = self._search_read(
            "purchase.order",
            [
                ("state", "=", "purchase"),
                ("date_planned", "<", today),
            ],
            ["name", "partner_id", "amount_total", "date_planned"],
            limit=100,
            order="date_planned asc"
        )
        
        if late_orders:
            total_late = sum(o.get("amount_total", 0) for o in late_orders)
            
            self._add_finding(
                level=4,
                category="Entregas Vencidas",
                title=f"🔴 {len(late_orders)} OC con entrega vencida",
                description="Órdenes de compra cuya fecha de entrega ya pasó",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(late_orders),
                affected_amount=total_late,
                sample_data=[
                    {
                        "po": o.get("name"),
                        "vendor": self._safe_get_name(o, "partner_id"),
                        "amount": o.get("amount_total"),
                        "planned": o.get("date_planned"),
                        "days_late": self._days_between(o.get("date_planned")),
                    }
                    for o in late_orders[:10]
                ],
                impacts=[
                    self._blocks_agent(
                        "inventario",
                        "Material no llegó",
                        f"{len(late_orders)} entregas pendientes vencidas",
                        "Contactar proveedores"
                    ),
                    self._delays_agent(
                        "produccion",
                        "Falta de material",
                        "Puede haber OPs esperando este material",
                        "Escalar urgentemente"
                    ),
                ],
                solution="Contactar proveedores y actualizar fechas",
                coordinated_actions=[
                    "COMPRAS: Llamar a proveedores",
                    "PRODUCCION: Verificar si afecta OPs",
                ]
            )
        
        # Posibles OC duplicadas (mismo proveedor, monto, fecha)
        recent_orders = self._search_read(
            "purchase.order",
            [
                ("state", "in", ["draft", "sent", "purchase"]),
                ("date_order", ">=", (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")),
            ],
            ["partner_id", "amount_total", "date_order", "name"],
            limit=500
        )
        
        seen = set()
        duplicates = []
        
        for o in recent_orders:
            key = (
                self._safe_get_id(o, "partner_id"),
                round(o.get("amount_total", 0), 2),
            )
            
            if key in seen:
                duplicates.append(o)
            else:
                seen.add(key)
        
        if duplicates:
            self._add_finding(
                level=4,
                category="Posibles Duplicados",
                title=f"⚠️ {len(duplicates)} OC posiblemente duplicadas",
                description="OC con mismo proveedor y monto en 7 días",
                severity=ImpactLevel.HIGH,
                affected_records=len(duplicates),
                sample_data=[
                    {
                        "po": d.get("name"),
                        "vendor": self._safe_get_name(d, "partner_id"),
                        "amount": d.get("amount_total"),
                    }
                    for d in duplicates[:10]
                ],
                solution="Verificar y cancelar duplicados"
            )
