"""
Agente de Finanzas - Planeación Financiera Profesional.

Sistema completo de planeación financiera que incluye:
- Análisis financiero avanzado (ratios, tendencias, variaciones)
- Presupuestos y proyecciones (real vs presupuestado, escenarios)
- Análisis de rentabilidad (centros de costo, márgenes, punto de equilibrio)
- Recomendaciones estratégicas (optimización de flujo, financiamiento)
- Reportes ejecutivos (KPIs, dashboards, alertas proactivas)
"""

from datetime import datetime, timedelta
from typing import Any
from collections import defaultdict

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.task import TaskDefinition, TaskResult
from aria.models.proposal import Priority


class FinanceAgent(BaseAgent):
    """
    Agente autónomo para planeación financiera profesional.
    
    Funcionalidades:
    - Proyección de flujo de caja (4 semanas y anual)
    - Análisis financiero avanzado (ratios, tendencias)
    - Presupuestos y comparación real vs presupuestado
    - Análisis de rentabilidad por centro de costo
    - Recomendaciones estratégicas de optimización
    - Reportes ejecutivos y KPIs financieros
    
    Filtros:
    - company_id: Configurable desde settings (ODOO_COMPANY_ID)
    - Tipo diario: bank, cash (NO tarjetas de crédito)
    - Tipo cuenta: asset_cash (NO liability_credit_card)
    - Saldos separados por divisa
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="finanzas",
            description="Planeación financiera profesional, tesorería y análisis estratégico"
        )
        
        # Configuración desde settings
        self.company_id = settings.odoo.company_id
        self.default_currency = settings.odoo.default_currency
        
        # Parámetros de alertas
        self.critical_runway_days = 7  # Días críticos de runway
        self.warning_runway_days = 14  # Días de advertencia
        self.projection_weeks = 4  # Semanas de proyección
        
        # Gestor de presupuestos (se carga dinámicamente desde Odoo/archivo/cálculo)
        self._budget_manager = None
        self._budgets_cache: Optional[dict] = None
    
    @property
    def budget_manager(self):
        """Obtiene el gestor de presupuestos."""
        if self._budget_manager is None:
            from aria.budget_manager import get_budget_manager
            self._budget_manager = get_budget_manager(self.company_id)
        return self._budget_manager
    
    def _get_budgets(self) -> dict:
        """Obtiene presupuestos desde la mejor fuente disponible."""
        if self._budgets_cache is None:
            self._budgets_cache = self.budget_manager.get_budgets(self.odoo)
        return self._budgets_cache
    
    @property
    def monthly_budget(self) -> float:
        """Presupuesto mensual de ingresos."""
        budgets = self._get_budgets()
        return budgets.get("monthly_revenue", 0)
    
    @property
    def monthly_expenses_budget(self) -> float:
        """Presupuesto mensual de gastos."""
        budgets = self._get_budgets()
        return budgets.get("monthly_expenses", 0)
    
    @property
    def annual_budget(self) -> float:
        """Presupuesto anual de ingresos."""
        return self.monthly_budget * 12
    
    @property
    def category_budgets(self) -> dict[str, float]:
        """Presupuestos por categoría."""
        budgets = self._get_budgets()
        return budgets.get("by_category", {})
    
    def _register_tasks(self) -> None:
        """Registra las tareas del agente de finanzas."""
        
        # Proyección de flujo de caja
        self.register_task(TaskDefinition(
            name="cash_flow_projection",
            method="project_cash_flow",
            schedule="0 7 * * *",  # Diario 7:00 AM
            description="Proyecta flujo de caja a 4 semanas"
        ))
        
        # Saldos bancarios
        self.register_task(TaskDefinition(
            name="bank_balances",
            method="check_bank_balances",
            schedule="0 8 * * *",  # Diario 8:00 AM
            description="Reporta saldos bancarios actuales"
        ))
        
        # Pagos próximos
        self.register_task(TaskDefinition(
            name="upcoming_payments",
            method="check_upcoming_payments",
            schedule="0 9 * * *",  # Diario 9:00 AM
            description="Verifica pagos próximos vs disponible"
        ))
        
        # Análisis financiero avanzado
        self.register_task(TaskDefinition(
            name="financial_analysis",
            method="analyze_financial_ratios",
            schedule="0 10 * * 1",  # Lunes 10:00 AM
            description="Análisis de ratios financieros y tendencias"
        ))
        
        # Comparación vs presupuesto
        self.register_task(TaskDefinition(
            name="budget_comparison",
            method="compare_vs_budget",
            schedule="0 8 * * 1",  # Lunes 8:00 AM (inicio de semana)
            description="Compara resultados reales vs presupuestado"
        ))
        
        # Análisis de rentabilidad
        self.register_task(TaskDefinition(
            name="profitability_analysis",
            method="analyze_profitability",
            schedule="0 11 * * 1",  # Lunes 11:00 AM
            description="Análisis de rentabilidad por centro de costo"
        ))
        
        # Proyecciones anuales
        self.register_task(TaskDefinition(
            name="annual_forecast",
            method="generate_annual_forecast",
            schedule="0 9 1 * *",  # Día 1 de cada mes 9:00 AM
            description="Genera proyecciones anuales con escenarios"
        ))
        
        # Reporte semanal
        self.register_task(TaskDefinition(
            name="weekly_report",
            method="weekly_treasury_report",
            schedule="0 17 * * 5",  # Viernes 5:00 PM
            description="Genera reporte semanal de tesorería"
        ))
        
        # Reporte ejecutivo mensual
        self.register_task(TaskDefinition(
            name="monthly_executive_report",
            method="generate_executive_report",
            schedule="0 9 1 * *",  # Día 1 de cada mes 9:00 AM
            description="Reporte ejecutivo mensual con KPIs y recomendaciones"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de finanzas con métricas avanzadas."""
        
        # Saldos por divisa
        balances_by_currency = self._get_cash_balance_by_currency()
        cash_local = balances_by_currency.get(self.default_currency, 0.0)
        
        daily_burn = self._calculate_daily_burn()
        runway = cash_local / daily_burn if daily_burn > 0 else 999
        
        # Pagos próximos 7 días
        upcoming = self._get_upcoming_payments(days=7)
        total_upcoming = sum(p.get("amount_residual", 0) for p in upcoming)
        
        # Cobranza esperada 7 días
        expected_collections = self._get_expected_collections(days=7)
        total_expected = sum(c.get("amount_residual", 0) for c in expected_collections)
        
        # Métricas del mes actual
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_end = datetime.now().strftime("%Y-%m-%d")
        
        invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_start),
                ("invoice_date", "<=", month_end),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total"],
            limit=500
        )
        monthly_revenue = sum(i.get("amount_total", 0) for i in invoices)
        
        # Cumplimiento de presupuesto
        budget_compliance = (monthly_revenue / self.monthly_budget * 100) if self.monthly_budget > 0 else 0
        
        # Determinar estado
        if cash_local < 0 or runway <= self.critical_runway_days:
            status = "critical"
        elif runway <= self.warning_runway_days:
            status = "warning"
        elif total_upcoming > cash_local + total_expected:
            status = "warning"
        elif budget_compliance < 80:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "company_id": self.company_id,
            "default_currency": self.default_currency,
            "cash_balance": cash_local,
            "cash_by_currency": balances_by_currency,
            "runway_days": runway,
            "daily_burn": daily_burn,
            "upcoming_payments_7d": total_upcoming,
            "expected_collections_7d": total_expected,
            "net_position_7d": cash_local + total_expected - total_upcoming,
            "monthly_revenue": monthly_revenue,
            "monthly_budget": self.monthly_budget,
            "budget_compliance": budget_compliance,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def project_cash_flow(self) -> TaskResult:
        """Proyecta flujo de caja a 4 semanas."""
        started_at = datetime.now()
        
        self.logger.info("Proyectando flujo de caja...")
        
        # Saldos por divisa
        balances_by_currency = self._get_cash_balance_by_currency()
        cash = balances_by_currency.get(self.default_currency, 0.0)
        
        # Proyección por semana
        projection = []
        running_balance = cash
        deficit_weeks = []
        
        for week in range(1, self.projection_weeks + 1):
            days_start = (week - 1) * 7
            days_end = week * 7
            
            # Cobranza esperada
            collections = self._get_expected_collections(days=days_end)
            week_collections = sum(
                c.get("amount_residual", 0) for c in collections
                if self.days_between(c.get("invoice_date_due", "")) >= days_start
            )
            
            # Pagos programados
            payments = self._get_upcoming_payments(days=days_end)
            week_payments = sum(
                p.get("amount_residual", 0) for p in payments
                if self.days_between(p.get("invoice_date_due", "")) >= days_start
            )
            
            running_balance = running_balance + week_collections - week_payments
            
            week_data = {
                "week": week,
                "collections": week_collections,
                "payments": week_payments,
                "net": week_collections - week_payments,
                "balance": running_balance,
            }
            projection.append(week_data)
            
            if running_balance < 0:
                deficit_weeks.append(week)
        
        # Mensaje de proyección
        message = f"""
*📊 Proyección de Flujo de Caja*

*Saldo actual:* {self.format_currency(cash)}

| Semana | Ingresos | Egresos | Saldo |
|--------|----------|---------|-------|
        """.strip()
        
        for w in projection:
            emoji = "🔴" if w["balance"] < 0 else "🟢"
            message += f"\n| S{w['week']} | {self.format_currency(w['collections'])} | {self.format_currency(w['payments'])} | {emoji} {self.format_currency(w['balance'])} |"
        
        # Alertas
        proposals_created = 0
        
        if deficit_weeks:
            message += f"\n\n⚠️ *DÉFICIT PROYECTADO en semana(s) {deficit_weeks}*"
            
            await self.propose(
                title="🔴 Déficit de caja proyectado",
                description=f"Se proyecta déficit en semana(s) {deficit_weeks}",
                priority=Priority.CRITICAL,
                situation_summary=f"""
Saldo actual: {self.format_currency(cash)}
Déficit proyectado: Semana(s) {deficit_weeks}
Saldo más bajo: {self.format_currency(min(w['balance'] for w in projection))}

⚠️ Se requieren acciones para evitar falta de liquidez.
                """.strip(),
                proposed_action_detail="Acelerar cobranza y/o postergar pagos no críticos",
                supporting_data={"projection": projection},
            )
            proposals_created += 1
            
            priority = Priority.CRITICAL
        else:
            message += f"\n\n✅ Flujo de caja saludable"
            priority = Priority.LOW
        
        await self.notify(
            title="📊 Proyección de Flujo - 4 Semanas",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="cash_flow_projection",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"projection": projection}
        )
    
    async def check_bank_balances(self) -> TaskResult:
        """Reporta saldos bancarios actuales."""
        started_at = datetime.now()
        
        self.logger.info("Verificando saldos bancarios...")
        
        # Saldos por divisa
        balances_by_currency = self._get_cash_balance_by_currency()
        cash_local = balances_by_currency.get(self.default_currency, 0.0)
        
        daily_burn = self._calculate_daily_burn()
        runway = cash_local / daily_burn if daily_burn > 0 else 999
        
        # Obtener detalle por cuenta bancaria
        bank_accounts = self._get_bank_accounts_detail()
        
        message = f"""
*🏦 Saldos Bancarios*
_Company ID: {self.company_id}_

*Por divisa:*"""
        
        for currency, balance in sorted(balances_by_currency.items()):
            emoji = "🟢" if balance >= 0 else "🔴"
            message += f"\n{emoji} *{currency}:* {balance:,.2f}"
        
        message += f"""

*Burn diario ({self.default_currency}):* {self.format_currency(daily_burn)}
*Runway:* {runway:.0f} días
        """.strip()
        
        if bank_accounts:
            message += "\n\n*Detalle por cuenta:*"
            # Agrupar por divisa
            by_currency: dict[str, list] = {}
            for acc in bank_accounts:
                curr = acc.get('currency', self.default_currency)
                if curr not in by_currency:
                    by_currency[curr] = []
                by_currency[curr].append(acc)
            
            for curr in sorted(by_currency.keys()):
                message += f"\n\n_{curr}:_"
                for acc in sorted(by_currency[curr], key=lambda x: x['balance'], reverse=True)[:5]:
                    emoji = "🟢" if acc['balance'] >= 0 else "🔴"
                    message += f"\n{emoji} {acc['name'][:25]}: {acc['balance']:,.2f}"
        
        # Determinar prioridad
        if runway <= self.critical_runway_days:
            priority = Priority.CRITICAL
            message += f"\n\n🔴 *CRÍTICO: Solo {runway:.0f} días de runway*"
        elif runway <= self.warning_runway_days:
            priority = Priority.HIGH
            message += f"\n\n⚠️ *Atención: {runway:.0f} días de runway*"
        else:
            priority = Priority.LOW
            message += f"\n\n✅ Liquidez saludable"
        
        await self.notify(
            title=f"🏦 Saldo: {self.format_currency(cash_local)} | Runway: {runway:.0f}d",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="bank_balances",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "cash_local": cash_local,
                "cash_by_currency": balances_by_currency,
                "runway": runway,
                "accounts": bank_accounts,
            }
        )
    
    async def check_upcoming_payments(self) -> TaskResult:
        """Verifica pagos próximos vs disponible."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando pagos próximos...")
        
        # Saldos por divisa
        balances_by_currency = self._get_cash_balance_by_currency()
        cash_local = balances_by_currency.get(self.default_currency, 0.0)
        
        # Pagos próximos 7 días
        payments = self._get_upcoming_payments(days=7)
        
        # Agrupar pagos por divisa
        payments_by_currency: dict[str, list] = {}
        for p in payments:
            currency = p.get("currency_id", [0, self.default_currency])[1] if p.get("currency_id") else self.default_currency
            p["currency"] = currency
            if currency not in payments_by_currency:
                payments_by_currency[currency] = []
            payments_by_currency[currency].append(p)
        
        # Calcular totales por divisa
        totals_by_currency = {
            curr: sum(p.get("amount_residual", 0) for p in plist)
            for curr, plist in payments_by_currency.items()
        }
        total_payments_local = totals_by_currency.get(self.default_currency, 0.0)
        
        # Cobranza esperada 7 días (divisa local)
        collections = self._get_expected_collections(days=7)
        total_collections = sum(c.get("amount_residual", 0) for c in collections)
        
        # Posición neta en divisa local
        net_position = cash_local + total_collections - total_payments_local
        
        message = f"""
