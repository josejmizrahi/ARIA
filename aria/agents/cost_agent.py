"""
Agente de Costos - Control y Análisis de Costos.

Responsabilidades:
- Monitorear variaciones de costo estándar vs real
- Analizar costos de productos
- Controlar gastos por categoría/cuenta analítica
- Detectar anomalías en costos de producción
- Evaluar costos de mano de obra
- Generar alertas de desviaciones de presupuesto
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class CostAgent(BaseAgent):
    """
    Agente autónomo para gestión y control de costos.
    
    Monitorea costos de productos, producción, gastos operativos
    y detecta desviaciones significativas.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="costos",
            description="Control de costos, márgenes y análisis de rentabilidad"
        )
        
        self.company_id = settings.odoo.company_id
        
        # Configuración de umbrales
        self.cost_variation_threshold = 0.10  # 10% variación para alertar
        self.margin_warning_threshold = 0.15  # 15% margen mínimo
        self.expense_growth_threshold = 0.20  # 20% crecimiento de gastos
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de costos."""
        
        # Variaciones de costo de productos
        self.register_task(TaskDefinition(
            name="product_cost_variations",
            method="check_product_cost_variations",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Detecta variaciones significativas en costos de productos"
        ))
        
        # Análisis de márgenes por producto
        self.register_task(TaskDefinition(
            name="product_margin_analysis",
            method="analyze_product_margins",
            schedule="0 9 1 * *",  # Día 1 del mes
            description="Analiza márgenes por producto/categoría"
        ))
        
        # Gastos por cuenta analítica
        self.register_task(TaskDefinition(
            name="analytic_costs",
            method="analyze_analytic_costs",
            schedule="0 10 * * 1",  # Lunes 10:00 AM
            description="Analiza costos por cuenta analítica"
        ))
        
        # Costos de producción
        self.register_task(TaskDefinition(
            name="production_costs",
            method="analyze_production_costs",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Analiza costos de órdenes de producción"
        ))
        
        # Gastos operativos
        self.register_task(TaskDefinition(
            name="operating_expenses",
            method="analyze_operating_expenses",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Analiza gastos operativos por categoría"
        ))
        
        # Productos sin costo definido
        self.register_task(TaskDefinition(
            name="missing_costs",
            method="check_missing_costs",
            schedule="0 7 * * 1",  # Lunes 7:00 AM
            description="Detecta productos sin costo estándar"
        ))
        
        # Comparación costo vs precio
        self.register_task(TaskDefinition(
            name="cost_vs_price",
            method="compare_cost_vs_price",
            schedule="0 8 15 * *",  # Día 15 del mes
            description="Compara costos vs precios de venta"
        ))
        
        # Resumen mensual de costos
        self.register_task(TaskDefinition(
            name="monthly_cost_summary",
            method="monthly_summary",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Resumen mensual de costos y márgenes"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de costos."""
        
        # Productos con costo = 0
        zero_cost = self.search_count(
            "product.product",
            [
                ("type", "in", ["product", "consu"]),
                ("standard_price", "<=", 0),
                ("active", "=", True),
                ("sale_ok", "=", True),
            ]
        )
        
        # Total productos vendibles
        total_products = self.search_count(
            "product.product",
            [
                ("type", "in", ["product", "consu"]),
                ("active", "=", True),
                ("sale_ok", "=", True),
            ]
        )
        
        # Obtener margen promedio del mes
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
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
        if zero_cost > total_products * 0.2:
            status = "critical"
        elif zero_cost > total_products * 0.1 or avg_margin < self.margin_warning_threshold * 100:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "products_without_cost": zero_cost,
            "total_products": total_products,
            "avg_margin_percent": round(avg_margin, 1),
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_product_cost_variations(self) -> TaskResult:
        """Detecta variaciones significativas en costos de productos."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando variaciones de costo de productos...")
        
        # Obtener productos con historial de precios
        # Usamos account.move.line de facturas de compra para detectar cambios
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        two_months_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        
        # Compras del último mes
        recent_purchases = self.search_read(
            "account.move.line",
            [
                ("move_id.move_type", "=", "in_invoice"),
                ("move_id.state", "=", "posted"),
                ("date", ">=", month_ago),
                ("product_id", "!=", False),
                ("company_id", "=", self.company_id),
            ],
            ["product_id", "price_unit", "quantity"],
            limit=5000
        )
        
        # Compras del mes anterior
        previous_purchases = self.search_read(
            "account.move.line",
            [
                ("move_id.move_type", "=", "in_invoice"),
                ("move_id.state", "=", "posted"),
                ("date", ">=", two_months_ago),
                ("date", "<", month_ago),
                ("product_id", "!=", False),
                ("company_id", "=", self.company_id),
            ],
            ["product_id", "price_unit", "quantity"],
            limit=5000
        )
        
        # Calcular precio promedio por producto
        def calc_avg_price(purchases):
            by_product = {}
            for p in purchases:
                prod = p.get("product_id")
                if not prod:
                    continue
                prod_id = prod[0]
                prod_name = prod[1]
                qty = p.get("quantity", 0)
                price = p.get("price_unit", 0)
                
                if prod_id not in by_product:
                    by_product[prod_id] = {"name": prod_name, "total": 0, "qty": 0}
                by_product[prod_id]["total"] += price * qty
                by_product[prod_id]["qty"] += qty
            
            return {
                pid: {
                    "name": data["name"],
                    "avg_price": data["total"] / data["qty"] if data["qty"] > 0 else 0
                }
                for pid, data in by_product.items()
            }
        
        recent_avg = calc_avg_price(recent_purchases)
        previous_avg = calc_avg_price(previous_purchases)
        
        # Detectar variaciones significativas
        variations = []
        
        for prod_id, current in recent_avg.items():
            if prod_id in previous_avg:
                prev_price = previous_avg[prod_id]["avg_price"]
                curr_price = current["avg_price"]
                
                if prev_price > 0:
                    variation = (curr_price - prev_price) / prev_price
                    
                    if abs(variation) >= self.cost_variation_threshold:
                        variations.append({
                            "product_id": prod_id,
                            "name": current["name"],
                            "prev_price": prev_price,
                            "curr_price": curr_price,
                            "variation": variation * 100,
                        })
        
        if variations:
            # Ordenar por variación (mayores primero)
            variations.sort(key=lambda x: abs(x["variation"]), reverse=True)
            
            increases = [v for v in variations if v["variation"] > 0]
            decreases = [v for v in variations if v["variation"] < 0]
            
            message = f"""
