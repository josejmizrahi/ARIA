"""
Agente de Inventario - Control de Stock y Almacenes.

Responsabilidades:
- Monitorear niveles de stock por almacén
- Detectar productos sin movimiento (slow-moving)
- Alertar sobre discrepancias de inventario
- Controlar fechas de caducidad (lotes)
- Optimizar ubicaciones de almacén
- Generar reportes de rotación
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class InventoryAgent(BaseAgent):
    """
    Agente autónomo para gestión de inventarios.
    
    Monitorea stock, detecta anomalías y optimiza almacenes.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="inventario",
            description="Control de stock y almacenes"
        )
        
        # Configuración desde settings
        self.company_id = settings.odoo.company_id
        
        # Parámetros de análisis
        self.slow_moving_days = 90  # Días sin movimiento para considerar slow-moving
        self.expiry_warning_days = 30  # Días antes de caducidad para alertar
        self.negative_stock_threshold = -0.01  # Tolerancia para stock negativo
        self.overstock_months = 6  # Meses de inventario para considerar sobrestock
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de inventario."""
        
        # Stock negativo o bajo
        self.register_task(TaskDefinition(
            name="check_stock_levels",
            method="check_stock_levels",
            schedule="0 7 * * *",  # 7:00 AM diario
            description="Verifica niveles de stock críticos"
        ))
        
        # Productos sin movimiento
        self.register_task(TaskDefinition(
            name="slow_moving_analysis",
            method="analyze_slow_moving",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Analiza productos sin rotación"
        ))
        
        # Fechas de caducidad
        self.register_task(TaskDefinition(
            name="expiry_check",
            method="check_expiry_dates",
            schedule="0 9 * * *",  # 9:00 AM diario
            description="Revisa lotes próximos a caducar"
        ))
        
        # Discrepancias de inventario
        self.register_task(TaskDefinition(
            name="inventory_discrepancies",
            method="check_discrepancies",
            schedule="0 10 * * 1",  # Lunes 10:00 AM
            description="Detecta discrepancias teórico vs físico"
        ))
        
        # Análisis de rotación ABC
        self.register_task(TaskDefinition(
            name="rotation_analysis",
            method="analyze_rotation",
            schedule="0 8 1 * *",  # Día 1 del mes
            description="Genera análisis de rotación ABC"
        ))
        
        # Sobrestock
        self.register_task(TaskDefinition(
            name="overstock_check",
            method="check_overstock",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Detecta productos con exceso de inventario"
        ))
        
        # Valorización de inventario
        self.register_task(TaskDefinition(
            name="inventory_valuation",
            method="calculate_valuation",
            schedule="0 7 1 * *",  # Día 1 del mes
            description="Calcula valorización del inventario"
        ))
        
        # Existencias por ubicación (stock.quant)
        self.register_task(TaskDefinition(
            name="stock_by_location",
            method="analyze_stock_by_location",
            schedule="0 10 1 * *",  # Día 1 del mes
            description="Analiza distribución de stock por ubicación"
        ))
        
        # Existencias reservadas
        self.register_task(TaskDefinition(
            name="reserved_stock",
            method="check_reserved_stock",
            schedule="0 8 * * 1-5",  # L-V 8:00 AM
            description="Verifica stock reservado vs disponible"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado del inventario."""
        
        # Stock negativo
        negative_stock = self._count_negative_stock()
        
        # Productos sin stock
        zero_stock = self._count_zero_stock()
        
        # Total productos almacenables
        total_products = self._count_storable_products()
        
        # Determinar estado
        if negative_stock > 0:
            status = "critical"
        elif total_products > 0 and zero_stock > total_products * 0.3:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "company_id": self.company_id,
            "negative_stock_count": negative_stock,
            "zero_stock_count": zero_stock,
            "total_products": total_products,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_stock_levels(self) -> TaskResult:
        """Verifica niveles de stock críticos."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando niveles de stock...")
        
        # Productos con stock negativo
        negative = self.search_read(
            "product.product",
            [
                ("qty_available", "<", self.negative_stock_threshold),
                ("type", "=", "product"),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["name", "default_code", "qty_available", "uom_id"],
            limit=100
        )
        
        if negative:
            for product in negative[:10]:  # Propuestas para los primeros 10
                await self.propose(
                    title=f"⚠️ Stock negativo: {product['name'][:40]}",
                    description=f"Stock: {product['qty_available']:.2f}",
                    priority=Priority.HIGH,
                    situation_summary=f"""