*💳 Pagos Próximos (7 días)*
_Company ID: {self.company_id}_

*Disponible por divisa:*"""
        
        for curr, balance in sorted(balances_by_currency.items()):
            emoji = "🟢" if balance >= 0 else "🔴"
            message += f"\n{emoji} {curr}: {balance:,.2f}"
        
        message += f"""

*Pagos programados por divisa:*"""
        
        for curr, total in sorted(totals_by_currency.items()):
            available = balances_by_currency.get(curr, 0.0)
            diff = available - total
            emoji = "🟢" if diff >= 0 else "🔴"
            message += f"\n{emoji} {curr}: {total:,.2f} (disponible: {available:,.2f}, diff: {diff:,.2f})"
        
        message += f"""

*Cobranza esperada ({self.default_currency}):* {self.format_currency(total_collections)}
*Posición neta ({self.default_currency}):* {self.format_currency(net_position)}"""
        
        # Top pagos por divisa
        for curr, plist in sorted(payments_by_currency.items()):
            plist.sort(key=lambda x: x.get("amount_residual", 0), reverse=True)
            message += f"\n\n*Principales pagos ({curr}):*"
            for p in plist[:5]:
                partner = p.get("partner_id", [0, ""])[1] if p.get("partner_id") else "N/A"
                due = p.get("invoice_date_due", "")[:10] if p.get("invoice_date_due") else "N/A"
                message += f"\n• {partner[:20]}: {p.get('amount_residual', 0):,.2f} (vence {due})"
        
        # Verificar si hay faltante en alguna divisa
        has_shortage = False
        shortage_currencies = []
        for curr, total in totals_by_currency.items():
            available = balances_by_currency.get(curr, 0.0)
            if total > available:
                has_shortage = True
                shortage_currencies.append({
                    "currency": curr,
                    "shortage": total - available,
                    "payments": total,
                    "available": available,
                })
        
        # Alerta si no alcanza
        if has_shortage:
            priority = Priority.CRITICAL
            message += f"\n\n🔴 *FONDOS INSUFICIENTES EN:*"
            for sc in shortage_currencies:
                message += f"\n• {sc['currency']}: faltante {sc['shortage']:,.2f}"
            
            await self.propose(
                title="⚠️ Fondos insuficientes para pagos",
                description=f"Faltante en {len(shortage_currencies)} divisas",
                priority=Priority.CRITICAL,
                situation_summary=f"""