*📈 Variaciones de Costo de Compra (vs mes anterior)*

*Aumentos ({len(increases)}):*
"""
            for v in increases[:10]:
                message += f"• {v['name'][:30]}: +{v['variation']:.1f}% ({self.format_currency(v['prev_price'])} → {self.format_currency(v['curr_price'])})\n"
            
            if decreases:
                message += f"\n*Disminuciones ({len(decreases)}):*\n"
                for v in decreases[:5]:
                    message += f"• {v['name'][:30]}: {v['variation']:.1f}%\n"
            
            # Propuesta si hay aumentos significativos
            significant_increases = [v for v in increases if v["variation"] > 20]
            if significant_increases:
                await self.propose(
                    title=f"⚠️ {len(significant_increases)} productos con aumento >20%",
                    description="Variaciones de costo que requieren revisión",
                    priority=Priority.HIGH,
                    situation_summary=message,
                    proposed_action_detail="Revisar proveedores alternativos o negociar precios",
                    supporting_data={"variations": significant_increases[:20]},
                    informational=True,
                )
                proposals_created += 1
            
            await self.notify(
                title=f"📈 {len(increases)} productos con aumento de costo",
                message=message,
                priority=Priority.MEDIUM if len(increases) > 10 else Priority.LOW,
            )
        
        return TaskResult(
            task_name="product_cost_variations",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"variations_count": len(variations) if variations else 0}
        )
    
    async def analyze_product_margins(self) -> TaskResult:
        """Analiza márgenes por producto y categoría."""
        started_at = datetime.now()
        
        self.logger.info("Analizando márgenes por producto...")
        
        # Líneas de venta del último mes
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        lines = self.search_read(
            "sale.order.line",
            [
                ("order_id.state", "in", ["sale", "done"]),
                ("order_id.date_order", ">=", month_ago),
                ("order_id.company_id", "=", self.company_id),
            ],
            ["product_id", "price_subtotal", "margin", "margin_percent", "product_uom_qty"],
            limit=10000
        )
        
        if not lines:
            return TaskResult(
                task_name="product_margin_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por producto
        by_product = {}
        total_sales = 0
        total_margin = 0
        
        for line in lines:
            prod = line.get("product_id")
            if not prod:
                continue
            
            prod_name = prod[1]
            sales = line.get("price_subtotal", 0)
            margin = line.get("margin", 0)
            
            if prod_name not in by_product:
                by_product[prod_name] = {"sales": 0, "margin": 0, "qty": 0}
            
            by_product[prod_name]["sales"] += sales
            by_product[prod_name]["margin"] += margin
            by_product[prod_name]["qty"] += line.get("product_uom_qty", 0)
            
            total_sales += sales
            total_margin += margin
        
        # Calcular margen % por producto
        for prod_name, data in by_product.items():
            data["margin_pct"] = (
                data["margin"] / data["sales"] * 100
                if data["sales"] > 0 else 0
            )
        
        # Ordenar por margen (menor primero para detectar problemas)
        sorted_by_margin = sorted(
            by_product.items(),
            key=lambda x: x[1]["margin_pct"]
        )
        
        # Productos con margen negativo o muy bajo
        low_margin = [(n, d) for n, d in sorted_by_margin if d["margin_pct"] < self.margin_warning_threshold * 100]
        negative_margin = [(n, d) for n, d in sorted_by_margin if d["margin_pct"] < 0]
        
        # Top vendidos
        sorted_by_sales = sorted(
            by_product.items(),
            key=lambda x: x[1]["sales"],
            reverse=True
        )
        
        avg_margin_pct = (total_margin / total_sales * 100) if total_sales > 0 else 0
        
        message = f"""
