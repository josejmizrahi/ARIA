"""
Inspector Contextual de Contabilidad.

Analiza contabilidad y cierres en 4 niveles:
1. Vista general: Asientos, estado de cierre, balance
2. Por categorías: Por diario, cuenta, período
3. Detalles: Borradores antiguos, cuentas puente
4. Anomalías: Descuadres, períodos sin cerrar
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class AccountingInspector(BaseContextInspector):
    """Inspector contextual para Contabilidad y Cierres."""
    
    AGENT_NAME = "contabilidad"
    AREA_NAME = "Contabilidad y Cierres"
    
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="upstream",
            data_flow="Asientos de ventas",
            criticality=ImpactLevel.HIGH,
            description="Facturas de venta generan asientos"
        ),
        AgentDependency(
            agent_name="compras",
            dependency_type="upstream",
            data_flow="Asientos de compras",
            criticality=ImpactLevel.HIGH,
            description="Facturas de compra generan asientos"
        ),
        AgentDependency(
            agent_name="inventario",
            dependency_type="upstream",
            data_flow="Valorización",
            criticality=ImpactLevel.HIGH,
            description="Movimientos de inventario generan asientos"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ceo",
            dependency_type="downstream",
            data_flow="Estados financieros",
            criticality=ImpactLevel.CRITICAL,
            description="Estados financieros para toma de decisiones"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="downstream",
            data_flow="Saldos correctos",
            criticality=ImpactLevel.HIGH,
            description="Saldos de cuentas para análisis"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.draft_warning_days = 7
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de contabilidad."""
        
        # Asientos del mes
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        entries_month = self._search_count(
            "account.move",
            [
                ("move_type", "=", "entry"),
                ("date", ">=", first_day),
            ]
        )
        
        # Asientos en borrador
        draft_entries = self._search_count(
            "account.move",
            [("state", "=", "draft")]
        )
        
        health = 100 - (draft_entries * 2)
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=entries_month,
            total_value=0,
            health_score=max(0, min(100, health)),
            status=self._get_status_from_health(max(0, min(100, health))),
            summary={
                "entries_this_month": entries_month,
                "draft_entries": draft_entries,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de contabilidad."""
        
        summary = self._context.summary if self._context else {}
        
        entries_month = summary.get("entries_this_month", 0)
        draft = summary.get("draft_entries", 0)
        
        # Asientos del mes
        self._add_finding(
            level=1,
            category="Asientos",
            title=f"Asientos del mes: {entries_month}",
            description="Total de asientos contables registrados",
            severity=ImpactLevel.INFO,
            affected_records=entries_month,
        )
        
        # Borradores pendientes
        if draft > 10:
            self._add_finding(
                level=1,
                category="Pendientes",
                title=f"⚠️ {draft} asientos en borrador",
                description="Asientos pendientes de publicar",
                severity=ImpactLevel.HIGH if draft > 50 else ImpactLevel.MEDIUM,
                affected_records=draft,
                impacts=[
                    self._create_impact(
                        "ceo",
                        ImpactType.REDUCES_QUALITY,
                        "Información financiera incompleta",
                        f"{draft} asientos no reflejados en reportes",
                        "Publicar asientos"
                    )
                ],
                solution="Revisar y publicar asientos pendientes"
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por diario y cuenta."""
        
        # Asientos por diario
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        entries = self._search_read(
            "account.move",
            [
                ("state", "=", "posted"),
                ("date", ">=", first_day),
            ],
            ["journal_id"],
            limit=5000
        )
        
        by_journal: dict[str, int] = {}
        for e in entries:
            journal = self._safe_get_name(e, "journal_id")
            by_journal[journal] = by_journal.get(journal, 0) + 1
        
        if by_journal:
            sorted_journals = sorted(by_journal.items(), key=lambda x: x[1], reverse=True)
            
            self._add_finding(
                level=2,
                category="Por Diario",
                title="Distribución de asientos por diario",
                description="Actividad por diario contable",
                severity=ImpactLevel.INFO,
                sample_data=[{"journal": j, "entries": c} for j, c in sorted_journals[:10]],
            )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Asientos específicos."""
        
        # Borradores antiguos
        old_date = (datetime.now() - timedelta(days=self.draft_warning_days)).strftime("%Y-%m-%d")
        
        old_drafts = self._search_read(
            "account.move",
            [
                ("state", "=", "draft"),
                ("date", "<", old_date),
            ],
            ["name", "date", "amount_total", "journal_id", "ref"],
            limit=100,
            order="date asc"
        )
        
        if old_drafts:
            total_draft = sum(d.get("amount_total", 0) for d in old_drafts)
            
            self._add_finding(
                level=3,
                category="Borradores Antiguos",
                title=f"{len(old_drafts)} borradores > {self.draft_warning_days} días",
                description="Asientos en borrador por mucho tiempo",
                severity=ImpactLevel.HIGH,
                affected_records=len(old_drafts),
                affected_amount=total_draft,
                sample_data=[
                    {
                        "entry": d.get("name"),
                        "date": d.get("date"),
                        "amount": d.get("amount_total"),
                        "journal": self._safe_get_name(d, "journal_id"),
                        "ref": d.get("ref"),
                    }
                    for d in old_drafts[:10]
                ],
                impacts=[
                    self._create_impact(
                        "finanzas",
                        ImpactType.REDUCES_QUALITY,
                        "Saldos incompletos",
                        "Los saldos no reflejan operaciones pendientes",
                        "Publicar o cancelar"
                    )
                ],
                solution="Publicar o cancelar borradores antiguos"
            )
        
        # Cuentas puente con saldo (suelen ser errores)
        # Buscar cuentas tipo "transitoria" o "puente" con saldo
        transit_accounts = self._search_read(
            "account.account",
            [
                ("name", "ilike", "transit%"),
            ],
            ["id", "name", "code"],
            limit=20
        )
        
        if transit_accounts:
            for acc in transit_accounts:
                # Verificar si tiene saldo
                lines = self._search_read(
                    "account.move.line",
                    [
                        ("account_id", "=", acc["id"]),
                        ("parent_state", "=", "posted"),
                    ],
                    ["balance"],
                    limit=1000
                )
                
                balance = sum(l.get("balance", 0) for l in lines)
                
                if abs(balance) > 1000:  # Saldo significativo
                    self._add_finding(
                        level=3,
                        category="Cuentas Puente",
                        title=f"Cuenta puente con saldo: {acc.get('name')}",
                        description=f"Saldo: {self._format_currency(balance)}",
                        severity=ImpactLevel.MEDIUM,
                        affected_amount=abs(balance),
                        solution="Reclasificar saldo de cuenta puente"
                    )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Asientos con diferencia (descuadrados)
        # En Odoo, esto no debería pasar, pero verificamos
        entries = self._search_read(
            "account.move",
            [("state", "=", "posted")],
            ["id", "name"],
            limit=100
        )
        
        unbalanced = []
        for entry in entries[:50]:  # Verificar muestra
            lines = self._search_read(
                "account.move.line",
                [("move_id", "=", entry["id"])],
                ["debit", "credit"],
                limit=100
            )
            
            total_debit = sum(l.get("debit", 0) for l in lines)
            total_credit = sum(l.get("credit", 0) for l in lines)
            
            if abs(total_debit - total_credit) > 0.01:
                unbalanced.append({
                    "entry": entry.get("name"),
                    "debit": total_debit,
                    "credit": total_credit,
                    "diff": total_debit - total_credit,
                })
        
        if unbalanced:
            self._add_finding(
                level=4,
                category="Error de Datos",
                title=f"🔴 {len(unbalanced)} asientos descuadrados",
                description="Asientos con diferencia entre débito y crédito",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(unbalanced),
                sample_data=unbalanced[:10],
                impacts=[
                    self._create_impact(
                        "ceo",
                        ImpactType.REDUCES_QUALITY,
                        "Estados financieros incorrectos",
                        "Asientos descuadrados invalidan reportes",
                        "Corregir urgentemente"
                    )
                ],
                solution="Corregir asientos descuadrados"
            )
        
        # Facturas sin contabilizar
        unposted_invoices = self._search_count(
            "account.move",
            [
                ("move_type", "in", ["out_invoice", "in_invoice"]),
                ("state", "=", "draft"),
            ]
        )
        
        if unposted_invoices > 20:
            self._add_finding(
                level=4,
                category="Facturas Pendientes",
                title=f"{unposted_invoices} facturas sin publicar",
                description="Facturas en borrador que no afectan contabilidad",
                severity=ImpactLevel.MEDIUM,
                affected_records=unposted_invoices,
                impacts=[
                    self._delays_agent(
                        "cobranza",
                        "CxC no reflejada",
                        "Facturas de venta sin registrar",
                        "Publicar facturas"
                    )
                ],
                solution="Revisar y publicar facturas pendientes"
            )
        
        # Cuentas con signo incorrecto (activos negativos, pasivos positivos incorrectos)
        # Esta verificación es compleja y depende del plan de cuentas
        # Por ahora, verificamos cuentas de banco con saldo muy negativo
        bank_accounts = self._search_read(
            "account.account",
            [("account_type", "=", "asset_cash")],
            ["id", "name"],
            limit=20
        )
        
        for acc in bank_accounts:
            lines = self._search_read(
                "account.move.line",
                [
                    ("account_id", "=", acc["id"]),
                    ("parent_state", "=", "posted"),
                ],
                ["balance"],
                limit=10000
            )
            
            balance = sum(l.get("balance", 0) for l in lines)
            
            if balance < -1000000:  # Más de 1M negativo es sospechoso
                self._add_finding(
                    level=4,
                    category="Saldo Anormal",
                    title=f"⚠️ Cuenta de banco muy negativa: {acc.get('name')}",
                    description=f"Saldo: {self._format_currency(balance)}",
                    severity=ImpactLevel.HIGH,
                    affected_amount=abs(balance),
                    solution="Verificar si es correcto o hay error"
                )