Divisas con faltante:
{chr(10).join(f"- {sc['currency']}: pagos {sc['payments']:,.2f} vs disponible {sc['available']:,.2f} (falta {sc['shortage']:,.2f})" for sc in shortage_currencies)}

Total pagos programados: {len(payments)}
                """.strip(),
                proposed_action_detail="Priorizar pagos críticos y acelerar cobranza",
                supporting_data={
                    "shortage_currencies": shortage_currencies,
                    "payments_by_currency": {c: len(p) for c, p in payments_by_currency.items()},
                },
            )
            proposals_created += 1
        elif net_position < 0:
            priority = Priority.HIGH
            message += f"\n\n⚠️ *Posición neta negativa - Monitorear*"
        else:
            priority = Priority.MEDIUM
            message += f"\n\n✅ Fondos suficientes"
        
        await self.notify(
            title=f"💳 Pagos 7d: {len(payments)} facturas | Neto: {self.format_currency(net_position)}",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="upcoming_payments",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={
                "total_payments_by_currency": totals_by_currency,
                "cash_by_currency": balances_by_currency,
                "net_local": net_position,
                "payments_count": len(payments),
            }
        )
    
    async def weekly_treasury_report(self) -> TaskResult:
        """Genera reporte semanal de tesorería."""
        started_at = datetime.now()
        
        self.logger.info("Generando reporte semanal de tesorería...")
        
        # Saldos por divisa
        balances_by_currency = self._get_cash_balance_by_currency()
        cash_local = balances_by_currency.get(self.default_currency, 0.0)
        
        daily_burn = self._calculate_daily_burn()
        runway = cash_local / daily_burn if daily_burn > 0 else 999
        
        # Movimientos de la semana
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Cobros recibidos
        received = self.search_read(
            "account.payment",
            [
                ("payment_type", "=", "inbound"),
                ("state", "=", "posted"),
                ("date", ">=", week_start),
                ("company_id", "=", self.company_id),
            ],
            ["amount", "currency_id"],
            limit=500
        )
        total_received = sum(p.get("amount", 0) for p in received)
        
        # Pagos realizados
        paid = self.search_read(
            "account.payment",
            [
                ("payment_type", "=", "outbound"),
                ("state", "=", "posted"),
                ("date", ">=", week_start),
                ("company_id", "=", self.company_id),
            ],
            ["amount", "currency_id"],
            limit=500
        )
        total_paid = sum(p.get("amount", 0) for p in paid)
        
        # Construir mensaje con saldos por divisa
        currency_summary = "\n".join(
            f"  • {curr}: {bal:,.2f}" 
            for curr, bal in sorted(balances_by_currency.items())
        )
        
        message = f"""
