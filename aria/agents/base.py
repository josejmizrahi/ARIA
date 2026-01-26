"""
ARIA - Clase Base de Agentes
=============================

Clase base abstracta para todos los agentes de ARIA.

Define:
- Estructura común de tareas y monitoreo
- Integración con NotificationManager y ApprovalEngine
- Métodos helper para Odoo
- Ciclo de vida del agente
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import traceback
from typing import Any, Optional

from aria.config import settings
from aria.models.proposal import Proposal, ProposalType, ProposalAction, Priority
from aria.models.task import TaskDefinition, TaskResult
from aria.utils.logger import get_logger


class BaseAgent(ABC):
    """
    Clase base para todos los agentes de ARIA.
    
    Cada agente:
    - Monitorea un área específica del negocio
    - Detecta situaciones que requieren atención
    - Genera propuestas de acción
    - Ejecuta acciones aprobadas
    
    Para crear un nuevo agente:
    
        class MyAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    name="mi_agente",
                    description="Descripción del agente"
                )
            
            def _register_tasks(self):
                self.register_task(TaskDefinition(
                    name="mi_tarea",
                    method="mi_tarea",
                    schedule="0 8 * * *",
                    description="Ejecuta algo diario"
                ))
            
            async def mi_tarea(self) -> TaskResult:
                # Lógica de la tarea
                pass
            
            async def get_status_summary(self) -> dict:
                return {"status": "ok"}
    """
    
    def __init__(self, name: str, description: str = "") -> None:
        """
        Inicializa el agente.
        
        Args:
            name: Identificador único del agente (ej: "cobranza", "ventas")
            description: Descripción legible del agente
        """
        self.name = name
        self.description = description
        self.logger = get_logger(f"aria.agents.{name}")
        
        # Estado
        self.is_running = False
        self.started_at: Optional[datetime] = None
        self.tasks: list[TaskDefinition] = []
        
        # Servicios (lazy loading)
        self._odoo = None
        self._notifications = None
        self._approvals = None
        self._executor = None
        
        # Registrar tareas del agente
        self._register_tasks()
        
        self.logger.info(
            f"Agente {name} inicializado",
            tasks=len(self.tasks)
        )
    
    # ==================== Propiedades de Servicios ====================
    
    @property
    def odoo(self):
        """Cliente Odoo (lazy loading)."""
        if self._odoo is None:
            from aria.odoo_client import OdooClient
            self._odoo = OdooClient.get_instance()
        return self._odoo
    
    @property
    def notifications(self):
        """NotificationManager (lazy loading)."""
        if self._notifications is None:
            from aria.notification_manager import notification_manager
            self._notifications = notification_manager
        return self._notifications
    
    @property
    def approvals(self):
        """ApprovalEngine (lazy loading)."""
        if self._approvals is None:
            from aria.approval_engine import approval_engine
            self._approvals = approval_engine
        return self._approvals
    
    @property
    def executor(self):
        """ActionExecutor (lazy loading)."""
        if self._executor is None:
            from aria.action_executor import action_executor
            self._executor = action_executor
        return self._executor
    
    # ==================== Métodos Abstractos ====================
    
    @abstractmethod
    def _register_tasks(self) -> None:
        """
        Registra las tareas del agente.
        
        Cada agente debe implementar este método para definir sus tareas.
        Usar self.register_task() para agregar cada tarea.
        """
        pass
    
    @abstractmethod
    async def get_status_summary(self) -> dict[str, Any]:
        """
        Retorna resumen del estado actual del área que monitorea.
        
        Usado por el dashboard y el agente CEO para consolidar información.
        
        Returns:
            Dict con métricas y estado del área
        """
        pass
    
    # ==================== Ciclo de Vida ====================
    
    async def start(self) -> None:
        """Inicia el agente."""
        if self.is_running:
            self.logger.warning(f"Agente {self.name} ya está corriendo")
            return
        
        self.is_running = True
        self.started_at = datetime.now()
        
        # Registrar callback para ejecución de acciones aprobadas
        self.executor.register_with_approval_engine(self.name)
        
        self.logger.info(f"Agente {self.name} iniciado")
    
    async def stop(self) -> None:
        """Detiene el agente."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.logger.info(f"Agente {self.name} detenido")
    
    # ==================== Gestión de Tareas ====================
    
    def register_task(self, task: TaskDefinition) -> None:
        """
        Registra una tarea en el agente.
        
        Args:
            task: Definición de la tarea
        """
        # Verificar que el método existe
        if not hasattr(self, task.method):
            raise ValueError(
                f"Método {task.method} no existe en {self.__class__.__name__}"
            )
        
        self.tasks.append(task)
        self.logger.debug(f"Tarea registrada: {task.name} ({task.schedule})")
    
    async def run_task(self, task: TaskDefinition) -> TaskResult:
        """
        Ejecuta una tarea específica.
        
        Args:
            task: Tarea a ejecutar
        
        Returns:
            Resultado de la ejecución
        """
        started_at = datetime.now()
        self.logger.info(f"Ejecutando tarea: {task.name}")
        
        try:
            # Obtener método y ejecutar
            method = getattr(self, task.method)
            result = await method()
            
            # Si el método retorna TaskResult, usarlo
            if isinstance(result, TaskResult):
                task.last_result = result
                task.last_run = datetime.now()
                return result
            
            # Si no, crear TaskResult genérico
            task_result = TaskResult(
                task_name=task.name,
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"result": result} if result else {}
            )
            
            task.last_result = task_result
            task.last_run = datetime.now()
            
            self.logger.info(
                f"Tarea completada: {task.name}",
                duration=f"{task_result.duration_seconds:.2f}s"
            )
            
            return task_result
            
        except Exception as e:
            error_tb = traceback.format_exc()
            self.logger.error(f"Error en tarea {task.name}: {e}")
            
            task_result = TaskResult(
                task_name=task.name,
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=False,
                error=str(e),
                error_traceback=error_tb
            )
            
            task.last_result = task_result
            task.last_run = datetime.now()
            
            return task_result
    
    async def run_all_tasks(self) -> list[TaskResult]:
        """
        Ejecuta todas las tareas habilitadas del agente.
        
        Returns:
            Lista de resultados
        """
        results = []
        
        for task in self.tasks:
            if task.enabled:
                result = await self.run_task(task)
                results.append(result)
        
        return results
    
    def get_task(self, task_name: str) -> Optional[TaskDefinition]:
        """Obtiene una tarea por nombre."""
        return next((t for t in self.tasks if t.name == task_name), None)
    
    # ==================== Propuestas de Acción ====================
    
    async def propose(
        self,
        title: str,
        description: str,
        action: ProposalAction = ProposalAction.EXECUTE_ACTION,
        proposal_type: Optional[ProposalType] = None,
        priority: Priority = Priority.MEDIUM,
        situation_summary: Optional[str] = None,
        proposed_action_detail: Optional[str] = None,
        target_model: Optional[str] = None,
        target_ids: Optional[list[int]] = None,
        odoo_method: Optional[str] = None,
        odoo_params: Optional[dict] = None,
        payload: Optional[dict] = None,
        supporting_data: Optional[dict] = None,
        alternatives: Optional[list[dict]] = None,
        risk_level: int = 1,
        reversible: bool = True,
        expires_in_hours: Optional[int] = None,
        auto_execute: bool = False,
        informational: bool = False,
    ) -> Proposal:
        """
        Crea y envía una propuesta de acción.
        
        Este es el método principal para que los agentes comuniquen
        situaciones detectadas y propongan acciones.
        
        Args:
            title: Título corto y descriptivo
            description: Descripción detallada
            action: Tipo de acción propuesta
            proposal_type: Tipo de propuesta (default: según agente)
            priority: Nivel de prioridad
            situation_summary: Descripción de la situación detectada
            proposed_action_detail: Detalle de la acción propuesta
            target_model: Modelo de Odoo afectado
            target_ids: IDs de registros afectados
            odoo_method: Método de Odoo para ejecución directa
            odoo_params: Parámetros para el método de Odoo
            payload: Datos adicionales para ejecución
            supporting_data: Datos de contexto
            alternatives: Lista de acciones alternativas
            risk_level: Nivel de riesgo (1-5)
            reversible: Si la acción es reversible
            expires_in_hours: Horas hasta que expire la propuesta
            auto_execute: Si True, ejecutar sin esperar aprobación
            informational: Si True, solo notificar sin registrar propuesta
        
        Returns:
            Proposal creada y registrada
        """
        # Determinar tipo de propuesta según el agente
        if proposal_type is None:
            type_map = {
                "cobranza": ProposalType.COBRANZA,
                "ventas": ProposalType.VENTAS,
                "compras": ProposalType.COMPRAS,
                "inventario": ProposalType.INVENTARIO,
            }
            proposal_type = type_map.get(self.name, ProposalType.GENERAL)
        
        # Crear propuesta
        proposal = Proposal(
            agent_id=self.name,
            type=proposal_type,
            action=action,
            priority=priority,
            title=title,
            description=description,
            situation_summary=situation_summary,
            proposed_action_detail=proposed_action_detail,
            target_model=target_model,
            target_ids=target_ids or [],
            odoo_method=odoo_method,
            odoo_params=odoo_params or {},
            payload=payload or {},
            supporting_data=supporting_data or {},
            alternatives=alternatives or [],
            risk_level=risk_level,
            reversible=reversible,
        )
        
        # Establecer expiración
        if expires_in_hours:
            proposal.expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        self.logger.info(
            f"Creando propuesta: {proposal.short_id}",
            title=title
        )
        
        # Según tipo de acción
        if auto_execute:
            # Ejecutar directamente sin aprobación
            try:
                result = await self.executor.execute(proposal)
                proposal.mark_completed(result)
                self.logger.info(f"Acción auto-ejecutada: {proposal.short_id}")
            except Exception as e:
                proposal.mark_failed(str(e))
                self.logger.error(f"Error en auto-ejecución: {e}")
            
        elif informational:
            # Solo notificar, no registrar para aprobación
            await self.notifications.send_proposal(proposal)
            self.logger.info(f"Notificación informativa enviada: {proposal.short_id}")
            
        else:
            # Requiere aprobación: registrar y notificar
            await self.approvals.register(proposal)
            await self.notifications.send_proposal(proposal)
            self.logger.info(f"Propuesta enviada para aprobación: {proposal.short_id}")
        
        return proposal
    
    async def notify(
        self,
        title: str,
        message: str,
        priority: Priority = Priority.MEDIUM,
        data: Optional[dict] = None,
    ) -> None:
        """
        Envía una notificación simple (sin propuesta de acción).
        
        Útil para alertas informativas o reportes.
        """
        from aria.models.notification import NotificationPriority
        
        priority_map = {
            Priority.CRITICAL: NotificationPriority.CRITICAL,
            Priority.HIGH: NotificationPriority.HIGH,
            Priority.MEDIUM: NotificationPriority.MEDIUM,
            Priority.LOW: NotificationPriority.LOW,
        }
        
        await self.notifications.notify(
            title=title,
            message=message,
            priority=priority_map.get(priority, NotificationPriority.MEDIUM),
            agent_id=self.name,
            data=data,
        )
    
    # ==================== Helpers de Odoo ====================
    
    def search_read(
        self,
        model: str,
        domain: Optional[list] = None,
        fields: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order: Optional[str] = None,
    ) -> list[dict]:
        """Wrapper conveniente para búsquedas en Odoo."""
        return self.odoo.search_read(
            model,
            domain or [],
            fields=fields,
            offset=offset,
            limit=limit,
            order=order
        )
    
    def search_count(self, model: str, domain: Optional[list] = None) -> int:
        """Cuenta registros en Odoo."""
        return self.odoo.search_count(model, domain or [])
    
    def create(self, model: str, values: dict) -> int:
        """Crea registro en Odoo."""
        return self.odoo.create(model, values)
    
    def write(self, model: str, ids: list[int], values: dict) -> bool:
        """Actualiza registros en Odoo."""
        return self.odoo.write(model, ids, values)
    
    def read(self, model: str, ids: list[int], fields: Optional[list[str]] = None) -> list[dict]:
        """Lee registros de Odoo."""
        return self.odoo.read(model, ids, fields)
    
    # ==================== Helpers de Formato ====================
    
    @staticmethod
    def format_currency(amount: float, currency: str = "MXN") -> str:
        """Formatea cantidad como moneda."""
        return f"${amount:,.2f} {currency}"
    
    @staticmethod
    def days_between(date_str: str, reference_date: Optional[datetime] = None) -> int:
        """
        Calcula días entre una fecha y otra (o hoy).
        
        Args:
            date_str: Fecha en formato YYYY-MM-DD
            reference_date: Fecha de referencia (default: hoy)
        
        Returns:
            Número de días (positivo si date_str es pasado)
        """
        if not date_str:
            return 0
        
        # Manejar datetime o string
        if isinstance(date_str, datetime):
            date = date_str
        else:
            # Puede tener hora, tomar solo fecha
            date_str = str(date_str)[:10]
            date = datetime.strptime(date_str, "%Y-%m-%d")
        
        reference = reference_date or datetime.now()
        
        return (reference - date).days
    
    @staticmethod
    def format_date(date_str: str, fmt: str = "%d/%m/%Y") -> str:
        """Formatea fecha para mostrar."""
        if not date_str:
            return ""
        try:
            date_str = str(date_str)[:10]
            date = datetime.strptime(date_str, "%Y-%m-%d")
            return date.strftime(fmt)
        except Exception:
            return str(date_str)
    
    def get_company_ids(self) -> list[int]:
        """Obtiene IDs de las compañías configuradas."""
        companies = self.search_read(
            "res.company",
            [],
            ["id", "name"],
            limit=10
        )
        return [c["id"] for c in companies]
    
    # ==================== Info del Agente ====================
    
    def get_info(self) -> dict[str, Any]:
        """Retorna información del agente."""
        return {
            "name": self.name,
            "description": self.description,
            "is_running": self.is_running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "tasks": [
                {
                    "name": t.name,
                    "description": t.description,
                    "schedule": t.schedule,
                    "enabled": t.enabled,
                    "last_run": t.last_run.isoformat() if t.last_run else None,
                    "last_success": t.last_result.success if t.last_result else None,
                }
                for t in self.tasks
            ],
        }
    
    def __repr__(self) -> str:
        """Representación del agente."""
        return f"<{self.__class__.__name__}(name={self.name}, running={self.is_running})>"