*📊 Análisis de Márgenes por Producto (últimos 30 días)*

*Totales:*
• Ventas: {self.format_currency(total_sales)}
• Margen: {self.format_currency(total_margin)}
• Margen promedio: {avg_margin_pct:.1f}%
• Productos vendidos: {len(by_product)}

"""
        
        if negative_margin:
            message += f"*🔴 Productos con margen negativo ({len(negative_margin)}):*\n"
            for name, data in negative_margin[:5]:
                message += f"• {name[:30]}: {data['margin_pct']:.1f}% ({self.format_currency(data['margin'])})\n"
            message += "\n"
        
        if low_margin and len(low_margin) != len(negative_margin):
            other_low = [(n, d) for n, d in low_margin if d["margin_pct"] >= 0]
            if other_low:
                message += f"*🟡 Margen bajo (<{self.margin_warning_threshold*100:.0f}%) ({len(other_low)}):*\n"
                for name, data in other_low[:5]:
                    message += f"• {name[:30]}: {data['margin_pct']:.1f}%\n"
                message += "\n"
        
        message += "*Top 5 por ventas:*\n"
        for name, data in sorted_by_sales[:5]:
            message += f"• {name[:30]}: {self.format_currency(data['sales'])} (Margen: {data['margin_pct']:.1f}%)\n"
        
        priority = Priority.HIGH if negative_margin else Priority.MEDIUM if low_margin else Priority.LOW
        
        await self.notify(
            title=f"📊 Margen promedio: {avg_margin_pct:.1f}% | {len(negative_margin)} productos negativos",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="product_margin_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_sales": total_sales,
                "total_margin": total_margin,
                "avg_margin_pct": avg_margin_pct,
                "negative_margin_count": len(negative_margin),
            }
        )
    
    async def analyze_analytic_costs(self) -> TaskResult:
        """Analiza costos por cuenta analítica."""
        started_at = datetime.now()
        
        self.logger.info("Analizando costos por cuenta analítica...")
        
        # Verificar si hay cuentas analíticas
        if not self._model_exists("account.analytic.line"):
            return TaskResult(
                task_name="analytic_costs",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo analítico no disponible"}
            )
        
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Líneas analíticas del último mes (costos son negativos)
        lines = self.search_read(
            "account.analytic.line",
            [
                ("date", ">=", month_ago),
                ("amount", "<", 0),  # Costos
                ("company_id", "=", self.company_id),
            ],
            ["account_id", "name", "amount", "date"],
            limit=5000
        )
        
        if not lines:
            return TaskResult(
                task_name="analytic_costs",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por cuenta analítica
        by_account = {}
        total_cost = 0
        
        for line in lines:
            account = line.get("account_id")
            account_name = account[1] if account else "Sin cuenta"
            
            amount = abs(line.get("amount", 0))  # Convertir a positivo
            
            if account_name not in by_account:
                by_account[account_name] = {"total": 0, "count": 0}
            
            by_account[account_name]["total"] += amount
            by_account[account_name]["count"] += 1
            total_cost += amount
        
        # Ordenar por costo
        sorted_accounts = sorted(
            by_account.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )
        
        message = f"""