Producto: {product['name']}
Código: {product.get('default_code', 'N/A')}
Stock actual: {product['qty_available']:.2f}

El stock negativo indica un problema de registro o 
movimientos no procesados correctamente.
                    """.strip(),
                    proposed_action_detail="Investigar y ajustar inventario",
                    supporting_data={"product_id": product["id"]},
                )
                proposals_created += 1
            
            if len(negative) > 10:
                await self.notify(
                    title=f"🔴 {len(negative)} productos con stock negativo",
                    message=f"Se crearon propuestas para los 10 más críticos. Revisar los {len(negative) - 10} restantes.",
                    priority=Priority.HIGH,
                )
        else:
            await self.notify(
                title="✅ Stock OK",
                message="No se encontraron productos con stock negativo",
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="check_stock_levels",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            records_processed=len(negative) if negative else 0,
        )
    
    async def analyze_slow_moving(self) -> TaskResult:
        """Analiza productos sin movimiento."""
        started_at = datetime.now()
        
        self.logger.info("Analizando productos slow-moving...")
        
        # Fecha límite para considerar slow-moving
        date_limit = (datetime.now() - timedelta(days=self.slow_moving_days)).strftime("%Y-%m-%d")
        
        # Productos con stock pero sin movimientos recientes
        products_with_stock = self.search_read(
            "product.product",
            [
                ("qty_available", ">", 0),
                ("type", "=", "product"),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["id", "name", "default_code", "qty_available", "standard_price"],
            limit=1000
        )
        
        slow_moving = []
        
        for product in products_with_stock:
            # Verificar último movimiento
            last_move = self.search_read(
                "stock.move",
                [
                    ("product_id", "=", product["id"]),
                    ("state", "=", "done"),
                    ("date", ">=", date_limit),
                    ("company_id", "=", self.company_id),
                ],
                ["id"],
                limit=1
            )
            
            if not last_move:
                product["value"] = product["qty_available"] * product.get("standard_price", 0)
                slow_moving.append(product)
        
        if slow_moving:
            # Ordenar por valor (mayor primero)
            slow_moving.sort(key=lambda x: x.get("value", 0), reverse=True)
            
            total_value = sum(p.get("value", 0) for p in slow_moving)
            
            message = f"""
*📦 Productos sin movimiento en {self.slow_moving_days} días*

Total: {len(slow_moving)} productos
Valor inmovilizado: {self.format_currency(total_value)}

