"""
Inspector Contextual de Cuentas por Cobrar.

Analiza la cartera de clientes en 4 niveles:
1. Vista general: Total CxC, antigüedad, % vencido
2. Por categorías: Por vendedor, zona, tipo de cliente
3. Detalles: Clientes sobre límite, patrones deteriorados
4. Anomalías: Facturas sin vencimiento, NC sin aplicar
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class ReceivablesInspector(BaseContextInspector):
    """Inspector contextual para Cuentas por Cobrar."""
    
    AGENT_NAME = "cobranza"
    AREA_NAME = "Cuentas por Cobrar"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="upstream",
            data_flow="Facturas generadas",
            criticality=ImpactLevel.HIGH,
            description="Ventas genera las facturas por cobrar"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="upstream",
            data_flow="Pagos recibidos",
            criticality=ImpactLevel.HIGH,
            description="Finanzas registra los pagos que reducen CxC"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="downstream",
            data_flow="Límites de crédito y bloqueos",
            criticality=ImpactLevel.CRITICAL,
            description="El estado de crédito afecta la capacidad de vender"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Flujo de caja proyectado",
            criticality=ImpactLevel.HIGH,
            description="La cobranza esperada afecta la proyección de flujo"
        ),
        AgentDependency(
            agent_name="ceo",
            dependency_type="downstream",
            data_flow="Indicadores de cartera",
            criticality=ImpactLevel.MEDIUM,
            description="Estado de cartera para reportes ejecutivos"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.aging_buckets = ["Not Due", "0-30", "31-60", "61-90", "91-120", "120+"]
        self.concentration_warning_pct = 30  # Alerta si un cliente > 30%
        self.critical_days_overdue = 90
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de CxC."""
        
        # Total CxC (facturas de cliente pendientes)
        invoices = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
            ],
            ["amount_residual", "invoice_date_due"],
            limit=5000
        )
        
        total_receivables = sum(inv.get("amount_residual", 0) for inv in invoices)
        total_invoices = len(invoices)
        
        # Calcular vencido
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = [inv for inv in invoices if (inv.get("invoice_date_due") or "") < today]
        total_overdue = sum(inv.get("amount_residual", 0) for inv in overdue)
        
        # Health score basado en % vencido
        overdue_pct = (total_overdue / total_receivables * 100) if total_receivables > 0 else 0
        health = max(0, 100 - overdue_pct)
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=total_invoices,
            total_value=total_receivables,
            health_score=health,
            status=self._get_status_from_health(health),
            summary={
                "total_receivables": total_receivables,
                "total_invoices": total_invoices,
                "total_overdue": total_overdue,
                "overdue_invoices": len(overdue),
                "overdue_pct": overdue_pct,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de cartera."""
        
        # Calcular aging
        invoices = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
            ],
            ["amount_residual", "invoice_date_due", "partner_id"],
            limit=5000
        )
        
        today = datetime.now()
        aging = {bucket: 0.0 for bucket in self.aging_buckets}
        
        for inv in invoices:
            due_date = inv.get("invoice_date_due")
            amount = inv.get("amount_residual", 0)
            
            if not due_date:
                aging["Not Due"] += amount
                continue
            
            try:
                due = datetime.strptime(str(due_date)[:10], "%Y-%m-%d")
                days = (today - due).days
            except (ValueError, TypeError):
                aging["Not Due"] += amount
                continue
            
            if days <= 0:
                aging["Not Due"] += amount
            elif days <= 30:
                aging["0-30"] += amount
            elif days <= 60:
                aging["31-60"] += amount
            elif days <= 90:
                aging["61-90"] += amount
            elif days <= 120:
                aging["91-120"] += amount
            else:
                aging["120+"] += amount
        
        total = sum(aging.values())
        
        # Hallazgo de aging general
        if total > 0:
            overdue_120_plus = aging["120+"]
            pct_120_plus = (overdue_120_plus / total) * 100
            
            if pct_120_plus > 10:
                self._add_finding(
                    level=1,
                    category="Antigüedad",
                    title=f"🔴 {pct_120_plus:.0f}% de cartera >120 días ({self._format_currency(overdue_120_plus)})",
                    description=f"Alta concentración de cartera antigua que puede requerir provisión",
                    severity=ImpactLevel.CRITICAL if pct_120_plus > 30 else ImpactLevel.HIGH,
                    affected_amount=overdue_120_plus,
                    sample_data=[{"bucket": k, "amount": v, "pct": (v/total)*100} for k, v in aging.items()],
                    impacts=[
                        self._increases_cost_for(
                            "finanzas",
                            "Provisión de incobrables",
                            f"Cartera >120 días requiere provisión",
                            "Intensificar gestión de cobro"
                        ),
                        self._increases_risk_for(
                            "ceo",
                            "Riesgo de incobrabilidad",
                            f"{pct_120_plus:.0f}% de la cartera en riesgo alto",
                            "Revisar política de crédito"
                        ),
                    ],
                    solution="Intensificar gestión de cobro y evaluar provisión",
                    coordinated_actions=[
                        "COBRANZA: Escalar a gerencia clientes >120 días",
                        "FINANZAS: Evaluar provisión de incobrables",
                    ]
                )
        
        # Concentración de cartera (top 5 clientes)
        by_partner: dict[int, dict] = {}
        for inv in invoices:
            partner_id = self._safe_get_id(inv, "partner_id")
            partner_name = self._safe_get_name(inv, "partner_id")
            
            if partner_id not in by_partner:
                by_partner[partner_id] = {"name": partner_name, "amount": 0}
            by_partner[partner_id]["amount"] += inv.get("amount_residual", 0)
        
        sorted_partners = sorted(by_partner.values(), key=lambda x: x["amount"], reverse=True)
        
        if sorted_partners and total > 0:
            top5_amount = sum(p["amount"] for p in sorted_partners[:5])
            top5_pct = (top5_amount / total) * 100
            
            if top5_pct > 50:
                self._add_finding(
                    level=1,
                    category="Concentración",
                    title=f"Top 5 clientes = {top5_pct:.0f}% de la cartera",
                    description="Alta concentración de cartera en pocos clientes",
                    severity=ImpactLevel.HIGH if top5_pct > 70 else ImpactLevel.MEDIUM,
                    affected_amount=top5_amount,
                    sample_data=[
                        {"customer": p["name"], "amount": p["amount"], "pct": (p["amount"]/total)*100}
                        for p in sorted_partners[:5]
                    ],
                    impacts=[
                        self._increases_risk_for(
                            "ceo",
                            "Riesgo de concentración",
                            f"Pérdida de un cliente top afectaría {top5_pct/5:.0f}% promedio",
                            "Diversificar cartera"
                        )
                    ],
                    solution="Diversificar base de clientes"
                )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Análisis por vendedor y tipo."""
        
        # CxC por vendedor
        invoices = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
            ],
            ["amount_residual", "invoice_date_due", "invoice_user_id"],
            limit=5000
        )
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        by_salesperson: dict[str, dict] = {}
        for inv in invoices:
            salesperson = self._safe_get_name(inv, "invoice_user_id") or "Sin asignar"
            due_date = inv.get("invoice_date_due", "")
            amount = inv.get("amount_residual", 0)
            is_overdue = due_date and due_date < today
            
            if salesperson not in by_salesperson:
                by_salesperson[salesperson] = {"total": 0, "overdue": 0, "count": 0}
            
            by_salesperson[salesperson]["total"] += amount
            by_salesperson[salesperson]["count"] += 1
            if is_overdue:
                by_salesperson[salesperson]["overdue"] += amount
        
        # Vendedores con alta cartera vencida
        for salesperson, data in by_salesperson.items():
            if data["total"] > 0:
                overdue_pct = (data["overdue"] / data["total"]) * 100
                
                if overdue_pct > 50 and data["overdue"] > 100000:  # Umbral mínimo
                    self._add_finding(
                        level=2,
                        category="Por Vendedor",
                        title=f"Vendedor {salesperson}: {overdue_pct:.0f}% vencido",
                        description=f"Alta cartera vencida para este vendedor",
                        severity=ImpactLevel.HIGH,
                        affected_amount=data["overdue"],
                        affected_records=data["count"],
                        impacts=[
                            self._delays_agent(
                                "ventas",
                                "Clientes con crédito bloqueado",
                                f"Clientes de {salesperson} podrían tener límite excedido",
                                "Cobrar antes de vender más"
                            )
                        ],
                        solution=f"Revisar gestión de cobro de {salesperson}"
                    )
        
        # Facturas sin vendedor asignado
        no_salesperson = by_salesperson.get("Sin asignar", {"total": 0, "count": 0})
        if no_salesperson["count"] > 10:
            self._add_finding(
                level=2,
                category="Asignación",
                title=f"{no_salesperson['count']} facturas sin vendedor asignado",
                description="Facturas sin responsable de cobro claro",
                severity=ImpactLevel.MEDIUM,
                affected_records=no_salesperson["count"],
                affected_amount=no_salesperson["total"],
                solution="Asignar vendedor responsable a facturas"
            )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Clientes y facturas específicas."""
        
        # Clientes sobre límite de crédito
        partners = self._search_read(
            "res.partner",
            [
                ("customer_rank", ">", 0),
                ("credit_limit", ">", 0),
                ("active", "=", True),
            ],
            ["name", "credit_limit", "credit"],
            limit=500
        )
        
        over_limit = [
            p for p in partners
            if p.get("credit", 0) > p.get("credit_limit", 0)
        ]
        
        if over_limit:
            total_excess = sum(
                p.get("credit", 0) - p.get("credit_limit", 0)
                for p in over_limit
            )
            
            self._add_finding(
                level=3,
                category="Límite de Crédito",
                title=f"{len(over_limit)} clientes sobre límite de crédito",
                description=f"Clientes que han excedido su límite autorizado",
                severity=ImpactLevel.HIGH,
                affected_records=len(over_limit),
                affected_amount=total_excess,
                sample_data=[
                    {
                        "customer": p.get("name"),
                        "credit": p.get("credit"),
                        "limit": p.get("credit_limit"),
                        "excess": p.get("credit", 0) - p.get("credit_limit", 0),
                    }
                    for p in sorted(over_limit, key=lambda x: x.get("credit", 0) - x.get("credit_limit", 0), reverse=True)[:10]
                ],
                impacts=[
                    self._blocks_agent(
                        "ventas",
                        "Crédito excedido",
                        f"{len(over_limit)} clientes deberían estar bloqueados",
                        "Cobrar o aumentar límite"
                    )
                ],
                solution="Bloquear ventas o autorizar excepción",
                coordinated_actions=[
                    "VENTAS: No procesar pedidos de clientes sobre límite",
                    "COBRANZA: Gestión intensiva",
                ]
            )
        
        # Facturas grandes vencidas (>60 días)
        sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        
        large_overdue = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
                ("invoice_date_due", "<", sixty_days_ago),
                ("amount_residual", ">", 50000),  # Facturas grandes
            ],
            ["name", "partner_id", "amount_residual", "invoice_date_due"],
            limit=50,
            order="amount_residual desc"
        )
        
        if large_overdue:
            total_large = sum(inv.get("amount_residual", 0) for inv in large_overdue)
            
            self._add_finding(
                level=3,
                category="Facturas Grandes",
                title=f"{len(large_overdue)} facturas grandes vencidas >60 días",
                description=f"Facturas >$50K con más de 60 días de vencimiento",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(large_overdue),
                affected_amount=total_large,
                sample_data=[
                    {
                        "invoice": inv.get("name"),
                        "customer": self._safe_get_name(inv, "partner_id"),
                        "amount": inv.get("amount_residual"),
                        "due_date": inv.get("invoice_date_due"),
                    }
                    for inv in large_overdue[:10]
                ],
                impacts=[
                    self._increases_risk_for(
                        "finanzas",
                        "Impacto significativo en flujo",
                        f"${total_large:,.0f} en facturas grandes sin cobrar",
                        "Escalar a dirección"
                    )
                ],
                solution="Escalar a gerencia para gestión directa",
                coordinated_actions=[
                    "CEO: Llamada ejecutiva a clientes",
                    "FINANZAS: Ajustar proyección de flujo",
                ]
            )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Facturas sin fecha de vencimiento
        no_due_date = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
                ("invoice_date_due", "=", False),
            ],
            ["name", "partner_id", "amount_residual", "invoice_date"],
            limit=100
        )
        
        if no_due_date:
            total_no_due = sum(inv.get("amount_residual", 0) for inv in no_due_date)
            
            self._add_finding(
                level=4,
                category="Datos Faltantes",
                title=f"{len(no_due_date)} facturas sin fecha de vencimiento",
                description="Facturas que no tienen fecha de vencimiento configurada",
                severity=ImpactLevel.HIGH,
                affected_records=len(no_due_date),
                affected_amount=total_no_due,
                sample_data=[
                    {
                        "invoice": inv.get("name"),
                        "customer": self._safe_get_name(inv, "partner_id"),
                        "amount": inv.get("amount_residual"),
                    }
                    for inv in no_due_date[:10]
                ],
                impacts=[
                    self._create_impact(
                        "cobranza",
                        ImpactType.REDUCES_QUALITY,
                        "Aging incorrecto",
                        "Estas facturas no aparecen correctamente en aging",
                        "Asignar fecha de vencimiento"
                    )
                ],
                solution="Asignar fecha de vencimiento según términos de pago"
            )
        
        # Notas de crédito sin aplicar
        credit_notes = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_refund"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
            ],
            ["name", "partner_id", "amount_residual", "invoice_date"],
            limit=100
        )
        
        if credit_notes:
            total_cn = sum(cn.get("amount_residual", 0) for cn in credit_notes)
            
            self._add_finding(
                level=4,
                category="Notas de Crédito",
                title=f"{len(credit_notes)} notas de crédito sin aplicar",
                description="NC emitidas pero no aplicadas a facturas",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(credit_notes),
                affected_amount=total_cn,
                sample_data=[
                    {
                        "credit_note": cn.get("name"),
                        "customer": self._safe_get_name(cn, "partner_id"),
                        "amount": cn.get("amount_residual"),
                    }
                    for cn in credit_notes[:10]
                ],
                solution="Aplicar NC a facturas pendientes o reembolsar"
            )
        
        # Saldos a favor de clientes (anticipos no aplicados)
        partners_with_credit = self._search_read(
            "res.partner",
            [
                ("customer_rank", ">", 0),
                ("credit", "<", -1000),  # Saldo negativo = a favor del cliente
                ("active", "=", True),
            ],
            ["name", "credit"],
            limit=100
        )
        
        if partners_with_credit:
            total_credit = sum(abs(p.get("credit", 0)) for p in partners_with_credit)
            
            self._add_finding(
                level=4,
                category="Anticipos",
                title=f"{len(partners_with_credit)} clientes con saldo a favor",
                description="Clientes con anticipos o pagos no aplicados",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(partners_with_credit),
                affected_amount=total_credit,
                sample_data=[
                    {
                        "customer": p.get("name"),
                        "credit_balance": abs(p.get("credit", 0)),
                    }
                    for p in sorted(partners_with_credit, key=lambda x: x.get("credit", 0))[:10]
                ],
                solution="Aplicar anticipos a facturas o comunicar al cliente"
            )
        
        # Facturas muy antiguas sin gestión (>180 días)
        very_old = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        
        stale_invoices = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("company_id", "=", self.company_id),
                ("invoice_date_due", "<", very_old),
            ],
            ["name", "partner_id", "amount_residual", "invoice_date_due"],
            limit=100,
            order="invoice_date_due asc"
        )
        
        if stale_invoices:
            total_stale = sum(inv.get("amount_residual", 0) for inv in stale_invoices)
            
            self._add_finding(
                level=4,
                category="Cartera Abandonada",
                title=f"{len(stale_invoices)} facturas >180 días sin cobrar",
                description="Facturas muy antiguas que probablemente sean incobrables",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(stale_invoices),
                affected_amount=total_stale,
                sample_data=[
                    {
                        "invoice": inv.get("name"),
                        "customer": self._safe_get_name(inv, "partner_id"),
                        "amount": inv.get("amount_residual"),
                        "due_date": inv.get("invoice_date_due"),
                        "days_overdue": self._days_between(inv.get("invoice_date_due")),
                    }
                    for inv in stale_invoices[:10]
                ],
                impacts=[
                    self._increases_cost_for(
                        "finanzas",
                        "Provisión de incobrables",
                        f"${total_stale:,.0f} probablemente incobrable",
                        "Castigar cartera"
                    )
                ],
                solution="Evaluar castigo de cartera o último intento de cobro",
                coordinated_actions=[
                    "LEGAL: Evaluar acciones legales",
                    "FINANZAS: Registrar provisión de incobrables",
                ]
            )
