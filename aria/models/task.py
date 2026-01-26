"""
ARIA - Modelo Task
===================

Representa tareas que los agentes ejecutan periódicamente.
Incluye definición de tareas y resultados de ejecución.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


class TaskStatus(str, Enum):
    """Estados posibles de una tarea."""
    PENDING = "pending"          # Pendiente de ejecución
    SCHEDULED = "scheduled"      # Programada para el futuro
    RUNNING = "running"          # En ejecución
    PAUSED = "paused"            # Pausada
    COMPLETED = "completed"      # Completada exitosamente
    FAILED = "failed"            # Falló durante ejecución
    CANCELLED = "cancelled"      # Cancelada


class TaskPriority(str, Enum):
    """Prioridades de tarea."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Tipos de tarea."""
    ONE_TIME = "one_time"        # Ejecución única
    RECURRING = "recurring"      # Recurrente (cron)
    TRIGGERED = "triggered"      # Disparada por evento
    MANUAL = "manual"            # Iniciada manualmente


class TaskDefinition(BaseModel):
    """
    Definición de una tarea programada de un agente.
    
    Ejemplo:
        task = TaskDefinition(
            name="check_overdue",
            method="check_overdue_invoices",
            schedule="0 8 * * *",  # 8:00 AM diario
            description="Revisa facturas vencidas"
        )
    """
    
    # Identificación
    name: str = Field(..., description="Nombre único de la tarea")
    method: str = Field(..., description="Nombre del método a ejecutar")
    
    # Programación (cron expression)
    schedule: str = Field(
        default="0 * * * *",
        description="Expresión cron para programación"
    )
    
    # Descripción
    description: str = Field(
        default="",
        description="Descripción de la tarea"
    )
    
    # Estado
    enabled: bool = Field(
        default=True,
        description="Si la tarea está habilitada"
    )
    
    # Timestamps
    last_run: Optional[datetime] = Field(
        default=None,
        description="Última ejecución"
    )
    next_run: Optional[datetime] = Field(
        default=None,
        description="Próxima ejecución programada"
    )
    
    # Resultado de última ejecución
    last_result: Optional["TaskResult"] = Field(
        default=None,
        description="Resultado de última ejecución"
    )
    
    class Config:
        """Configuración del modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class TaskResult(BaseModel):
    """
    Resultado de la ejecución de una tarea.
    
    Captura métricas y datos de la ejecución.
    """
    
    # Identificación
    id: UUID = Field(default_factory=uuid4, description="ID único del resultado")
    task_name: str = Field(..., description="Nombre de la tarea")
    agent_name: str = Field(..., description="Nombre del agente")
    
    # Timestamps
    started_at: datetime = Field(
        default_factory=datetime.now,
        description="Inicio de ejecución"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Fin de ejecución"
    )
    
    # Resultado
    success: bool = Field(
        default=True,
        description="Si la ejecución fue exitosa"
    )
    error: Optional[str] = Field(
        default=None,
        description="Mensaje de error si falló"
    )
    error_traceback: Optional[str] = Field(
        default=None,
        description="Traceback completo del error"
    )
    
    # Métricas
    records_processed: int = Field(
        default=0,
        description="Registros procesados"
    )
    proposals_created: int = Field(
        default=0,
        description="Propuestas creadas"
    )
    
    # Datos adicionales
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Datos adicionales del resultado"
    )
    
    @computed_field
    @property
    def duration_seconds(self) -> float:
        """Duración de la ejecución en segundos."""
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()
    
    class Config:
        """Configuración del modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class Task(BaseModel):
    """
    Tarea a ejecutar por un agente (modelo legacy para compatibilidad).
    
    Las tareas representan trabajos que los agentes deben realizar.
    Pueden generar Proposals si requieren acciones con impacto.
    """
    
    # Identificación
    id: UUID = Field(default_factory=uuid4, description="ID único de la tarea")
    agent_id: str = Field(..., description="ID del agente responsable")
    
    # Descripción
    name: str = Field(..., min_length=3, max_length=200, description="Nombre de la tarea")
    description: Optional[str] = Field(default=None, description="Descripción detallada")
    
    # Clasificación
    type: TaskType = Field(default=TaskType.ONE_TIME, description="Tipo de tarea")
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL,
        description="Prioridad de ejecución"
    )
    
    # Estado
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Estado actual"
    )
    
    # Configuración
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuración específica de la tarea"
    )
    
    # Programación
    schedule: Optional[str] = Field(
        default=None,
        description="Expresión cron para tareas recurrentes"
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="Próxima ejecución programada"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Fecha de creación"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="Inicio de ejecución"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Fin de ejecución"
    )
    
    # Resultados
    result: Optional[dict[str, Any]] = Field(
        default=None,
        description="Resultado de la ejecución"
    )
    error: Optional[str] = Field(
        default=None,
        description="Mensaje de error si falló"
    )
    
    # Métricas
    execution_count: int = Field(
        default=0,
        description="Número de ejecuciones"
    )
    last_execution_duration: Optional[float] = Field(
        default=None,
        description="Duración de última ejecución en segundos"
    )
    proposals_generated: int = Field(
        default=0,
        description="Propuestas generadas en última ejecución"
    )
    
    # Relaciones
    parent_task_id: Optional[UUID] = Field(
        default=None,
        description="ID de tarea padre (para subtareas)"
    )
    
    class Config:
        """Configuración del modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    
    def start(self) -> "Task":
        """Marca la tarea como iniciada."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        self.execution_count += 1
        return self
    
    def complete(
        self,
        result: Optional[dict] = None,
        proposals_count: int = 0
    ) -> "Task":
        """Marca la tarea como completada."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        if self.started_at:
            self.last_execution_duration = (
                self.completed_at - self.started_at
            ).total_seconds()
        if result:
            self.result = result
        self.proposals_generated = proposals_count
        return self
    
    def fail(self, error: str) -> "Task":
        """Marca la tarea como fallida."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error
        if self.started_at:
            self.last_execution_duration = (
                self.completed_at - self.started_at
            ).total_seconds()
        return self
    
    def cancel(self) -> "Task":
        """Cancela la tarea."""
        self.status = TaskStatus.CANCELLED
        return self
    
    def pause(self) -> "Task":
        """Pausa la tarea."""
        self.status = TaskStatus.PAUSED
        return self
    
    def resume(self) -> "Task":
        """Reanuda la tarea."""
        self.status = TaskStatus.PENDING
        return self
    
    def is_runnable(self) -> bool:
        """Indica si la tarea puede ejecutarse."""
        return self.status in (TaskStatus.PENDING, TaskStatus.SCHEDULED)
    
    def is_active(self) -> bool:
        """Indica si la tarea está activa."""
        return self.status in (
            TaskStatus.PENDING,
            TaskStatus.SCHEDULED,
            TaskStatus.RUNNING,
            TaskStatus.PAUSED
        )
    
    @property
    def priority_order(self) -> int:
        """Retorna orden numérico de prioridad (mayor = más urgente)."""
        priority_map = {
            TaskPriority.LOW: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.HIGH: 3,
            TaskPriority.URGENT: 4,
            TaskPriority.CRITICAL: 5,
        }
        return priority_map[self.priority]