*Top 10 por valor:*
"""
            for p in slow_moving[:10]:
                message += f"• {p['name'][:30]}: {p['qty_available']:.0f} uds ({self.format_currency(p.get('value', 0))})\n"
            
            await self.propose(
                title=f"📦 {len(slow_moving)} productos slow-moving",
                description=f"Valor inmovilizado: {self.format_currency(total_value)}",
                priority=Priority.MEDIUM,
                situation_summary=message,
                proposed_action_detail="Evaluar liquidación o promoción",
                supporting_data={"slow_moving": slow_moving[:50], "total_value": total_value},
            )
        
        return TaskResult(
            task_name="slow_moving_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"slow_moving_count": len(slow_moving) if slow_moving else 0}
        )
    
    async def check_expiry_dates(self) -> TaskResult:
        """Revisa lotes próximos a caducar."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Revisando fechas de caducidad...")
        
        # Verificar si el modelo stock.lot tiene campo expiration_date
        if not self._field_exists("stock.lot", "expiration_date"):
            self.logger.info("Módulo de lotes con caducidad no instalado")
            return TaskResult(
                task_name="expiry_check",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"message": "Módulo de caducidad no instalado"}
            )
        
        # Fecha límite
        expiry_limit = (datetime.now() + timedelta(days=self.expiry_warning_days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Lotes próximos a caducar con stock
        expiring_lots = self.search_read(
            "stock.lot",
            [
                ("expiration_date", "<=", expiry_limit),
                ("expiration_date", ">=", today),
                ("product_qty", ">", 0),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "expiration_date", "product_qty"],
            limit=100,
            order="expiration_date asc"
        )
        
        # Lotes ya caducados
        expired_lots = self.search_read(
            "stock.lot",
            [
                ("expiration_date", "<", today),
                ("product_qty", ">", 0),
                ("company_id", "=", self.company_id),
            ],
            ["name", "product_id", "expiration_date", "product_qty"],
            limit=50
        )
        
        if expired_lots:
            await self.propose(
                title=f"🔴 {len(expired_lots)} lotes CADUCADOS con stock",
                description="Requieren acción inmediata para dar de baja",
                priority=Priority.CRITICAL,
                situation_summary=f"""
Se encontraron lotes caducados que aún tienen stock registrado.
Requieren acción inmediata para dar de baja.

Cantidad de lotes: {len(expired_lots)}
                """.strip(),
                proposed_action_detail="Dar de baja lotes caducados",
                supporting_data={"expired_lots": expired_lots},
            )
            proposals_created += 1
        
        if expiring_lots:
            # Agrupar por urgencia
            this_week = []
            next_weeks = []
            
            for lot in expiring_lots:
                exp_date = lot.get("expiration_date", "")[:10]
                days_to_expire = (datetime.strptime(exp_date, "%Y-%m-%d") - datetime.now()).days
                lot["days_to_expire"] = days_to_expire
                
                if days_to_expire <= 7:
                    this_week.append(lot)
                else:
                    next_weeks.append(lot)
            
            if this_week:
                await self.notify(
                    title=f"⚠️ {len(this_week)} lotes caducan esta semana",
                    message="Lotes que requieren atención urgente",
                    priority=Priority.HIGH,
                )
            
            if next_weeks:
                await self.notify(
                    title=f"📅 {len(next_weeks)} lotes caducan en {self.expiry_warning_days} días",
                    message="Planificar rotación o promoción",
                    priority=Priority.MEDIUM,
                )
        
        return TaskResult(
            task_name="expiry_check",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={
                "expired": len(expired_lots) if expired_lots else 0,
                "expiring": len(expiring_lots) if expiring_lots else 0,
            }
        )
    
    async def check_discrepancies(self) -> TaskResult:
        """Detecta discrepancias de inventario."""
        started_at = datetime.now()
        
        self.logger.info("Buscando discrepancias de inventario...")
        
        # Buscar ajustes de inventario recientes (últimos 7 días)
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Movimientos de ajuste de inventario
        adjustments = self.search_read(
            "stock.move",
            [
                ("date", ">=", week_ago),
                ("state", "=", "done"),
                ("company_id", "=", self.company_id),
                "|",
                ("location_id.usage", "=", "inventory"),
                ("location_dest_id.usage", "=", "inventory"),
            ],
            ["product_id", "product_uom_qty", "date", "reference"],
            limit=500
        )
        
        if adjustments:
            # Agrupar por producto
            by_product: dict[int, dict] = {}
            for adj in adjustments:
                pid = adj["product_id"][0] if adj["product_id"] else None
                if pid:
                    if pid not in by_product:
                        by_product[pid] = {
                            "name": adj["product_id"][1],
                            "total_qty": 0,
                            "count": 0,
                        }
                    by_product[pid]["total_qty"] += adj["product_uom_qty"]
                    by_product[pid]["count"] += 1
            
            # Productos con múltiples ajustes (posible problema recurrente)
            recurring = [
                {"product": data["name"], "adjustments": data["count"], "qty": data["total_qty"]}
                for pid, data in by_product.items()
                if data["count"] >= 3
            ]
            
            if recurring:
                message = f"*{len(recurring)} productos con ajustes recurrentes:*\n\n"
                for r in recurring[:10]:
                    message += f"• {r['product'][:30]}: {r['adjustments']} ajustes\n"
                
                await self.notify(
                    title=f"⚠️ {len(recurring)} productos con ajustes recurrentes",
                    message=message,
                    priority=Priority.MEDIUM,
                )
            
            await self.notify(
                title=f"📊 {len(adjustments)} ajustes de inventario esta semana",
                message=f"En {len(by_product)} productos diferentes",
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="inventory_discrepancies",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"adjustments": len(adjustments) if adjustments else 0}
        )
    
    async def analyze_rotation(self) -> TaskResult:
        """Genera análisis de rotación ABC."""
        started_at = datetime.now()
        
        self.logger.info("Generando análisis de rotación ABC...")
        
        # Últimos 12 meses
        year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        # Movimientos de salida (ventas)
        moves = self.search_read(
            "stock.move",
            [
                ("date", ">=", year_ago),
                ("state", "=", "done"),
                ("location_dest_id.usage", "=", "customer"),
                ("company_id", "=", self.company_id),
            ],
            ["product_id", "product_uom_qty"],
            limit=50000
        )
        
        # Agrupar por producto
        by_product: dict[int, dict] = {}
        for move in moves:
            pid = move["product_id"][0] if move["product_id"] else None
            if pid:
                if pid not in by_product:
                    by_product[pid] = {"name": move["product_id"][1], "qty": 0}
                by_product[pid]["qty"] += move["product_uom_qty"]
        
        # Ordenar por cantidad
        sorted_products = sorted(by_product.items(), key=lambda x: x[1]["qty"], reverse=True)
        
        total_qty = sum(p[1]["qty"] for p in sorted_products)
        
        # Clasificar ABC
        cumulative = 0
        a_products = []
        b_products = []
        c_products = []
        
        for pid, data in sorted_products:
            cumulative += data["qty"]
            pct = cumulative / total_qty if total_qty > 0 else 0
            
            if pct <= 0.8:
                a_products.append(data["name"])
            elif pct <= 0.95:
                b_products.append(data["name"])
            else:
                c_products.append(data["name"])
        
        message = f"""
*📊 Análisis de Rotación ABC - Último año*

Total productos con movimiento: {len(sorted_products)}

*Clasificación:*
- **A (80% ventas):** {len(a_products)} productos
- **B (15% ventas):** {len(b_products)} productos  
- **C (5% ventas):** {len(c_products)} productos

Los productos A requieren mayor control y disponibilidad.
Los productos C son candidatos a reducción de inventario.
        """.strip()
        
        await self.notify(
            title="📊 Análisis de Rotación ABC",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="rotation_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_products": len(sorted_products),
                "a_count": len(a_products),
                "b_count": len(b_products),
                "c_count": len(c_products),
            }
        )
    
    async def check_overstock(self) -> TaskResult:
        """Detecta productos con exceso de inventario."""
        started_at = datetime.now()
        
        self.logger.info("Detectando sobrestock...")
        
        # Productos con stock
        products = self.search_read(
            "product.product",
            [
                ("qty_available", ">", 0),
                ("type", "=", "product"),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["id", "name", "qty_available", "standard_price"],
            limit=1000
        )
        
        # Calcular meses de inventario basado en ventas promedio
        year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        overstock = []
        
        for product in products:
            # Ventas del último año
            sales = self.search_read(
                "stock.move",
                [
                    ("product_id", "=", product["id"]),
                    ("state", "=", "done"),
                    ("date", ">=", year_ago),
                    ("location_dest_id.usage", "=", "customer"),
                    ("company_id", "=", self.company_id),
                ],
                ["product_uom_qty"],
                limit=1000
            )
            
            total_sales = sum(s["product_uom_qty"] for s in sales)
            monthly_avg = total_sales / 12 if total_sales > 0 else 0.1
            
            months_of_stock = product["qty_available"] / monthly_avg
            
            if months_of_stock >= self.overstock_months:
                product["months_of_stock"] = months_of_stock
                product["value"] = product["qty_available"] * product.get("standard_price", 0)
                overstock.append(product)
        
        if overstock:
            overstock.sort(key=lambda x: x.get("value", 0), reverse=True)
            total_value = sum(p.get("value", 0) for p in overstock)
            
            message = f"""
*📦 Productos con sobrestock (>{self.overstock_months} meses)*

Total: {len(overstock)} productos
Valor en exceso: {self.format_currency(total_value)}

*Top 10 por valor:*
"""
            for p in overstock[:10]:
                message += f"• {p['name'][:30]}: {p['months_of_stock']:.0f} meses ({self.format_currency(p.get('value', 0))})\n"
            
            await self.propose(
                title=f"📦 {len(overstock)} productos con sobrestock",
                description=f"Valor en exceso: {self.format_currency(total_value)}",
                priority=Priority.MEDIUM,
                situation_summary=message,
                proposed_action_detail="Evaluar reducción de inventario",
                supporting_data={"overstock": overstock[:20]},
            )
        
        return TaskResult(
            task_name="overstock_check",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"overstock_count": len(overstock) if overstock else 0}
        )
    
    async def calculate_valuation(self) -> TaskResult:
        """Calcula valorización del inventario."""
        started_at = datetime.now()
        
        self.logger.info("Calculando valorización de inventario...")
        
        # Obtener valorización por categoría
        products = self.search_read(
            "product.product",
            [
                ("qty_available", ">", 0),
                ("type", "=", "product"),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["name", "categ_id", "qty_available", "standard_price"],
            limit=5000
        )
        
        by_category: dict[str, dict] = {}
        total_value = 0
        
        for product in products:
            value = product["qty_available"] * product.get("standard_price", 0)
            total_value += value
            
            categ_name = product["categ_id"][1] if product.get("categ_id") else "Sin categoría"
            
            if categ_name not in by_category:
                by_category[categ_name] = {"value": 0, "count": 0}
            
            by_category[categ_name]["value"] += value
            by_category[categ_name]["count"] += 1
        
        # Ordenar por valor
        sorted_categories = sorted(by_category.items(), key=lambda x: x[1]["value"], reverse=True)
        
        message = f"""
*💰 Valorización de Inventario*

**Total: {self.format_currency(total_value)}**
Productos: {len(products)}

*Por categoría:*
"""
        for categ, data in sorted_categories[:10]:
            pct = data["value"] / total_value * 100 if total_value > 0 else 0
            message += f"• {categ[:30]}: {self.format_currency(data['value'])} ({pct:.1f}%)\n"
        
        await self.notify(
            title=f"💰 Inventario: {self.format_currency(total_value)}",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="inventory_valuation",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"total_value": total_value, "products_count": len(products)}
        )
    
    async def analyze_stock_by_location(self) -> TaskResult:
        """Analiza distribución de stock por ubicación usando stock.quant."""
        started_at = datetime.now()
        
        self.logger.info("Analizando stock por ubicación (stock.quant)...")
        
        # Obtener quants con stock
        quants = self.search_read(
            "stock.quant",
            [
                ("quantity", ">", 0),
                ("location_id.usage", "=", "internal"),  # Solo ubicaciones internas
            ],
            ["product_id", "location_id", "quantity", "reserved_quantity", "lot_id"],
            limit=10000
        )
        
        if not quants:
            return TaskResult(
                task_name="stock_by_location",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Agrupar por ubicación
        by_location = {}
        total_qty = 0
        total_reserved = 0
        
        for quant in quants:
            location = quant.get("location_id")
            location_name = location[1] if location else "Sin ubicación"
            
            if location_name not in by_location:
                by_location[location_name] = {
                    "quantity": 0,
                    "reserved": 0,
                    "products": 0,
                    "with_lots": 0,
                }
            
            qty = quant.get("quantity", 0)
            reserved = quant.get("reserved_quantity", 0)
            
            by_location[location_name]["quantity"] += qty
            by_location[location_name]["reserved"] += reserved
            by_location[location_name]["products"] += 1
            
            if quant.get("lot_id"):
                by_location[location_name]["with_lots"] += 1
            
            total_qty += qty
            total_reserved += reserved
        
        # Ordenar por cantidad
        sorted_locations = sorted(
            by_location.items(),
            key=lambda x: x[1]["quantity"],
            reverse=True
        )
        
        message = f"""
*📍 Stock por Ubicación*

*Totales:*
• Cantidad total: {total_qty:,.0f} unidades
• Reservado: {total_reserved:,.0f} unidades
• Disponible real: {total_qty - total_reserved:,.0f} unidades

*Por ubicación (Top 10):*
"""
        
        for loc_name, data in sorted_locations[:10]:
            pct = (data["quantity"] / total_qty * 100) if total_qty > 0 else 0
            available = data["quantity"] - data["reserved"]
            message += f"• {loc_name[:30]}: {data['quantity']:,.0f} ({pct:.0f}%) - Disp: {available:,.0f}\n"
        
        if len(sorted_locations) > 10:
            message += f"\n... y {len(sorted_locations) - 10} ubicaciones más"
        
        await self.notify(
            title=f"📍 Stock en {len(sorted_locations)} ubicaciones",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="stock_by_location",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_quantity": total_qty,
                "total_reserved": total_reserved,
                "locations_count": len(sorted_locations),
            }
        )
    
    async def check_reserved_stock(self) -> TaskResult:
        """Verifica stock reservado vs disponible."""
        started_at = datetime.now()
        
        self.logger.info("Verificando stock reservado...")
        
        # Productos con alta reserva (>50% del stock)
        quants = self.search_read(
            "stock.quant",
            [
                ("quantity", ">", 0),
                ("reserved_quantity", ">", 0),
                ("location_id.usage", "=", "internal"),
            ],
            ["product_id", "quantity", "reserved_quantity", "location_id"],
            limit=5000
        )
        
        # Agrupar por producto
        by_product = {}
        
        for quant in quants:
            product = quant.get("product_id")
            if not product:
                continue
            
            prod_name = product[1]
            
            if prod_name not in by_product:
                by_product[prod_name] = {"quantity": 0, "reserved": 0}
            
            by_product[prod_name]["quantity"] += quant.get("quantity", 0)
            by_product[prod_name]["reserved"] += quant.get("reserved_quantity", 0)
        
        # Calcular disponibilidad
        for prod_name, data in by_product.items():
            data["available"] = data["quantity"] - data["reserved"]
            data["reserved_pct"] = (
                (data["reserved"] / data["quantity"] * 100)
                if data["quantity"] > 0 else 0
            )
        
        # Productos con alta reserva (>80%)
        high_reserved = [
            (name, data) for name, data in by_product.items()
            if data["reserved_pct"] >= 80
        ]
        
        # Productos sin disponibilidad real (100% reservado)
        fully_reserved = [
            (name, data) for name, data in by_product.items()
            if data["available"] <= 0
        ]
        
        if fully_reserved or high_reserved:
            message = f"""
*🔒 Análisis de Stock Reservado*

*Resumen:*
• Productos con stock reservado: {len(by_product)}
• 100% reservado (sin disponible): {len(fully_reserved)}
• >80% reservado: {len(high_reserved)}

"""
            
            if fully_reserved:
                message += "*⚠️ Sin disponibilidad (100% reservado):*\n"
                for name, data in sorted(fully_reserved, key=lambda x: x[1]["quantity"], reverse=True)[:10]:
                    message += f"• {name[:35]}: {data['quantity']:,.0f} reservado\n"
            
            await self.notify(
                title=f"🔒 {len(fully_reserved)} productos sin stock disponible",
                message=message,
                priority=Priority.MEDIUM if len(fully_reserved) > 10 else Priority.LOW,
            )
        
        return TaskResult(
            task_name="reserved_stock",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "products_with_reservation": len(by_product),
                "fully_reserved": len(fully_reserved),
                "high_reserved": len(high_reserved),
            }
        )
    
    # ==================== Helpers ====================
    
    def _count_negative_stock(self) -> int:
        """Cuenta productos con stock negativo."""
        return len(self.search_read(
            "product.product",
            [
                ("qty_available", "<", self.negative_stock_threshold),
                ("type", "=", "product"),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["id"],
            limit=1000
        ))
    
    def _count_zero_stock(self) -> int:
        """Cuenta productos sin stock."""
        return len(self.search_read(
            "product.product",
            [
                ("qty_available", "=", 0),
                ("type", "=", "product"),
                ("active", "=", True),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["id"],
            limit=5000
        ))
    
    def _count_storable_products(self) -> int:
        """Cuenta total de productos almacenables."""
        return len(self.search_read(
            "product.product",
            [
                ("type", "=", "product"),
                ("active", "=", True),
                ("company_id", "in", [self.company_id, False]),
            ],
            ["id"],
            limit=10000
        ))
    
    def _field_exists(self, model: str, field: str) -> bool:
        """Verifica si un campo existe en un modelo."""
        try:
            self.search_read(model, [("id", ">", 0)], [field], limit=1)
            return True
        except Exception:
            return False


def create_inventory_agent() -> InventoryAgent:
    """Crea y retorna el agente de inventario."""
    return InventoryAgent()
