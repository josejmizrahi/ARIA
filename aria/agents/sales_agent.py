"""
ARIA - Agente de Ventas
========================

Agente de Ventas - Gestión Comercial

Responsabilidades:
- Monitorear pedidos nuevos e inusuales
- Detectar clientes inactivos
- Analizar rentabilidad por cliente/producto
- Analizar márgenes de venta
- Monitorear entregas pendientes
- Evaluar rendimiento por vendedor/equipo
- Alertar sobre concentración de ventas
- Generar resúmenes semanales
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class SalesAgent(BaseAgent):
    """
    Agente autónomo para gestión de ventas.
    
    Monitorea la actividad comercial, márgenes y detecta
    oportunidades y riesgos en la cartera de clientes.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="ventas",
            description="Gestión comercial y seguimiento de clientes"
        )
        
        self.company_id = settings.odoo.company_id
        
        # Configuración
        self.inactive_days_threshold = 45
        self.unusual_order_threshold = 2.0
        self.concentration_warning_pct = 30
        self.min_margin_percent = 15  # Margen mínimo esperado
        self.delivery_delay_days = 3  # Días de retraso para alertar
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de ventas."""
        
        # Revisión de pedidos nuevos
        self.register_task(TaskDefinition(
            name="check_new_orders",
            method="check_new_orders",
            schedule="0 */2 * * *",  # Cada 2 horas
            description="Revisa pedidos nuevos e identifica inusuales"
        ))
        
        # Clientes inactivos
        self.register_task(TaskDefinition(
            name="inactive_customers",
            method="check_inactive_customers",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Detecta clientes sin actividad reciente"
        ))
        
        # Análisis de rentabilidad
        self.register_task(TaskDefinition(
            name="profitability_analysis",
            method="analyze_profitability",
            schedule="0 8 1 * *",  # Día 1 de cada mes
            description="Analiza rentabilidad por cliente"
        ))
        
        # Concentración de ventas
        self.register_task(TaskDefinition(
            name="sales_concentration",
            method="check_sales_concentration",
            schedule="0 10 1 * *",  # Día 1 de cada mes
            description="Alerta sobre concentración de ventas"
        ))
        
        # Resumen semanal de ventas
        self.register_task(TaskDefinition(
            name="weekly_summary",
            method="weekly_sales_summary",
            schedule="0 17 * * 5",  # Viernes 5:00 PM
            description="Genera resumen semanal de ventas"
        ))
        
        # Análisis de márgenes
        self.register_task(TaskDefinition(
            name="margin_analysis",
            method="analyze_margins",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Analiza márgenes de pedidos y productos"
        ))
        
        # Entregas pendientes
        self.register_task(TaskDefinition(
            name="pending_deliveries",
            method="check_pending_deliveries",
            schedule="0 8 * * 1-5",  # L-V 8:00 AM
            description="Revisa entregas pendientes y retrasadas"
        ))
        
        # Rendimiento por vendedor
        self.register_task(TaskDefinition(
            name="salesperson_performance",
            method="analyze_salesperson_performance",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Análisis de rendimiento por vendedor"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de ventas."""
        
        # Facturación del mes (usando account.move para coincidir con reportes)
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        invoices = self.search_read(
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
        
        total_month = sum(inv.get("amount_total_signed", 0) for inv in invoices)
        
        # Cotizaciones pendientes
        pending = self.search_count(
            "sale.order",
            [("state", "=", "draft"), ("company_id", "=", self.company_id)]
        )
        
        # Entregas retrasadas
        today = datetime.now().strftime("%Y-%m-%d")
        delayed = self.search_count(
            "sale.order",
            [
                ("state", "=", "sale"),
                ("delivery_status", "in", ["pending", "partial"]),
                ("commitment_date", "<", today),
                ("company_id", "=", self.company_id),
            ]
        )
        
        # Pedidos del mes con margen
        orders = self.search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", first_day),
                ("company_id", "=", self.company_id),
            ],
            ["margin_percent"],
            limit=1000
        )
        
        avg_margin = (
            sum(o.get("margin_percent", 0) for o in orders) / len(orders)
            if orders else 0
        )
        
        # Determinar estado
        if delayed > 10 or avg_margin < 10:
            status = "warning"
        elif delayed > 20:
            status = "critical"
        else:
            status = "ok"
        
        return {
            "status": status,
            "month_sales": total_month,
            "invoices_count": len(invoices),
            "pending_quotes": pending,
            "delayed_deliveries": delayed,
            "avg_margin_percent": round(avg_margin, 1),
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_new_orders(self) -> TaskResult:
        """Revisa pedidos nuevos e identifica inusuales."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Revisando pedidos nuevos...")
        
        # Pedidos de las últimas 4 horas
        since = (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        
        new_orders = self.search_read(
            "sale.order",
            [
                ("create_date", ">=", since),
                ("state", "in", ["draft", "sent", "sale"]),
            ],
            ["name", "partner_id", "amount_total", "date_order", "state"],
            limit=100,
            order="create_date desc"
        )
        
        if not new_orders:
            return TaskResult(
                task_name="check_new_orders",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                records_processed=0,
            )
        
        # Verificar si alguno es inusual
        for order in new_orders:
            partner = order.get("partner_id")
            partner_id = partner[0] if partner else None
            
            if not partner_id:
                continue
            
            # Obtener promedio histórico del cliente (basado en facturas)
            avg = self._get_customer_average_invoice(partner_id)
            amount = order.get("amount_total", 0)
            
            if avg > 0 and amount > avg * self.unusual_order_threshold:
                partner_name = partner[1] if partner else "Desconocido"
                
                await self.propose(
                    title=f"Pedido inusual: {partner_name}",
                    description=f"Pedido {order.get('name')} es {amount/avg:.1f}x mayor que el promedio",
                    priority=Priority.MEDIUM,
                    situation_summary=f"""
Pedido: {order.get('name')}
Cliente: {partner_name}
Monto: {self.format_currency(amount)}
Promedio histórico: {self.format_currency(avg)}
Variación: {amount/avg:.1f}x el promedio

⚠️ Este pedido es significativamente mayor que el promedio del cliente.
                    """.strip(),
                    proposed_action_detail="Verificar pedido con el cliente antes de procesar",
                    supporting_data={
                        "order_id": order["id"],
                        "order_name": order.get("name"),
                        "partner_id": partner_id,
                        "amount": amount,
                        "average": avg,
                    },
                    informational=True,
                )
                proposals_created += 1
        
        return TaskResult(
            task_name="check_new_orders",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            records_processed=len(new_orders),
        )
    
    async def check_inactive_customers(self) -> TaskResult:
        """Detecta clientes sin actividad reciente."""
        started_at = datetime.now()
        
        self.logger.info("Buscando clientes inactivos...")
        
        # Fecha límite para considerar inactivo
        cutoff_date = (datetime.now() - timedelta(days=self.inactive_days_threshold)).strftime("%Y-%m-%d")
        
        # Obtener todas las facturas posteriores a la fecha de corte EN UNA SOLA CONSULTA
        # Esto nos da los clientes activos
        recent_invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", cutoff_date),
                ("company_id", "=", self.company_id),
            ],
            ["partner_id"],
            limit=10000
        )
        
        # IDs de clientes con facturas recientes
        active_customer_ids = {inv["partner_id"][0] for inv in recent_invoices if inv.get("partner_id")}
        
        # Clientes con facturas pero sin actividad reciente (inactivos)
        # Obtenemos los que tienen customer_rank > 0 y no están en los activos
        all_customers = self.search_read(
            "res.partner",
            [
                ("customer_rank", ">", 0),
                ("active", "=", True),
            ],
            ["id", "name"],
            limit=2000
        )
        
        # Filtrar para obtener solo los inactivos
        inactive_customer_ids = [c["id"] for c in all_customers if c["id"] not in active_customer_ids]
        
        if not inactive_customer_ids:
            return TaskResult(
                task_name="inactive_customers",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"inactive_count": 0}
            )
        
        # Obtener última factura de los clientes inactivos
        # Hacemos una consulta agrupada para obtener las fechas
        last_invoices = self.search_read(
            "account.move",
            [
                ("partner_id", "in", inactive_customer_ids[:500]),  # Limitar a 500
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
            ],
            ["partner_id", "invoice_date"],
            limit=10000,
            order="invoice_date desc"
        )
        
        # Mapear última fecha por cliente
        last_date_by_customer: dict[int, str] = {}
        for inv in last_invoices:
            if inv.get("partner_id") and inv.get("invoice_date"):
                cust_id = inv["partner_id"][0]
                if cust_id not in last_date_by_customer:
                    last_date_by_customer[cust_id] = str(inv["invoice_date"])[:10]
        
        # Crear lista de inactivos con info
        customer_map = {c["id"]: c["name"] for c in all_customers}
        inactive = []
        
        for cust_id, last_date in last_date_by_customer.items():
            days_inactive = self.days_between(last_date)
            if days_inactive >= self.inactive_days_threshold:
                inactive.append({
                    "id": cust_id,
                    "name": customer_map.get(cust_id, "N/A"),
                    "days_inactive": days_inactive,
                    "last_invoice": last_date,
                })
        
        if inactive:
            inactive.sort(key=lambda x: x["days_inactive"], reverse=True)
            
            message = f"*{len(inactive)} clientes inactivos (>{self.inactive_days_threshold} días)*\n\n"
            
            for c in inactive[:10]:
                message += f"• {c['name']}: {c['days_inactive']} días (último: {self.format_date(c['last_invoice'])})\n"
            
            if len(inactive) > 10:
                message += f"\n... y {len(inactive) - 10} más"
            
            await self.notify(
                title=f"⚠️ {len(inactive)} clientes inactivos",
                message=message,
                priority=Priority.MEDIUM,
                data={"inactive": inactive[:20]}
            )
        
        return TaskResult(
            task_name="inactive_customers",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"inactive_count": len(inactive)}
        )
    
    async def analyze_profitability(self) -> TaskResult:
        """
        Analiza rentabilidad por cliente.
        
        Usa account.move (facturas) para coincidir con reportes financieros de Odoo.
        """
        started_at = datetime.now()
        
        self.logger.info("Analizando rentabilidad (desde facturas)...")
        
        # Últimos 12 meses
        date_from = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        # Usar facturas de cliente publicadas
        invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),  # Facturas de cliente
                ("state", "=", "posted"),           # Publicadas
                ("invoice_date", ">=", date_from),
            ],
            ["partner_id", "amount_total_signed"],
            limit=10000
        )
        
        # Agrupar por cliente
        by_customer: dict[int, dict] = {}
        total = 0
        
        for inv in invoices:
            partner = inv.get("partner_id")
            partner_id = partner[0] if partner else 0
            partner_name = partner[1] if partner else "Desconocido"
            amount = inv.get("amount_total_signed", 0)
            
            if partner_id not in by_customer:
                by_customer[partner_id] = {"name": partner_name, "total": 0, "invoices": 0}
            
            by_customer[partner_id]["total"] += amount
            by_customer[partner_id]["invoices"] += 1
            total += amount
        
        # Top 10
        customers = sorted(by_customer.values(), key=lambda x: x["total"], reverse=True)
        top_10 = customers[:10]
        top_10_sales = sum(c["total"] for c in top_10)
        top_10_pct = (top_10_sales / total * 100) if total > 0 else 0
        
        message = f"""
*Análisis de Rentabilidad - Últimos 12 meses (Facturado)*

*Facturación total:* {self.format_currency(total)}
*Clientes activos:* {len(customers)}

*Top 10 clientes ({top_10_pct:.1f}% de facturación):*
        """.strip()
        
        for i, c in enumerate(top_10, 1):
            pct = (c["total"] / total * 100) if total > 0 else 0
            message += f"\n{i}. {c['name']}: {self.format_currency(c['total'])} ({pct:.1f}%)"
        
        await self.notify(
            title="📊 Análisis de Rentabilidad",
            message=message,
            priority=Priority.LOW,
            data={"total": total, "customer_count": len(customers)}
        )
        
        return TaskResult(
            task_name="profitability_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"total_sales": total}
        )
    
    async def check_sales_concentration(self) -> TaskResult:
        """
        Alerta sobre concentración excesiva de ventas.
        
        Usa account.move (facturas) para coincidir con reportes financieros.
        """
        started_at = datetime.now()
        
        self.logger.info("Verificando concentración de ventas (desde facturas)...")
        
        # Últimos 12 meses
        date_from = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", date_from),
            ],
            ["partner_id", "amount_total_signed"],
            limit=10000
        )
        
        # Agrupar por cliente
        by_customer: dict[int, dict] = {}
        total = 0
        
        for inv in invoices:
            partner = inv.get("partner_id")
            partner_id = partner[0] if partner else 0
            partner_name = partner[1] if partner else "Desconocido"
            amount = inv.get("amount_total_signed", 0)
            
            if partner_id not in by_customer:
                by_customer[partner_id] = {"name": partner_name, "total": 0}
            
            by_customer[partner_id]["total"] += amount
            total += amount
        
        # Identificar clientes con concentración alta
        concentrated = []
        
        for partner_id, data in by_customer.items():
            pct = (data["total"] / total * 100) if total > 0 else 0
            
            if pct >= self.concentration_warning_pct:
                concentrated.append({
                    "id": partner_id,
                    "name": data["name"],
                    "total": data["total"],
                    "percentage": pct,
                })
        
        if concentrated:
            concentrated.sort(key=lambda x: x["percentage"], reverse=True)
            
            message = f"*⚠️ Concentración de facturación detectada*\n\n"
            message += f"Clientes que representan >{self.concentration_warning_pct}% de facturación:\n\n"
            
            for c in concentrated:
                message += f"• {c['name']}: {self.format_currency(c['total'])} ({c['percentage']:.1f}%)\n"
            
            message += "\n_Alta dependencia de pocos clientes representa riesgo._"
            
            await self.propose(
                title="⚠️ Alta concentración de facturación",
                description="Algunos clientes representan un alto porcentaje de la facturación total",
                priority=Priority.HIGH if len(concentrated) > 1 else Priority.MEDIUM,
                situation_summary=message,
                proposed_action_detail="Desarrollar estrategia de diversificación de cartera",
                supporting_data={"concentrated": concentrated},
                informational=True,
            )
        
        return TaskResult(
            task_name="sales_concentration",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"concentrated_count": len(concentrated)}
        )
    
    async def weekly_sales_summary(self) -> TaskResult:
        """
        Genera resumen semanal de ventas.
        
        Usa account.move (facturas) para coincidir con reportes financieros.
        """
        started_at = datetime.now()
        
        self.logger.info("Generando resumen semanal (desde facturas)...")
        
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Facturas de la semana
        invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", week_start),
            ],
            ["amount_total_signed", "partner_id"],
            limit=1000
        )
        
        total_week = sum(inv.get("amount_total_signed", 0) for inv in invoices)
        unique_customers = len(set(
            inv["partner_id"][0] for inv in invoices 
            if inv.get("partner_id")
        ))
        
        # Cotizaciones pendientes (esto sí es de sale.order)
        quotes = self.search_read(
            "sale.order",
            [("state", "=", "draft")],
            ["amount_total"],
            limit=500
        )
        
        pending_amount = sum(q.get("amount_total", 0) for q in quotes)
        
        message = f"""
*📊 Resumen Semanal de Facturación*
_{self.format_date(week_start)} - {datetime.now().strftime('%d/%m/%Y')}_

*Facturación:* {self.format_currency(total_week)}
*Facturas:* {len(invoices)}
*Clientes únicos:* {unique_customers}

*Cotizaciones pendientes:*
- Cantidad: {len(quotes)}
- Monto: {self.format_currency(pending_amount)}

_¡Buen fin de semana!_
        """.strip()
        
        await self.notify(
            title=f"📊 Ventas semanales: {self.format_currency(total_week)}",
            message=message,
            priority=Priority.LOW,
            data={"weekly_total": total_week}
        )
        
        return TaskResult(
            task_name="weekly_summary",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"weekly_total": total_week}
        )
    
    async def analyze_margins(self) -> TaskResult:
        """Analiza márgenes de pedidos de venta."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Analizando márgenes de venta...")
        
        # Pedidos del último mes con margen
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        orders = self.search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            ["name", "partner_id", "amount_total", "margin", "margin_percent", "user_id"],
            limit=1000,
            order="date_order desc"
        )
        
        if not orders:
            return TaskResult(
                task_name="margin_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Calcular estadísticas
        total_sales = sum(o.get("amount_total", 0) for o in orders)
        total_margin = sum(o.get("margin", 0) for o in orders)
        avg_margin_pct = (total_margin / total_sales * 100) if total_sales > 0 else 0
        
        # Pedidos con margen bajo o negativo
        low_margin = [
            o for o in orders 
            if o.get("margin_percent", 100) < self.min_margin_percent
        ]
        
        negative_margin = [o for o in orders if o.get("margin", 0) < 0]
        
        message = f"""
*📊 Análisis de Márgenes (últimos 30 días)*

*Total ventas:* {self.format_currency(total_sales)}
*Margen total:* {self.format_currency(total_margin)}
*Margen promedio:* {avg_margin_pct:.1f}%

*Alertas:*
• Pedidos con margen <{self.min_margin_percent}%: {len(low_margin)}
• Pedidos con margen negativo: {len(negative_margin)}
"""
        
        if negative_margin:
            message += "\n*Pedidos con margen negativo:*\n"
            for o in negative_margin[:5]:
                partner = o["partner_id"][1] if o.get("partner_id") else "N/A"
                message += f"• {o['name']}: {o.get('margin_percent', 0):.1f}% ({partner[:20]})\n"
            
            await self.propose(
                title=f"⚠️ {len(negative_margin)} pedidos con margen negativo",
                description="Pedidos que generan pérdida",
                priority=Priority.HIGH,
                situation_summary=message,
                proposed_action_detail="Revisar costos y precios de estos pedidos",
                supporting_data={"negative_margin_orders": [o["id"] for o in negative_margin]},
                informational=True,
            )
            proposals_created += 1
        
        # Top 5 productos/líneas con peor margen
        lines = self.search_read(
            "sale.order.line",
            [
                ("order_id.state", "in", ["sale", "done"]),
                ("order_id.date_order", ">=", month_ago),
                ("margin_percent", "<", self.min_margin_percent),
            ],
            ["product_id", "margin_percent", "price_subtotal", "purchase_price"],
            limit=100,
            order="margin_percent asc"
        )
        
        if lines:
            # Agrupar por producto
            by_product = {}
            for line in lines:
                prod = line.get("product_id")
                if not prod:
                    continue
                prod_name = prod[1]
                if prod_name not in by_product:
                    by_product[prod_name] = {"count": 0, "total": 0, "margin_sum": 0}
                by_product[prod_name]["count"] += 1
                by_product[prod_name]["total"] += line.get("price_subtotal", 0)
                by_product[prod_name]["margin_sum"] += line.get("margin_percent", 0)
            
            message += "\n*Productos con margen bajo frecuente:*\n"
            sorted_prods = sorted(by_product.items(), key=lambda x: x[1]["count"], reverse=True)
            for prod, data in sorted_prods[:5]:
                avg = data["margin_sum"] / data["count"] if data["count"] > 0 else 0
                message += f"• {prod[:30]}: {data['count']} veces, promedio {avg:.1f}%\n"
        
        await self.notify(
            title=f"📊 Margen promedio: {avg_margin_pct:.1f}%",
            message=message,
            priority=Priority.MEDIUM if len(negative_margin) > 0 else Priority.LOW,
        )
        
        return TaskResult(
            task_name="margin_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={
                "total_sales": total_sales,
                "total_margin": total_margin,
                "avg_margin_pct": avg_margin_pct,
                "low_margin_count": len(low_margin),
                "negative_margin_count": len(negative_margin),
            }
        )
    
    async def check_pending_deliveries(self) -> TaskResult:
        """Revisa entregas pendientes y retrasadas."""
        started_at = datetime.now()
        
        self.logger.info("Revisando entregas pendientes...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Pedidos confirmados sin entregar completamente
        orders = self.search_read(
            "sale.order",
            [
                ("state", "=", "sale"),
                ("delivery_status", "in", ["pending", "partial"]),
                ("company_id", "=", self.company_id),
            ],
            ["name", "partner_id", "commitment_date", "expected_date", "amount_total", 
             "delivery_status", "user_id"],
            limit=200,
            order="commitment_date asc"
        )
        
        if not orders:
            return TaskResult(
                task_name="pending_deliveries",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Clasificar por estado
        delayed = []
        due_today = []
        upcoming = []
        
        for order in orders:
            # Usar commitment_date o expected_date
            due_date = order.get("commitment_date") or order.get("expected_date")
            if not due_date:
                upcoming.append(order)
                continue
            
            due_str = str(due_date)[:10]
            
            if due_str < today:
                order["days_late"] = self.days_between(due_str)
                delayed.append(order)
            elif due_str == today:
                due_today.append(order)
            else:
                upcoming.append(order)
        
        message = f"""
*🚚 Entregas Pendientes*

*Resumen:*
• 🔴 Retrasadas: {len(delayed)}
• 🟡 Para hoy: {len(due_today)}
• 🟢 Próximas: {len(upcoming)}
"""
        
        if delayed:
            delayed.sort(key=lambda x: x.get("days_late", 0), reverse=True)
            total_delayed = sum(o.get("amount_total", 0) for o in delayed)
            
            message += f"\n*🔴 Pedidos retrasados ({self.format_currency(total_delayed)}):*\n"
            for o in delayed[:10]:
                partner = o["partner_id"][1] if o.get("partner_id") else "N/A"
                days = o.get("days_late", 0)
                message += f"• {o['name']}: {partner[:20]} ({days} días)\n"
        
        if due_today:
            message += f"\n*🟡 Para entregar hoy ({len(due_today)}):*\n"
            for o in due_today[:5]:
                partner = o["partner_id"][1] if o.get("partner_id") else "N/A"
                message += f"• {o['name']}: {partner[:25]}\n"
        
        priority = Priority.HIGH if len(delayed) > 5 else Priority.MEDIUM if delayed else Priority.LOW
        
        await self.notify(
            title=f"🚚 {len(delayed)} entregas retrasadas, {len(due_today)} para hoy",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="pending_deliveries",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "delayed": len(delayed),
                "due_today": len(due_today),
                "upcoming": len(upcoming),
            }
        )
    
    async def analyze_salesperson_performance(self) -> TaskResult:
        """Analiza rendimiento por vendedor."""
        started_at = datetime.now()
        
        self.logger.info("Analizando rendimiento por vendedor...")
        
        # Último mes
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Pedidos confirmados del mes
        orders = self.search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            ["user_id", "team_id", "amount_total", "margin", "margin_percent"],
            limit=5000
        )
        
        # Agrupar por vendedor
        by_salesperson = {}
        by_team = {}
        
        for order in orders:
            user = order.get("user_id")
            team = order.get("team_id")
            
            user_name = user[1] if user else "Sin asignar"
            team_name = team[1] if team else "Sin equipo"
            
            # Por vendedor
            if user_name not in by_salesperson:
                by_salesperson[user_name] = {
                    "orders": 0, "total": 0, "margin": 0
                }
            by_salesperson[user_name]["orders"] += 1
            by_salesperson[user_name]["total"] += order.get("amount_total", 0)
            by_salesperson[user_name]["margin"] += order.get("margin", 0)
            
            # Por equipo
            if team_name not in by_team:
                by_team[team_name] = {"orders": 0, "total": 0, "margin": 0}
            by_team[team_name]["orders"] += 1
            by_team[team_name]["total"] += order.get("amount_total", 0)
            by_team[team_name]["margin"] += order.get("margin", 0)
        
        # Ordenar por total
        sorted_salespeople = sorted(
            by_salesperson.items(), 
            key=lambda x: x[1]["total"], 
            reverse=True
        )
        
        sorted_teams = sorted(
            by_team.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )
        
        total_sales = sum(s[1]["total"] for s in sorted_salespeople)
        total_margin = sum(s[1]["margin"] for s in sorted_salespeople)
        
        message = f"""
*👥 Rendimiento de Ventas (últimos 30 días)*

*Total:* {self.format_currency(total_sales)}
*Margen:* {self.format_currency(total_margin)}

*Por vendedor:*
"""
        
        for i, (name, data) in enumerate(sorted_salespeople[:10], 1):
            pct = (data["total"] / total_sales * 100) if total_sales > 0 else 0
            margin_pct = (data["margin"] / data["total"] * 100) if data["total"] > 0 else 0
            message += f"{i}. {name[:20]}: {self.format_currency(data['total'])} ({pct:.0f}%) - Margen: {margin_pct:.0f}%\n"
        
        if len(sorted_teams) > 1:
            message += "\n*Por equipo:*\n"
            for name, data in sorted_teams[:5]:
                pct = (data["total"] / total_sales * 100) if total_sales > 0 else 0
                message += f"• {name}: {self.format_currency(data['total'])} ({pct:.0f}%)\n"
        
        await self.notify(
            title=f"👥 Top vendedor: {sorted_salespeople[0][0] if sorted_salespeople else 'N/A'}",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="salesperson_performance",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_sales": total_sales,
                "salespeople_count": len(sorted_salespeople),
                "teams_count": len(sorted_teams),
            }
        )
    
    # ==================== Helpers ====================
    
    def _get_customer_average_invoice(self, partner_id: int) -> float:
        """Calcula el monto promedio de factura de un cliente."""
        invoices = self.search_read(
            "account.move",
            [
                ("partner_id", "=", partner_id),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
            ],
            ["amount_total_signed"],
            limit=50,
            order="invoice_date desc"
        )
        
        if not invoices:
            return 0
        
        return sum(inv.get("amount_total_signed", 0) for inv in invoices) / len(invoices)


def create_sales_agent() -> SalesAgent:
    """Crea y retorna el agente de ventas."""
    return SalesAgent()
