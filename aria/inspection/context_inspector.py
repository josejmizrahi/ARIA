"""
Clase base para inspectores contextuales.

BaseContextInspector define la estructura común para todos los inspectores,
incluyendo el análisis en 4 niveles y la gestión de impactos entre agentes.

Integración con Propuestas:
- Los hallazgos con severidad HIGH o CRITICAL pueden generar propuestas
- Las propuestas se registran en el ApprovalEngine
- El ciclo completo: Inspección → Hallazgo → Propuesta → Aprobación → Ejecución
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from aria.approval_engine import ApprovalEngine
from aria.config import settings
from aria.models.proposal import (
    Proposal,
    ProposalAction,
    ProposalType,
    Priority,
)
from aria.odoo_client import OdooClient
from aria.utils.logger import get_logger

from .models import (
    AgentDependency,
    AgentImpact,
    AreaContext,
    Finding,
    ImpactLevel,
    ImpactType,
    InspectionReport,
)


class BaseContextInspector(ABC):
    """
    Clase base abstracta para inspectores contextuales.
    
    Cada inspector analiza un área del negocio en 4 niveles:
    1. Vista General: KPIs, tendencias, distribución
    2. Por Categorías: Agrupado por dimensiones relevantes
    3. Detalles: Registros específicos con problemas
    4. Anomalías: Errores, inconsistencias, datos incorrectos
    
    Los inspectores identifican hallazgos y determinan sus impactos
    en otros agentes para proponer soluciones coordinadas.
    
    Integración con Propuestas:
    - Hallazgos HIGH/CRITICAL pueden generar propuestas automáticas
    - Usar inspect(create_proposals=True) para activar
    """
    
    # Estas constantes deben ser definidas por cada inspector
    AGENT_NAME: str = ""
    AREA_NAME: str = ""
    
    # Dependencias con otros agentes
    UPSTREAM_DEPENDENCIES: list[AgentDependency] = []
    DOWNSTREAM_DEPENDENCIES: list[AgentDependency] = []
    
    # Mapeo de agent names a ProposalType
    PROPOSAL_TYPE_MAP: dict[str, ProposalType] = {
        "inventario": ProposalType.INVENTARIO,
        "cobranza": ProposalType.COBRANZA,
        "ventas": ProposalType.VENTAS,
        "compras": ProposalType.COMPRAS,
        "contabilidad": ProposalType.CONTABILIDAD,
        "rrhh": ProposalType.RRHH,
    }
    
    # Mapeo de ImpactLevel a Priority
    PRIORITY_MAP: dict[ImpactLevel, Priority] = {
        ImpactLevel.CRITICAL: Priority.CRITICAL,
        ImpactLevel.HIGH: Priority.HIGH,
        ImpactLevel.MEDIUM: Priority.MEDIUM,
        ImpactLevel.LOW: Priority.LOW,
        ImpactLevel.INFO: Priority.LOW,
    }
    
    def __init__(self) -> None:
        """Inicializa el inspector."""
        self.logger = get_logger(f"inspector.{self.AGENT_NAME}")
        self.odoo = OdooClient.get_instance()
        self.company_id = settings.odoo.company_id
        self.approval_engine = ApprovalEngine()
        
        # Estado de la inspección
        self._findings: list[Finding] = []
        self._context: AreaContext | None = None
        self._started_at: datetime | None = None
        self._proposals_created: list[Proposal] = []
    
    # ==================== API Pública ====================
    
    def inspect(
        self,
        max_level: int = 4,
        create_proposals: bool = False,
        min_severity_for_proposal: ImpactLevel = ImpactLevel.HIGH,
    ) -> InspectionReport:
        """
        Ejecuta la inspección completa.
        
        Args:
            max_level: Nivel máximo de inspección (1-4)
            create_proposals: Si True, crea propuestas para hallazgos graves
            min_severity_for_proposal: Severidad mínima para crear propuestas
            
        Returns:
            InspectionReport con todos los hallazgos
        """
        self._started_at = datetime.now()
        self._findings = []
        self._proposals_created = []
        
        self.logger.info(
            f"Iniciando inspección de {self.AREA_NAME}",
            max_level=max_level,
            create_proposals=create_proposals,
        )
        
        try:
            # Obtener contexto del área
            self._context = self._get_area_context()
            
            # Ejecutar niveles de inspección
            if max_level >= 1:
                self.logger.debug("Nivel 1: Vista general")
                self._inspect_level_1_overview()
            
            if max_level >= 2:
                self.logger.debug("Nivel 2: Por categorías")
                self._inspect_level_2_categories()
            
            if max_level >= 3:
                self.logger.debug("Nivel 3: Detalles")
                self._inspect_level_3_details()
            
            if max_level >= 4:
                self.logger.debug("Nivel 4: Anomalías")
                self._inspect_level_4_anomalies()
            
            # Calcular health score basado en hallazgos
            self._update_health_score()
            
            # Crear propuestas si está habilitado
            if create_proposals:
                self._create_proposals_from_findings(min_severity_for_proposal)
            
        except Exception as e:
            self.logger.error(f"Error en inspección: {e}")
            self._add_finding(
                level=4,
                category="Error",
                title=f"Error en inspección de {self.AREA_NAME}",
                description=str(e),
                severity=ImpactLevel.CRITICAL,
            )
        
        # Generar reporte
        report = InspectionReport(
            inspector_name=self.__class__.__name__,
            agent_name=self.AGENT_NAME,
            context=self._context or AreaContext(area_name=self.AREA_NAME),
            findings=self._findings,
            started_at=self._started_at,
            completed_at=datetime.now(),
            proposals_created=len(self._proposals_created),
        )
        
        self.logger.info(
            f"Inspección completada",
            findings=len(self._findings),
            critical=report.critical_count,
            proposals=len(self._proposals_created),
            health_score=self._context.health_score if self._context else 0,
        )
        
        return report
    
    async def inspect_and_propose(
        self,
        max_level: int = 4,
        min_severity: ImpactLevel = ImpactLevel.HIGH,
    ) -> tuple[InspectionReport, list[Proposal]]:
        """
        Ejecuta inspección y crea propuestas para hallazgos graves.
        
        Este método combina inspección + generación de propuestas
        en una sola llamada conveniente.
        
        Args:
            max_level: Nivel máximo de inspección (1-4)
            min_severity: Severidad mínima para crear propuestas
            
        Returns:
            Tupla de (InspectionReport, lista de Proposals creadas)
        """
        report = self.inspect(
            max_level=max_level,
            create_proposals=True,
            min_severity_for_proposal=min_severity,
        )
        return report, self._proposals_created
    
    def get_dependencies(self) -> dict[str, list[AgentDependency]]:
        """Retorna las dependencias del inspector."""
        return {
            "upstream": self.UPSTREAM_DEPENDENCIES,
            "downstream": self.DOWNSTREAM_DEPENDENCIES,
        }
    
    # ==================== Métodos Abstractos ====================
    
    @abstractmethod
    def _get_area_context(self) -> AreaContext:
        """
        Obtiene el contexto general del área.
        
        Debe retornar un snapshot con:
        - Totales (registros, valor)
        - Health score inicial
        - Resumen de métricas clave
        """
        pass
    
    @abstractmethod
    def _inspect_level_1_overview(self) -> None:
        """
        Nivel 1: Vista general.
        
        Analiza:
        - KPIs principales
        - Tendencias
        - Distribución general
        """
        pass
    
    @abstractmethod
    def _inspect_level_2_categories(self) -> None:
        """
        Nivel 2: Por categorías.
        
        Analiza agrupado por:
        - Categoría de producto
        - Vendedor/responsable
        - Almacén/ubicación
        - Período
        """
        pass
    
    @abstractmethod
    def _inspect_level_3_details(self) -> None:
        """
        Nivel 3: Detalles específicos.
        
        Identifica registros con problemas:
        - Bajo mínimo/sobre máximo
        - Vencimientos próximos
        - Valores fuera de rango
        """
        pass
    
    @abstractmethod
    def _inspect_level_4_anomalies(self) -> None:
        """
        Nivel 4: Anomalías.
        
        Detecta errores e inconsistencias:
        - Valores negativos imposibles
        - Datos faltantes obligatorios
        - Inconsistencias entre modelos
        """
        pass
    
    # ==================== Helpers para Hallazgos ====================
    
    def _add_finding(
        self,
        level: int,
        category: str,
        title: str,
        description: str,
        severity: ImpactLevel,
        affected_records: int = 0,
        affected_amount: float = 0.0,
        sample_data: list | None = None,
        impacts: list[AgentImpact] | None = None,
        solution: str = "",
        coordinated_actions: list[str] | None = None,
    ) -> None:
        """
        Agrega un hallazgo a la inspección.
        
        Args:
            level: Nivel del hallazgo (1-4)
            category: Categoría (ej: "Stock", "Crédito")
            title: Título descriptivo
            description: Descripción detallada
            severity: Nivel de severidad
            affected_records: Cantidad de registros afectados
            affected_amount: Monto afectado
            sample_data: Muestra de datos (max 10 registros)
            impacts: Lista de impactos a otros agentes
            solution: Solución propuesta
            coordinated_actions: Acciones que requieren otros agentes
        """
        finding = Finding(
            level=level,
            category=category,
            title=title,
            description=description,
            severity=severity,
            affected_records=affected_records,
            affected_amount=affected_amount,
            sample_data=sample_data[:10] if sample_data else [],
            impacts=impacts or [],
            solution=solution,
            coordinated_actions=coordinated_actions or [],
        )
        
        self._findings.append(finding)
        
        # Log según severidad
        if severity == ImpactLevel.CRITICAL:
            self.logger.warning(f"[CRÍTICO] {title}", affected=affected_records)
        elif severity == ImpactLevel.HIGH:
            self.logger.warning(f"[ALTO] {title}", affected=affected_records)
        else:
            self.logger.info(f"[{severity.value.upper()}] {title}", affected=affected_records)
    
    def _update_health_score(self) -> None:
        """Actualiza el health score basado en los hallazgos."""
        if not self._context:
            return
        
        # Empezar en 100 y restar según severidad
        score = 100.0
        
        for finding in self._findings:
            if finding.severity == ImpactLevel.CRITICAL:
                score -= 25
            elif finding.severity == ImpactLevel.HIGH:
                score -= 10
            elif finding.severity == ImpactLevel.MEDIUM:
                score -= 5
            elif finding.severity == ImpactLevel.LOW:
                score -= 2
        
        self._context.health_score = max(0, min(100, score))
        self._context.status = self._get_status_from_health(self._context.health_score)
    
    # ==================== Helpers de Datos ====================
    
    def _safe_get(self, record: dict, field: str, default: Any = None) -> Any:
        """Obtiene un campo de forma segura."""
        return record.get(field, default) if record else default
    
    def _safe_get_name(self, record: dict, field: str) -> str:
        """Obtiene el nombre de un campo Many2one."""
        value = record.get(field) if record else None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return str(value[1])
        return ""
    
    def _safe_get_id(self, record: dict, field: str) -> int:
        """Obtiene el ID de un campo Many2one."""
        value = record.get(field) if record else None
        if isinstance(value, (list, tuple)) and len(value) >= 1:
            return int(value[0])
        if isinstance(value, int):
            return value
        return 0
    
    def _calculate_health_score(
        self,
        total: int,
        with_issues: int,
        critical_count: int = 0,
    ) -> float:
        """
        Calcula un health score basado en proporciones.
        
        Args:
            total: Total de registros
            with_issues: Registros con problemas
            critical_count: Cantidad de problemas críticos
            
        Returns:
            Score de 0 a 100
        """
        if total == 0:
            return 100.0
        
        # Base: porcentaje sin problemas
        base_score = ((total - with_issues) / total) * 100
        
        # Penalizar por críticos
        critical_penalty = critical_count * 10
        
        return max(0, min(100, base_score - critical_penalty))
    
    def _get_status_from_health(self, health_score: float) -> str:
        """Determina el estado basado en el health score."""
        if health_score >= 80:
            return "healthy"
        elif health_score >= 50:
            return "warning"
        else:
            return "critical"
    
    def _model_exists(self, model_name: str) -> bool:
        """Verifica si un modelo existe en Odoo."""
        try:
            count = self.odoo.search_count(
                "ir.model",
                [("model", "=", model_name)]
            )
            return count > 0
        except Exception:
            return False
    
    def _days_between(self, date_str: str | None) -> int:
        """Calcula días entre una fecha y hoy."""
        if not date_str:
            return 0
        try:
            date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            return (datetime.now() - date).days
        except (ValueError, TypeError):
            return 0
    
    def _format_currency(self, amount: float, currency: str = "MXN") -> str:
        """Formatea un monto como moneda."""
        return f"${amount:,.2f} {currency}"
    
    def _search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        limit: int = 500,
        order: str | None = None,
    ) -> list[dict]:
        """Wrapper para search_read con manejo de errores."""
        try:
            return self.odoo.search_read(
                model,
                domain,
                fields,
                limit=limit,
                order=order,
            )
        except Exception as e:
            self.logger.error(f"Error en search_read({model}): {e}")
            return []
    
    def _search_count(self, model: str, domain: list) -> int:
        """Wrapper para search_count con manejo de errores."""
        try:
            return self.odoo.search_count(model, domain)
        except Exception as e:
            self.logger.error(f"Error en search_count({model}): {e}")
            return 0
    
    # ==================== Helpers para Impactos ====================
    
    def _create_impact(
        self,
        agent_name: str,
        impact_type: ImpactType,
        description: str,
        specific_effect: str,
        mitigation: str = "",
    ) -> AgentImpact:
        """Crea un impacto a otro agente."""
        return AgentImpact(
            agent_name=agent_name,
            impact_type=impact_type,
            description=description,
            specific_effect=specific_effect,
            mitigation=mitigation,
        )
    
    def _blocks_agent(
        self,
        agent_name: str,
        reason: str,
        effect: str,
        mitigation: str = "",
    ) -> AgentImpact:
        """Helper para crear impacto de tipo BLOCKS."""
        return self._create_impact(
            agent_name=agent_name,
            impact_type=ImpactType.BLOCKS,
            description=f"Bloquea a {agent_name}: {reason}",
            specific_effect=effect,
            mitigation=mitigation,
        )
    
    def _delays_agent(
        self,
        agent_name: str,
        reason: str,
        effect: str,
        mitigation: str = "",
    ) -> AgentImpact:
        """Helper para crear impacto de tipo DELAYS."""
        return self._create_impact(
            agent_name=agent_name,
            impact_type=ImpactType.DELAYS,
            description=f"Retrasa a {agent_name}: {reason}",
            specific_effect=effect,
            mitigation=mitigation,
        )
    
    def _increases_cost_for(
        self,
        agent_name: str,
        reason: str,
        effect: str,
        mitigation: str = "",
    ) -> AgentImpact:
        """Helper para crear impacto de tipo INCREASES_COST."""
        return self._create_impact(
            agent_name=agent_name,
            impact_type=ImpactType.INCREASES_COST,
            description=f"Incrementa costos para {agent_name}: {reason}",
            specific_effect=effect,
            mitigation=mitigation,
        )
    
    def _increases_risk_for(
        self,
        agent_name: str,
        reason: str,
        effect: str,
        mitigation: str = "",
    ) -> AgentImpact:
        """Helper para crear impacto de tipo INCREASES_RISK."""
        return self._create_impact(
            agent_name=agent_name,
            impact_type=ImpactType.INCREASES_RISK,
            description=f"Incrementa riesgo para {agent_name}: {reason}",
            specific_effect=effect,
            mitigation=mitigation,
        )
    
    # ==================== Generación de Propuestas ====================
    
    def _create_proposals_from_findings(
        self,
        min_severity: ImpactLevel = ImpactLevel.HIGH,
    ) -> None:
        """
        Crea propuestas para hallazgos que superen la severidad mínima.
        
        Args:
            min_severity: Severidad mínima para crear propuesta
        """
        severity_order = [
            ImpactLevel.INFO,
            ImpactLevel.LOW,
            ImpactLevel.MEDIUM,
            ImpactLevel.HIGH,
            ImpactLevel.CRITICAL,
        ]
        min_index = severity_order.index(min_severity)
        
        actionable_findings = [
            f for f in self._findings
            if severity_order.index(f.severity) >= min_index
            and f.solution  # Solo si tiene solución propuesta
        ]
        
        self.logger.info(
            f"Creando propuestas para {len(actionable_findings)} hallazgos"
        )
        
        for finding in actionable_findings:
            try:
                proposal = self._finding_to_proposal(finding)
                if proposal:
                    # Registrar en el ApprovalEngine (sync)
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Si ya hay un loop, crear tarea
                            asyncio.create_task(
                                self.approval_engine.register(proposal)
                            )
                        else:
                            loop.run_until_complete(
                                self.approval_engine.register(proposal)
                            )
                    except RuntimeError:
                        # No hay loop, crear uno nuevo
                        asyncio.run(self.approval_engine.register(proposal))
                    
                    self._proposals_created.append(proposal)
                    self.logger.info(
                        f"Propuesta creada: {proposal.short_id}",
                        title=proposal.title,
                    )
            except Exception as e:
                self.logger.error(
                    f"Error creando propuesta para hallazgo: {e}",
                    finding=finding.title,
                )
    
    def _finding_to_proposal(self, finding: Finding) -> Proposal | None:
        """
        Convierte un hallazgo en una propuesta de acción.
        
        Args:
            finding: Hallazgo a convertir
            
        Returns:
            Proposal o None si no se puede convertir
        """
        if not finding.solution:
            return None
        
        # Determinar tipo de propuesta según el agente
        proposal_type = self.PROPOSAL_TYPE_MAP.get(
            self.AGENT_NAME,
            ProposalType.GENERAL
        )
        
        # Determinar prioridad según severidad
        priority = self.PRIORITY_MAP.get(finding.severity, Priority.MEDIUM)
        
        # Determinar acción basada en el tipo de hallazgo
        action = self._determine_action_for_finding(finding)
        
        # Construir descripción detallada
        description = f"{finding.description}"
        if finding.affected_records:
            description += f"\n\nRegistros afectados: {finding.affected_records}"
        if finding.affected_amount:
            description += f"\nMonto afectado: ${finding.affected_amount:,.2f}"
        
        # Construir resumen de situación con impactos
        situation_parts = [finding.description]
        if finding.impacts:
            situation_parts.append("\nImpactos en otros agentes:")
            for impact in finding.impacts:
                situation_parts.append(f"  • {impact.agent_name}: {impact.description}")
        situation_summary = "\n".join(situation_parts)
        
        # Construir acciones coordinadas
        coordinated_text = ""
        if finding.coordinated_actions:
            coordinated_text = "\n\nAcciones coordinadas requeridas:\n" + "\n".join(
                f"  • {action}" for action in finding.coordinated_actions
            )
        
        # Datos de soporte
        supporting_data = {
            "inspection_level": finding.level,
            "category": finding.category,
            "severity": finding.severity.value,
            "impacted_agents": [i.agent_name for i in finding.impacts],
            "sample_data": finding.sample_data[:5] if finding.sample_data else [],
        }
        
        # Crear propuesta
        proposal = Proposal(
            agent_id=f"inspector_{self.AGENT_NAME}",
            type=proposal_type,
            action=action,
            priority=priority,
            title=f"[Inspección] {finding.title}",
            description=description,
            situation_summary=situation_summary,
            proposed_action_detail=finding.solution + coordinated_text,
            supporting_data=supporting_data,
            risk_level=self._severity_to_risk_level(finding.severity),
            reversible=True,  # La mayoría de acciones de inspección son reversibles
        )
        
        return proposal
    
    def _determine_action_for_finding(self, finding: Finding) -> ProposalAction:
        """
        Determina la acción apropiada para un hallazgo.
        
        Mapea el tipo de hallazgo a una ProposalAction.
        """
        category_lower = finding.category.lower()
        title_lower = finding.title.lower()
        
        # Mapeo basado en categoría/título
        if "stock" in category_lower or "inventario" in category_lower:
            if "negativo" in title_lower or "bajo" in title_lower:
                return ProposalAction.CREATE_PURCHASE_ORDER
            if "transferir" in title_lower:
                return ProposalAction.TRANSFER_STOCK
            return ProposalAction.ADJUST_STOCK
        
        if "cobr" in category_lower or "vencid" in title_lower:
            if "recordatorio" in title_lower:
                return ProposalAction.SEND_REMINDER
            if "bloquear" in title_lower or "crédito" in category_lower:
                return ProposalAction.BLOCK_CREDIT
            return ProposalAction.SEND_PAYMENT_REQUEST
        
        if "venta" in category_lower:
            if "cotización" in title_lower or "propuesta" in title_lower:
                return ProposalAction.CREATE_QUOTATION
            if "descuento" in title_lower:
                return ProposalAction.APPLY_DISCOUNT
        
        if "compra" in category_lower:
            return ProposalAction.CREATE_PURCHASE_ORDER
        
        # Default: acción genérica
        return ProposalAction.EXECUTE_ACTION
    
    def _severity_to_risk_level(self, severity: ImpactLevel) -> int:
        """Convierte severidad a nivel de riesgo (1-5)."""
        risk_map = {
            ImpactLevel.INFO: 1,
            ImpactLevel.LOW: 2,
            ImpactLevel.MEDIUM: 3,
            ImpactLevel.HIGH: 4,
            ImpactLevel.CRITICAL: 5,
        }
        return risk_map.get(severity, 3)