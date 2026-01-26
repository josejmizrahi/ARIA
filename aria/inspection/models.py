"""
Modelos de datos para el sistema de inspección contextual.

Define las estructuras para hallazgos, impactos entre agentes,
dependencias y contexto de área.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ImpactLevel(Enum):
    """Nivel de severidad de un hallazgo o impacto."""
    
    CRITICAL = "critical"  # Bloquea operaciones - acción inmediata
    HIGH = "high"          # Acción requerida en 24 horas
    MEDIUM = "medium"      # Acción requerida esta semana
    LOW = "low"            # Cuando se pueda
    INFO = "info"          # Solo informativo


class ImpactType(Enum):
    """Tipo de impacto que un hallazgo tiene en otro agente."""
    
    BLOCKS = "blocks"                    # No puede trabajar
    DELAYS = "delays"                    # Se retrasa
    REDUCES_QUALITY = "reduces_quality"  # Menor calidad de datos/proceso
    INCREASES_COST = "increases_cost"    # Incrementa costos
    INCREASES_RISK = "increases_risk"    # Incrementa riesgo
    INFORMATIONAL = "informational"      # Solo para conocimiento


@dataclass
class AgentDependency:
    """
    Define una dependencia entre agentes.
    
    Ejemplo: Inventario depende de Compras (upstream) para recepciones,
    y Ventas depende de Inventario (downstream) para disponibilidad.
    """
    
    agent_name: str
    dependency_type: str  # "upstream" o "downstream"
    data_flow: str        # Descripción del flujo de datos
    criticality: ImpactLevel
    description: str


@dataclass
class AgentImpact:
    """
    Describe el impacto específico de un hallazgo en otro agente.
    
    Ejemplo: Stock negativo impacta a Ventas bloqueando pedidos.
    """
    
    agent_name: str
    impact_type: ImpactType
    description: str
    specific_effect: str  # Efecto específico medible
    mitigation: str       # Qué hacer para mitigar


@dataclass
class Finding:
    """
    Un hallazgo identificado durante la inspección.
    
    Los hallazgos se clasifican en 4 niveles:
    - Nivel 1: Vista general (KPIs, tendencias)
    - Nivel 2: Por categorías (por vendedor, almacén, etc.)
    - Nivel 3: Detalles específicos (registros con problemas)
    - Nivel 4: Anomalías (errores, inconsistencias)
    """
    
    level: int                              # 1-4
    category: str                           # Categoría del hallazgo
    title: str                              # Título descriptivo
    description: str                        # Descripción detallada
    severity: ImpactLevel                   # Severidad
    affected_records: int = 0               # Cantidad de registros afectados
    affected_amount: float = 0.0            # Monto afectado
    sample_data: list = field(default_factory=list)  # Muestra de datos
    impacts: list[AgentImpact] = field(default_factory=list)  # Impactos a otros agentes
    solution: str = ""                      # Solución propuesta
    coordinated_actions: list[str] = field(default_factory=list)  # Acciones coordinadas
    
    def to_dict(self) -> dict[str, Any]:
        """Convierte el hallazgo a diccionario."""
        return {
            "level": self.level,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "affected_records": self.affected_records,
            "affected_amount": self.affected_amount,
            "sample_data": self.sample_data[:5],  # Limitar muestra
            "impacts": [
                {
                    "agent": i.agent_name,
                    "type": i.impact_type.value,
                    "description": i.description,
                    "effect": i.specific_effect,
                    "mitigation": i.mitigation,
                }
                for i in self.impacts
            ],
            "solution": self.solution,
            "coordinated_actions": self.coordinated_actions,
        }


@dataclass
class AreaContext:
    """
    Contexto general de un área de negocio.
    
    Proporciona un snapshot del estado actual del área
    antes de la inspección detallada.
    """
    
    area_name: str
    total_records: int = 0
    total_value: float = 0.0
    health_score: float = 100.0  # 0-100
    status: str = "healthy"      # healthy, warning, critical
    summary: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """Convierte el contexto a diccionario."""
        return {
            "area_name": self.area_name,
            "total_records": self.total_records,
            "total_value": self.total_value,
            "health_score": self.health_score,
            "status": self.status,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class InspectionReport:
    """
    Reporte completo de una inspección.
    
    Contiene el contexto del área, todos los hallazgos por nivel,
    y un resumen de impactos a otros agentes.
    
    Si create_proposals=True en inspect(), también incluye
    el conteo de propuestas generadas.
    """
    
    inspector_name: str
    agent_name: str
    context: AreaContext
    findings: list[Finding] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    proposals_created: int = 0  # Propuestas generadas de hallazgos
    
    @property
    def findings_by_level(self) -> dict[int, list[Finding]]:
        """Agrupa hallazgos por nivel."""
        by_level: dict[int, list[Finding]] = {1: [], 2: [], 3: [], 4: []}
        for f in self.findings:
            if f.level in by_level:
                by_level[f.level].append(f)
        return by_level
    
    @property
    def findings_by_severity(self) -> dict[str, list[Finding]]:
        """Agrupa hallazgos por severidad."""
        by_severity: dict[str, list[Finding]] = {
            "critical": [], "high": [], "medium": [], "low": [], "info": []
        }
        for f in self.findings:
            by_severity[f.severity.value].append(f)
        return by_severity
    
    @property
    def critical_count(self) -> int:
        """Cuenta hallazgos críticos."""
        return len(self.findings_by_severity["critical"])
    
    @property
    def high_count(self) -> int:
        """Cuenta hallazgos de alta prioridad."""
        return len(self.findings_by_severity["high"])
    
    @property
    def impacted_agents(self) -> set[str]:
        """Retorna set de agentes impactados."""
        agents = set()
        for f in self.findings:
            for impact in f.impacts:
                agents.add(impact.agent_name)
        return agents
    
    @property
    def total_affected_amount(self) -> float:
        """Suma total de montos afectados."""
        return sum(f.affected_amount for f in self.findings)
    
    def to_dict(self) -> dict[str, Any]:
        """Convierte el reporte completo a diccionario."""
        return {
            "inspector_name": self.inspector_name,
            "agent_name": self.agent_name,
            "context": self.context.to_dict(),
            "summary": {
                "total_findings": len(self.findings),
                "critical": self.critical_count,
                "high": self.high_count,
                "health_score": self.context.health_score,
                "status": self.context.status,
                "total_affected_amount": self.total_affected_amount,
                "impacted_agents": list(self.impacted_agents),
                "proposals_created": self.proposals_created,
            },
            "findings_by_level": {
                level: [f.to_dict() for f in findings]
                for level, findings in self.findings_by_level.items()
            },
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
    
    def get_markdown_summary(self) -> str:
        """Genera resumen en Markdown."""
        lines = [
            f"# Inspección: {self.context.area_name}",
            "",
            f"**Estado:** {self.context.status.upper()}",
            f"**Health Score:** {self.context.health_score:.0f}/100",
            f"**Hallazgos:** {len(self.findings)} ({self.critical_count} críticos, {self.high_count} altos)",
        ]
        if self.proposals_created > 0:
            lines.append(f"**Propuestas creadas:** {self.proposals_created}")
        lines.append("")
        
        # Hallazgos críticos primero
        critical = self.findings_by_severity["critical"]
        if critical:
            lines.append("## 🔴 Hallazgos Críticos")
            lines.append("")
            for f in critical:
                lines.append(f"### {f.title}")
                lines.append(f"{f.description}")
                if f.impacts:
                    lines.append("")
                    lines.append("**Impactos:**")
                    for i in f.impacts:
                        lines.append(f"- {i.agent_name}: {i.description}")
                if f.solution:
                    lines.append(f"\n**Solución:** {f.solution}")
                lines.append("")
        
        # Hallazgos altos
        high = self.findings_by_severity["high"]
        if high:
            lines.append("## 🟠 Hallazgos de Alta Prioridad")
            lines.append("")
            for f in high[:5]:  # Limitar a 5
                lines.append(f"- **{f.title}**: {f.description[:100]}...")
            if len(high) > 5:
                lines.append(f"- ... y {len(high) - 5} más")
            lines.append("")
        
        return "\n".join(lines)
