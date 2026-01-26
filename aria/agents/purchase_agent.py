"""
Agente de Compras - Gestión de abastecimiento.

Monitorea niveles de stock, órdenes de compra pendientes,
evaluación de proveedores y variaciones de precios.
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.task import TaskDefinition, TaskResult
from aria.models.proposal import Priority


class PurchaseAgent(BaseAgent):
    """
    Agente autónomo para gestión de compras y abastecimiento.
    
    Monitorea:
    - Productos bajo punto de reorden
    - Órdenes de compra pendientes
    - Estado de recepción (receipt_status)
    - Evaluación de proveedores (OTIF)
    - Variaciones de precios
    - Recepciones atrasadas
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="compras",
            description="Gestión de abastecimiento y órdenes de compra"
        )
        
        self.company_id = settings.odoo.company_id
        
        # Configuración
        self.critical_stock_days = 5  # Días de stock crítico
        self.price_variation_threshold = 0.05  # 5% variación de precio
        self.late_receipt_days = 2  # Días de atraso para alertar
    
    def _register_tasks(self) -> None:
        """Registra las tareas del agente de compras."""
        
        # Verificar puntos de reorden
        self.register_task(TaskDefinition(
            name="check_reorder_points",
            method="check_reorder_points",
            schedule="0 7 * * *",  # Diario 7:00 AM
            description="Verifica productos bajo punto de reorden"
        ))
        
        # OC pendientes
        self.register_task(TaskDefinition(
            name="check_pending_orders",
            method="check_pending_orders",
            schedule="0 9 * * *",  # Diario 9:00 AM
            description="Revisa órdenes de compra pendientes de confirmar"
        ))
        
        # Evaluación de proveedores
        self.register_task(TaskDefinition(
            name="supplier_evaluation",
            method="evaluate_suppliers",
            schedule="0 10 1 * *",  # Día 1 de cada mes
            description="Evalúa desempeño de proveedores (OTIF)"
        ))
        
        # Variaciones de precio
        self.register_task(TaskDefinition(
            name="price_variations",
            method="check_price_variations",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Detecta variaciones significativas de precio"
        ))
        
        # Recepciones pendientes
        self.register_task(TaskDefinition(
            name="pending_receipts",
            method="check_pending_receipts",
            schedule="0 */4 * * *",  # Cada 4 horas
            description="Alerta sobre recepciones atrasadas"
        ))
        
        # Análisis de estado de recepciones
        self.register_task(TaskDefinition(
            name="receipt_status_analysis",
            method="analyze_receipt_status",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Analiza estados de recepción de OC"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de compras."""
        
        low_stock = self._get_products_below_reorder()
        low_stock_count = len(low_stock)
        
        pending_orders = self.search_count(
            "purchase.order",
            [("state", "in", ["draft", "sent"])]
        )
        
        late_receipts = self.search_count(
            "stock.picking",
            [
                ("picking_type_code", "=", "incoming"),
                ("state", "not in", ["done", "cancel"]),
                ("scheduled_date", "<", datetime.now().strftime("%Y-%m-%d")),
            ]
        )
        
        # Determinar estado
        if low_stock_count > 10 or late_receipts > 5:
            status = "critical"
        elif low_stock_count > 5 or late_receipts > 2:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "low_stock_products": low_stock_count,
            "pending_purchase_orders": pending_orders,
            "late_receipts": late_receipts,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_reorder_points(self) -> TaskResult:
        """Verifica productos bajo punto de reorden."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando puntos de reorden...")
        
        products = self._get_products_below_reorder()
        
        if not products:
            return TaskResult(
                task_name="check_reorder_points",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                records_processed=0,
            )
        
        # Productos críticos (stock para menos de X días)
        critical = []
        warning = []
        
        for p in products:
            product_info = p.get("product_id", [0, "Desconocido"])
            product_name = product_info[1] if isinstance(product_info, list) else str(product_info)
            qty_to_order = p.get("qty_to_order", 0)
            
            # Calcular días de stock aproximados
            # (simplificado - en producción usar consumo promedio)
            days_stock = p.get("product_min_qty", 0) / max(qty_to_order, 1) * 7
            
            item = {
                "id": p.get("id"),
                "product_id": product_info[0] if isinstance(product_info, list) else 0,
                "name": product_name,
                "qty_to_order": qty_to_order,
                "days_stock": days_stock,
            }
            
            if days_stock <= self.critical_stock_days:
                critical.append(item)
            else:
                warning.append(item)
        
        # Propuestas para productos críticos
        for p in critical:
            await self.propose(
                title=f"🔴 Compra urgente: {p['name'][:40]}",
                description="Stock crítico - requiere reabastecimiento inmediato",
                priority=Priority.CRITICAL,
                situation_summary=f"""
Producto: {p['name']}
Stock estimado: {p['days_stock']:.0f} días
Cantidad a ordenar: {p['qty_to_order']:.0f} unidades

⚠️ CRÍTICO: Stock por debajo del mínimo operativo.
                """.strip(),
                proposed_action_detail="Generar orden de compra urgente",
                supporting_data=p,
                payload={"product_id": p["product_id"], "qty": p["qty_to_order"]},
            )
            proposals_created += 1
        
        # Notificación resumen
        if products:
            message = f"*{len(critical)} productos críticos, {len(warning)} en alerta*\n\n"
            
            if critical:
                message += "*🔴 Críticos:*\n"
                for p in critical[:5]:
                    message += f"• {p['name'][:30]}: {p['qty_to_order']:.0f} unidades\n"
            
            if warning:
                message += "\n*🟡 Alerta:*\n"
                for p in warning[:5]:
                    message += f"• {p['name'][:30]}: {p['qty_to_order']:.0f} unidades\n"
            
            await self.notify(
                title=f"📦 {len(products)} productos bajo reorden",
                message=message,
                priority=Priority.HIGH if critical else Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="check_reorder_points",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            records_processed=len(products),
        )
    
    async def check_pending_orders(self) -> TaskResult:
        """Revisa órdenes de compra pendientes de confirmar."""
        started_at = datetime.now()
        
        self.logger.info("Verificando OC pendientes...")
        
        pending = self.search_read(
            "purchase.order",
            [("state", "in", ["draft", "sent"])],
            ["name", "partner_id", "amount_total", "date_order", "create_date"],
            limit=100,
            order="create_date asc"
        )
        
        if not pending:
            return TaskResult(
                task_name="check_pending_orders",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por antigüedad
        old_orders = []  # > 3 días
        recent_orders = []
        
        for order in pending:
            create_date = order.get("create_date", "")
            if create_date:
                days_old = self.days_between(create_date)
                if days_old >= 3:
                    old_orders.append({
                        "name": order.get("name"),
                        "partner": order.get("partner_id", [0, ""])[1] if order.get("partner_id") else "",
                        "amount": order.get("amount_total", 0),
                        "days_old": days_old,
                    })
                else:
                    recent_orders.append(order)
        
        total_amount = sum(o.get("amount_total", 0) for o in pending)
        
        message = f"""
*📋 {len(pending)} órdenes de compra pendientes*

*Total:* {self.format_currency(total_amount)}
*Antiguas (>3 días):* {len(old_orders)}
*Recientes:* {len(recent_orders)}
        """.strip()
        
        if old_orders:
            message += "\n\n*Requieren atención:*\n"
            for o in old_orders[:5]:
                message += f"• {o['name']}: {o['partner'][:20]} - {self.format_currency(o['amount'])} ({o['days_old']}d)\n"
        
        await self.notify(
            title=f"📋 {len(pending)} OC pendientes: {self.format_currency(total_amount)}",
            message=message,
            priority=Priority.HIGH if old_orders else Priority.MEDIUM,
        )
        
        return TaskResult(
            task_name="check_pending_orders",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"pending_count": len(pending), "total": total_amount}
        )
    
    async def evaluate_suppliers(self) -> TaskResult:
        """Evalúa desempeño de proveedores (OTIF - On Time In Full)."""
        started_at = datetime.now()
        
        self.logger.info("Evaluando proveedores...")
        
        # Últimos 6 meses
        date_from = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        
        # Obtener recepciones completadas
        receipts = self.search_read(
            "stock.picking",
            [
                ("picking_type_code", "=", "incoming"),
                ("state", "=", "done"),
                ("date_done", ">=", date_from),
            ],
            ["partner_id", "scheduled_date", "date_done"],
            limit=5000
        )
        
        if not receipts:
            return TaskResult(
                task_name="supplier_evaluation",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Calcular OTIF por proveedor
        by_supplier: dict[int, dict] = {}
        
        for r in receipts:
            partner = r.get("partner_id")
            if not partner:
                continue
            
            partner_id = partner[0]
            partner_name = partner[1]
            
            if partner_id not in by_supplier:
                by_supplier[partner_id] = {
                    "name": partner_name,
                    "total": 0,
                    "on_time": 0,
                }
            
            by_supplier[partner_id]["total"] += 1
            
            # Verificar si fue a tiempo
            scheduled = r.get("scheduled_date", "")
            done = r.get("date_done", "")
            
            if scheduled and done:
                scheduled_date = scheduled[:10] if isinstance(scheduled, str) else str(scheduled)[:10]
                done_date = done[:10] if isinstance(done, str) else str(done)[:10]
                
                if done_date <= scheduled_date:
                    by_supplier[partner_id]["on_time"] += 1
        
        # Calcular OTIF %
        suppliers = []
        for partner_id, data in by_supplier.items():
            if data["total"] >= 3:  # Mínimo 3 entregas para evaluar
                otif = (data["on_time"] / data["total"]) * 100
                suppliers.append({
                    "id": partner_id,
                    "name": data["name"],
                    "total": data["total"],
                    "on_time": data["on_time"],
                    "otif": otif,
                })
        
        # Ordenar por OTIF
        suppliers.sort(key=lambda x: x["otif"])
        
        # Proveedores con bajo OTIF
        low_performers = [s for s in suppliers if s["otif"] < 80]
        top_performers = sorted(suppliers, key=lambda x: x["otif"], reverse=True)[:5]
        
        message = f"""
*📊 Evaluación de Proveedores (6 meses)*

*Proveedores evaluados:* {len(suppliers)}
*Entregas analizadas:* {len(receipts)}

*🏆 Top 5:*
        """.strip()
        
        for s in top_performers:
            message += f"\n• {s['name'][:25]}: {s['otif']:.0f}% ({s['on_time']}/{s['total']})"
        
        if low_performers:
            message += "\n\n*⚠️ Bajo desempeño (<80%):*"
            for s in low_performers[:5]:
                message += f"\n• {s['name'][:25]}: {s['otif']:.0f}%"
        
        await self.notify(
            title="📊 Evaluación de Proveedores",
            message=message,
            priority=Priority.LOW,
            data={"suppliers": suppliers[:20]}
        )
        
        return TaskResult(
            task_name="supplier_evaluation",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"evaluated": len(suppliers), "low_performers": len(low_performers)}
        )
    
    async def check_price_variations(self) -> TaskResult:
        """Detecta variaciones significativas de precio en compras."""
        started_at = datetime.now()
        
        self.logger.info("Analizando variaciones de precio...")
        
        # Últimos 90 días
        date_from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # Obtener líneas de OC confirmadas
        lines = self.search_read(
            "purchase.order.line",
            [
                ("order_id.state", "in", ["purchase", "done"]),
                ("order_id.date_order", ">=", date_from),
            ],
            ["product_id", "price_unit", "order_id", "date_planned"],
            limit=5000,
            order="date_planned asc"
        )
        
        if not lines:
            return TaskResult(
                task_name="price_variations",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por producto
        by_product: dict[int, list] = {}
        
        for line in lines:
            product = line.get("product_id")
            if not product:
                continue
            
            product_id = product[0]
            
            if product_id not in by_product:
                by_product[product_id] = []
            
            by_product[product_id].append({
                "price": line.get("price_unit", 0),
                "date": line.get("date_planned", ""),
                "product_name": product[1],
            })
        
        # Detectar variaciones
        variations = []
        
        for product_id, prices in by_product.items():
            if len(prices) < 2:
                continue
            
            # Ordenar por fecha
            prices.sort(key=lambda x: x["date"])
            
            first_price = prices[0]["price"]
            last_price = prices[-1]["price"]
            
            if first_price > 0:
                variation = (last_price - first_price) / first_price
                
                if abs(variation) >= self.price_variation_threshold:
                    variations.append({
                        "product_id": product_id,
                        "name": prices[0]["product_name"],
                        "first_price": first_price,
                        "last_price": last_price,
                        "variation_pct": variation * 100,
                    })
        
        if variations:
            # Ordenar por variación (mayor primero)
            variations.sort(key=lambda x: abs(x["variation_pct"]), reverse=True)
            
            increases = [v for v in variations if v["variation_pct"] > 0]
            decreases = [v for v in variations if v["variation_pct"] < 0]
            
            message = f"*Variaciones de precio detectadas (últimos 90 días)*\n\n"
            
            if increases:
                message += "*📈 Incrementos:*\n"
                for v in increases[:5]:
                    message += f"• {v['name'][:25]}: +{v['variation_pct']:.1f}%\n"
            
            if decreases:
                message += "\n*📉 Reducciones:*\n"
                for v in decreases[:5]:
                    message += f"• {v['name'][:25]}: {v['variation_pct']:.1f}%\n"
            
            await self.notify(
                title=f"💰 {len(variations)} productos con variación de precio",
                message=message,
                priority=Priority.MEDIUM if increases else Priority.LOW,
                data={"variations": variations[:20]}
            )
        
        return TaskResult(
            task_name="price_variations",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"variations_found": len(variations)}
        )
    
    async def check_pending_receipts(self) -> TaskResult:
        """Alerta sobre recepciones atrasadas."""
        started_at = datetime.now()
        
        self.logger.info("Verificando recepciones pendientes...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        late = self.search_read(
            "stock.picking",
            [
                ("picking_type_code", "=", "incoming"),
                ("state", "not in", ["done", "cancel"]),
                ("scheduled_date", "<", today),
            ],
            ["name", "partner_id", "scheduled_date", "origin"],
            limit=100,
            order="scheduled_date asc"
        )
        
        if not late:
            return TaskResult(
                task_name="pending_receipts",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        message = f"*📦 {len(late)} recepciones atrasadas*\n\n"
        
        for r in late[:10]:
            partner = r.get("partner_id", [0, ""])[1] if r.get("partner_id") else "N/A"
            scheduled = r.get("scheduled_date", "")[:10] if r.get("scheduled_date") else "N/A"
            days_late = self.days_between(scheduled) if scheduled != "N/A" else 0
            
            message += f"• {r.get('name', '')}: {partner[:20]} ({days_late}d atraso)\n"
        
        if len(late) > 10:
            message += f"\n... y {len(late) - 10} más"
        
        message += "\n\n_Contactar proveedores para seguimiento_"
        
        await self.notify(
            title=f"📦 {len(late)} recepciones atrasadas",
            message=message,
            priority=Priority.HIGH,
        )
        
        return TaskResult(
            task_name="pending_receipts",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"late_count": len(late)}
        )
    
    async def analyze_receipt_status(self) -> TaskResult:
        """Analiza estados de recepción de órdenes de compra."""
        started_at = datetime.now()
        
        self.logger.info("Analizando estados de recepción...")
        
        # Obtener OC confirmadas del último mes
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        orders = self.search_read(
            "purchase.order",
            [
                ("state", "=", "purchase"),
                ("date_order", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            [
                "name", "partner_id", "amount_total", "date_order",
                "date_planned", "effective_date", "receipt_status", "invoice_status"
            ],
            limit=500,
            order="date_order desc"
        )
        
        if not orders:
            return TaskResult(
                task_name="receipt_status_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por estado de recepción
        by_receipt_status = {
            "pending": [],
            "partial": [],
            "full": [],
        }
        
        total_amount = 0
        
        for order in orders:
            status = order.get("receipt_status", "pending")
            if status in by_receipt_status:
                by_receipt_status[status].append(order)
            total_amount += order.get("amount_total", 0)
        
        # Calcular montos por estado
        pending_amount = sum(o.get("amount_total", 0) for o in by_receipt_status["pending"])
        partial_amount = sum(o.get("amount_total", 0) for o in by_receipt_status["partial"])
        full_amount = sum(o.get("amount_total", 0) for o in by_receipt_status["full"])
        
        message = f"""
*📦 Estado de Recepciones (últimos 30 días)*

*Resumen de {len(orders)} OC confirmadas:*
• Total: {self.format_currency(total_amount)}

*Por estado de recepción:*
• 🔴 Pendiente: {len(by_receipt_status['pending'])} OC ({self.format_currency(pending_amount)})
• 🟡 Parcial: {len(by_receipt_status['partial'])} OC ({self.format_currency(partial_amount)})
• 🟢 Completa: {len(by_receipt_status['full'])} OC ({self.format_currency(full_amount)})

"""
        
        # Listar OC con recepción parcial
        if by_receipt_status["partial"]:
            message += "*OC con recepción parcial:*\n"
            for order in by_receipt_status["partial"][:5]:
                partner = order["partner_id"][1] if order.get("partner_id") else "N/A"
                message += f"• {order['name']}: {partner[:20]} ({self.format_currency(order.get('amount_total', 0))})\n"
        
        # Identificar OC antiguas sin recibir
        old_pending = [
            o for o in by_receipt_status["pending"]
            if o.get("date_planned") and o["date_planned"] < datetime.now().strftime("%Y-%m-%d")
        ]
        
        if old_pending:
            message += f"\n⚠️ *{len(old_pending)} OC atrasadas sin recibir*"
        
        await self.notify(
            title=f"📦 {len(by_receipt_status['pending'])} OC pendientes de recepción",
            message=message,
            priority=Priority.MEDIUM if len(old_pending) > 5 else Priority.LOW,
        )
        
        return TaskResult(
            task_name="receipt_status_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_orders": len(orders),
                "pending": len(by_receipt_status["pending"]),
                "partial": len(by_receipt_status["partial"]),
                "full": len(by_receipt_status["full"]),
                "old_pending": len(old_pending),
            }
        )
    
    # ==================== Helpers ====================
    
    def _get_products_below_reorder(self) -> list[dict]:
        """Obtiene productos que necesitan reordenarse."""
        return self.search_read(
            "stock.warehouse.orderpoint",
            [("qty_to_order", ">", 0)],
            ["product_id", "qty_to_order", "product_min_qty", "product_max_qty"],
            limit=500
        )


def create_purchase_agent() -> PurchaseAgent:
    """Crea y retorna el agente de compras."""
    return PurchaseAgent()
