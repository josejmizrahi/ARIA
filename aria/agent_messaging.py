"""
Sistema de Mensajería entre Agentes.

Permite que los agentes se comuniquen entre sí para:
- Compartir información relevante
- Colaborar en la resolución de problemas
- Validar datos antes de tomar decisiones
- Aprender de experiencias previas
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("aria.agent_messaging")


class MessageType(str, Enum):
    """Tipos de mensajes entre agentes."""
    QUERY = "query"                    # Pregunta a otro agente
    RESPONSE = "response"              # Respuesta a una pregunta
    ALERT = "alert"                    # Alerta sobre un problema
    DATA_REQUEST = "data_request"      # Solicitud de datos específicos
    DATA_PROVIDED = "data_provided"    # Datos proporcionados
    VALIDATION_REQUEST = "validation"  # Solicitud de validación
    COLLABORATION = "collaboration"    # Propuesta de colaboración
    LEARNING = "learning"              # Compartir aprendizaje


class MessagePriority(str, Enum):
    """Prioridad del mensaje."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentMessage(BaseModel):
    """Mensaje entre agentes."""
    
    id: UUID = Field(default_factory=uuid4)
    from_agent: str = Field(..., description="Agente que envía el mensaje")
    to_agent: Optional[str] = Field(None, description="Agente destinatario (None = broadcast)")
    message_type: MessageType = Field(..., description="Tipo de mensaje")
    priority: MessagePriority = Field(default=MessagePriority.MEDIUM)
    
    # Contenido
    subject: str = Field(..., description="Asunto del mensaje")
    content: str = Field(..., description="Contenido del mensaje")
    data: dict[str, Any] = Field(default_factory=dict, description="Datos estructurados")
    
    # Contexto
    context: dict[str, Any] = Field(default_factory=dict, description="Contexto adicional")
    requires_response: bool = Field(default=False, description="Requiere respuesta")
    response_to: Optional[UUID] = Field(None, description="ID del mensaje al que responde")
    
    # Metadatos
    created_at: datetime = Field(default_factory=datetime.now)
    read_at: Optional[datetime] = Field(None)
    responded_at: Optional[datetime] = Field(None)
    
    # Resultado
    response_data: Optional[dict[str, Any]] = Field(None, description="Datos de respuesta")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class AgentMessaging:
    """Sistema de mensajería entre agentes."""
    
    def __init__(self):
        self.messages: list[AgentMessage] = []
        self.message_file = Path(settings.log_dir) / "agent_messages.json"
        self._load_messages()
    
    def _load_messages(self) -> None:
        """Carga mensajes desde archivo."""
        if self.message_file.exists():
            try:
                with open(self.message_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages = [
                        AgentMessage(**msg) for msg in data.get("messages", [])
                    ]
            except Exception as e:
                logger.warning(f"Error cargando mensajes: {e}")
                self.messages = []
    
    def _save_messages(self) -> None:
        """Guarda mensajes en archivo."""
        try:
            self.message_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.message_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "messages": [msg.model_dump() for msg in self.messages],
                    "last_updated": datetime.now().isoformat(),
                }, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Error guardando mensajes: {e}")
    
    def send(
        self,
        from_agent: str,
        to_agent: Optional[str],
        message_type: MessageType,
        subject: str,
        content: str,
        data: Optional[dict] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
        requires_response: bool = False,
        response_to: Optional[UUID] = None,
        context: Optional[dict] = None,
    ) -> AgentMessage:
        """
        Envía un mensaje entre agentes.
        
        Args:
            from_agent: Nombre del agente que envía
            to_agent: Nombre del agente destinatario (None = broadcast a todos)
            message_type: Tipo de mensaje
            subject: Asunto
            content: Contenido del mensaje
            data: Datos estructurados
            priority: Prioridad
            requires_response: Si requiere respuesta
            response_to: ID del mensaje al que responde
            context: Contexto adicional
            
        Returns:
            Mensaje creado
        """
        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            subject=subject,
            content=content,
            data=data or {},
            priority=priority,
            requires_response=requires_response,
            response_to=response_to,
            context=context or {},
        )
        
        self.messages.append(message)
        self._save_messages()
        
        logger.info(
            f"Mensaje enviado: {from_agent} → {to_agent or 'ALL'}: {subject}",
            message_id=str(message.id)[:8]
        )
        
        return message
    
    def query(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        data: Optional[dict] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
    ) -> AgentMessage:
        """Envía una pregunta a otro agente."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.QUERY,
            subject=f"Pregunta de {from_agent}",
            content=question,
            data=data or {},
            priority=priority,
            requires_response=True,
        )
    
    def respond(
        self,
        from_agent: str,
        to_message_id: UUID,
        response: str,
        data: Optional[dict] = None,
    ) -> AgentMessage:
        """Responde a un mensaje."""
        original = self.get_message(to_message_id)
        if not original:
            raise ValueError(f"Mensaje {to_message_id} no encontrado")
        
        response_msg = self.send(
            from_agent=from_agent,
            to_agent=original.from_agent,
            message_type=MessageType.RESPONSE,
            subject=f"Respuesta: {original.subject}",
            content=response,
            data=data or {},
            priority=original.priority,
            response_to=to_message_id,
        )
        
        # Marcar original como respondido
        original.responded_at = datetime.now()
        original.response_data = data
        self._save_messages()
        
        return response_msg
    
    def alert(
        self,
        from_agent: str,
        to_agent: Optional[str],
        alert_subject: str,
        alert_content: str,
        data: Optional[dict] = None,
        priority: MessagePriority = MessagePriority.HIGH,
    ) -> AgentMessage:
        """Envía una alerta a otro agente."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.ALERT,
            subject=alert_subject,
            content=alert_content,
            data=data or {},
            priority=priority,
        )
    
    def request_data(
        self,
        from_agent: str,
        to_agent: str,
        data_request: str,
        fields: Optional[list[str]] = None,
        filters: Optional[dict] = None,
    ) -> AgentMessage:
        """Solicita datos específicos a otro agente."""
        return self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.DATA_REQUEST,
            subject=f"Solicitud de datos: {data_request}",
            content=f"Necesito los siguientes datos: {data_request}",
            data={
                "request": data_request,
                "fields": fields or [],
                "filters": filters or {},
            },
            priority=MessagePriority.MEDIUM,
            requires_response=True,
        )
    
    def get_messages(
        self,
        agent_name: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        unread_only: bool = False,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """Obtiene mensajes filtrados."""
        messages = self.messages
        
        if agent_name:
            messages = [
                m for m in messages
                if m.to_agent == agent_name or m.from_agent == agent_name or m.to_agent is None
            ]
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        if unread_only:
            messages = [m for m in messages if m.read_at is None]
        
        # Ordenar por fecha (más recientes primero)
        messages.sort(key=lambda x: x.created_at, reverse=True)
        
        return messages[:limit]
    
    def get_message(self, message_id: UUID) -> Optional[AgentMessage]:
        """Obtiene un mensaje por ID."""
        return next((m for m in self.messages if m.id == message_id), None)
    
    def mark_read(self, message_id: UUID, agent_name: str) -> None:
        """Marca un mensaje como leído."""
        message = self.get_message(message_id)
        if message and (message.to_agent == agent_name or message.to_agent is None):
            message.read_at = datetime.now()
            self._save_messages()
    
    def get_conversation(self, message_id: UUID) -> list[AgentMessage]:
        """Obtiene una conversación completa (mensaje original + respuestas)."""
        original = self.get_message(message_id)
        if not original:
            return []
        
        conversation = [original]
        
        # Buscar respuestas
        responses = [
            m for m in self.messages
            if m.response_to == message_id
        ]
        
        conversation.extend(sorted(responses, key=lambda x: x.created_at))
        
        return conversation


# Instancia global
_agent_messaging: Optional[AgentMessaging] = None


def get_messaging() -> AgentMessaging:
    """Obtiene la instancia global del sistema de mensajería."""
    global _agent_messaging
    if _agent_messaging is None:
        _agent_messaging = AgentMessaging()
    return _agent_messaging
