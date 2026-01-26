"""
Inspector Contextual de Costos.

Analiza control de costos en 4 niveles:
1. Vista general: Valor inventario, margen promedio, variaciones
2. Por categorías: Margen por categoría, variación por proveedor
3. Detalles: Productos costo>=precio, costos desactualizados
4. Anomalías: Costo=0, costo negativo, inconsistencias

NOTA: En este sistema, los BOMs incluyen servicios (mano de obra) como líneas
de producto tipo servicio con un factor. Al producir, Odoo calcula el costo
como MP + (Servicio × Factor). Periódicamente se hace un asiento contable
para quitar el costo de los servicios y dejar el inventario a costo primo.
Esto significa que standard_price NO refleja el costo real del producto.
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class CostInspector(BaseContextInspector):
    """Inspector contextual para Control de Costos."""
    
    AGENT_NAME = "costos"
    AREA_NAME = "Control de Costos"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="compras",
            dependency_type="upstream",
            data_flow="Precio de compra",
            criticality=ImpactLevel.HIGH,
            description="Precios de compra determinan costo de materiales"
        ),
        AgentDependency(
            agent_name="inventario",
            dependency_type="upstream",
            data_flow="Cantidades en stock",
            criticality=ImpactLevel.HIGH,
            description="Stock para valorización"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="upstream",
            data_flow="Costos de manufactura",
            criticality=ImpactLevel.HIGH,
            description="Costo real de producción"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="downstream",
            data_flow="Margen mínimo",
            criticality=ImpactLevel.HIGH,
            description="Costo determina margen de venta"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Valorización contable",
            criticality=ImpactLevel.HIGH,
            description="Valor del inventario para estados financieros"
        ),
        AgentDependency(
            agent_name="ceo",
            dependency_type="downstream",
            data_flow="Rentabilidad",
            criticality=ImpactLevel.MEDIUM,
            description="Análisis de rentabilidad por producto/línea"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.min_margin_pct = 15
        self.variation_threshold_pct = 20
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de costos."""
        
        # Productos con stock y costo
        products = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("qty_available", ">", 0),
            ],
            ["qty_available", "standard_price", "list_price"],
            limit=5000
        )
        
        total_value = sum(
            p.get("qty_available", 0) * p.get("standard_price", 0)
            for p in products
        )
        
        # Productos con costo 0
        zero_cost = len([p for p in products if (p.get("standard_price") or 0) <= 0])
        
        # Productos costo >= precio
        cost_over_price = len([
            p for p in products
            if p.get("standard_price", 0) > 0 
            and p.get("list_price", 0) > 0
            and p.get("standard_price", 0) >= p.get("list_price", 0)
        ])
        
        # Health basado en problemas
        issues = zero_cost + cost_over_price
        health = self._calculate_health_score(
            total=len(products),
            with_issues=issues,
            critical_count=cost_over_price
        )
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=len(products),
            total_value=total_value,
            health_score=health,
            status=self._get_status_from_health(health),
            summary={
                "products_with_stock": len(products),
                "inventory_value": total_value,
                "zero_cost_count": zero_cost,
                "cost_over_price_count": cost_over_price,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de costos."""
        
        summary = self._context.summary if self._context else {}
        
        total_value = summary.get("inventory_value", 0)
        zero_cost = summary.get("zero_cost_count", 0)
        cost_over_price = summary.get("cost_over_price_count", 0)
        
        # Valor del inventario
        self._add_finding(
            level=1,
            category="Valorización",
            title=f"Valor del inventario: {self._format_currency(total_value)}",
            description="Valorización total del inventario a costo estándar",
            severity=ImpactLevel.INFO,
            affected_amount=total_value,
        )
        
        # Productos sin costo
        if zero_cost > 0:
            self._add_finding(
                level=1,
                category="Costos Faltantes",
                title=f"🔴 {zero_cost} productos sin costo definido",
                description="Productos con stock pero costo estándar = 0",
                severity=ImpactLevel.CRITICAL if zero_cost > 50 else ImpactLevel.HIGH,
                affected_records=zero_cost,
                impacts=[
                    self._create_impact(
                        "finanzas",
                        ImpactType.REDUCES_QUALITY,
                        "Valorización incorrecta",
                        f"{zero_cost} productos sin valor en inventario",
                        "Asignar costos"
                    ),
                    self._blocks_agent(
                        "ventas",
                        "No se conoce el margen",
                        "No se puede calcular rentabilidad",
                        "Definir costo antes de vender"
                    ),
                ],
                solution="Asignar costo estándar a productos"
            )
        
        # Productos vendiendo a pérdida
        if cost_over_price > 0:
            self._add_finding(
                level=1,
                category="Margen Negativo",
                title=f"🔴 {cost_over_price} productos con costo >= precio",
                description="Productos que se venderían a pérdida",
                severity=ImpactLevel.CRITICAL,
                affected_records=cost_over_price,
                impacts=[
                    self._increases_cost_for(
                        "ventas",
                        "Ventas a pérdida",
                        f"{cost_over_price} productos sin margen positivo",
                        "Ajustar precios o costos"
                    )
                ],
                solution="Revisar y ajustar precios de venta o costos",
                coordinated_actions=[
                    "VENTAS: Revisar lista de precios",
                    "COMPRAS: Renegociar con proveedores",
                ]
            )
        
        # Margen bruto promedio
        products = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("qty_available", ">", 0),
                ("standard_price", ">", 0),
                ("list_price", ">", 0),
            ],
            ["standard_price", "list_price"],
            limit=5000
        )
        
        if products:
            margins = [
                ((p.get("list_price", 0) - p.get("standard_price", 0)) / p.get("list_price", 1)) * 100
                for p in products
                if p.get("list_price", 0) > 0
            ]
            
            if margins:
                avg_margin = sum(margins) / len(margins)
                
                if avg_margin < self.min_margin_pct:
                    self._add_finding(
                        level=1,
                        category="Margen",
                        title=f"⚠️ Margen promedio bajo: {avg_margin:.1f}%",
                        description=f"Margen promedio por debajo del mínimo ({self.min_margin_pct}%)",
                        severity=ImpactLevel.HIGH,
                        impacts=[
                            self._increases_risk_for(
                                "ceo",
                                "Rentabilidad en riesgo",
                                f"Margen promedio {avg_margin:.1f}% < {self.min_margin_pct}%",
                                "Revisar estructura de precios"
                            )
                        ],
                        solution="Revisar política de precios y costos"
                    )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por categoría y proveedor."""
        
        # Margen por categoría
        products = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("standard_price", ">", 0),
                ("list_price", ">", 0),
            ],
            ["categ_id", "standard_price", "list_price"],
            limit=5000
        )
        
        by_category: dict[str, dict] = {}
        for p in products:
            categ = self._safe_get_name(p, "categ_id") or "Sin categoría"
            
            if categ not in by_category:
                by_category[categ] = {"count": 0, "total_cost": 0, "total_price": 0}
            
            by_category[categ]["count"] += 1
            by_category[categ]["total_cost"] += p.get("standard_price", 0)
            by_category[categ]["total_price"] += p.get("list_price", 0)
        
        # Categorías con margen bajo
        low_margin_categories = []
        for categ, data in by_category.items():
            if data["total_price"] > 0:
                margin = ((data["total_price"] - data["total_cost"]) / data["total_price"]) * 100
                if margin < self.min_margin_pct:
                    low_margin_categories.append({
                        "category": categ,
                        "margin": margin,
                        "products": data["count"],
                    })
        
        if low_margin_categories:
            self._add_finding(
                level=2,
                category="Margen por Categoría",
                title=f"{len(low_margin_categories)} categorías con margen bajo",
                description=f"Categorías con margen < {self.min_margin_pct}%",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(low_margin_categories),
                sample_data=sorted(low_margin_categories, key=lambda x: x["margin"])[:10],
                solution="Revisar precios por categoría"
            )
        
        # Análisis de servicios en BOMs (problema específico de este sistema)
        if self._model_exists("mrp.bom.line"):
            service_lines = self._search_read(
                "mrp.bom.line",
                [("product_id.type", "=", "service")],
                ["bom_id", "product_id", "product_qty"],
                limit=500
            )
            
            if service_lines:
                boms_with_services = len(set(
                    self._safe_get_id(l, "bom_id") for l in service_lines
                ))
                
                self._add_finding(
                    level=2,
                    category="BOMs con Servicios",
                    title=f"ℹ️ {boms_with_services} BOMs incluyen servicios como MO",
                    description="BOMs que tienen servicios (mano de obra) como componentes",
                    severity=ImpactLevel.INFO,
                    affected_records=boms_with_services,
                    sample_data=[
                        {
                            "bom": self._safe_get_name(l, "bom_id"),
                            "service": self._safe_get_name(l, "product_id"),
                        }
                        for l in service_lines[:10]
                    ],
                    solution="NOTA: El costo estándar incluye MO que se ajusta contablemente",
                    coordinated_actions=[
                        "COSTOS: El standard_price NO refleja costo primo real",
                        "CONTABILIDAD: Ajuste periódico para quitar costo de servicios",
                    ]
                )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Productos específicos con problemas."""
        
        # Productos con costo = 0 y stock > 0
        zero_cost_products = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("qty_available", ">", 0),
                "|",
                ("standard_price", "=", 0),
                ("standard_price", "=", False),
            ],
            ["name", "default_code", "qty_available", "categ_id"],
            limit=100
        )
        
        if zero_cost_products:
            self._add_finding(
                level=3,
                category="Sin Costo",
                title=f"{len(zero_cost_products)} productos sin costo con stock",
                description="Detalle de productos que necesitan costo",
                severity=ImpactLevel.HIGH,
                affected_records=len(zero_cost_products),
                sample_data=[
                    {
                        "product": p.get("name"),
                        "code": p.get("default_code"),
                        "qty": p.get("qty_available"),
                        "category": self._safe_get_name(p, "categ_id"),
                    }
                    for p in zero_cost_products[:15]
                ],
                solution="Asignar costo estándar"
            )
        
        # Productos con costo > precio
        cost_over_price = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("standard_price", ">", 0),
                ("list_price", ">", 0),
            ],
            ["name", "default_code", "standard_price", "list_price", "qty_available"],
            limit=5000
        )
        
        over_price = [
            p for p in cost_over_price
            if p.get("standard_price", 0) >= p.get("list_price", 1)
        ]
        
        if over_price:
            potential_loss = sum(
                (p.get("standard_price", 0) - p.get("list_price", 0)) * p.get("qty_available", 0)
                for p in over_price
            )
            
            self._add_finding(
                level=3,
                category="Costo >= Precio",
                title=f"{len(over_price)} productos con margen negativo",
                description=f"Pérdida potencial: {self._format_currency(potential_loss)}",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(over_price),
                affected_amount=potential_loss,
                sample_data=[
                    {
                        "product": p.get("name"),
                        "code": p.get("default_code"),
                        "cost": p.get("standard_price"),
                        "price": p.get("list_price"),
                        "diff": p.get("standard_price", 0) - p.get("list_price", 0),
                    }
                    for p in sorted(over_price, key=lambda x: x.get("standard_price", 0) - x.get("list_price", 0), reverse=True)[:15]
                ],
                impacts=[
                    self._blocks_agent(
                        "ventas",
                        "Venta genera pérdida",
                        f"Cada venta de estos productos pierde dinero",
                        "No vender hasta corregir"
                    )
                ],
                solution="Ajustar precio de venta o renegociar costo"
            )
        
        # Variaciones de costo significativas
        # Comparar costo actual vs último precio de compra
        products_with_purchase = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("standard_price", ">", 0),
            ],
            ["id", "name", "standard_price"],
            limit=500
        )
        
        variations = []
        for prod in products_with_purchase[:100]:  # Limitar verificación
            last_purchase = self._search_read(
                "purchase.order.line",
                [
                    ("product_id", "=", prod["id"]),
                    ("order_id.state", "in", ["purchase", "done"]),
                ],
                ["price_unit", "date_order"],
                limit=1,
                order="date_order desc"
            )
            
            if last_purchase:
                purchase_price = last_purchase[0].get("price_unit", 0)
                standard = prod.get("standard_price", 0)
                
                if standard > 0 and purchase_price > 0:
                    variation = ((purchase_price - standard) / standard) * 100
                    
                    if abs(variation) > self.variation_threshold_pct:
                        variations.append({
                            "product": prod.get("name"),
                            "standard": standard,
                            "purchase": purchase_price,
                            "variation": variation,
                        })
        
        if variations:
            self._add_finding(
                level=3,
                category="Variaciones",
                title=f"{len(variations)} productos con variación de costo >{self.variation_threshold_pct}%",
                description="Diferencia significativa entre costo estándar y última compra",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(variations),
                sample_data=sorted(variations, key=lambda x: abs(x["variation"]), reverse=True)[:10],
                solution="Actualizar costos estándar o revisar precios de compra"
            )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Productos con costo negativo (error grave)
        negative_cost = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("standard_price", "<", 0),
            ],
            ["name", "default_code", "standard_price"],
            limit=100
        )
        
        if negative_cost:
            self._add_finding(
                level=4,
                category="Error de Datos",
                title=f"🔴 {len(negative_cost)} productos con costo NEGATIVO",
                description="Costo negativo es un error de datos",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(negative_cost),
                sample_data=[
                    {
                        "product": p.get("name"),
                        "code": p.get("default_code"),
                        "cost": p.get("standard_price"),
                    }
                    for p in negative_cost[:10]
                ],
                impacts=[
                    self._create_impact(
                        "finanzas",
                        ImpactType.REDUCES_QUALITY,
                        "Valorización incorrecta",
                        "El inventario tiene valor negativo erróneo",
                        "Corregir costos"
                    )
                ],
                solution="Corregir costos negativos inmediatamente"
            )
        
        # Productos vendibles sin lista de precios
        no_price = self._search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("sale_ok", "=", True),
                "|",
                ("list_price", "=", 0),
                ("list_price", "=", False),
            ],
            ["name", "default_code"],
            limit=100
        )
        
        if no_price:
            self._add_finding(
                level=4,
                category="Sin Precio",
                title=f"{len(no_price)} productos vendibles sin precio",
                description="Productos marcados como vendibles pero sin precio de venta",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(no_price),
                sample_data=[
                    {"product": p.get("name"), "code": p.get("default_code")}
                    for p in no_price[:10]
                ],
                solution="Asignar precio de venta o desmarcar como vendible"
            )
        
        # Discrepancias entre BOM cost y standard_price (si MRP está instalado)
        if self._model_exists("mrp.bom"):
            # Productos con BOM
            products_with_bom = self._search_read(
                "product.product",
                [
                    ("type", "=", "product"),
                    ("bom_count", ">", 0),
                    ("standard_price", ">", 0),
                ],
                ["id", "name", "standard_price"],
                limit=100
            )
            
            # Nota: La discrepancia es esperada porque standard_price incluye
            # servicios que luego se ajustan contablemente
            if products_with_bom:
                self._add_finding(
                    level=4,
                    category="Costos BOM",
                    title=f"ℹ️ {len(products_with_bom)} productos manufacturados",
                    description="Recordatorio: standard_price incluye MO que se ajusta contablemente",
                    severity=ImpactLevel.INFO,
                    affected_records=len(products_with_bom),
                    solution="El costo primo real debe calcularse sin servicios de MO",
                    coordinated_actions=[
                        "COSTOS: Para costo primo: standard_price - (servicios × factor)",
                        "CONTABILIDAD: Mantener ajuste periódico de MO",
                    ]
                )
