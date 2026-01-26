"""
Agente de Producción - Control de Manufactura y MRP.

Responsabilidades:
- Monitorear órdenes de producción
- Detectar retrasos y cuellos de botella
- Controlar eficiencia de centros de trabajo
- Analizar desperdicio y calidad
- Revisar costos de lista de materiales
- Optimizar rutas de producción
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class ManufacturingAgent(BaseAgent):
    """
    Agente autónomo para gestión de producción/manufactura.
    
    Monitorea MRP, eficiencia y calidad de producción.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="produccion",
            description="Control de manufactura, MRP y eficiencia de planta"
        )
        
        # Configuración desde settings
        self.company_id = settings.odoo.company_id
        
        # Parámetros de análisis
        self.delay_threshold_hours = 4  # Horas de retraso para alertar
        self.efficiency_warning_threshold = 0.75  # 75% eficiencia mínima
        self.scrap_alert_percentage = 5  # % de desperdicio para alertar
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de producción."""
        
        # Órdenes que vencen hoy
        self.register_task(TaskDefinition(
            name="orders_due_today",
            method="check_orders_due_today",
            schedule="0 7 * * 1-5",  # 7:00 AM L-V
            description="Órdenes de producción que deben completarse hoy"
        ))
        
        # Órdenes retrasadas
        self.register_task(TaskDefinition(
            name="orders_delayed",
            method="check_delayed_orders",
            schedule="0 8 * * 1-5",  # 8:00 AM L-V
            description="Órdenes de producción retrasadas vs fecha planificada"
        ))
        
        # Faltantes de material
        self.register_task(TaskDefinition(
            name="material_shortage",
            method="check_material_shortage",
            schedule="0 7 * * 1-5",  # 7:00 AM L-V
            description="Faltantes de material para órdenes de producción"
        ))
        
        # Capacidad vs carga
        self.register_task(TaskDefinition(
            name="capacity_check",
            method="check_capacity",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Capacidad disponible vs carga de trabajo planificada"
        ))
        
        # Eficiencia de centros de trabajo
        self.register_task(TaskDefinition(
            name="work_center_efficiency",
            method="analyze_work_center_efficiency",
            schedule="0 18 * * 1-5",  # 6:00 PM L-V
            description="Eficiencia por centro de trabajo"
        ))
        
        # Producción vs plan
        self.register_task(TaskDefinition(
            name="production_vs_plan",
            method="check_production_vs_plan",
            schedule="0 18 * * 1-5",  # 6:00 PM L-V
            description="Producción real vs planificada del día"
        ))
        
        # Cuellos de botella
        self.register_task(TaskDefinition(
            name="bottleneck_detection",
            method="detect_bottlenecks",
            schedule="0 */2 * * 1-5",  # Cada 2 horas L-V
            description="Detectar cuellos de botella en producción"
        ))
        
        # Análisis de desperdicio
        self.register_task(TaskDefinition(
            name="scrap_analysis",
            method="analyze_scrap",
            schedule="0 16 * * 5",  # Viernes 4:00 PM
            description="Análisis de desperdicio/scrap por producto"
        ))
        
        # Mantenimientos pendientes
        self.register_task(TaskDefinition(
            name="maintenance_due",
            method="check_maintenance_due",
            schedule="0 8 * * 1-5",  # 8:00 AM L-V
            description="Mantenimientos preventivos de equipos pendientes"
        ))
        
        # Costos de BOM
        self.register_task(TaskDefinition(
            name="bom_cost_review",
            method="review_bom_costs",
            schedule="0 9 1 * *",  # Día 1 del mes
            description="Revisar costos de lista de materiales"
        ))
        
        # Eficiencia de rutas
        self.register_task(TaskDefinition(
            name="routing_efficiency",
            method="analyze_routing_efficiency",
            schedule="0 9 15 * *",  # Día 15 del mes
            description="Análisis de eficiencia de rutas de producción"
        ))
        
        # Resumen semanal
        self.register_task(TaskDefinition(
            name="weekly_production_summary",
            method="weekly_summary",
            schedule="0 17 * * 5",  # Viernes 5:00 PM
            description="Resumen semanal de producción"
        ))
        
        # Análisis de OEE
        self.register_task(TaskDefinition(
            name="oee_analysis",
            method="analyze_oee",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Análisis de OEE (Overall Equipment Effectiveness)"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de producción."""
        
        # Verificar si MRP está instalado
        if not self._model_exists("mrp.production"):
            return {
                "status": "warning",
                "message": "Módulo MRP no instalado",
                "last_updated": datetime.now().isoformat(),
            }
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Órdenes en progreso
        in_progress = self._count_orders_by_state("progress")
        
        # Órdenes confirmadas (pendientes)
        confirmed = self._count_orders_by_state("confirmed")
        
        # Órdenes retrasadas
        delayed = self._count_delayed_orders()
        
        # Determinar estado
        if delayed > 5:
            status = "critical"
        elif delayed > 0:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "company_id": self.company_id,
            "orders_in_progress": in_progress,
            "orders_confirmed": confirmed,
            "orders_delayed": delayed,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_orders_due_today(self) -> TaskResult:
        """Verifica órdenes que deben completarse hoy."""
        started_at = datetime.now()
        
        self.logger.info("Verificando órdenes de producción del día...")
        
        if not self._model_exists("mrp.production"):
            return self._no_mrp_result("orders_due_today", started_at)
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Órdenes con fecha de fin hoy que no están terminadas
        orders = self.search_read(
            "mrp.production",
            [
                ("date_finished", ">=", f"{today} 00:00:00"),
                ("date_finished", "<=", f"{today} 23:59:59"),
                ("state", "in", ["confirmed", "progress"]),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "product_qty", "state", "date_start", "date_finished"],
            limit=50,
            order="date_finished asc"
        )
        
        if orders:
            in_progress = [o for o in orders if o["state"] == "progress"]
            not_started = [o for o in orders if o["state"] == "confirmed"]
            
            message = f"""
*📋 Órdenes de Producción del Día*

*En progreso:* {len(in_progress)}
*Sin iniciar:* {len(not_started)}
*Total:* {len(orders)}

"""
            if not_started:
                message += "*⚠️ Sin iniciar:*\n"
                for o in not_started[:5]:
                    product = o["product_id"][1] if o.get("product_id") else "N/A"
                    message += f"• {o['name']}: {product} ({o['product_qty']:.0f} uds)\n"
            
            priority = Priority.HIGH if not_started else Priority.MEDIUM
            
            await self.notify(
                title=f"📋 {len(orders)} órdenes para hoy",
                message=message,
                priority=priority,
            )
        else:
            await self.notify(
                title="✅ Sin órdenes pendientes hoy",
                message="No hay órdenes de producción programadas para completar hoy",
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="orders_due_today",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"orders_count": len(orders) if orders else 0}
        )
    
    async def check_delayed_orders(self) -> TaskResult:
        """Verifica órdenes retrasadas."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando órdenes retrasadas...")
        
        if not self._model_exists("mrp.production"):
            return self._no_mrp_result("orders_delayed", started_at)
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Órdenes con fecha de fin pasada que no están terminadas
        delayed = self.search_read(
            "mrp.production",
            [
                ("date_finished", "<", now),
                ("state", "in", ["confirmed", "progress"]),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "product_qty", "state", "date_start", "date_finished"],
            limit=50,
            order="date_finished asc"
        )
        
        if delayed:
            # Calcular días de retraso
            for order in delayed:
                if order.get("date_finished"):
                    try:
                        planned_end = datetime.strptime(order["date_finished"][:19], "%Y-%m-%d %H:%M:%S")
                        order["delay_hours"] = (datetime.now() - planned_end).total_seconds() / 3600
                    except (ValueError, TypeError):
                        order["delay_hours"] = 0
            
            # Ordenar por retraso
            delayed.sort(key=lambda x: x.get("delay_hours", 0), reverse=True)
            
            # Propuestas para las más críticas
            critical = [o for o in delayed if o.get("delay_hours", 0) > 24]
            
            for order in critical[:5]:
                product = order["product_id"][1] if order.get("product_id") else "N/A"
                
                await self.propose(
                    title=f"🔴 Producción retrasada: {order['name']}",
                    description=f"{product} - {order.get('delay_hours', 0):.0f}h de retraso",
                    priority=Priority.CRITICAL if order.get("delay_hours", 0) > 48 else Priority.HIGH,
                    situation_summary=f"""
