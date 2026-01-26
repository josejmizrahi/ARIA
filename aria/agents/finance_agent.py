"""
Agente de Finanzas - Tesorería y flujo de caja.

Monitorea saldos bancarios, proyecciones de flujo,
pagos próximos y alertas de liquidez.
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.task import TaskDefinition, TaskResult
from aria.models.proposal import Priority


class FinanceAgent(BaseAgent):
    """
    Agente autónomo para gestión de tesorería y finanzas.
    
    Monitorea:
    - Proyección de flujo de caja (4 semanas)
    - Saldos bancarios (separados por divisa)
    - Pagos próximos vs disponible
    - Reporte semanal de tesorería
    
    Filtros:
    - company_id: Configurable desde settings (ODOO_COMPANY_ID)
    - Tipo diario: bank, cash (NO tarjetas de crédito)
    - Tipo cuenta: asset_cash (NO liability_credit_card)
    - Saldos separados por divisa
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="finanzas",
            description="Tesorería, flujo de caja y gestión de liquidez"
        )
        
        # Configuración desde settings
        self.company_id = settings.odoo.company_id
        self.default_currency = settings.odoo.default_currency
        
        # Parámetros de alertas
        self.critical_runway_days = 7  # Días críticos de runway
        self.warning_runway_days = 14  # Días de advertencia
        self.projection_weeks = 4  # Semanas de proyección
    
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
        
        # Reporte semanal
        self.register_task(TaskDefinition(
            name="weekly_report",
            method="weekly_treasury_report",
            schedule="0 17 * * 5",  # Viernes 5:00 PM
            description="Genera reporte semanal de tesorería"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de finanzas."""
        
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
        
        # Determinar estado
        if cash_local < 0 or runway <= self.critical_runway_days:
            status = "critical"
        elif runway <= self.warning_runway_days:
            status = "warning"
        elif total_upcoming > cash_local + total_expected:
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


def create_finance_agent() -> FinanceAgent:
    """Crea y retorna el agente de finanzas."""
    return FinanceAgent()