*💰 Costos por Cuenta Analítica (últimos 30 días)*

*Total costos:* {self.format_currency(total_cost)}
*Cuentas analíticas:* {len(by_account)}

*Distribución:*
"""
        
        for name, data in sorted_accounts[:10]:
            pct = (data["total"] / total_cost * 100) if total_cost > 0 else 0
            message += f"• {name[:35]}: {self.format_currency(data['total'])} ({pct:.1f}%)\n"
        
        await self.notify(
            title=f"💰 Costos analíticos: {self.format_currency(total_cost)}",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="analytic_costs",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"total_cost": total_cost}
        )
    
    async def analyze_production_costs(self) -> TaskResult:
        """Analiza costos de órdenes de producción."""
        started_at = datetime.now()
        
        self.logger.info("Analizando costos de producción...")
        
        if not self._model_exists("mrp.production"):
            return TaskResult(
                task_name="production_costs",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo MRP no disponible"}
            )
        
        # Órdenes terminadas del último mes
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        productions = self.search_read(
            "mrp.production",
            [
                ("state", "=", "done"),
                ("date_finished", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "product_qty", "qty_produced"],
            limit=500
        )
        
        if not productions:
            return TaskResult(
                task_name="production_costs",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Obtener costos de productos producidos
        product_ids = [p["product_id"][0] for p in productions if p.get("product_id")]
        
        if product_ids:
            products = self.search_read(
                "product.product",
                [("id", "in", product_ids)],
                ["id", "name", "standard_price"],
                limit=500
            )
            product_costs = {p["id"]: p["standard_price"] for p in products}
        else:
            product_costs = {}
        
        # Calcular valor de producción
        total_produced_value = 0
        by_product = {}
        
        for prod in productions:
            product = prod.get("product_id")
            if not product:
                continue
            
            prod_id = product[0]
            prod_name = product[1]
            qty = prod.get("qty_produced", 0)
            cost = product_costs.get(prod_id, 0)
            value = qty * cost
            
            total_produced_value += value
            
            if prod_name not in by_product:
                by_product[prod_name] = {"qty": 0, "value": 0}
            by_product[prod_name]["qty"] += qty
            by_product[prod_name]["value"] += value
        
        # Ordenar por valor
        sorted_products = sorted(
            by_product.items(),
            key=lambda x: x[1]["value"],
            reverse=True
        )
        
        message = f"""
*🏭 Costos de Producción (últimos 30 días)*

*Órdenes completadas:* {len(productions)}
*Valor total producido:* {self.format_currency(total_produced_value)}