Orden: {order['name']}
Producto: {product}
Cantidad: {order['product_qty']:.0f}
Estado: {order['state']}
Retraso: {order.get('delay_hours', 0):.0f} horas

Requiere atención inmediata para evitar impacto en entregas.
                    """.strip(),
                    proposed_action_detail="Evaluar causa del retraso y reprogramar o asignar recursos adicionales",
                    supporting_data={"order": order},
                )
                proposals_created += 1
            
            message = f"""
*🔴 Órdenes de Producción Retrasadas*

*Total retrasadas:* {len(delayed)}
*Críticas (>24h):* {len(critical)}

*Top 5 por retraso:*
"""
            for o in delayed[:5]:
                product = o["product_id"][1][:25] if o.get("product_id") else "N/A"
                message += f"• {o['name']}: {product} ({o.get('delay_hours', 0):.0f}h)\n"
            
            await self.notify(
                title=f"🔴 {len(delayed)} órdenes retrasadas",
                message=message,
                priority=Priority.CRITICAL if critical else Priority.HIGH,
            )
        
        return TaskResult(
            task_name="orders_delayed",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"delayed_count": len(delayed) if delayed else 0}
        )
    
    async def check_material_shortage(self) -> TaskResult:
        """Verifica faltantes de material para producción."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando faltantes de material...")
        
        if not self._model_exists("mrp.production"):
            return self._no_mrp_result("material_shortage", started_at)
        
        # Órdenes confirmadas o en progreso
        orders = self.search_read(
            "mrp.production",
            [
                ("state", "in", ["confirmed", "progress"]),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "product_qty", "reservation_state"],
            limit=100
        )
        
        # Filtrar órdenes sin reserva completa
        shortage = [o for o in orders if o.get("reservation_state") != "assigned"]
        
        if shortage:
            message = f"""
*⚠️ Órdenes con Faltante de Material*

*Total:* {len(shortage)} de {len(orders)} órdenes

"""
            for o in shortage[:10]:
                product = o["product_id"][1][:30] if o.get("product_id") else "N/A"
                status = "🟡 Parcial" if o.get("reservation_state") == "waiting" else "🔴 Sin reserva"
                message += f"• {o['name']}: {product} - {status}\n"
            
            if len(shortage) > 10:
                message += f"\n... y {len(shortage) - 10} más"
            
            # Propuesta para las críticas
            if len(shortage) > 5:
                await self.propose(
                    title=f"⚠️ {len(shortage)} órdenes con faltante de material",
                    description="Revisar disponibilidad y generar compras urgentes",
                    priority=Priority.HIGH,
                    situation_summary=message,
                    proposed_action_detail="Generar órdenes de compra urgentes o reasignar material",
                    supporting_data={"shortage_orders": shortage[:20]},
                )
                proposals_created += 1
            
            await self.notify(
                title=f"⚠️ {len(shortage)} órdenes sin material completo",
                message=message,
                priority=Priority.HIGH,
            )
        
        return TaskResult(
            task_name="material_shortage",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"shortage_count": len(shortage) if shortage else 0}
        )
    
    async def check_capacity(self) -> TaskResult:
        """Verifica capacidad vs carga de trabajo."""
        started_at = datetime.now()
        
        self.logger.info("Analizando capacidad de producción...")
        
        if not self._model_exists("mrp.workcenter"):
            return self._no_mrp_result("capacity_check", started_at)
        
        # Obtener centros de trabajo (Odoo 19 no tiene campo 'capacity')
        workcenters = self.search_read(
            "mrp.workcenter",
            [("company_id", "=", self.company_id)],
            ["name", "time_efficiency", "workcenter_load", "working_state"],
            limit=50
        )
        
        if not workcenters:
            await self.notify(
                title="ℹ️ Sin centros de trabajo configurados",
                message="No hay centros de trabajo para analizar capacidad",
                priority=Priority.LOW,
            )
            return TaskResult(
                task_name="capacity_check",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Próxima semana
        week_start = datetime.now()
        week_end = week_start + timedelta(days=7)
        
        # Órdenes de trabajo programadas
        if self._model_exists("mrp.workorder"):
            workorders = self.search_read(
                "mrp.workorder",
                [
                    ("state", "not in", ["done", "cancel"]),
                    ("date_start", ">=", week_start.strftime("%Y-%m-%d")),
                    ("date_start", "<=", week_end.strftime("%Y-%m-%d")),
                    ("company_id", "=", self.company_id),
                ],
                ["workcenter_id", "duration_expected"],
                limit=500
            )
            
            # Agrupar carga por centro
            load_by_wc: dict[int, float] = {}
            for wo in workorders:
                wc_id = wo["workcenter_id"][0] if wo.get("workcenter_id") else None
                if wc_id:
                    if wc_id not in load_by_wc:
                        load_by_wc[wc_id] = 0
                    load_by_wc[wc_id] += wo.get("duration_expected", 0) / 60  # Convertir a horas
            
            # Calcular utilización (capacidad estándar: 40h/semana por centro)
            HOURS_PER_WEEK = 40
            
            message = f"""
*📊 Capacidad de Producción - Próxima Semana*

*Centros de trabajo:* {len(workcenters)}
*Órdenes programadas:* {len(workorders)}

*Carga por centro:*
"""
            overloaded = []
            for wc in workcenters:
                load = load_by_wc.get(wc["id"], 0)
                # Usar eficiencia para ajustar capacidad (default 100%)
                efficiency = wc.get("time_efficiency", 100) / 100
                capacity = HOURS_PER_WEEK * efficiency if efficiency > 0 else HOURS_PER_WEEK
                utilization = (load / capacity * 100) if capacity > 0 else 0
                
                emoji = "🟢" if utilization < 80 else "🟡" if utilization < 100 else "🔴"
                message += f"{emoji} {wc['name'][:25]}: {utilization:.0f}% ({load:.0f}h/{capacity:.0f}h)\n"
                
                if utilization >= 100:
                    overloaded.append(wc["name"])
            
            if overloaded:
                message += f"\n⚠️ *Sobrecarga:* {', '.join(overloaded)}"
            
            await self.notify(
                title=f"📊 Capacidad: {len(overloaded)} centros sobrecargados" if overloaded else "📊 Capacidad OK",
                message=message,
                priority=Priority.HIGH if overloaded else Priority.LOW,
            )
        
        return TaskResult(
            task_name="capacity_check",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"workcenters": len(workcenters)}
        )
    
    async def analyze_work_center_efficiency(self) -> TaskResult:
        """Analiza eficiencia por centro de trabajo."""
        started_at = datetime.now()
        
        self.logger.info("Analizando eficiencia de centros de trabajo...")
        
        if not self._model_exists("mrp.workorder"):
            return self._no_mrp_result("work_center_efficiency", started_at)
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Órdenes de trabajo completadas hoy
        completed = self.search_read(
            "mrp.workorder",
            [
                ("state", "=", "done"),
                ("date_finished", ">=", f"{today} 00:00:00"),
                ("date_finished", "<=", f"{today} 23:59:59"),
                ("company_id", "=", self.company_id),
            ],
            ["workcenter_id", "duration_expected", "duration"],
            limit=500
        )
        
        if not completed:
            await self.notify(
                title="ℹ️ Sin órdenes completadas hoy",
                message="No hay datos de eficiencia para analizar",
                priority=Priority.LOW,
            )
            return TaskResult(
                task_name="work_center_efficiency",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Calcular eficiencia por centro
        by_wc: dict[str, dict] = {}
        for wo in completed:
            wc_name = wo["workcenter_id"][1] if wo.get("workcenter_id") else "N/A"
            
            if wc_name not in by_wc:
                by_wc[wc_name] = {"expected": 0, "actual": 0, "count": 0}
            
            by_wc[wc_name]["expected"] += wo.get("duration_expected", 0)
            by_wc[wc_name]["actual"] += wo.get("duration", 0)
            by_wc[wc_name]["count"] += 1
        
        message = f"""
*⚙️ Eficiencia de Centros de Trabajo - Hoy*

*Órdenes completadas:* {len(completed)}

"""
        low_efficiency = []
        for wc_name, data in sorted(by_wc.items()):
            if data["actual"] > 0:
                efficiency = (data["expected"] / data["actual"]) * 100
                emoji = "🟢" if efficiency >= 90 else "🟡" if efficiency >= 75 else "🔴"
                message += f"{emoji} {wc_name[:25]}: {efficiency:.0f}% ({data['count']} OT)\n"
                
                if efficiency < self.efficiency_warning_threshold * 100:
                    low_efficiency.append(wc_name)
        
        priority = Priority.HIGH if low_efficiency else Priority.LOW
        
        await self.notify(
            title=f"⚙️ Eficiencia: {len(low_efficiency)} centros bajo objetivo" if low_efficiency else "⚙️ Eficiencia OK",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="work_center_efficiency",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"completed_orders": len(completed), "low_efficiency": low_efficiency}
        )
    
    async def check_production_vs_plan(self) -> TaskResult:
        """Compara producción real vs planificada."""
        started_at = datetime.now()
        
        self.logger.info("Comparando producción vs plan...")
        
        if not self._model_exists("mrp.production"):
            return self._no_mrp_result("production_vs_plan", started_at)
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Órdenes planificadas para hoy
        planned = self.search_read(
            "mrp.production",
            [
                ("date_start", ">=", f"{today} 00:00:00"),
                ("date_start", "<=", f"{today} 23:59:59"),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "product_qty", "qty_produced", "state"],
            limit=100
        )
        
        if not planned:
            return TaskResult(
                task_name="production_vs_plan",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Sin órdenes planificadas para hoy"}
            )
        
        # Calcular avance
        total_planned = sum(o.get("product_qty", 0) for o in planned)
        total_produced = sum(o.get("qty_produced", 0) for o in planned)
        completed = [o for o in planned if o["state"] == "done"]
        
        completion_rate = (total_produced / total_planned * 100) if total_planned > 0 else 0
        
        message = f"""
*📊 Producción del Día vs Plan*

*Órdenes planificadas:* {len(planned)}
*Órdenes completadas:* {len(completed)}

*Unidades:*
• Planificadas: {total_planned:,.0f}
• Producidas: {total_produced:,.0f}
• Avance: {completion_rate:.1f}%

"""
        # Órdenes no completadas
        pending = [o for o in planned if o["state"] != "done"]
        if pending:
            message += "*Pendientes:*\n"
            for o in pending[:5]:
                product = o["product_id"][1][:25] if o.get("product_id") else "N/A"
                progress = (o.get("qty_produced", 0) / o.get("product_qty", 1)) * 100
                message += f"• {o['name']}: {product} ({progress:.0f}%)\n"
        
        priority = Priority.HIGH if completion_rate < 80 else Priority.LOW
        
        await self.notify(
            title=f"📊 Producción: {completion_rate:.0f}% del plan completado",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="production_vs_plan",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"planned": total_planned, "produced": total_produced, "rate": completion_rate}
        )
    
    async def detect_bottlenecks(self) -> TaskResult:
        """Detecta cuellos de botella en producción."""
        started_at = datetime.now()
        
        self.logger.info("Detectando cuellos de botella...")
        
        if not self._model_exists("mrp.workorder"):
            return self._no_mrp_result("bottleneck_detection", started_at)
        
        # Órdenes de trabajo en cola por centro
        pending_wo = self.search_read(
            "mrp.workorder",
            [
                ("state", "in", ["pending", "ready"]),
                ("company_id", "=", self.company_id),
            ],
            ["workcenter_id", "duration_expected"],
            limit=500
        )
        
        if not pending_wo:
            return TaskResult(
                task_name="bottleneck_detection",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Sin órdenes en cola"}
            )
        
        # Agrupar por centro de trabajo
        by_wc: dict[str, dict] = {}
        for wo in pending_wo:
            wc_name = wo["workcenter_id"][1] if wo.get("workcenter_id") else "N/A"
            
            if wc_name not in by_wc:
                by_wc[wc_name] = {"count": 0, "hours": 0}
            
            by_wc[wc_name]["count"] += 1
            by_wc[wc_name]["hours"] += wo.get("duration_expected", 0) / 60
        
        # Ordenar por carga
        sorted_wc = sorted(by_wc.items(), key=lambda x: x[1]["hours"], reverse=True)
        
        # Identificar cuellos de botella (más de 8 horas en cola)
        bottlenecks = [(name, data) for name, data in sorted_wc if data["hours"] > 8]
        
        if bottlenecks:
            message = f"""
*🚧 Cuellos de Botella Detectados*

*Centros con cola >8 horas:*
"""
            for name, data in bottlenecks[:5]:
                message += f"• {name[:25]}: {data['count']} OT ({data['hours']:.1f}h)\n"
            
            await self.notify(
                title=f"🚧 {len(bottlenecks)} cuellos de botella detectados",
                message=message,
                priority=Priority.HIGH,
            )
        
        return TaskResult(
            task_name="bottleneck_detection",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"bottlenecks": len(bottlenecks) if bottlenecks else 0}
        )
    
    async def analyze_scrap(self) -> TaskResult:
        """Analiza desperdicio/scrap de la semana."""
        started_at = datetime.now()
        
        self.logger.info("Analizando desperdicio...")
        
        if not self._model_exists("stock.scrap"):
            return TaskResult(
                task_name="scrap_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Modelo de scrap no disponible"}
            )
        
        # Scrap de la última semana
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        scraps = self.search_read(
            "stock.scrap",
            [
                ("date_done", ">=", week_ago),
                ("state", "=", "done"),
                ("company_id", "=", self.company_id),
            ],
            ["product_id", "scrap_qty", "origin"],
            limit=500
        )
        
        if not scraps:
            await self.notify(
                title="✅ Sin desperdicio esta semana",
                message="No se registró scrap en los últimos 7 días",
                priority=Priority.LOW,
            )
            return TaskResult(
                task_name="scrap_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por producto
        by_product: dict[str, float] = {}
        for s in scraps:
            product_name = s["product_id"][1] if s.get("product_id") else "N/A"
            if product_name not in by_product:
                by_product[product_name] = 0
            by_product[product_name] += s.get("scrap_qty", 0)
        
        # Ordenar por cantidad
        sorted_products = sorted(by_product.items(), key=lambda x: x[1], reverse=True)
        
        message = f"""
*♻️ Análisis de Desperdicio Semanal*

*Total registros:* {len(scraps)}
*Productos afectados:* {len(by_product)}

*Top por cantidad:*
"""
        for product, qty in sorted_products[:10]:
            message += f"• {product[:30]}: {qty:.0f} uds\n"
        
        await self.notify(
            title=f"♻️ Desperdicio: {len(scraps)} registros esta semana",
            message=message,
            priority=Priority.MEDIUM,
        )
        
        return TaskResult(
            task_name="scrap_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"scrap_count": len(scraps)}
        )
    
    async def check_maintenance_due(self) -> TaskResult:
        """Verifica mantenimientos preventivos pendientes."""
        started_at = datetime.now()
        
        self.logger.info("Verificando mantenimientos pendientes...")
        
        if not self._model_exists("maintenance.request"):
            return TaskResult(
                task_name="maintenance_due",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo de mantenimiento no instalado"}
            )
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Mantenimientos pendientes
        pending = self.search_read(
            "maintenance.request",
            [
                ("stage_id.done", "=", False),
                ("schedule_date", "<=", today),
                ("company_id", "=", self.company_id),
            ],
            ["name", "equipment_id", "schedule_date", "maintenance_type"],
            limit=50,
            order="schedule_date asc"
        )
        
        if pending:
            preventive = [m for m in pending if m.get("maintenance_type") == "preventive"]
            corrective = [m for m in pending if m.get("maintenance_type") == "corrective"]
            
            message = f"""
*🔧 Mantenimientos Pendientes*

*Preventivos:* {len(preventive)}
*Correctivos:* {len(corrective)}
*Total:* {len(pending)}

"""
            for m in pending[:10]:
                equip = m["equipment_id"][1][:25] if m.get("equipment_id") else "N/A"
                mtype = "🟡 Prev" if m.get("maintenance_type") == "preventive" else "🔴 Corr"
                message += f"• {mtype} | {equip}: {m['name'][:30]}\n"
            
            await self.notify(
                title=f"🔧 {len(pending)} mantenimientos pendientes",
                message=message,
                priority=Priority.HIGH if corrective else Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="maintenance_due",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"pending_maintenance": len(pending) if pending else 0}
        )
    
    async def review_bom_costs(self) -> TaskResult:
        """Revisa costos de lista de materiales."""
        started_at = datetime.now()
        
        self.logger.info("Revisando costos de BOM...")
        
        if not self._model_exists("mrp.bom"):
            return self._no_mrp_result("bom_cost_review", started_at)
        
        # BOMs activos
        boms = self.search_read(
            "mrp.bom",
            [
                ("active", "=", True),
                ("company_id", "=", self.company_id),
            ],
            ["product_tmpl_id", "product_id", "product_qty"],
            limit=100
        )
        
        if not boms:
            return TaskResult(
                task_name="bom_cost_review",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Sin BOMs configurados"}
            )
        
        message = f"""
*📋 Revisión de Lista de Materiales*

*BOMs activos:* {len(boms)}

_Nota: Verificar que los costos de materiales estén actualizados
para que la valorización de producción sea correcta._
        """.strip()
        
        await self.notify(
            title=f"📋 {len(boms)} BOMs revisados",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="bom_cost_review",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"bom_count": len(boms)}
        )
    
    async def analyze_routing_efficiency(self) -> TaskResult:
        """Analiza eficiencia de rutas de producción."""
        started_at = datetime.now()
        
        self.logger.info("Analizando eficiencia de rutas...")
        
        if not self._model_exists("mrp.routing.workcenter"):
            return TaskResult(
                task_name="routing_efficiency",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Rutas de producción no configuradas"}
            )
        
        # Rutas activas
        routes = self.search_read(
            "mrp.routing.workcenter",
            [("company_id", "=", self.company_id)],
            ["name", "workcenter_id", "time_cycle", "time_mode"],
            limit=100
        )
        
        message = f"""
*🔄 Análisis de Rutas de Producción*

*Operaciones configuradas:* {len(routes)}

_Revisar tiempos estándar vs tiempos reales para 
identificar oportunidades de mejora._
        """.strip()
        
        await self.notify(
            title=f"🔄 {len(routes)} operaciones de ruta analizadas",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="routing_efficiency",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"routes_count": len(routes) if routes else 0}
        )
    
    async def weekly_summary(self) -> TaskResult:
        """Genera resumen semanal de producción."""
        started_at = datetime.now()
        
        self.logger.info("Generando resumen semanal de producción...")
        
        if not self._model_exists("mrp.production"):
            return self._no_mrp_result("weekly_production_summary", started_at)
        
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Órdenes de la semana
        orders = self.search_read(
            "mrp.production",
            [
                ("date_start", ">=", week_ago),
                ("company_id", "=", self.company_id),
            ],
            ["state", "product_qty", "qty_produced"],
            limit=1000
        )
        
        # Estadísticas
        total = len(orders)
        completed = len([o for o in orders if o["state"] == "done"])
        in_progress = len([o for o in orders if o["state"] == "progress"])
        
        total_planned = sum(o.get("product_qty", 0) for o in orders)
        total_produced = sum(o.get("qty_produced", 0) for o in orders)
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        message = f"""
*📊 Resumen Semanal de Producción*
_{self.format_date(week_ago)} - {datetime.now().strftime('%d/%m/%Y')}_

*Órdenes:*
• Total: {total}
• Completadas: {completed} ({completion_rate:.0f}%)
• En progreso: {in_progress}

*Producción:*
• Planificada: {total_planned:,.0f} unidades
• Producida: {total_produced:,.0f} unidades
• Eficiencia: {(total_produced/total_planned*100) if total_planned > 0 else 0:.1f}%

_¡Buen fin de semana!_
        """.strip()
        
        await self.notify(
            title=f"📊 Resumen: {completed}/{total} órdenes completadas",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="weekly_production_summary",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_orders": total,
                "completed": completed,
                "total_produced": total_produced,
            }
        )
    
    async def analyze_oee(self) -> TaskResult:
        """Analiza OEE (Overall Equipment Effectiveness) de centros de trabajo."""
        started_at = datetime.now()
        
        self.logger.info("Analizando OEE de centros de trabajo...")
        
        # Obtener centros de trabajo con sus métricas
        workcenters = self.search_read(
            "mrp.workcenter",
            [("active", "=", True)],
            [
                "name", "code", "time_efficiency", "oee_target",
                "costs_hour", "employee_costs_hour", "working_state"
            ],
            limit=100
        )
        
        if not workcenters:
            return TaskResult(
                task_name="oee_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Obtener workorders del último mes para calcular OEE real
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        workorders = self.search_read(
            "mrp.workorder",
            [
                ("state", "=", "done"),
                ("date_finished", ">=", month_ago),
            ],
            ["workcenter_id", "duration", "duration_expected"],
            limit=5000
        )
        
        # Calcular eficiencia real por centro de trabajo
        wc_stats = {}
        for wo in workorders:
            wc = wo.get("workcenter_id")
            if not wc:
                continue
            
            wc_name = wc[1]
            if wc_name not in wc_stats:
                wc_stats[wc_name] = {"duration": 0, "expected": 0, "count": 0}
            
            wc_stats[wc_name]["duration"] += wo.get("duration", 0)
            wc_stats[wc_name]["expected"] += wo.get("duration_expected", 0)
            wc_stats[wc_name]["count"] += 1
        
        # Calcular OEE por centro
        oee_results = []
        below_target = []
        
        for wc in workcenters:
            wc_name = wc["name"]
            target = wc.get("oee_target", 85) or 85  # Default 85%
            configured_efficiency = wc.get("time_efficiency", 100)
            
            # Calcular OEE real si hay datos
            if wc_name in wc_stats and wc_stats[wc_name]["expected"] > 0:
                stats = wc_stats[wc_name]
                # OEE = (Tiempo esperado / Tiempo real) * 100
                actual_oee = (stats["expected"] / stats["duration"] * 100) if stats["duration"] > 0 else 0
            else:
                actual_oee = configured_efficiency
            
            result = {
                "name": wc_name,
                "code": wc.get("code", ""),
                "target": target,
                "actual": actual_oee,
                "configured": configured_efficiency,
                "state": wc.get("working_state", "normal"),
                "workorders": wc_stats.get(wc_name, {}).get("count", 0),
            }
            
            oee_results.append(result)
            
            if actual_oee < target:
                below_target.append(result)
        
        # Ordenar por OEE
        oee_results.sort(key=lambda x: x["actual"], reverse=True)
        
        # Calcular promedio
        if oee_results:
            avg_oee = sum(r["actual"] for r in oee_results) / len(oee_results)
            avg_target = sum(r["target"] for r in oee_results) / len(oee_results)
        else:
            avg_oee = 0
            avg_target = 85
        
        message = f"""
*📊 Análisis de OEE (últimos 30 días)*

*Resumen:*
• Centros de trabajo: {len(workcenters)}
• OEE promedio: {avg_oee:.1f}%
• Target promedio: {avg_target:.1f}%
• Bajo target: {len(below_target)}

*Por centro de trabajo:*
"""
        
        for wc in oee_results[:10]:
            status_emoji = "🟢" if wc["actual"] >= wc["target"] else "🔴"
            state_emoji = "⚠️" if wc["state"] == "blocked" else ""
            message += f"{status_emoji} {wc['name'][:25]}: {wc['actual']:.0f}% (target: {wc['target']:.0f}%) {state_emoji}\n"
        
        if below_target:
            message += f"\n*⚠️ Centros bajo target:*\n"
            for wc in below_target[:5]:
                gap = wc["target"] - wc["actual"]
                message += f"• {wc['name'][:25]}: -{gap:.0f}% del target\n"
        
        priority = Priority.HIGH if len(below_target) > len(workcenters) * 0.5 else Priority.MEDIUM if below_target else Priority.LOW
        
        await self.notify(
            title=f"📊 OEE Promedio: {avg_oee:.1f}% ({len(below_target)} bajo target)",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="oee_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "workcenters": len(workcenters),
                "avg_oee": avg_oee,
                "below_target": len(below_target),
            }
        )
    
    # ==================== Helpers ====================
    
    def _model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo existe en Odoo usando introspección."""
        try:
            from aria.agent_introspection import get_introspection
            introspection = get_introspection(self.odoo)
            model = introspection.get_model(model_name)
            return model.exists()
        except Exception:
            return False
    
    def _no_mrp_result(self, task_name: str, started_at: datetime) -> TaskResult:
        """Retorna resultado para cuando MRP no está instalado."""
        return TaskResult(
            task_name=task_name,
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"message": "Módulo MRP no instalado"}
        )
    
    def _count_orders_by_state(self, state: str) -> int:
        """Cuenta órdenes por estado."""
        if not self._model_exists("mrp.production"):
            return 0
        
        return len(self.search_read(
            "mrp.production",
            [
                ("state", "=", state),
                ("company_id", "=", self.company_id),
            ],
            ["id"],
            limit=1000
        ))
    
    def _count_delayed_orders(self) -> int:
        """Cuenta órdenes retrasadas."""
        if not self._model_exists("mrp.production"):
            return 0
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return len(self.search_read(
            "mrp.production",
            [
                ("date_finished", "<", now),
                ("state", "in", ["confirmed", "progress"]),
                ("company_id", "=", self.company_id),
            ],
            ["id"],
            limit=500
        ))


def create_manufacturing_agent() -> ManufacturingAgent:
    """Crea y retorna el agente de producción."""
    return ManufacturingAgent()
