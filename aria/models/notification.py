"""
ARIA - Modelo Notification
===========================

Representa una notificación para el usuario humano.
Puede ser informativa, una alerta, o solicitar acción.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NotificationStatus(str, Enum):
    """Estados de una notificación."""
    PENDING = "pending"          # Pendiente de envío
    SENT = "sent"                # Enviada
    DELIVERED = "delivered"      # Entregada/confirmada
    READ = "read"                # Leída por usuario
    FAILED = "failed"            # Falló el envío


class NotificationPriority(str, Enum):
    """Prioridades de notificación."""
    LOW = "low"                  # Informativa, no urgente
    MEDIUM = "medium"            # Normal
    HIGH = "high"                # Importante
    CRITICAL = "critical"        # Urgente, requiere atención


class NotificationType(str, Enum):
    """Tipos de notificación."""
    INFO = "info"                # Informativa
    SUCCESS = "success"          # Operación exitosa
    WARNING = "warning"          # Advertencia
    ERROR = "error"              # Error
    APPROVAL_REQUEST = "approval_request"  # Solicita aprobación
    STATUS_UPDATE = "status_update"        # Actualización de estado


class Notification(BaseModel):
    """
    Notificación para el usuario.
    
    Las notificaciones informan al usuario sobre eventos,
    solicitan aprobaciones, o alertan sobre problemas.
    
    Ejemplo:
        notification = Notification(
            type=NotificationType.APPROVAL_REQUEST,
            priority=NotificationPriority.HIGH,
            title="Aprobación requerida",
            message="El agente de cobranza necesita tu aprobación...",
            proposal_id=proposal.id
        )
    """
    
    # Identificación
    id: UUID = Field(default_factory=uuid4, description="ID único")
    
    # Clasificación
    type: NotificationType = Field(
        default=NotificationType.INFO,
        description="Tipo de notificación"
    )
    priority: NotificationPriority = Field(
        default=NotificationPriority.MEDIUM,
        description="Prioridad"
    )
    
    # Contenido
    title: str = Field(..., min_length=3, max_length=200, description="Título")
    message: str = Field(..., min_length=5, description="Mensaje completo")
    
    # Datos adicionales
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Datos adicionales estructurados"
    )
    
    # Relaciones
    proposal_id: Optional[str] = Field(
        default=None,
        description="ID de propuesta relacionada"
    )
    task_id: Optional[UUID] = Field(
        default=None,
        description="ID de tarea relacionada"
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="ID del agente que genera la notificación"
    )
    
    # Estado
    status: NotificationStatus = Field(
        default=NotificationStatus.PENDING,
        description="Estado de envío"
    )
    
    # Canal
    channel: Optional[str] = Field(
        default=None,
        description="Canal por el que se envió"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Fecha de creación"
    )
    sent_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de envío"
    )
    delivered_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de entrega"
    )
    read_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de lectura"
    )
    
    # Respuesta (para approval_request)
    response: Optional[str] = Field(
        default=None,
        description="Respuesta del usuario"
    )
    responded_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de respuesta"
    )
    
    class Config:
        """Configuración del modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    
    def mark_sent(self, channel: str) -> "Notification":
        """Marca como enviada."""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now()
        self.channel = channel
        return self
    
    def mark_delivered(self) -> "Notification":
        """Marca como entregada."""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.now()
        return self
    
    def mark_read(self) -> "Notification":
        """Marca como leída."""
        self.status = NotificationStatus.READ
        self.read_at = datetime.now()
        return self
    
    def mark_failed(self) -> "Notification":
        """Marca como fallida."""
        self.status = NotificationStatus.FAILED
        return self
    
    def set_response(self, response: str) -> "Notification":
        """Registra respuesta del usuario."""
        self.response = response
        self.responded_at = datetime.now()
        return self
    
    def is_approval_request(self) -> bool:
        """Indica si es una solicitud de aprobación."""
        return self.type == NotificationType.APPROVAL_REQUEST
    
    def requires_action(self) -> bool:
        """Indica si requiere acción del usuario."""
        return self.type == NotificationType.APPROVAL_REQUEST and self.response is None
    
    def get_emoji(self) -> str:
        """Retorna emoji según el tipo."""
        emoji_map = {
            NotificationType.INFO: "ℹ️",
            NotificationType.SUCCESS: "✅",
            NotificationType.WARNING: "⚠️",
            NotificationType.ERROR: "❌",
            NotificationType.APPROVAL_REQUEST: "🔔",
            NotificationType.STATUS_UPDATE: "📊",
        }
        return emoji_map.get(self.type, "📌")
    
    def to_text(self) -> str:
        """Genera texto formateado para la notificación."""
        priority_indicator = ""
        if self.priority == NotificationPriority.CRITICAL:
            priority_indicator = "🚨 URGENTE: "
        elif self.priority == NotificationPriority.HIGH:
            priority_indicator = "❗ "
        
        return f"""
{self.get_emoji()} {priority_indicator}**{self.title}**

{self.message}

📅 {self.created_at.strftime('%Y-%m-%d %H:%M')}
""".strip()
    
    def to_short_text(self) -> str:
        """Genera texto corto para resumen."""
        return f"{self.get_emoji()} {self.title}"