*📊 Reporte Semanal de Tesorería*
_Company ID: {self.company_id} | {self.format_date(week_start)} - {datetime.now().strftime('%d/%m/%Y')}_

*Saldos actuales por divisa:*
{currency_summary}

*Runway ({self.default_currency}):* {runway:.0f} días

*Movimientos de la semana:*
• Cobros recibidos: {self.format_currency(total_received)} ({len(received)} pagos)
• Pagos realizados: {self.format_currency(total_paid)} ({len(paid)} pagos)
• Flujo neto: {self.format_currency(total_received - total_paid)}

*Próxima semana:*
• Cobranza esperada: {self.format_currency(sum(c.get('amount_residual', 0) for c in self._get_expected_collections(7)))}
• Pagos programados: {self.format_currency(sum(p.get('amount_residual', 0) for p in self._get_upcoming_payments(7)))}

_¡Buen fin de semana!_
        """.strip()
        
        await self.notify(
            title="📊 Reporte Semanal Tesorería",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="weekly_report",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "cash_local": cash_local,
                "cash_by_currency": balances_by_currency,
                "received": total_received,
                "paid": total_paid,
                "net": total_received - total_paid,
            }
        )
    
    # ==================== Helpers ====================
    
    def _get_cash_balance(self, company_id: int | None = None) -> float:
        """
        Obtiene saldo total de cuentas bancarias operativas EN DIVISA LOCAL.
        
        Para saldos por divisa, usar _get_cash_balance_by_currency().
        """
        balances = self._get_cash_balance_by_currency(company_id)
        # Retorna solo el saldo en divisa por defecto para compatibilidad
        return balances.get(self.default_currency, 0.0)
    
    def _get_cash_balance_by_currency(self, company_id: int | None = None) -> dict[str, float]:
        """
        Obtiene saldos de cuentas bancarias SEPARADOS POR DIVISA.
        
        FILTROS:
        - company_id: Configurable (default desde settings.odoo.company_id)
        - Tipo de diario: bank, cash (NO tarjetas de crédito)
        - Solo cuentas tipo asset_cash (NO liability_credit_card)
        
        Returns:
            dict: {"MXN": 123456.78, "USD": 5000.00, ...}
        """
        company_id = company_id or self.company_id
        
        # Obtener diarios de banco/caja de la empresa (NO tarjetas)
        journals = self.search_read(
            "account.journal",
            [
                ("type", "in", ["bank", "cash"]),  # Solo banco y efectivo
                ("company_id", "=", company_id),
            ],
            ["name", "default_account_id", "currency_id"],
            limit=50
        )
        
        if not journals:
            return {}
        
        # Mapear cuenta -> divisa
        account_currency_map = {}
        account_ids = []
        
        for j in journals:
            if j.get("default_account_id"):
                acc_id = j["default_account_id"][0]
                # Si el diario tiene divisa específica, usarla; si no, divisa local
                currency = j.get("currency_id", [0, self.default_currency])[1] if j.get("currency_id") else self.default_currency
                account_currency_map[acc_id] = currency
                account_ids.append(acc_id)
        
        if not account_ids:
            return {}
        
        # Filtrar duplicados
        account_ids = list(set(account_ids))
        
        # Verificar que las cuentas sean de tipo asset_cash (NO tarjetas de crédito)
        valid_accounts = self.search_read(
            "account.account",
            [
                ("id", "in", account_ids),
                ("account_type", "=", "asset_cash"),
            ],
            ["id"],
            limit=50
        )
        valid_account_ids = [a["id"] for a in valid_accounts]
        
        if not valid_account_ids:
            return {}
        
        # Obtener saldos por cuenta
        balances_by_currency: dict[str, float] = {}
        
        for acc_id in valid_account_ids:
            lines = self.search_read(
                "account.move.line",
                [
                    ("account_id", "=", acc_id),
                    ("parent_state", "=", "posted"),
                    ("company_id", "=", company_id),
                ],
                ["balance"],
                limit=10000
            )
            
            balance = sum(l.get("balance", 0) for l in lines)
            currency = account_currency_map.get(acc_id, self.default_currency)
            
            if currency not in balances_by_currency:
                balances_by_currency[currency] = 0.0
            balances_by_currency[currency] += balance
        
        return balances_by_currency
    
    def _get_bank_accounts_detail(self, company_id: int | None = None) -> list[dict]:
        """
        Obtiene detalle de saldos por cuenta bancaria.
        
        FILTROS:
        - company_id: Configurable (default desde settings)
        - Tipo de diario: bank, cash (NO tarjetas)
        - Tipo de cuenta: asset_cash (NO liability_credit_card)
        
        Returns:
            list[dict]: [{"name": "BBVA", "balance": 123.45, "currency": "MXN"}, ...]
        """
        company_id = company_id or self.company_id
        
        # Diarios de banco/caja de la empresa
        journals = self.search_read(
            "account.journal",
            [
                ("type", "in", ["bank", "cash"]),
                ("company_id", "=", company_id),
            ],
            ["name", "default_account_id", "currency_id"],
            limit=20
        )
        
        result = []
        for j in journals:
            account_id = j.get("default_account_id", [0])[0] if j.get("default_account_id") else 0
            if not account_id:
                continue
            
            # Verificar que la cuenta sea asset_cash
            account = self.search_read(
                "account.account",
                [
                    ("id", "=", account_id),
                    ("account_type", "=", "asset_cash"),
                ],
                ["id", "name"],
                limit=1
            )
            
            if not account:
                continue  # Saltar si no es cuenta de efectivo
            
            # Obtener saldo
            lines = self.search_read(
                "account.move.line",
                [
                    ("account_id", "=", account_id),
                    ("parent_state", "=", "posted"),
                    ("company_id", "=", company_id),
                ],
                ["balance"],
                limit=5000
            )
            
            balance = sum(l.get("balance", 0) for l in lines)
            currency = j.get("currency_id", [0, self.default_currency])[1] if j.get("currency_id") else self.default_currency
            
            result.append({
                "name": j["name"],
                "balance": balance,
                "currency": currency,
            })
        
        return result
    
    def _calculate_daily_burn(self, company_id: int | None = None) -> float:
        """Calcula el gasto diario promedio (últimos 30 días)."""
        company_id = company_id or self.company_id
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        payments = self.search_read(
            "account.payment",
            [
                ("payment_type", "=", "outbound"),
                ("state", "=", "posted"),
                ("date", ">=", date_from),
                ("company_id", "=", company_id),
            ],
            ["amount", "currency_id"],
            limit=1000
        )
        
        total = sum(p.get("amount", 0) for p in payments)
        return total / 30 if total > 0 else 25000.0  # Default si no hay datos
    
    def _get_upcoming_payments(self, days: int = 7, company_id: int | None = None) -> list[dict]:
        """Obtiene pagos próximos (facturas de proveedor pendientes)."""
        company_id = company_id or self.company_id
        due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        return self.search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("invoice_date_due", "<=", due_date),
                ("company_id", "=", company_id),
            ],
            ["partner_id", "amount_residual", "invoice_date_due", "ref", "currency_id"],
            limit=200,
            order="invoice_date_due asc"
        )
    
    def _get_expected_collections(self, days: int = 7, company_id: int | None = None) -> list[dict]:
        """Obtiene cobranza esperada (facturas de cliente por vencer)."""
        company_id = company_id or self.company_id
        due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        return self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("invoice_date_due", ">=", today),
                ("invoice_date_due", "<=", due_date),
                ("company_id", "=", company_id),
            ],
            ["partner_id", "amount_residual", "invoice_date_due", "currency_id"],
            limit=200,
            order="invoice_date_due asc"
        )
    
    # ==================== Planeación Financiera Profesional ====================
    
    async def analyze_financial_ratios(self) -> TaskResult:
        """Análisis avanzado de ratios financieros y tendencias."""
        started_at = datetime.now()
        
        self.logger.info("Analizando ratios financieros...")
        
        # Obtener datos históricos (últimos 3 meses)
        months_data = []
        for i in range(3):
            month_start = (datetime.now() - timedelta(days=30*(i+1))).strftime("%Y-%m-%d")
            month_end = (datetime.now() - timedelta(days=30*i)).strftime("%Y-%m-%d")
            
            # Ingresos del mes
            invoices = self.search_read(
                "account.move",
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("invoice_date", ">=", month_start),
                    ("invoice_date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["amount_total", "amount_residual"],
                limit=1000
            )
            revenue = sum(i.get("amount_total", 0) for i in invoices)
            
            # Gastos del mes
            expenses = self.search_read(
                "account.payment",
                [
                    ("payment_type", "=", "outbound"),
                    ("state", "=", "posted"),
                    ("date", ">=", month_start),
                    ("date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["amount"],
                limit=1000
            )
            expenses_total = sum(e.get("amount", 0) for e in expenses)
            
            months_data.append({
                "month": month_start[:7],
                "revenue": revenue,
                "expenses": expenses_total,
                "net": revenue - expenses_total,
            })
        
        # Calcular ratios
        current_month = months_data[0] if months_data else {}
        prev_month = months_data[1] if len(months_data) > 1 else {}
        
        # Margen neto
        net_margin = (current_month.get("net", 0) / current_month.get("revenue", 1) * 100) if current_month.get("revenue", 0) > 0 else 0
        
        # Crecimiento de ingresos
        revenue_growth = 0
        if prev_month.get("revenue", 0) > 0:
            revenue_growth = ((current_month.get("revenue", 0) - prev_month.get("revenue", 0)) / prev_month.get("revenue", 0)) * 100
        
        # Ratio de gastos sobre ingresos
        expense_ratio = (current_month.get("expenses", 0) / current_month.get("revenue", 1) * 100) if current_month.get("revenue", 0) > 0 else 0
        
        # Liquidez corriente (simplificado)
        cash_balance = self._get_cash_balance_by_currency().get(self.default_currency, 0.0)
        upcoming_payments_30d = sum(p.get("amount_residual", 0) for p in self._get_upcoming_payments(30))
        current_ratio = cash_balance / upcoming_payments_30d if upcoming_payments_30d > 0 else 999
        
        # Construir mensaje
        message = f"""
