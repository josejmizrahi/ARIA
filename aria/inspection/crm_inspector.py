"""
Inspector Contextual de CRM.

Analiza pipeline comercial en 4 niveles:
1. Vista general: Pipeline, conversión, valor esperado
2. Por categorías: Por vendedor, fuente, etapa
3. Detalles: Oportunidades estancadas, alto valor
4. Anomalías: Sin vendedor, sin fecha cierre
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class CRMInspector(BaseContextInspector):
    """Inspector contextual para Pipeline Comercial."""
    
    AGENT_NAME = "crm"
    AREA_NAME = "Pipeline Comercial"
    
    UPSTREAM_DEPENDENCIES = []  # CRM genera leads
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="downstream",
            data_flow="Oportunidades a convertir",
            criticality=ImpactLevel.HIGH,
            description="Oportunidades ganadas se convierten en pedidos"
        ),
        AgentDependency(
            agent_name="ceo",
            dependency_type="downstream",
            data_flow="Pipeline y forecast",
            criticality=ImpactLevel.MEDIUM,
            description="Valor esperado para proyecciones"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.stagnant_days = 30
        self.high_value_threshold = 500000
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto general de CRM."""
        
        if not self._model_exists("crm.lead"):
            return AreaContext(
                area_name=self.AREA_NAME,
                status="unavailable",
                summary={"error": "Módulo CRM no instalado"}
            )
        
        # Pipeline activo
        opportunities = self._search_read(
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)],
            ["expected_revenue", "probability"],
            limit=5000
        )
        
        total_pipeline = sum(o.get("expected_revenue", 0) for o in opportunities)
        weighted_pipeline = sum(
            o.get("expected_revenue", 0) * (o.get("probability", 0) / 100)
            for o in opportunities
        )
        
        # Oportunidades estancadas
        stagnant_date = (datetime.now() - timedelta(days=self.stagnant_days)).strftime("%Y-%m-%d")
        stagnant = self._search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("write_date", "<", stagnant_date),
            ]
        )
        
        health = 100 - (stagnant / len(opportunities) * 100) if opportunities else 100
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=len(opportunities),
            total_value=total_pipeline,
            health_score=max(0, min(100, health)),
            status=self._get_status_from_health(max(0, min(100, health))),
            summary={
                "opportunities": len(opportunities),
                "total_pipeline": total_pipeline,
                "weighted_pipeline": weighted_pipeline,
                "stagnant_count": stagnant,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs generales de CRM."""
        
        if not self._model_exists("crm.lead"):
            self._add_finding(
                level=1,
                category="Sistema",
                title="Módulo CRM no disponible",
                description="El módulo CRM no está instalado",
                severity=ImpactLevel.INFO,
            )
            return
        
        summary = self._context.summary if self._context else {}
        
        total_pipeline = summary.get("total_pipeline", 0)
        weighted = summary.get("weighted_pipeline", 0)
        opps = summary.get("opportunities", 0)
        
        # Pipeline total
        self._add_finding(
            level=1,
            category="Pipeline",
            title=f"Pipeline: {self._format_currency(total_pipeline)}",
            description=f"{opps} oportunidades activas, ponderado: {self._format_currency(weighted)}",
            severity=ImpactLevel.INFO,
            affected_records=opps,
            affected_amount=total_pipeline,
        )
        
        # Conversión del mes
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        won = self._search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("stage_id.is_won", "=", True),
                ("date_closed", ">=", first_day),
            ]
        )
        
        lost = self._search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("probability", "=", 0),
                ("active", "=", False),
                ("write_date", ">=", first_day),
            ]
        )
        
        total_closed = won + lost
        win_rate = (won / total_closed * 100) if total_closed > 0 else 0
        
        if total_closed > 0:
            severity = ImpactLevel.LOW if win_rate >= 30 else ImpactLevel.MEDIUM if win_rate >= 20 else ImpactLevel.HIGH
            
            self._add_finding(
                level=1,
                category="Conversión",
                title=f"Tasa de conversión: {win_rate:.0f}% (Ganadas: {won}, Perdidas: {lost})",
                description="Conversión de oportunidades este mes",
                severity=severity,
                impacts=[
                    self._increases_risk_for(
                        "ventas",
                        "Baja conversión",
                        f"Solo {win_rate:.0f}% de oportunidades se ganan",
                        "Revisar proceso comercial"
                    )
                ] if win_rate < 20 else [],
                solution="Analizar causas de pérdida" if win_rate < 20 else ""
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por vendedor y etapa."""
        
        if not self._model_exists("crm.lead"):
            return
        
        opportunities = self._search_read(
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)],
            ["user_id", "stage_id", "expected_revenue"],
            limit=2000
        )
        
        # Por vendedor
        by_salesperson: dict[str, dict] = {}
        for opp in opportunities:
            salesperson = self._safe_get_name(opp, "user_id") or "Sin asignar"
            
            if salesperson not in by_salesperson:
                by_salesperson[salesperson] = {"count": 0, "value": 0}
            
            by_salesperson[salesperson]["count"] += 1
            by_salesperson[salesperson]["value"] += opp.get("expected_revenue", 0)
        
        if by_salesperson:
            sorted_sales = sorted(by_salesperson.items(), key=lambda x: x[1]["value"], reverse=True)
            
            self._add_finding(
                level=2,
                category="Por Vendedor",
                title="Pipeline por vendedor",
                description="Distribución de oportunidades",
                severity=ImpactLevel.INFO,
                sample_data=[
                    {"salesperson": s, "opportunities": d["count"], "value": d["value"]}
                    for s, d in sorted_sales[:10]
                ],
            )
        
        # Vendedores sin pipeline
        no_pipeline = by_salesperson.get("Sin asignar", {"count": 0})
        if no_pipeline["count"] > 5:
            self._add_finding(
                level=2,
                category="Sin Asignar",
                title=f"{no_pipeline['count']} oportunidades sin vendedor",
                description="Oportunidades que no tienen responsable",
                severity=ImpactLevel.HIGH,
                affected_records=no_pipeline["count"],
                solution="Asignar vendedor a oportunidades"
            )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Oportunidades específicas."""
        
        if not self._model_exists("crm.lead"):
            return
        
        # Oportunidades estancadas
        stagnant_date = (datetime.now() - timedelta(days=self.stagnant_days)).strftime("%Y-%m-%d")
        
        stagnant = self._search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("write_date", "<", stagnant_date),
            ],
            ["name", "partner_id", "expected_revenue", "user_id", "stage_id", "write_date"],
            limit=100,
            order="expected_revenue desc"
        )
        
        if stagnant:
            total_stagnant = sum(s.get("expected_revenue", 0) for s in stagnant)
            
            self._add_finding(
                level=3,
                category="Estancadas",
                title=f"⚠️ {len(stagnant)} oportunidades sin actividad > {self.stagnant_days} días",
                description=f"Valor en riesgo: {self._format_currency(total_stagnant)}",
                severity=ImpactLevel.HIGH,
                affected_records=len(stagnant),
                affected_amount=total_stagnant,
                sample_data=[
                    {
                        "opportunity": s.get("name"),
                        "customer": self._safe_get_name(s, "partner_id"),
                        "value": s.get("expected_revenue"),
                        "salesperson": self._safe_get_name(s, "user_id"),
                        "stage": self._safe_get_name(s, "stage_id"),
                        "last_activity": s.get("write_date")[:10] if s.get("write_date") else "",
                    }
                    for s in stagnant[:10]
                ],
                impacts=[
                    self._increases_risk_for(
                        "ventas",
                        "Pipeline en riesgo",
                        f"{self._format_currency(total_stagnant)} sin movimiento",
                        "Dar seguimiento o cerrar"
                    )
                ],
                solution="Contactar clientes o marcar como perdidas",
            )
        
        # Oportunidades de alto valor
        high_value = self._search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("expected_revenue", ">=", self.high_value_threshold),
            ],
            ["name", "partner_id", "expected_revenue", "probability", "date_deadline", "user_id"],
            limit=50,
            order="expected_revenue desc"
        )
        
        if high_value:
            total_high = sum(h.get("expected_revenue", 0) for h in high_value)
            
            self._add_finding(
                level=3,
                category="Alto Valor",
                title=f"📊 {len(high_value)} oportunidades de alto valor",
                description=f"Oportunidades >= {self._format_currency(self.high_value_threshold)}",
                severity=ImpactLevel.INFO,
                affected_records=len(high_value),
                affected_amount=total_high,
                sample_data=[
                    {
                        "opportunity": h.get("name"),
                        "customer": self._safe_get_name(h, "partner_id"),
                        "value": h.get("expected_revenue"),
                        "probability": h.get("probability"),
                        "deadline": h.get("date_deadline"),
                        "salesperson": self._safe_get_name(h, "user_id"),
                    }
                    for h in high_value[:10]
                ],
            )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        if not self._model_exists("crm.lead"):
            return
        
        # Sin fecha de cierre esperada
        no_deadline = self._search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("date_deadline", "=", False),
            ],
            ["name", "partner_id", "expected_revenue"],
            limit=100
        )
        
        if no_deadline:
            total_no_date = sum(n.get("expected_revenue", 0) for n in no_deadline)
            
            self._add_finding(
                level=4,
                category="Sin Fecha",
                title=f"{len(no_deadline)} oportunidades sin fecha de cierre",
                description="No se puede proyectar cuándo se cerrarán",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(no_deadline),
                affected_amount=total_no_date,
                solution="Asignar fecha de cierre esperada"
            )
        
        # Probabilidad 100% pero no cerrada
        certain_but_open = self._search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("probability", "=", 100),
                ("stage_id.is_won", "=", False),
            ],
            ["name", "partner_id", "expected_revenue"],
            limit=50
        )
        
        if certain_but_open:
            self._add_finding(
                level=4,
                category="Inconsistencia",
                title=f"⚠️ {len(certain_but_open)} oportunidades 100% que no están ganadas",
                description="Probabilidad 100% pero no en etapa ganada",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(certain_but_open),
                sample_data=[
                    {
                        "opportunity": c.get("name"),
                        "customer": self._safe_get_name(c, "partner_id"),
                        "value": c.get("expected_revenue"),
                    }
                    for c in certain_but_open[:10]
                ],
                solution="Mover a etapa ganada o ajustar probabilidad"
            )
        
        # Sin vendedor
        no_salesperson = self._search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("user_id", "=", False),
            ]
        )
        
        if no_salesperson > 0:
            self._add_finding(
                level=4,
                category="Sin Asignar",
                title=f"{no_salesperson} oportunidades sin vendedor asignado",
                description="Oportunidades que nadie está gestionando",
                severity=ImpactLevel.HIGH,
                affected_records=no_salesperson,
                solution="Asignar vendedor responsable"
            )