*Por producto (Top 10):*
"""
        
        for name, data in sorted_products[:10]:
            pct = (data["value"] / total_produced_value * 100) if total_produced_value > 0 else 0
            message += f"• {name[:30]}: {data['qty']:.0f} uds ({self.format_currency(data['value'])}) - {pct:.0f}%\n"
        
        await self.notify(
            title=f"🏭 Producción: {self.format_currency(total_produced_value)}",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="production_costs",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_produced_value": total_produced_value,
                "orders_count": len(productions),
            }
        )
    
    async def analyze_operating_expenses(self) -> TaskResult:
        """Analiza gastos operativos por categoría."""
        started_at = datetime.now()
        
        self.logger.info("Analizando gastos operativos...")
        
        # Último mes
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Obtener facturas de proveedor (gastos)
        expenses = self.search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            ["partner_id", "amount_total_signed", "ref", "invoice_date"],
            limit=1000
        )
        
        if not expenses:
            return TaskResult(
                task_name="operating_expenses",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por proveedor
        by_supplier = {}
        total_expenses = 0
        
        for exp in expenses:
            partner = exp.get("partner_id")
            supplier_name = partner[1] if partner else "Sin proveedor"
            amount = abs(exp.get("amount_total_signed", 0))
            
            if supplier_name not in by_supplier:
                by_supplier[supplier_name] = {"total": 0, "count": 0}
            
            by_supplier[supplier_name]["total"] += amount
            by_supplier[supplier_name]["count"] += 1
            total_expenses += amount
        
        # Ordenar por monto
        sorted_suppliers = sorted(
            by_supplier.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )
        
        message = f"""
*📋 Gastos Operativos (últimos 30 días)*

*Total gastos:* {self.format_currency(total_expenses)}
*Facturas:* {len(expenses)}
*Proveedores:* {len(by_supplier)}