*📊 Análisis Financiero Avanzado*

*Ratios del Mes Actual:*
• Margen Neto: {net_margin:.1f}%
• Ratio Gastos/Ingresos: {expense_ratio:.1f}%
• Liquidez Corriente: {current_ratio:.2f}
• Crecimiento Ingresos: {revenue_growth:+.1f}%

*Tendencias (últimos 3 meses):*
| Mes | Ingresos | Gastos | Neto |
|-----|----------|--------|------|
        """.strip()
        
        for data in reversed(months_data):
            message += f"\n| {data['month']} | {self.format_currency(data['revenue'])} | {self.format_currency(data['expenses'])} | {self.format_currency(data['net'])} |"
        
        # Alertas y recomendaciones
        proposals_created = 0
        
        if net_margin < 10:
            message += f"\n\n⚠️ *Margen neto bajo ({net_margin:.1f}%)*"
            await self.propose(
                title="Margen neto bajo - Revisar estructura de costos",
                description=f"El margen neto es {net_margin:.1f}%, por debajo del umbral recomendado",
                priority=Priority.HIGH,
                situation_summary=f"""
Margen neto actual: {net_margin:.1f}%
Ingresos: {self.format_currency(current_month.get('revenue', 0))}
Gastos: {self.format_currency(current_month.get('expenses', 0))}
                """.strip(),
                proposed_action_detail="Revisar estructura de costos y optimizar gastos operativos",
                supporting_data={"net_margin": net_margin, "months_data": months_data},
            )
            proposals_created += 1
        
        if expense_ratio > 90:
            message += f"\n\n⚠️ *Ratio de gastos muy alto ({expense_ratio:.1f}%)*"
        
        if current_ratio < 1.0:
            message += f"\n\n🔴 *Liquidez crítica (ratio {current_ratio:.2f})*"
            priority = Priority.CRITICAL
        else:
            priority = Priority.MEDIUM
        
        await self.notify(
            title="📊 Análisis Financiero - Ratios y Tendencias",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="financial_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={
                "net_margin": net_margin,
                "revenue_growth": revenue_growth,
                "expense_ratio": expense_ratio,
                "current_ratio": current_ratio,
                "months_data": months_data,
            }
        )
    
    async def compare_vs_budget(self) -> TaskResult:
        """Compara resultados reales vs presupuestado."""
        started_at = datetime.now()
        
        self.logger.info("Comparando vs presupuesto...")
        
        # Mes actual
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_end = datetime.now().strftime("%Y-%m-%d")
        
        # Ingresos reales del mes
        invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_start),
                ("invoice_date", "<=", month_end),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total"],
            limit=1000
        )
        actual_revenue = sum(i.get("amount_total", 0) for i in invoices)
        
        # Gastos reales del mes
        expenses = self.search_read(
            "account.payment",
            [
                ("payment_type", "=", "outbound"),
                ("state", "=", "posted"),
                ("date", ">=", month_start),
                ("date", "<=", month_end),
                ("company_id", "=", self.company_id),
            ],
            ["amount"],
            limit=1000
        )
        actual_expenses = sum(e.get("amount", 0) for e in expenses)
        
        # Calcular días transcurridos del mes
        days_elapsed = datetime.now().day
        days_in_month = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        days_in_month = days_in_month.day
        progress_pct = (days_elapsed / days_in_month) * 100
        
        # Presupuesto esperado hasta la fecha
        expected_revenue = self.monthly_budget * (progress_pct / 100)
        expected_expenses = self.monthly_expenses_budget * (progress_pct / 100)
        
        # Variaciones
        revenue_variance = actual_revenue - expected_revenue
        revenue_variance_pct = (revenue_variance / expected_revenue * 100) if expected_revenue > 0 else 0
        
        expense_variance = actual_expenses - expected_expenses
        expense_variance_pct = (expense_variance / expected_expenses * 100) if expected_expenses > 0 else 0
        
        # Proyección al final del mes
        projected_revenue = (actual_revenue / progress_pct * 100) if progress_pct > 0 else 0
        projected_expenses = (actual_expenses / progress_pct * 100) if progress_pct > 0 else 0
        
        message = f"""
