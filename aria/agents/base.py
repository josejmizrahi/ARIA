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

from pydantic import BaseModel, Field

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
    
    @property
    def messaging(self):
        """Sistema de mensajería entre agentes (lazy loading)."""
        from aria.agent_messaging import get_messaging
        return get_messaging()
    
    @property
    def introspection(self):
        """Sistema de introspección (lazy loading)."""
        from aria.agent_introspection import get_introspection
        return get_introspection(self.odoo)
    
    @property
    def learning(self):
        """Sistema de aprendizaje (lazy loading)."""
        from aria.agent_learning import get_learning
        return get_learning()
    
    # ==================== Métodos de Comunicación ====================
    
    async def ask_agent(
        self,
        to_agent: str,
        question: str,
        data: Optional[dict] = None,
        priority: str = "medium",
    ) -> Optional[dict]:
        """
        Hace una pregunta a otro agente.
        
        Returns:
            Respuesta del agente o None si no responde
        """
        from aria.agent_messaging import MessagePriority
        
        priority_map = {
            "low": MessagePriority.LOW,
            "medium": MessagePriority.MEDIUM,
            "high": MessagePriority.HIGH,
            "critical": MessagePriority.CRITICAL,
        }
        
        message = self.messaging.query(
            from_agent=self.name,
            to_agent=to_agent,
            question=question,
            data=data or {},
            priority=priority_map.get(priority, MessagePriority.MEDIUM),
        )
        
        # Esperar respuesta (simplificado - en producción usaría async/await con timeout)
        # Por ahora retornamos None y el otro agente debe responder manualmente
        return None
    
    async def respond_to_agent(
        self,
        message_id: str,
        response: str,
        data: Optional[dict] = None,
    ) -> None:
        """Responde a un mensaje de otro agente."""
        from uuid import UUID
        
        try:
            msg_id = UUID(message_id)
            self.messaging.respond(
                from_agent=self.name,
                to_message_id=msg_id,
                response=response,
                data=data or {},
            )
        except Exception as e:
            self.logger.error(f"Error respondiendo a mensaje {message_id}: {e}")
    
    async def alert_agent(
        self,
        to_agent: str,
        alert_subject: str,
        alert_content: str,
        data: Optional[dict] = None,
        priority: str = "high",
    ) -> None:
        """Envía una alerta a otro agente."""
        from aria.agent_messaging import MessagePriority
        
        priority_map = {
            "low": MessagePriority.LOW,
            "medium": MessagePriority.MEDIUM,
            "high": MessagePriority.HIGH,
            "critical": MessagePriority.CRITICAL,
        }
        
        self.messaging.alert(
            from_agent=self.name,
            to_agent=to_agent,
            alert_subject=alert_subject,
            alert_content=alert_content,
            data=data or {},
            priority=priority_map.get(priority, MessagePriority.HIGH),
        )
    
    async def request_data_from_agent(
        self,
        to_agent: str,
        data_request: str,
        fields: Optional[list[str]] = None,
        filters: Optional[dict] = None,
    ) -> Optional[dict]:
        """Solicita datos específicos a otro agente."""
        message = self.messaging.request_data(
            from_agent=self.name,
            to_agent=to_agent,
            data_request=data_request,
            fields=fields,
            filters=filters,
        )
        
        # El otro agente debe responder manualmente por ahora
        return None
    
    def check_messages(self, unread_only: bool = True) -> list[dict]:
        """Revisa mensajes recibidos."""
        from aria.agent_messaging import MessageType
        
        messages = self.messaging.get_messages(
            agent_name=self.name,
            unread_only=unread_only,
        )
        
        # Convertir a dict y marcar como leído si es necesario
        result = []
        for msg in messages:
            msg_dict = msg.model_dump()
            result.append(msg_dict)
            if not unread_only:
                self.messaging.mark_read(msg.id, self.name)
        
        return result
    
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
        Ejecuta una tarea específica con introspección y aprendizaje.
        
        Args:
            task: Tarea a ejecutar
        
        Returns:
            Resultado de la ejecución
        """
        started_at = datetime.now()
        self.logger.info(f"Ejecutando tarea: {task.name}")
        
        # Procesar mensajes pendientes antes de ejecutar
        try:
            await self._process_pending_messages()
        except Exception as e:
            self.logger.warning(f"Error procesando mensajes pendientes: {e}")
        
        try:
            # Obtener método y ejecutar
            method = getattr(self, task.method)
            result = await method()
            
            # Si el método retorna TaskResult, usarlo
            if isinstance(result, TaskResult):
                task.last_result = result
                task.last_run = datetime.now()
                
                # Aprender de la ejecución exitosa
                if result.success:
                    self.learning.record_success(
                        self.name,
                        f"task_{task.name}",
                        {"task": task.name, "method": task.method}
                    )
                
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
            
            # Aprender de éxito
            self.learning.record_success(
                self.name,
                f"task_{task.name}",
                {"task": task.name, "method": task.method}
            )
            
            self.logger.info(
                f"Tarea completada: {task.name}",
                duration=f"{task_result.duration_seconds:.2f}s"
            )
            
            return task_result
            
        except Exception as e:
            error_tb = traceback.format_exc()
            self.logger.error(f"Error en tarea {task.name}: {e}")
            
            # Aprender del error
            self.learning.record_failure(
                self.name,
                f"task_{task.name}",
                {"task": task.name, "error": str(e)}
            )
            
            # Intentar aprender de logs
            try:
                from pathlib import Path
                log_file = Path(settings.log_dir) / "aria.log"
                self.learning.learn_from_logs(self.name, log_file)
            except Exception as learn_error:
                self.logger.warning(f"Error aprendiendo de logs: {learn_error}")
            
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
    
    async def _process_pending_messages(self) -> None:
        """Procesa mensajes pendientes (puede ser sobrescrito por agentes específicos)."""
        # Por defecto, solo marca como leído
        # Los agentes pueden sobrescribir para responder automáticamente
        messages = self.check_messages(unread_only=True)
        for msg in messages:
            try:
                from uuid import UUID
                msg_id = UUID(msg.get("id"))
                self.messaging.mark_read(msg_id, self.name)
            except Exception:
                pass
    
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
        validate: bool = True,  # Validar campos antes de consultar
    ) -> list[dict]:
        """
        Wrapper conveniente para búsquedas en Odoo con introspección automática.
        
        Args:
            validate: Si True, valida campos antes de consultar (recomendado)
        """
        fields = fields or []
        
        # Introspección automática si está habilitada
        if validate and fields:
            from aria.agent_introspection import get_introspection
            
            try:
                introspection = get_introspection(self.odoo)
                validation = introspection.validate_query(model, fields, domain)
                
                if not validation["valid"]:
                    # Si el modelo no existe, retornar lista vacía sin intentar consultar
                    if not validation.get("model_exists", True):
                        # Solo loguear una vez por modelo para evitar spam
                        if not hasattr(self, '_logged_missing_models'):
                            self._logged_missing_models = set()
                        if model not in self._logged_missing_models:
                            self.logger.debug(
                                f"Modelo {model} no existe en Odoo. Retornando lista vacía."
                            )
                            self._logged_missing_models.add(model)
                        return []
                    
                    # Usar solo campos válidos
                    valid_fields = [
                        field for field, valid in validation["fields_valid"].items()
                        if valid
                    ]
                    
                    if valid_fields:
                        self.logger.warning(
                            f"Campos inválidos en {model}: {validation['missing_fields']}. "
                            f"Usando solo campos válidos: {valid_fields}"
                        )
                        fields = valid_fields
                    else:
                        # Solo loguear una vez por modelo para evitar spam
                        if not hasattr(self, '_logged_missing_fields'):
                            self._logged_missing_fields = set()
                        model_key = f"{model}:{','.join(sorted(fields))}"
                        if model_key not in self._logged_missing_fields:
                            self.logger.warning(
                                f"Modelo {model} existe pero ningún campo solicitado es válido. "
                                f"Campos solicitados: {fields}"
                            )
                            self._logged_missing_fields.add(model_key)
                        return []
                
                # Si hay sugerencias, loguearlas
                if validation.get("suggestions"):
                    for missing, suggestion in validation["suggestions"].items():
                        self.logger.info(
                            f"Campo '{missing}' no existe en {model}. "
                            f"Sugerencia: usar '{suggestion}'"
                        )
            except Exception as e:
                self.logger.warning(f"Error en introspección de {model}: {e}. Continuando sin validación.")
        
        # Ejecutar consulta con manejo de errores mejorado
        try:
            return self.odoo.search_read(
                model,
                domain or [],
                fields=fields,
                offset=offset,
                limit=limit,
                order=order
            )
        except Exception as e:
            # Si el error es que el modelo no existe y ya lo validamos, solo retornar vacío
            error_str = str(e).lower()
            if "doesn't exist" in error_str or "no existe" in error_str:
                if not hasattr(self, '_logged_missing_models'):
                    self._logged_missing_models = set()
                if model not in self._logged_missing_models:
                    self.logger.debug(f"Modelo {model} no existe en Odoo (confirmado por error). Retornando lista vacía.")
                    self._logged_missing_models.add(model)
                return []
            # Para otros errores, relanzar
            raise
    
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
