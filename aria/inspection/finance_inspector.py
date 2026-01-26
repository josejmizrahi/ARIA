"""
Inspector Contextual de Finanzas.

Analiza tesorería y flujo de caja en 4 niveles:
1. Vista general: Posición de caja, flujo proyectado
2. Por categorías: Saldo por banco/cuenta, pagos por semana
3. Detalles: Pagos próximos, partidas sin conciliar
4. Anomalías: Saldos negativos, extractos sin cerrar
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class FinanceInspector(BaseContextInspector):
    """Inspector contextual para Tesorería y Flujo de Caja."""
    
    AGENT_NAME = "finanzas"
    AREA_NAME = "Tesorería y Flujo de Caja"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="upstream",
            data_flow="Facturas de ingreso",
            criticality=ImpactLevel.HIGH,
            description="Ventas genera ingresos proyectados"
        ),
        AgentDependency(
            agent_name="compras",
            dependency_type="upstream",
            data_flow="Facturas de gasto",
            criticality=ImpactLevel.HIGH,
            description="Compras genera egresos a programar"
        ),
        AgentDependency(
            agent_name="cobranza",
            dependency_type="upstream",
            data_flow="Pagos recibidos",
            criticality=ImpactLevel.HIGH,
            description="Cobranza convierte CxC en efectivo"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="compras",
            dependency_type="downstream",
            data_flow="Disponibilidad para pagar",
            criticality=ImpactLevel.HIGH,
            description="Compras depende de fondos para pagar"
        ),
        AgentDependency(
            agent_name="ceo",
            dependency_type="downstream",
            data_flow="Reportes financieros",
            criticality=ImpactLevel.CRITICAL,
            description="CEO requiere posición de caja para decisiones"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.default_currency = "MXN"
        self.critical_runway_days = 7
        self.warning_runway_days = 14
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de tesorería."""
        
        # Obtener saldos por divisa
        balances = self._get_cash_balances()
        total_cash = sum(balances.values())
        
        # Pagos próximos 7 días
        payments_7d = self._get_upcoming_payments(7)
        total_payments = sum(p.get("amount_residual", 0) for p in payments_7d)
        
        # Cobranza esperada 7 días
        collections_7d = self._get_expected_collections(7)
        total_collections = sum(c.get("amount_residual", 0) for c in collections_7d)
        
        # Posición neta
        net_position = total_cash + total_collections - total_payments
        
        # Health basado en runway
        daily_burn = total_payments / 7 if total_payments > 0 else 0
        runway = total_cash / daily_burn if daily_burn > 0 else 999
        
        if runway <= self.critical_runway_days:
            health = 20
        elif runway <= self.warning_runway_days:
            health = 50
        elif net_position < 0:
            health = 60
        else:
            health = 100
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=len(payments_7d),
            total_value=total_cash,
            health_score=health,
            status=self._get_status_from_health(health),
            summary={
                "total_cash": total_cash,
                "balances_by_currency": balances,
                "payments_7d": total_payments,
                "collections_7d": total_collections,
                "net_position": net_position,
                "runway_days": runway,
            }
        )
    
    def _get_cash_balances(self) -> dict[str, float]:
        """Obtiene saldos de caja por divisa."""
        
        # Diarios de banco/caja
        journals = self._search_read(
            "account.journal",
            [
                ("type", "in", ["bank", "cash"]),
                ("company_id", "=", self.company_id),
            ],
            ["name", "default_account_id", "currency_id"],
            limit=50
        )
        
        balances: dict[str, float] = {}
        
        for journal in journals:
            account_id = self._safe_get_id(journal, "default_account_id")
            if not account_id:
                continue
            
            currency = self._safe_get_name(journal, "currency_id") or self.default_currency
            
            # Obtener saldo de la cuenta
            lines = self._search_read(
                "account.move.line",
                [
                    ("account_id", "=", account_id),
                    ("parent_state", "=", "posted"),
                    ("company_id", "=", self.company_id),
                ],
                ["balance"],
                limit=10000
            )
            
            balance = sum(l.get("balance", 0) for l in lines)
            
            if currency not in balances:
                balances[currency] = 0
            balances[currency] += balance
        
        return balances
    
    def _get_upcoming_payments(self, days: int) -> list[dict]:
        """Obtiene pagos próximos (CxP)."""
        due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        return self._search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("invoice_date_due", "<=", due_date),
                ("company_id", "=", self.company_id),
            ],
            ["partner_id", "amount_residual", "invoice_date_due", "currency_id"],
            limit=500,
            order="invoice_date_due asc"
        )
    
    def _get_expected_collections(self, days: int) -> list[dict]:
        """Obtiene cobranza esperada (CxC por vencer)."""
        today = datetime.now().strftime("%Y-%m-%d")
        due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        return self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("invoice_date_due", ">=", today),
                ("invoice_date_due", "<=", due_date),
                ("company_id", "=", self.company_id),
            ],
            ["partner_id", "amount_residual", "invoice_date_due", "currency_id"],
            limit=500,
            order="invoice_date_due asc"
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: Posición de caja y flujo."""
        
        summary = self._context.summary if self._context else {}
        
        total_cash = summary.get("total_cash", 0)
        balances = summary.get("balances_by_currency", {})
        payments_7d = summary.get("payments_7d", 0)
        collections_7d = summary.get("collections_7d", 0)
        net_position = summary.get("net_position", 0)
        runway = summary.get("runway_days", 999)
        
        # Saldo por divisa
        self._add_finding(
            level=1,
            category="Saldos",
            title=f"Posición de caja: {self._format_currency(total_cash)}",
            description="Saldos en cuentas bancarias y caja",
            severity=ImpactLevel.INFO,
            affected_amount=total_cash,
            sample_data=[{"currency": k, "balance": v} for k, v in balances.items()],
        )
        
        # Alerta de runway
        if runway <= self.critical_runway_days:
            self._add_finding(
                level=1,
                category="Liquidez",
                title=f"🔴 CRÍTICO: Solo {runway:.0f} días de runway",
                description=f"Fondos insuficientes para operar más de {runway:.0f} días",
                severity=ImpactLevel.CRITICAL,
                impacts=[
                    self._blocks_agent(
                        "compras",
                        "Sin fondos para pagar",
                        "No se podrán pagar proveedores",
                        "Conseguir fondos urgente"
                    ),
                    self._increases_risk_for(
                        "ceo",
                        "Riesgo de iliquidez",
                        "Empresa en riesgo de no poder operar",
                        "Acción inmediata requerida"
                    ),
                ],
                solution="Acelerar cobranza y/o buscar financiamiento",
                coordinated_actions=[
                    "COBRANZA: Cobranza de emergencia",
                    "CEO: Evaluar línea de crédito",
                ]
            )
        elif runway <= self.warning_runway_days:
            self._add_finding(
                level=1,
                category="Liquidez",
                title=f"⚠️ Runway de {runway:.0f} días",
                description=f"Menos de {self.warning_runway_days} días de operación",
                severity=ImpactLevel.HIGH,
                impacts=[
                    self._delays_agent(
                        "compras",
                        "Fondos limitados",
                        "Puede ser necesario priorizar pagos",
                        "Monitorear de cerca"
                    )
                ],
                solution="Monitorear flujo y acelerar cobranza"
            )
        
        # Posición neta
        if net_position < 0:
            self._add_finding(
                level=1,
                category="Flujo",
                title=f"Posición neta negativa: {self._format_currency(net_position)}",
                description="Pagos próximos superan disponible + cobranza esperada",
                severity=ImpactLevel.HIGH,
                affected_amount=abs(net_position),
                impacts=[
                    self._delays_agent(
                        "compras",
                        "Faltante de fondos",
                        f"Faltarán ${abs(net_position):,.0f} para pagos",
                        "Priorizar o diferir pagos"
                    )
                ],
                solution="Priorizar pagos críticos y diferir los demás"
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por banco y categoría de gasto."""
        
        # Saldo por cuenta bancaria
        journals = self._search_read(
            "account.journal",
            [
                ("type", "in", ["bank", "cash"]),
                ("company_id", "=", self.company_id),
            ],
            ["name", "default_account_id", "currency_id"],
            limit=20
        )
        
        accounts_detail = []
        negative_accounts = []
        
        for journal in journals:
            account_id = self._safe_get_id(journal, "default_account_id")
            if not account_id:
                continue
            
            lines = self._search_read(
                "account.move.line",
                [
                    ("account_id", "=", account_id),
                    ("parent_state", "=", "posted"),
                    ("company_id", "=", self.company_id),
                ],
                ["balance"],
                limit=10000
            )
            
            balance = sum(l.get("balance", 0) for l in lines)
            currency = self._safe_get_name(journal, "currency_id") or self.default_currency
            
            account_info = {
                "name": journal.get("name"),
                "balance": balance,
                "currency": currency,
            }
            accounts_detail.append(account_info)
            
            if balance < -1000:  # Saldo negativo significativo
                negative_accounts.append(account_info)
        
        if negative_accounts:
            total_negative = sum(a["balance"] for a in negative_accounts)
            
            self._add_finding(
                level=2,
                category="Cuentas Bancarias",
                title=f"{len(negative_accounts)} cuentas con saldo negativo",
                description="Cuentas bancarias con saldo deudor",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(negative_accounts),
                affected_amount=abs(total_negative),
                sample_data=negative_accounts,
                impacts=[
                    self._create_impact(
                        "ceo",
                        ImpactType.INCREASES_COST,
                        "Sobregiros generan intereses",
                        f"${abs(total_negative):,.0f} en sobregiro",
                        "Fondear cuentas"
                    )
                ],
                solution="Fondear cuentas en negativo"
            )
        
        # Pagos por semana
        payments = self._get_upcoming_payments(30)
        by_week: dict[int, float] = {1: 0, 2: 0, 3: 0, 4: 0}
        
        today = datetime.now()
        for p in payments:
            due = p.get("invoice_date_due", "")
            if due:
                try:
                    due_date = datetime.strptime(str(due)[:10], "%Y-%m-%d")
                    days = (due_date - today).days
                    week = min(4, max(1, (days // 7) + 1))
                    by_week[week] += p.get("amount_residual", 0)
                except (ValueError, TypeError):
                    pass
        
        self._add_finding(
            level=2,
            category="Pagos Programados",
            title="Distribución de pagos próximos 4 semanas",
            description="CxP por semana de vencimiento",
            severity=ImpactLevel.INFO,
            sample_data=[{"week": k, "amount": v} for k, v in by_week.items()],
        )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Pagos específicos y conciliaciones."""
        
        # Pagos que vencen esta semana
        payments_week = self._get_upcoming_payments(7)
        
        if payments_week:
            total_week = sum(p.get("amount_residual", 0) for p in payments_week)
            
            # Agrupar por divisa
            by_currency: dict[str, float] = {}
            for p in payments_week:
                currency = self._safe_get_name(p, "currency_id") or self.default_currency
                by_currency[currency] = by_currency.get(currency, 0) + p.get("amount_residual", 0)
            
            self._add_finding(
                level=3,
                category="Pagos Urgentes",
                title=f"{len(payments_week)} pagos vencen esta semana",
                description=f"Total: {self._format_currency(total_week)}",
                severity=ImpactLevel.HIGH,
                affected_records=len(payments_week),
                affected_amount=total_week,
                sample_data=[
                    {
                        "vendor": self._safe_get_name(p, "partner_id"),
                        "amount": p.get("amount_residual"),
                        "due": p.get("invoice_date_due"),
                        "currency": self._safe_get_name(p, "currency_id") or self.default_currency,
                    }
                    for p in sorted(payments_week, key=lambda x: x.get("amount_residual", 0), reverse=True)[:10]
                ],
                solution="Programar pagos y verificar fondos"
            )
        
        # Conciliaciones pendientes
        if self._model_exists("account.bank.statement"):
            pending_statements = self._search_read(
                "account.bank.statement",
                [
                    ("is_complete", "=", False),
                    ("company_id", "=", self.company_id),
                ],
                ["name", "journal_id", "balance_end_real"],
                limit=50
            )
            
            if pending_statements:
                self._add_finding(
                    level=3,
                    category="Conciliación",
                    title=f"{len(pending_statements)} extractos bancarios sin cerrar",
                    description="Extractos pendientes de conciliar",
                    severity=ImpactLevel.MEDIUM,
                    affected_records=len(pending_statements),
                    sample_data=[
                        {
                            "statement": s.get("name"),
                            "journal": self._safe_get_name(s, "journal_id"),
                        }
                        for s in pending_statements[:10]
                    ],
                    impacts=[
                        self._create_impact(
                            "contabilidad",
                            ImpactType.REDUCES_QUALITY,
                            "Saldos no verificados",
                            "Los saldos bancarios pueden no ser precisos",
                            "Completar conciliación"
                        )
                    ],
                    solution="Completar conciliaciones bancarias"
                )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Asientos en borrador
        draft_entries = self._search_read(
            "account.move",
            [
                ("state", "=", "draft"),
                ("move_type", "=", "entry"),
                ("company_id", "=", self.company_id),
            ],
            ["name", "date", "amount_total"],
            limit=100
        )
        
        if draft_entries:
            total_draft = sum(e.get("amount_total", 0) for e in draft_entries)
            
            self._add_finding(
                level=4,
                category="Asientos",
                title=f"{len(draft_entries)} asientos contables en borrador",
                description="Asientos pendientes de publicar",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(draft_entries),
                affected_amount=total_draft,
                impacts=[
                    self._create_impact(
                        "contabilidad",
                        ImpactType.REDUCES_QUALITY,
                        "Saldos incompletos",
                        "Los saldos no reflejan todas las operaciones",
                        "Publicar asientos"
                    )
                ],
                solution="Revisar y publicar asientos pendientes"
            )
        
        # Pagos posiblemente duplicados
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        recent_payments = self._search_read(
            "account.payment",
            [
                ("state", "=", "posted"),
                ("date", ">=", week_ago),
                ("company_id", "=", self.company_id),
            ],
            ["partner_id", "amount", "date", "ref"],
            limit=500
        )
        
        # Buscar duplicados (mismo partner, monto, fecha)
        seen = set()
        duplicates = []
        
        for p in recent_payments:
            key = (
                self._safe_get_id(p, "partner_id"),
                round(p.get("amount", 0), 2),
                p.get("date", "")[:10],
            )
            
            if key in seen:
                duplicates.append(p)
            else:
                seen.add(key)
        
        if duplicates:
            total_dup = sum(d.get("amount", 0) for d in duplicates)
            
            self._add_finding(
                level=4,
                category="Posibles Duplicados",
                title=f"⚠️ {len(duplicates)} pagos posiblemente duplicados",
                description="Pagos con mismo partner, monto y fecha",
                severity=ImpactLevel.HIGH,
                affected_records=len(duplicates),
                affected_amount=total_dup,
                sample_data=[
                    {
                        "partner": self._safe_get_name(d, "partner_id"),
                        "amount": d.get("amount"),
                        "date": d.get("date"),
                        "ref": d.get("ref"),
                    }
                    for d in duplicates[:10]
                ],
                solution="Verificar si son pagos duplicados"
            )
        
        # CxP sin fecha de vencimiento
        no_due_date = self._search_read(
            "account.move",
            [
                ("move_type", "=", "in_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("invoice_date_due", "=", False),
                ("company_id", "=", self.company_id),
            ],
            ["name", "partner_id", "amount_residual"],
            limit=100
        )
        
        if no_due_date:
            total_no_due = sum(inv.get("amount_residual", 0) for inv in no_due_date)
            
            self._add_finding(
                level=4,
                category="Datos Faltantes",
                title=f"{len(no_due_date)} facturas de proveedor sin vencimiento",
                description="Facturas que no tienen fecha de pago definida",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(no_due_date),
                affected_amount=total_no_due,
                solution="Asignar fecha de vencimiento según términos"
            )