*💰 Comparativo vs Presupuesto*
_Mes: {datetime.now().strftime('%B %Y')} ({progress_pct:.0f}% transcurrido)_

*Ingresos:*
• Real: {self.format_currency(actual_revenue)}
• Esperado: {self.format_currency(expected_revenue)}
• Variación: {self.format_currency(revenue_variance)} ({revenue_variance_pct:+.1f}%)
• Proyección mes: {self.format_currency(projected_revenue)}

*Gastos:*
• Real: {self.format_currency(actual_expenses)}
• Esperado: {self.format_currency(expected_expenses)}
• Variación: {self.format_currency(expense_variance)} ({expense_variance_pct:+.1f}%)
• Proyección mes: {self.format_currency(projected_expenses)}

*Neto Proyectado:*
• {self.format_currency(projected_revenue - projected_expenses)}
        """.strip()
        
        proposals_created = 0
        priority = Priority.MEDIUM
        
        # Alertas por desviaciones significativas
        if revenue_variance_pct < -10:
            message += f"\n\n⚠️ *Ingresos {abs(revenue_variance_pct):.1f}% por debajo del presupuesto*"
            await self.propose(
                title="Desviación negativa en ingresos",
                description=f"Ingresos {revenue_variance_pct:.1f}% por debajo del presupuesto esperado",
                priority=Priority.HIGH,
                situation_summary=f"""
Presupuesto mensual: {self.format_currency(self.monthly_budget)}
Ingresos reales: {self.format_currency(actual_revenue)}
Esperado hasta hoy: {self.format_currency(expected_revenue)}
Variación: {revenue_variance_pct:.1f}%
                """.strip(),
                proposed_action_detail="Acelerar ventas y revisar estrategia comercial",
                supporting_data={
                    "actual_revenue": actual_revenue,
                    "expected_revenue": expected_revenue,
                    "variance_pct": revenue_variance_pct,
                },
            )
            proposals_created += 1
            priority = Priority.HIGH
        
        if expense_variance_pct > 15:
            message += f"\n\n⚠️ *Gastos {expense_variance_pct:.1f}% por encima del presupuesto*"
            await self.propose(
                title="Desviación positiva en gastos",
                description=f"Gastos {expense_variance_pct:.1f}% por encima del presupuesto esperado",
                priority=Priority.HIGH,
                situation_summary=f"""
Gastos reales: {self.format_currency(actual_expenses)}
Esperado hasta hoy: {self.format_currency(expected_expenses)}
Variación: {expense_variance_pct:.1f}%
                """.strip(),
                proposed_action_detail="Revisar gastos y optimizar costos operativos",
                supporting_data={
                    "actual_expenses": actual_expenses,
                    "expected_expenses": expected_expenses,
                    "variance_pct": expense_variance_pct,
                },
            )
            proposals_created += 1
        
        await self.notify(
            title="💰 Comparativo vs Presupuesto",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="budget_comparison",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={
                "actual_revenue": actual_revenue,
                "expected_revenue": expected_revenue,
                "revenue_variance_pct": revenue_variance_pct,
                "actual_expenses": actual_expenses,
                "expected_expenses": expected_expenses,
                "expense_variance_pct": expense_variance_pct,
                "projected_revenue": projected_revenue,
                "projected_expenses": projected_expenses,
            }
        )
    
    async def analyze_profitability(self) -> TaskResult:
        """Análisis de rentabilidad por centro de costo y producto/servicio."""
        started_at = datetime.now()
        
        self.logger.info("Analizando rentabilidad...")
        
        # Obtener ingresos y gastos del mes actual
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_end = datetime.now().strftime("%Y-%m-%d")
        
        # Ingresos totales
        invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_start),
                ("invoice_date", "<=", month_end),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total", "invoice_line_ids"],
            limit=1000
        )
        total_revenue = sum(i.get("amount_total", 0) for i in invoices)
        
        # Análisis por producto/servicio (si hay líneas de factura)
        revenue_by_product = {}
        if invoices:
            # Obtener líneas de factura con productos
            for invoice in invoices[:50]:  # Limitar para performance
                invoice_lines = self.search_read(
                    "account.move.line",
                    [
                        ("move_id", "=", invoice["id"]),
                        ("product_id", "!=", False),
                    ],
                    ["product_id", "price_subtotal"],
                    limit=100
                )
                
                for line in invoice_lines:
                    product_id = line.get("product_id")
                    if product_id:
                        product_name = product_id[1] if isinstance(product_id, list) else "Sin nombre"
                        amount = line.get("price_subtotal", 0)
                        if product_name not in revenue_by_product:
                            revenue_by_product[product_name] = 0
                        revenue_by_product[product_name] += amount
        
        # Análisis por categoría usando cuentas analíticas (si existen)
        expenses_by_category = {}
        revenue_by_category = {}
        
        # Intentar usar cuentas analíticas primero
        if self._model_exists("account.analytic.line"):
            analytic_lines = self.search_read(
                "account.analytic.line",
                [
                    ("date", ">=", month_start),
                    ("date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["account_id", "amount", "account_id"],
                limit=500
            )
            
            for line in analytic_lines:
                account_id = line.get("account_id")
                if account_id:
                    account_name = account_id[1] if isinstance(account_id, list) else "Sin nombre"
                    amount = abs(line.get("amount", 0))
                    
                    if amount < 0:  # Gastos
                        if account_name not in expenses_by_category:
                            expenses_by_category[account_name] = 0
                        expenses_by_category[account_name] += amount
                    else:  # Ingresos
                        if account_name not in revenue_by_category:
                            revenue_by_category[account_name] = 0
                        revenue_by_category[account_name] += amount
        
        # Si no hay cuentas analíticas, usar cuentas contables
        if not expenses_by_category:
            expense_accounts = self.search_read(
                "account.account",
                [
                    ("account_type", "in", ["expense", "expense_depreciation", "expense_direct_cost"]),
                    ("company_id", "=", self.company_id),
                ],
                ["id", "name", "code"],
                limit=50
            )
            
            for account in expense_accounts:
                account_id = account["id"]
                account_name = account.get("name", "Sin nombre")
                
                lines = self.search_read(
                    "account.move.line",
                    [
                        ("account_id", "=", account_id),
                        ("parent_state", "=", "posted"),
                        ("date", ">=", month_start),
                        ("date", "<=", month_end),
                        ("company_id", "=", self.company_id),
                    ],
                    ["balance"],
                    limit=1000
                )
                
                total = abs(sum(l.get("balance", 0) for l in lines))
                if total > 0:
                    expenses_by_category[account_name] = total
        
        # Comparar con presupuestos por categoría si están configurados
        budget_comparison = {}
        if self.category_budgets:
            for category, budget_amount in self.category_budgets.items():
                actual = expenses_by_category.get(category, 0)
                variance = actual - budget_amount
                variance_pct = (variance / budget_amount * 100) if budget_amount > 0 else 0
                budget_comparison[category] = {
                    "budget": budget_amount,
                    "actual": actual,
                    "variance": variance,
                    "variance_pct": variance_pct,
                }
        
        # Calcular margen de contribución
        total_expenses = sum(expenses_by_category.values())
        contribution_margin = total_revenue - total_expenses
        margin_pct = (contribution_margin / total_revenue * 100) if total_revenue > 0 else 0
        
        # Punto de equilibrio (simplificado)
        fixed_costs = total_expenses * 0.7
        variable_costs = total_expenses * 0.3
        break_even = fixed_costs / (1 - (variable_costs / total_revenue)) if total_revenue > 0 and variable_costs < total_revenue else 0
        
        message = f"""
