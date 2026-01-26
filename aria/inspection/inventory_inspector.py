"""
Inspector Contextual de Inventario.

Analiza el estado del inventario en 4 niveles:
1. Vista general: Valor total, cobertura, rotación
2. Por categorías: Stock por categoría, almacén, clasificación ABC
3. Detalles: Productos bajo mínimo, sobre máximo, slow-moving
4. Anomalías: Stock negativo, lotes vencidos, sin regla de reorden
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AgentImpact,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class InventoryInspector(BaseContextInspector):
    """Inspector contextual para Control de Inventario."""
    
    AGENT_NAME = "inventario"
    AREA_NAME = "Control de Inventario"
    
    # Dependencias upstream (me alimentan)
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="compras",
            dependency_type="upstream",
            data_flow="Recepciones de mercancía",
            criticality=ImpactLevel.HIGH,
            description="Compras genera recepciones que incrementan el stock"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="upstream",
            data_flow="Productos terminados",
            criticality=ImpactLevel.HIGH,
            description="Producción genera productos terminados al inventario"
        ),
    ]
    
    # Dependencias downstream (dependen de mí)
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="downstream",
            data_flow="Disponibilidad de productos",
            criticality=ImpactLevel.CRITICAL,
            description="Ventas requiere stock disponible para vender"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="downstream",
            data_flow="Materiales para fabricar",
            criticality=ImpactLevel.CRITICAL,
            description="Producción requiere materiales del inventario"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Valorización de inventario",
            criticality=ImpactLevel.HIGH,
            description="Finanzas usa el valor del inventario para reportes"
        ),
        AgentDependency(
            agent_name="costos",
            dependency_type="downstream",
            data_flow="Costo de productos",
            criticality=ImpactLevel.HIGH,
            description="Costos usa el costo de inventario para análisis"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.slow_moving_days = 90
        self.expiry_warning_days = 30
        self.overstock_months = 6
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general del inventario."""
        
        # Total de productos almacenables con stock
        products = self._search_read(
            "product.product",
            [("type", "=", "product"), ("qty_available", ">", 0)],
            ["id", "qty_available", "standard_price"],
            limit=5000
        )
        
        total_products = len(products)
        total_value = sum(
            p.get("qty_available", 0) * p.get("standard_price", 0)
            for p in products
        )
        total_units = sum(p.get("qty_available", 0) for p in products)
        
        # Productos con stock negativo (problema grave)
        negative_count = self._search_count(
            "product.product",
            [("type", "=", "product"), ("qty_available", "<", -0.01)]
        )
        
        # Calcular health score inicial
        health = self._calculate_health_score(
            total=total_products,
            with_issues=negative_count,
            critical_count=negative_count
        )
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=total_products,
            total_value=total_value,
            health_score=health,
            status=self._get_status_from_health(health),
            summary={
                "total_products": total_products,
                "total_value": total_value,
                "total_units": total_units,
                "negative_stock_count": negative_count,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales del inventario."""
        
        # KPI: Valor total del inventario
        total_value = self._context.total_value if self._context else 0
        
        if total_value == 0:
            self._add_finding(
                level=1,
                category="Valorización",
                title="Inventario sin valor",
                description="El inventario tiene valor cero o no hay productos con stock",
                severity=ImpactLevel.HIGH,
                impacts=[
                    self._increases_risk_for(
                        "finanzas",
                        "Inventario sin valorizar",
                        "Reportes financieros incorrectos",
                        "Revisar costos de productos"
                    )
                ],
                solution="Verificar costos estándar de productos"
            )
        
        # KPI: Distribución por almacén
        warehouses = self._search_read(
            "stock.warehouse",
            [("company_id", "=", self.company_id)],
            ["name", "lot_stock_id"],
            limit=50
        )
        
        if len(warehouses) > 1:
            # Analizar distribución
            self._add_finding(
                level=1,
                category="Distribución",
                title=f"Inventario en {len(warehouses)} almacenes",
                description=f"Distribución de inventario entre múltiples almacenes",
                severity=ImpactLevel.INFO,
                affected_records=len(warehouses),
            )
        
        # KPI: Productos sin movimiento (cobertura general)
        date_limit = (datetime.now() - timedelta(days=self.slow_moving_days)).strftime("%Y-%m-%d")
        
        # Contar productos con stock pero sin movimientos recientes
        products_with_stock = self._search_read(
            "product.product",
            [("type", "=", "product"), ("qty_available", ">", 0)],
            ["id"],
            limit=5000
        )
        
        if products_with_stock:
            product_ids = [p["id"] for p in products_with_stock]
            
            # Productos con movimientos recientes
            recent_moves = self._search_read(
                "stock.move",
                [
                    ("product_id", "in", product_ids[:500]),  # Limitar
                    ("state", "=", "done"),
                    ("date", ">=", date_limit),
                ],
                ["product_id"],
                limit=5000
            )
            
            products_with_movement = {m["product_id"][0] for m in recent_moves if m.get("product_id")}
            slow_moving_count = len(product_ids) - len(products_with_movement)
            
            if slow_moving_count > 0:
                pct = (slow_moving_count / len(product_ids)) * 100
                
                severity = ImpactLevel.HIGH if pct > 30 else ImpactLevel.MEDIUM if pct > 15 else ImpactLevel.LOW
                
                self._add_finding(
                    level=1,
                    category="Rotación",
                    title=f"{slow_moving_count} productos sin movimiento ({pct:.0f}%)",
                    description=f"Productos con stock pero sin movimiento en {self.slow_moving_days} días",
                    severity=severity,
                    affected_records=slow_moving_count,
                    impacts=[
                        self._increases_cost_for(
                            "finanzas",
                            "Capital inmovilizado",
                            f"{pct:.0f}% del inventario sin rotar",
                            "Evaluar liquidación o promociones"
                        )
                    ],
                    solution="Revisar productos slow-moving para liquidación"
                )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Análisis por categorías."""
        
        # Stock por categoría de producto
        products = self._search_read(
            "product.product",
            [("type", "=", "product"), ("qty_available", ">", 0)],
            ["categ_id", "qty_available", "standard_price"],
            limit=5000
        )
        
        by_category: dict[str, dict] = {}
        for p in products:
            categ_name = self._safe_get_name(p, "categ_id") or "Sin categoría"
            if categ_name not in by_category:
                by_category[categ_name] = {"count": 0, "value": 0, "units": 0}
            
            qty = p.get("qty_available", 0)
            value = qty * p.get("standard_price", 0)
            
            by_category[categ_name]["count"] += 1
            by_category[categ_name]["value"] += value
            by_category[categ_name]["units"] += qty
        
        # Identificar categorías sin stock
        if "Sin categoría" in by_category and by_category["Sin categoría"]["count"] > 0:
            self._add_finding(
                level=2,
                category="Categorización",
                title=f"{by_category['Sin categoría']['count']} productos sin categoría",
                description="Productos que no tienen categoría asignada",
                severity=ImpactLevel.LOW,
                affected_records=by_category["Sin categoría"]["count"],
                solution="Asignar categorías a productos"
            )
        
        # Análisis ABC (si hay suficientes productos)
        if len(by_category) >= 3:
            sorted_categories = sorted(
                by_category.items(),
                key=lambda x: x[1]["value"],
                reverse=True
            )
            
            total_value = sum(c[1]["value"] for c in sorted_categories)
            
            if total_value > 0:
                # Top 3 categorías
                top_categories = sorted_categories[:3]
                top_value = sum(c[1]["value"] for c in top_categories)
                top_pct = (top_value / total_value) * 100
                
                self._add_finding(
                    level=2,
                    category="Concentración",
                    title=f"Top 3 categorías = {top_pct:.0f}% del valor",
                    description=f"Las 3 categorías principales concentran {top_pct:.0f}% del valor del inventario",
                    severity=ImpactLevel.INFO if top_pct < 80 else ImpactLevel.MEDIUM,
                    affected_amount=top_value,
                    sample_data=[
                        {"category": c[0], "value": c[1]["value"], "products": c[1]["count"]}
                        for c in top_categories
                    ],
                )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Registros específicos con problemas."""
        
        # Productos bajo punto de reorden
        orderpoints = self._search_read(
            "stock.warehouse.orderpoint",
            [("product_min_qty", ">", 0)],
            ["product_id", "product_min_qty", "product_max_qty", "qty_to_order"],
            limit=500
        )
        
        below_min = [op for op in orderpoints if op.get("qty_to_order", 0) > 0]
        
        if below_min:
            self._add_finding(
                level=3,
                category="Stock Mínimo",
                title=f"{len(below_min)} productos bajo punto de reorden",
                description="Productos que necesitan reabastecimiento",
                severity=ImpactLevel.HIGH,
                affected_records=len(below_min),
                sample_data=[
                    {
                        "product": self._safe_get_name(op, "product_id"),
                        "min": op.get("product_min_qty"),
                        "to_order": op.get("qty_to_order"),
                    }
                    for op in below_min[:10]
                ],
                impacts=[
                    self._blocks_agent(
                        "ventas",
                        "Stock insuficiente",
                        f"{len(below_min)} productos podrían agotarse",
                        "Generar órdenes de compra"
                    ),
                    self._blocks_agent(
                        "produccion",
                        "Falta de materiales",
                        "Puede detener producción si son materias primas",
                        "Verificar si son componentes de producción"
                    ),
                ],
                solution="Generar órdenes de compra para productos bajo mínimo",
                coordinated_actions=[
                    "COMPRAS: Generar OC para productos bajo mínimo",
                    "VENTAS: Verificar pedidos que podrían afectarse",
                ]
            )
        
        # Productos sobre máximo (sobreinversión)
        over_max = [
            op for op in orderpoints
            if op.get("product_max_qty", 0) > 0 and op.get("qty_to_order", 0) < 0
        ]
        
        if over_max:
            self._add_finding(
                level=3,
                category="Sobrestock",
                title=f"{len(over_max)} productos sobre el máximo",
                description="Productos con stock superior al máximo configurado",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(over_max),
                impacts=[
                    self._increases_cost_for(
                        "finanzas",
                        "Capital sobreinvertido en inventario",
                        "Exceso de stock inmoviliza capital",
                        "Ajustar compras futuras"
                    )
                ],
                solution="Reducir compras futuras o evaluar promociones"
            )
        
        # Lotes próximos a vencer (si existe el módulo)
        if self._model_exists("stock.lot"):
            expiry_date = (datetime.now() + timedelta(days=self.expiry_warning_days)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")
            
            expiring_lots = self._search_read(
                "stock.lot",
                [
                    ("expiration_date", "<=", expiry_date),
                    ("expiration_date", ">=", today),
                    ("product_qty", ">", 0),
                ],
                ["name", "product_id", "expiration_date", "product_qty"],
                limit=100,
                order="expiration_date asc"
            )
            
            if expiring_lots:
                self._add_finding(
                    level=3,
                    category="Caducidad",
                    title=f"{len(expiring_lots)} lotes por vencer en {self.expiry_warning_days} días",
                    description="Lotes con fecha de caducidad próxima",
                    severity=ImpactLevel.HIGH,
                    affected_records=len(expiring_lots),
                    sample_data=[
                        {
                            "lot": lot.get("name"),
                            "product": self._safe_get_name(lot, "product_id"),
                            "expiry": lot.get("expiration_date"),
                            "qty": lot.get("product_qty"),
                        }
                        for lot in expiring_lots[:10]
                    ],
                    impacts=[
                        self._blocks_agent(
                            "ventas",
                            "Producto próximo a vencer",
                            "No se puede vender producto caducado",
                            "Vender con descuento antes de vencimiento"
                        )
                    ],
                    solution="Priorizar venta de lotes próximos a vencer",
                    coordinated_actions=[
                        "VENTAS: Ofrecer descuentos en productos por vencer",
                    ]
                )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Stock NEGATIVO (error grave)
        negative_products = self._search_read(
            "product.product",
            [("type", "=", "product"), ("qty_available", "<", -0.01)],
            ["name", "default_code", "qty_available"],
            limit=100
        )
        
        if negative_products:
            self._add_finding(
                level=4,
                category="Error de Datos",
                title=f"🔴 {len(negative_products)} productos con stock NEGATIVO",
                description="Stock negativo indica errores en movimientos o configuración",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(negative_products),
                sample_data=[
                    {
                        "product": p.get("name"),
                        "code": p.get("default_code"),
                        "qty": p.get("qty_available"),
                    }
                    for p in negative_products[:10]
                ],
                impacts=[
                    self._blocks_agent(
                        "ventas",
                        "Stock negativo impide ventas",
                        "Sistema puede bloquear o generar backorders incorrectos",
                        "Corregir inventario antes de vender"
                    ),
                    self._create_impact(
                        "finanzas",
                        ImpactType.REDUCES_QUALITY,
                        "Valorización incorrecta",
                        "El valor del inventario está distorsionado",
                        "Corregir stock antes de reportes"
                    ),
                ],
                solution="Investigar y corregir con ajustes de inventario",
                coordinated_actions=[
                    "INVENTARIO: Realizar conteo físico",
                    "CONTABILIDAD: Ajustar valorización después de corrección",
                ]
            )
        
        # Lotes VENCIDOS con stock (si existe el módulo)
        if self._model_exists("stock.lot"):
            today = datetime.now().strftime("%Y-%m-%d")
            
            expired_lots = self._search_read(
                "stock.lot",
                [
                    ("expiration_date", "<", today),
                    ("product_qty", ">", 0),
                ],
                ["name", "product_id", "expiration_date", "product_qty"],
                limit=100
            )
            
            if expired_lots:
                self._add_finding(
                    level=4,
                    category="Error de Datos",
                    title=f"🔴 {len(expired_lots)} lotes VENCIDOS con stock",
                    description="Lotes caducados que aún tienen stock registrado",
                    severity=ImpactLevel.CRITICAL,
                    affected_records=len(expired_lots),
                    sample_data=[
                        {
                            "lot": lot.get("name"),
                            "product": self._safe_get_name(lot, "product_id"),
                            "expired": lot.get("expiration_date"),
                            "qty": lot.get("product_qty"),
                        }
                        for lot in expired_lots[:10]
                    ],
                    impacts=[
                        self._blocks_agent(
                            "ventas",
                            "Producto caducado",
                            "No se puede vender producto vencido",
                            "Dar de baja lotes vencidos"
                        )
                    ],
                    solution="Dar de baja lotes vencidos con ajuste de inventario",
                    coordinated_actions=[
                        "INVENTARIO: Crear movimiento de baja por caducidad",
                        "CONTABILIDAD: Registrar pérdida por caducidad",
                    ]
                )
        
        # Productos almacenables sin regla de reorden
        storable_products = self._search_read(
            "product.product",
            [("type", "=", "product"), ("active", "=", True)],
            ["id", "name"],
            limit=5000
        )
        
        products_with_rule = self._search_read(
            "stock.warehouse.orderpoint",
            [],
            ["product_id"],
            limit=5000
        )
        
        products_with_rule_ids = {
            self._safe_get_id(r, "product_id")
            for r in products_with_rule
        }
        
        products_without_rule = [
            p for p in storable_products
            if p["id"] not in products_with_rule_ids
        ]
        
        if len(products_without_rule) > 10:  # Solo si es significativo
            pct = (len(products_without_rule) / len(storable_products)) * 100 if storable_products else 0
            
            self._add_finding(
                level=4,
                category="Configuración",
                title=f"{len(products_without_rule)} productos sin regla de reorden ({pct:.0f}%)",
                description="Productos almacenables que no tienen configurado punto de reorden",
                severity=ImpactLevel.MEDIUM if pct > 50 else ImpactLevel.LOW,
                affected_records=len(products_without_rule),
                impacts=[
                    self._increases_risk_for(
                        "compras",
                        "Sin alerta de reabastecimiento",
                        "Estos productos pueden agotarse sin aviso",
                        "Configurar reglas de reorden"
                    )
                ],
                solution="Configurar reglas de reorden para productos críticos"
            )
        
        # Discrepancias entre stock teórico y quants
        # Verificar si hay productos donde qty_available != sum(quants)
        sample_products = self._search_read(
            "product.product",
            [("type", "=", "product"), ("qty_available", "!=", 0)],
            ["id", "name", "qty_available"],
            limit=100
        )
        
        discrepancies = []
        for prod in sample_products[:20]:  # Verificar solo muestra
            quants = self._search_read(
                "stock.quant",
                [
                    ("product_id", "=", prod["id"]),
                    ("location_id.usage", "=", "internal"),
                ],
                ["quantity"],
                limit=100
            )
            
            quant_total = sum(q.get("quantity", 0) for q in quants)
            product_qty = prod.get("qty_available", 0)
            
            if abs(quant_total - product_qty) > 0.01:
                discrepancies.append({
                    "product": prod.get("name"),
                    "product_qty": product_qty,
                    "quant_total": quant_total,
                    "diff": product_qty - quant_total,
                })
        
        if discrepancies:
            self._add_finding(
                level=4,
                category="Inconsistencia",
                title=f"Posibles discrepancias de stock detectadas",
                description="Diferencias entre qty_available y suma de quants",
                severity=ImpactLevel.HIGH,
                affected_records=len(discrepancies),
                sample_data=discrepancies[:5],
                impacts=[
                    self._create_impact(
                        "finanzas",
                        ImpactType.REDUCES_QUALITY,
                        "Valorización puede ser incorrecta",
                        "Diferencias afectan el valor del inventario",
                        "Recalcular stock"
                    )
                ],
                solution="Ejecutar recálculo de stock o revisar movimientos"
            )