*Top 10 proveedores:*
"""
        
        for name, data in sorted_suppliers[:10]:
            pct = (data["total"] / total_expenses * 100) if total_expenses > 0 else 0
            message += f"• {name[:30]}: {self.format_currency(data['total'])} ({pct:.0f}%) - {data['count']} fact.\n"
        
        await self.notify(
            title=f"📋 Gastos: {self.format_currency(total_expenses)}",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="operating_expenses",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"total_expenses": total_expenses}
        )
    
    async def check_missing_costs(self) -> TaskResult:
        """Detecta productos sin costo estándar definido."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Buscando productos sin costo...")
        
        # Productos vendibles sin costo
        zero_cost = self.search_read(
            "product.product",
            [
                ("type", "in", ["product", "consu"]),
                ("standard_price", "<=", 0),
                ("active", "=", True),
                ("sale_ok", "=", True),
            ],
            ["name", "default_code", "list_price", "categ_id"],
            limit=200
        )
        
        if zero_cost:
            # Agrupar por categoría
            by_category = {}
            for prod in zero_cost:
                categ = prod.get("categ_id")
                categ_name = categ[1] if categ else "Sin categoría"
                
                if categ_name not in by_category:
                    by_category[categ_name] = []
                by_category[categ_name].append(prod)
            
            message = f"""
*⚠️ {len(zero_cost)} Productos sin Costo Definido*

*Por categoría:*
"""
            for categ, prods in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
                message += f"• {categ}: {len(prods)} productos\n"
            
            message += f"\n*Ejemplos:*\n"
            for prod in zero_cost[:10]:
                code = prod.get("default_code", "N/A")
                price = prod.get("list_price", 0)
                message += f"• [{code}] {prod['name'][:30]} (Precio: {self.format_currency(price)})\n"
            
            if len(zero_cost) > 20:
                await self.propose(
                    title=f"⚠️ {len(zero_cost)} productos sin costo",
                    description="Productos que requieren actualización de costo estándar",
                    priority=Priority.HIGH,
                    situation_summary=message,
                    proposed_action_detail="Actualizar costos estándar de productos",
                    supporting_data={"products": [p["id"] for p in zero_cost[:50]]},
                    informational=True,
                )
                proposals_created += 1
            
            await self.notify(
                title=f"⚠️ {len(zero_cost)} productos sin costo",
                message=message,
                priority=Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="missing_costs",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"zero_cost_count": len(zero_cost) if zero_cost else 0}
        )
    
    async def compare_cost_vs_price(self) -> TaskResult:
        """Compara costos vs precios de venta."""
        started_at = datetime.now()
        
        self.logger.info("Comparando costo vs precio...")
        
        # Productos vendibles con costo
        products = self.search_read(
            "product.product",
            [
                ("type", "in", ["product", "consu"]),
                ("standard_price", ">", 0),
                ("list_price", ">", 0),
                ("active", "=", True),
                ("sale_ok", "=", True),
            ],
            ["name", "default_code", "standard_price", "list_price"],
            limit=2000
        )
        
        if not products:
            return TaskResult(
                task_name="cost_vs_price",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Calcular margen teórico
        for prod in products:
            cost = prod["standard_price"]
            price = prod["list_price"]
            prod["margin"] = price - cost
            prod["margin_pct"] = ((price - cost) / price * 100) if price > 0 else 0
        
        # Productos con margen negativo (costo > precio)
        negative = [p for p in products if p["margin"] < 0]
        
        # Productos con margen muy bajo (<10%)
        low_margin = [p for p in products if 0 <= p["margin_pct"] < 10]
        
        # Ordenar por margen %
        products.sort(key=lambda x: x["margin_pct"])
        
        message = f"""
*💵 Análisis Costo vs Precio de Lista*

*Total productos analizados:* {len(products)}

*Alertas:*
• 🔴 Costo > Precio: {len(negative)}
• 🟡 Margen <10%: {len(low_margin)}

"""
        
        if negative:
            message += "*🔴 Productos con pérdida (costo > precio):*\n"
            for p in negative[:10]:
                message += f"• {p['name'][:30]}: Costo {self.format_currency(p['standard_price'])} > Precio {self.format_currency(p['list_price'])}\n"
        
        if low_margin:
            message += f"\n*🟡 Margen <10% ({len(low_margin)} productos):*\n"
            for p in low_margin[:5]:
                message += f"• {p['name'][:30]}: {p['margin_pct']:.1f}%\n"
        
        priority = Priority.HIGH if negative else Priority.MEDIUM if low_margin else Priority.LOW
        
        await self.notify(
            title=f"💵 {len(negative)} productos con costo > precio",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="cost_vs_price",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_products": len(products),
                "negative_margin": len(negative),
                "low_margin": len(low_margin),
            }
        )
    
    async def monthly_summary(self) -> TaskResult:
        """Genera resumen mensual de costos."""
        started_at = datetime.now()
        
        self.logger.info("Generando resumen mensual de costos...")
        
        # Ejecutar análisis para obtener datos
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Ventas y márgenes
        orders = self.search_read(
            "sale.order",
            [
                ("state", "in", ["sale", "done"]),
                ("date_order", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total", "margin"],
            limit=5000
        )
        
        total_sales = sum(o.get("amount_total", 0) for o in orders)
        total_margin = sum(o.get("margin", 0) for o in orders)
        margin_pct = (total_margin / total_sales * 100) if total_sales > 0 else 0
        
        # Gastos (facturas de proveedor)
        expenses = self.search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_ago),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total_signed"],
            limit=5000
        )
        
        total_expenses = sum(abs(e.get("amount_total_signed", 0)) for e in expenses)
        
        # Resultado operativo estimado
        gross_profit = total_margin
        operating_result = gross_profit - total_expenses
        
        message = f"""
*📊 Resumen Mensual de Costos*
_{month_ago} - {datetime.now().strftime('%d/%m/%Y')}_

*Ventas:*
• Total ventas: {self.format_currency(total_sales)}
• Margen bruto: {self.format_currency(total_margin)} ({margin_pct:.1f}%)

*Gastos:*
• Total gastos: {self.format_currency(total_expenses)}

*Resultado:*
• Utilidad operativa: {self.format_currency(operating_result)}
• Margen operativo: {(operating_result / total_sales * 100) if total_sales > 0 else 0:.1f}%
"""
        
        status_emoji = "🟢" if operating_result > 0 else "🔴"
        
        await self.notify(
            title=f"{status_emoji} Resultado operativo: {self.format_currency(operating_result)}",
            message=message,
            priority=Priority.MEDIUM if operating_result < 0 else Priority.LOW,
        )
        
        return TaskResult(
            task_name="monthly_cost_summary",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_sales": total_sales,
                "total_margin": total_margin,
                "total_expenses": total_expenses,
                "operating_result": operating_result,
            }
        )
    
    # ==================== Helpers ====================
    
    def _model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo existe en Odoo."""
        try:
            self.search_read(model_name, [("id", ">", 0)], ["id"], limit=1)
            return True
        except Exception:
            return False


def create_cost_agent() -> CostAgent:
    """Crea y retorna el agente de costos."""
    return CostAgent()
