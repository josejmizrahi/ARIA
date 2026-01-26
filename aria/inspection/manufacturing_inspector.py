"""
Inspector Contextual de Manufactura.

Analiza producción en 4 niveles:
1. Vista general: OPs en progreso, capacidad, producción vs plan
2. Por categorías: Por centro de trabajo, producto, eficiencia
3. Detalles: OPs retrasadas, bloqueadas, centros sobrecargados
4. Anomalías: Material reservado no consumido, BOMs desactualizadas
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class ManufacturingInspector(BaseContextInspector):
    """Inspector contextual para Manufactura."""
    
    AGENT_NAME = "produccion"
    AREA_NAME = "Manufactura"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="inventario",
            dependency_type="upstream",
            data_flow="Materiales disponibles",
            criticality=ImpactLevel.CRITICAL,
            description="Producción requiere materiales del inventario"
        ),
        AgentDependency(
            agent_name="ventas",
            dependency_type="upstream",
            data_flow="Demanda de productos",
            criticality=ImpactLevel.HIGH,
            description="Pedidos de venta generan necesidad de producción"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="inventario",
            dependency_type="downstream",
            data_flow="Productos terminados",
            criticality=ImpactLevel.HIGH,
            description="Producción entrega PT al inventario"
        ),
        AgentDependency(
            agent_name="ventas",
            dependency_type="downstream",
            data_flow="Disponibilidad de producto",
            criticality=ImpactLevel.HIGH,
            description="PT producidos están disponibles para venta"
        ),
        AgentDependency(
            agent_name="costos",
            dependency_type="downstream",
            data_flow="Costo de producción",
            criticality=ImpactLevel.HIGH,
            description="Costo real de manufactura para análisis"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.late_threshold_days = 1
        self.efficiency_warning = 80  # %
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de producción."""
        
        if not self._model_exists("mrp.production"):
            return AreaContext(
                area_name=self.AREA_NAME,
                status="unavailable",
                summary={"error": "Módulo MRP no instalado"}
            )
        
        # OPs en progreso
        in_progress = self._search_read(
            "mrp.production",
            [("state", "in", ["confirmed", "progress"])],
            ["name", "product_qty", "date_start", "date_finished"],
            limit=1000
        )
        
        total_ops = len(in_progress)
        
        # OPs retrasadas (fecha planificada < hoy)
        today = datetime.now().strftime("%Y-%m-%d")
        delayed = [
            op for op in in_progress
            if op.get("date_finished") and str(op.get("date_finished"))[:10] < today
        ]
        
        # Health basado en % de OPs retrasadas
        delayed_pct = (len(delayed) / total_ops * 100) if total_ops > 0 else 0
        health = max(0, 100 - delayed_pct * 2)  # -2% por cada OP retrasada
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=total_ops,
            total_value=0,  # No aplica valor monetario directo
            health_score=health,
            status=self._get_status_from_health(health),
            summary={
                "ops_in_progress": total_ops,
                "ops_delayed": len(delayed),
                "delayed_pct": delayed_pct,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de producción."""
        
        if not self._model_exists("mrp.production"):
            self._add_finding(
                level=1,
                category="Sistema",
                title="Módulo MRP no disponible",
                description="El módulo de manufactura no está instalado",
                severity=ImpactLevel.INFO,
            )
            return
        
        # OPs por estado
        states = {
            "draft": "Borrador",
            "confirmed": "Confirmada",
            "progress": "En Progreso",
            "to_close": "Por Cerrar",
            "done": "Completada",
            "cancel": "Cancelada",
        }
        
        ops_by_state = {}
        for state, label in states.items():
            count = self._search_count("mrp.production", [("state", "=", state)])
            if count > 0:
                ops_by_state[label] = count
        
        self._add_finding(
            level=1,
            category="Estado de OPs",
            title="Distribución de órdenes de producción",
            description="OPs por estado actual",
            severity=ImpactLevel.INFO,
            sample_data=[{"state": k, "count": v} for k, v in ops_by_state.items()],
        )
        
        # Producción del mes vs mes anterior
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        prev_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
        prev_month_end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        
        this_month = self._search_count(
            "mrp.production",
            [("state", "=", "done"), ("date_finished", ">=", first_day)]
        )
        
        last_month = self._search_count(
            "mrp.production",
            [
                ("state", "=", "done"),
                ("date_finished", ">=", prev_month_start),
                ("date_finished", "<=", prev_month_end),
            ]
        )
        
        if last_month > 0:
            variance = ((this_month - last_month) / last_month) * 100
            
            if variance < -20:
                self._add_finding(
                    level=1,
                    category="Volumen",
                    title=f"Producción {variance:.0f}% vs mes anterior",
                    description=f"Este mes: {this_month} OPs vs {last_month} el mes pasado",
                    severity=ImpactLevel.HIGH if variance < -30 else ImpactLevel.MEDIUM,
                    impacts=[
                        self._delays_agent(
                            "ventas",
                            "Menos producto disponible",
                            "Puede haber faltantes de producto terminado",
                            "Verificar causas"
                        )
                    ],
                    solution="Investigar causas de menor producción"
                )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por centro de trabajo y producto."""
        
        if not self._model_exists("mrp.production"):
            return
        
        # Eficiencia por centro de trabajo
        workcenters = self._search_read(
            "mrp.workcenter",
            [("active", "=", True)],
            ["name", "time_efficiency", "oee_target"],
            limit=50
        )
        
        low_efficiency = []
        for wc in workcenters:
            efficiency = wc.get("time_efficiency", 100)
            target = wc.get("oee_target", 85)
            
            if efficiency < self.efficiency_warning:
                low_efficiency.append({
                    "workcenter": wc.get("name"),
                    "efficiency": efficiency,
                    "target": target,
                })
        
        if low_efficiency:
            self._add_finding(
                level=2,
                category="Eficiencia",
                title=f"{len(low_efficiency)} centros con baja eficiencia",
                description=f"Centros de trabajo por debajo de {self.efficiency_warning}%",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(low_efficiency),
                sample_data=low_efficiency,
                impacts=[
                    self._increases_cost_for(
                        "costos",
                        "Ineficiencia productiva",
                        "Mayor costo por unidad producida",
                        "Mejorar procesos"
                    )
                ],
                solution="Analizar causas de ineficiencia y corregir"
            )
        
        # OPs por producto (concentración)
        ops = self._search_read(
            "mrp.production",
            [("state", "in", ["confirmed", "progress"])],
            ["product_id", "product_qty"],
            limit=500
        )
        
        by_product: dict[str, int] = {}
        for op in ops:
            product = self._safe_get_name(op, "product_id")
            by_product[product] = by_product.get(product, 0) + 1
        
        if by_product:
            sorted_products = sorted(by_product.items(), key=lambda x: x[1], reverse=True)
            
            self._add_finding(
                level=2,
                category="Productos",
                title=f"OPs activas por producto",
                description="Concentración de producción en curso",
                severity=ImpactLevel.INFO,
                sample_data=[{"product": p, "ops": c} for p, c in sorted_products[:10]],
            )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: OPs específicas con problemas."""
        
        if not self._model_exists("mrp.production"):
            return
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # OPs retrasadas
        delayed_ops = self._search_read(
            "mrp.production",
            [
                ("state", "in", ["confirmed", "progress"]),
                ("date_finished", "<", today),
            ],
            ["name", "product_id", "product_qty", "date_finished", "date_start"],
            limit=100,
            order="date_finished asc"
        )
        
        if delayed_ops:
            self._add_finding(
                level=3,
                category="Retrasos",
                title=f"🔴 {len(delayed_ops)} OPs retrasadas",
                description="Órdenes de producción fuera de fecha",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(delayed_ops),
                sample_data=[
                    {
                        "op": op.get("name"),
                        "product": self._safe_get_name(op, "product_id"),
                        "qty": op.get("product_qty"),
                        "planned_end": op.get("date_finished"),
                        "days_late": self._days_between(op.get("date_finished")),
                    }
                    for op in delayed_ops[:10]
                ],
                impacts=[
                    self._blocks_agent(
                        "ventas",
                        "Producto no disponible",
                        f"{len(delayed_ops)} productos retrasados",
                        "Escalar para acelerar"
                    )
                ],
                solution="Priorizar y acelerar OPs retrasadas",
                coordinated_actions=[
                    "PRODUCCION: Horas extra o reasignar recursos",
                    "VENTAS: Comunicar a clientes afectados",
                ]
            )
        
        # OPs bloqueadas por material
        ops_in_progress = self._search_read(
            "mrp.production",
            [("state", "in", ["confirmed", "progress"])],
            ["name", "product_id", "reservation_state"],
            limit=500
        )
        
        blocked = [
            op for op in ops_in_progress
            if op.get("reservation_state") == "waiting"
        ]
        
        if blocked:
            self._add_finding(
                level=3,
                category="Bloqueos",
                title=f"⚠️ {len(blocked)} OPs esperando material",
                description="OPs que no pueden avanzar por falta de componentes",
                severity=ImpactLevel.HIGH,
                affected_records=len(blocked),
                sample_data=[
                    {
                        "op": op.get("name"),
                        "product": self._safe_get_name(op, "product_id"),
                    }
                    for op in blocked[:10]
                ],
                impacts=[
                    self._delays_agent(
                        "ventas",
                        "Producción detenida",
                        "Producto no se terminará a tiempo",
                        "Conseguir material"
                    )
                ],
                solution="Verificar con Compras el estado de materiales",
                coordinated_actions=[
                    "COMPRAS: Verificar OC de materiales faltantes",
                    "INVENTARIO: Confirmar stock real",
                ]
            )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        if not self._model_exists("mrp.production"):
            return
        
        # OPs muy antiguas sin cerrar
        old_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        old_ops = self._search_read(
            "mrp.production",
            [
                ("state", "in", ["confirmed", "progress", "to_close"]),
                ("date_start", "<", old_date),
            ],
            ["name", "product_id", "date_start", "state"],
            limit=50
        )
        
        if old_ops:
            self._add_finding(
                level=4,
                category="OPs Antiguas",
                title=f"{len(old_ops)} OPs abiertas >30 días",
                description="Órdenes de producción muy antiguas sin cerrar",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(old_ops),
                sample_data=[
                    {
                        "op": op.get("name"),
                        "product": self._safe_get_name(op, "product_id"),
                        "started": op.get("date_start"),
                        "state": op.get("state"),
                        "days_open": self._days_between(op.get("date_start")),
                    }
                    for op in old_ops[:10]
                ],
                solution="Revisar y cerrar o cancelar OPs antiguas"
            )
        
        # BOMs sin componentes (probable error)
        if self._model_exists("mrp.bom"):
            boms = self._search_read(
                "mrp.bom",
                [("active", "=", True)],
                ["product_tmpl_id", "bom_line_ids"],
                limit=500
            )
            
            empty_boms = [
                b for b in boms
                if not b.get("bom_line_ids")
            ]
            
            if empty_boms:
                self._add_finding(
                    level=4,
                    category="BOMs",
                    title=f"{len(empty_boms)} BOMs sin componentes",
                    description="Listas de materiales vacías",
                    severity=ImpactLevel.HIGH,
                    affected_records=len(empty_boms),
                    sample_data=[
                        {"product": self._safe_get_name(b, "product_tmpl_id")}
                        for b in empty_boms[:10]
                    ],
                    impacts=[
                        self._blocks_agent(
                            "produccion",
                            "No se puede producir",
                            "Sin BOM no hay consumo de materiales",
                            "Completar BOM"
                        ),
                        self._create_impact(
                            "costos",
                            ImpactType.REDUCES_QUALITY,
                            "Costo de producción incorrecto",
                            "Sin BOM el costo es cero",
                            "Completar BOM"
                        ),
                    ],
                    solution="Completar las BOMs con componentes"
                )
        
        # Centros de trabajo sin eficiencia configurada
        workcenters = self._search_read(
            "mrp.workcenter",
            [("active", "=", True)],
            ["name", "time_efficiency"],
            limit=50
        )
        
        no_efficiency = [
            wc for wc in workcenters
            if not wc.get("time_efficiency") or wc.get("time_efficiency") == 0
        ]
        
        if no_efficiency:
            self._add_finding(
                level=4,
                category="Configuración",
                title=f"{len(no_efficiency)} centros sin eficiencia configurada",
                description="Centros de trabajo sin factor de eficiencia",
                severity=ImpactLevel.LOW,
                affected_records=len(no_efficiency),
                sample_data=[{"workcenter": wc.get("name")} for wc in no_efficiency],
                solution="Configurar eficiencia de centros de trabajo"
            )