*📈 Análisis de Rentabilidad*

*Resumen del Mes:*
• Ingresos Totales: {self.format_currency(total_revenue)}
• Gastos Totales: {self.format_currency(total_expenses)}
• Margen de Contribución: {self.format_currency(contribution_margin)} ({margin_pct:.1f}%)
• Punto de Equilibrio: {self.format_currency(break_even)}

*Gastos por Categoría (Top 10):*
        """.strip()
        
        # Top 10 categorías de gasto
        sorted_expenses = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)[:10]
        for category, amount in sorted_expenses:
            pct = (amount / total_expenses * 100) if total_expenses > 0 else 0
            budget_info = ""
            if category in budget_comparison:
                bc = budget_comparison[category]
                budget_info = f" (Presup: {self.format_currency(bc['budget'])}, Var: {bc['variance_pct']:+.1f}%)"
            message += f"\n• {category[:30]}: {self.format_currency(amount)} ({pct:.1f}%){budget_info}"
        
        # Análisis por producto si hay datos
        if revenue_by_product:
            message += f"\n\n*Ingresos por Producto/Servicio (Top 5):*"
            sorted_products = sorted(revenue_by_product.items(), key=lambda x: x[1], reverse=True)[:5]
            for product, amount in sorted_products:
                pct = (amount / total_revenue * 100) if total_revenue > 0 else 0
                message += f"\n• {product[:30]}: {self.format_currency(amount)} ({pct:.1f}%)"
        
        priority = Priority.MEDIUM
        
        if margin_pct < 20:
            message += f"\n\n⚠️ *Margen de contribución bajo ({margin_pct:.1f}%)*"
            priority = Priority.HIGH
        
        # Alertas por desviaciones de presupuesto
        if budget_comparison:
            significant_deviations = [
                cat for cat, data in budget_comparison.items()
                if abs(data["variance_pct"]) > 15
            ]
            if significant_deviations:
                message += f"\n\n⚠️ *Desviaciones significativas en: {', '.join(significant_deviations[:3])}*"
        
        await self.notify(
            title="📈 Análisis de Rentabilidad",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="profitability_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "contribution_margin": contribution_margin,
                "margin_pct": margin_pct,
                "break_even": break_even,
                "expenses_by_category": expenses_by_category,
                "revenue_by_product": revenue_by_product,
                "budget_comparison": budget_comparison,
                "budget_source": self._get_budgets().get("source", "unknown"),
            }
        )
    
    def _model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo de Odoo existe."""
        try:
            self.odoo.execute(model_name, "check_access_rights", ["read"], {"raise_exception": False})
            return True
        except Exception:
            return False
    
    async def generate_annual_forecast(self) -> TaskResult:
        """Genera proyecciones anuales con múltiples escenarios."""
        started_at = datetime.now()
        
        self.logger.info("Generando proyecciones anuales...")
        
        # Obtener datos históricos (últimos 6 meses)
        historical_data = []
        for i in range(6):
            month_start = (datetime.now() - timedelta(days=30*(i+1))).strftime("%Y-%m-%d")
            month_end = (datetime.now() - timedelta(days=30*i)).strftime("%Y-%m-%d")
            
            invoices = self.search_read(
                "account.move",
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("invoice_date", ">=", month_start),
                    ("invoice_date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["amount_total"],
                limit=500
            )
            revenue = sum(i.get("amount_total", 0) for i in invoices)
            
            expenses = self.search_read(
                "account.payment",
                [
                    ("payment_type", "=", "outbound"),
                    ("state", "=", "posted"),
                    ("date", ">=", month_start),
                    ("date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["amount"],
                limit=500
            )
            expenses_total = sum(e.get("amount", 0) for e in expenses)
            
            historical_data.append({
                "revenue": revenue,
                "expenses": expenses_total,
            })
        
        # Calcular promedios y tendencias
        avg_monthly_revenue = sum(d["revenue"] for d in historical_data) / len(historical_data) if historical_data else 0
        avg_monthly_expenses = sum(d["expenses"] for d in historical_data) / len(historical_data) if historical_data else 0
        
        # Calcular crecimiento promedio
        if len(historical_data) >= 2:
            recent_avg = sum(d["revenue"] for d in historical_data[:3]) / 3
            older_avg = sum(d["revenue"] for d in historical_data[3:]) / 3
            growth_rate = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            growth_rate = 0
        
        # Escenarios anuales
        months_remaining = 12 - datetime.now().month
        
        # Escenario Optimista: crecimiento del 10%
        optimistic_revenue = avg_monthly_revenue * months_remaining * 1.10
        optimistic_expenses = avg_monthly_expenses * months_remaining * 1.05
        optimistic_net = optimistic_revenue - optimistic_expenses
        
        # Escenario Realista: sin crecimiento
        realistic_revenue = avg_monthly_revenue * months_remaining
        realistic_expenses = avg_monthly_expenses * months_remaining
        realistic_net = realistic_revenue - realistic_expenses
        
        # Escenario Pesimista: decrecimiento del 10%
        pessimistic_revenue = avg_monthly_revenue * months_remaining * 0.90
        pessimistic_expenses = avg_monthly_expenses * months_remaining * 1.10
        pessimistic_net = pessimistic_revenue - pessimistic_expenses
        
        message = f"""
*🔮 Proyección Anual {datetime.now().year}*
_Meses restantes: {months_remaining}_

*Promedio Histórico (últimos 6 meses):*
• Ingresos mensuales: {self.format_currency(avg_monthly_revenue)}
• Gastos mensuales: {self.format_currency(avg_monthly_expenses)}
• Tasa de crecimiento: {growth_rate:+.1f}%

*Escenarios para el resto del año:*

*🟢 Optimista (crecimiento 10%):*
• Ingresos: {self.format_currency(optimistic_revenue)}
• Gastos: {self.format_currency(optimistic_expenses)}
• Neto: {self.format_currency(optimistic_net)}

*🟡 Realista (sin cambios):*
• Ingresos: {self.format_currency(realistic_revenue)}
• Gastos: {self.format_currency(realistic_expenses)}
• Neto: {self.format_currency(realistic_net)}

*🔴 Pesimista (decrecimiento 10%):*
• Ingresos: {self.format_currency(pessimistic_revenue)}
• Gastos: {self.format_currency(pessimistic_expenses)}
• Neto: {self.format_currency(pessimistic_net)}
        """.strip()
        
        # Recomendaciones según escenario pesimista
        if pessimistic_net < 0:
            message += f"\n\n⚠️ *En escenario pesimista habría pérdidas*"
            priority = Priority.HIGH
        else:
            priority = Priority.MEDIUM
        
        await self.notify(
            title="🔮 Proyección Anual",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="annual_forecast",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "avg_monthly_revenue": avg_monthly_revenue,
                "avg_monthly_expenses": avg_monthly_expenses,
                "growth_rate": growth_rate,
                "scenarios": {
                    "optimistic": {"revenue": optimistic_revenue, "expenses": optimistic_expenses, "net": optimistic_net},
                    "realistic": {"revenue": realistic_revenue, "expenses": realistic_expenses, "net": realistic_net},
                    "pessimistic": {"revenue": pessimistic_revenue, "expenses": pessimistic_expenses, "net": pessimistic_net},
                }
            }
        )
    
    async def generate_executive_report(self) -> TaskResult:
        """Genera reporte ejecutivo mensual con KPIs y recomendaciones."""
        started_at = datetime.now()
        
        self.logger.info("Generando reporte ejecutivo mensual...")
        
        # Consolidar información de todas las métricas
        balances = self._get_cash_balance_by_currency()
        cash_local = balances.get(self.default_currency, 0.0)
        
        daily_burn = self._calculate_daily_burn()
        runway = cash_local / daily_burn if daily_burn > 0 else 999
        
        # Mes anterior completo
        prev_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
        prev_month_end = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        
        prev_invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", prev_month_start),
                ("invoice_date", "<=", prev_month_end),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total"],
            limit=1000
        )
        prev_revenue = sum(i.get("amount_total", 0) for i in prev_invoices)
        
        # Mes actual
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_end = datetime.now().strftime("%Y-%m-%d")
        
        curr_invoices = self.search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", month_start),
                ("invoice_date", "<=", month_end),
                ("company_id", "=", self.company_id),
            ],
            ["amount_total"],
            limit=1000
        )
        curr_revenue = sum(i.get("amount_total", 0) for i in curr_invoices)
        
        # Crecimiento mensual
        revenue_growth = ((curr_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
        
        # KPIs consolidados
        message = f"""
*📊 Reporte Ejecutivo Mensual*
_{datetime.now().strftime('%B %Y')}_

*🎯 KPIs Principales:*

*Liquidez:*
• Saldo disponible: {self.format_currency(cash_local)}
• Runway: {runway:.0f} días
• Posición: {"🔴 Crítica" if runway <= self.critical_runway_days else "⚠️ Atención" if runway <= self.warning_runway_days else "✅ Saludable"}

*Ingresos:*
• Mes anterior: {self.format_currency(prev_revenue)}
• Mes actual: {self.format_currency(curr_revenue)}
• Crecimiento: {revenue_growth:+.1f}%

*Presupuesto:*
• Presupuesto mensual: {self.format_currency(self.monthly_budget)}
• Cumplimiento: {(curr_revenue / self.monthly_budget * 100):.1f}%

*Recomendaciones Estratégicas:*
        """.strip()
        
        recommendations = []
        
        if runway <= self.warning_runway_days:
            recommendations.append("🔴 Acelerar cobranza y/o buscar financiamiento")
        
        if revenue_growth < 0:
            recommendations.append("⚠️ Revisar estrategia comercial - ingresos en descenso")
        
        if curr_revenue < self.monthly_budget * 0.8:
            recommendations.append("⚠️ Acelerar ventas para alcanzar presupuesto")
        
        if not recommendations:
            recommendations.append("✅ Situación financiera estable - mantener curso")
        
        for rec in recommendations:
            message += f"\n{rec}"
        
        priority = Priority.CRITICAL if runway <= self.critical_runway_days else Priority.HIGH if runway <= self.warning_runway_days else Priority.MEDIUM
        
        await self.notify(
            title="📊 Reporte Ejecutivo Mensual",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="monthly_executive_report",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "cash_balance": cash_local,
                "runway_days": runway,
                "prev_revenue": prev_revenue,
                "curr_revenue": curr_revenue,
                "revenue_growth": revenue_growth,
                "budget_compliance": (curr_revenue / self.monthly_budget * 100) if self.monthly_budget > 0 else 0,
            }
        )


def create_finance_agent() -> FinanceAgent:
    """Crea y retorna el agente de finanzas."""
    return FinanceAgent()
