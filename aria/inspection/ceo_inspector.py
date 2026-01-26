"""
Inspector Contextual del CEO.

Consolida información de todos los agentes en 4 niveles:
1. Vista general: KPIs consolidados, alertas críticas
2. Por categorías: Por área de negocio
3. Detalles: Top alertas, propuestas pendientes
4. Anomalías: Agentes sin reportar, métricas inconsistentes
"""

from datetime import datetime

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class CEOInspector(BaseContextInspector):
    """Inspector contextual para Dashboard Ejecutivo."""
    
    AGENT_NAME = "ceo"
    AREA_NAME = "Dashboard Ejecutivo"
    
    # CEO recibe información de TODOS los agentes
    UPSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="ventas",
            dependency_type="upstream",
            data_flow="KPIs de ventas",
            criticality=ImpactLevel.HIGH,
            description="Métricas comerciales"
        ),
        AgentDependency(
            agent_name="cobranza",
            dependency_type="upstream",
            data_flow="Estado de cartera",
            criticality=ImpactLevel.HIGH,
            description="Cartera y cobranza"
        ),
        AgentDependency(
            agent_name="finanzas",
            dependency_type="upstream",
            data_flow="Posición financiera",
            criticality=ImpactLevel.CRITICAL,
            description="Liquidez y flujo de caja"
        ),
        AgentDependency(
            agent_name="inventario",
            dependency_type="upstream",
            data_flow="Estado del inventario",
            criticality=ImpactLevel.MEDIUM,
            description="Valor y rotación de inventario"
        ),
        AgentDependency(
            agent_name="produccion",
            dependency_type="upstream",
            data_flow="Estado de producción",
            criticality=ImpactLevel.MEDIUM,
            description="OPs y capacidad"
        ),
        AgentDependency(
            agent_name="costos",
            dependency_type="upstream",
            data_flow="Rentabilidad",
            criticality=ImpactLevel.HIGH,
            description="Márgenes y costos"
        ),
    ]
    
    DOWNSTREAM_DEPENDENCIES = []  # CEO es el consumidor final
    
    def __init__(self) -> None:
        super().__init__()
        self._agent_summaries: dict[str, dict] = {}
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto ejecutivo consolidado."""
        
        # Intentar obtener resúmenes de otros inspectores
        self._collect_agent_summaries()
        
        # Calcular health score consolidado
        health_scores = []
        critical_areas = 0
        
        for agent, summary in self._agent_summaries.items():
            if "health_score" in summary:
                health_scores.append(summary["health_score"])
            if summary.get("status") == "critical":
                critical_areas += 1
        
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 50
        
        # Penalizar por áreas críticas
        consolidated_health = avg_health - (critical_areas * 10)
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=len(self._agent_summaries),
            total_value=0,
            health_score=max(0, min(100, consolidated_health)),
            status=self._get_status_from_health(max(0, min(100, consolidated_health))),
            summary={
                "agents_reporting": len(self._agent_summaries),
                "critical_areas": critical_areas,
                "average_health": avg_health,
            }
        )
    
    def _collect_agent_summaries(self) -> None:
        """Recolecta resúmenes de otros inspectores."""
        # En una implementación completa, esto ejecutaría los otros inspectores
        # Por ahora, recolectamos métricas básicas directamente
        
        # Ventas del mes
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        sales = self._search_read(
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
        
        total_sales = sum(s.get("amount_total_signed", 0) for s in sales)
        
        # CxC vencido
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = self._search_read(
            "account.move",
            [
                ("move_type", "=", "out_invoice"),
                ("payment_state", "!=", "paid"),
                ("state", "=", "posted"),
                ("invoice_date_due", "<", today),
                ("company_id", "=", self.company_id),
            ],
            ["amount_residual"],
            limit=5000
        )
        
        total_overdue = sum(o.get("amount_residual", 0) for o in overdue)
        
        self._agent_summaries = {
            "ventas": {
                "sales_month": total_sales,
                "health_score": 80,  # Simplificado
                "status": "ok",
            },
            "cobranza": {
                "overdue": total_overdue,
                "health_score": 100 - (total_overdue / total_sales * 100) if total_sales > 0 else 50,
                "status": "warning" if total_overdue > total_sales * 0.3 else "ok",
            },
        }
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: KPIs ejecutivos consolidados."""
        
        sales_data = self._agent_summaries.get("ventas", {})
        receivables_data = self._agent_summaries.get("cobranza", {})
        
        total_sales = sales_data.get("sales_month", 0)
        total_overdue = receivables_data.get("overdue", 0)
        
        # Resumen ejecutivo
        self._add_finding(
            level=1,
            category="Resumen",
            title=f"Ventas del mes: {self._format_currency(total_sales)}",
            description="Facturación del período actual",
            severity=ImpactLevel.INFO,
            affected_amount=total_sales,
        )
        
        if total_overdue > 0:
            overdue_pct = (total_overdue / total_sales * 100) if total_sales > 0 else 0
            
            severity = ImpactLevel.CRITICAL if overdue_pct > 30 else ImpactLevel.HIGH if overdue_pct > 15 else ImpactLevel.MEDIUM
            
            self._add_finding(
                level=1,
                category="Cartera",
                title=f"Cartera vencida: {self._format_currency(total_overdue)} ({overdue_pct:.0f}% de ventas)",
                description="Total de cuentas por cobrar vencidas",
                severity=severity,
                affected_amount=total_overdue,
            )
        
        # Alertas críticas de agentes
        critical_agents = [
            agent for agent, data in self._agent_summaries.items()
            if data.get("status") == "critical"
        ]
        
        if critical_agents:
            self._add_finding(
                level=1,
                category="Alertas",
                title=f"🔴 {len(critical_agents)} áreas en estado crítico",
                description=f"Áreas: {', '.join(critical_agents)}",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(critical_agents),
                solution="Atender áreas críticas con prioridad"
            )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por área de negocio."""
        
        # Status por área
        areas = []
        for agent, data in self._agent_summaries.items():
            areas.append({
                "area": agent,
                "health": data.get("health_score", 0),
                "status": data.get("status", "unknown"),
            })
        
        if areas:
            areas.sort(key=lambda x: x.get("health", 100))
            
            self._add_finding(
                level=2,
                category="Salud por Área",
                title="Estado de salud por área de negocio",
                description="Métricas consolidadas de cada área",
                severity=ImpactLevel.INFO,
                sample_data=areas,
            )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Propuestas y alertas pendientes."""
        
        # Aquí se podrían listar propuestas pendientes del ApprovalEngine
        # Por ahora es informativo
        
        self._add_finding(
            level=3,
            category="Acciones",
            title="Revisar propuestas pendientes de aprobación",
            description="Verificar sistema de aprobaciones",
            severity=ImpactLevel.INFO,
            solution="Usar 'aria proposal list' para ver pendientes"
        )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Inconsistencias entre agentes."""
        
        # Verificar si hay agentes que no reportaron
        expected_agents = ["ventas", "cobranza", "finanzas", "inventario", "produccion", "costos"]
        
        missing = [a for a in expected_agents if a not in self._agent_summaries]
        
        if missing:
            self._add_finding(
                level=4,
                category="Cobertura",
                title=f"⚠️ {len(missing)} áreas sin datos completos",
                description=f"Áreas: {', '.join(missing)}",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(missing),
                solution="Ejecutar inspección completa de todos los agentes"
            )
        
        # Verificar consistencia de métricas
        # Por ejemplo: ventas vs CxC debería tener relación
        sales = self._agent_summaries.get("ventas", {}).get("sales_month", 0)
        overdue = self._agent_summaries.get("cobranza", {}).get("overdue", 0)
        
        if sales > 0 and overdue > sales * 2:
            self._add_finding(
                level=4,
                category="Inconsistencia",
                title="⚠️ CxC vencida > 2x ventas del mes",
                description="La cartera vencida es anormalmente alta respecto a las ventas",
                severity=ImpactLevel.HIGH,
                solution="Verificar si los datos son correctos"
            )
