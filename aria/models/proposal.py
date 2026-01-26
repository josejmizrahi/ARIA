"""
ARIA - Modelo Proposal
=======================

Representa una propuesta de acción que requiere aprobación humana.
Los agentes generan Proposals, el humano las aprueba o rechaza.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


class ProposalStatus(str, Enum):
    """Estados posibles de una propuesta."""
    PENDING = "pending"          # Esperando revisión
    APPROVED = "approved"        # Aprobada por humano
    REJECTED = "rejected"        # Rechazada por humano
    MODIFIED = "modified"        # Modificada antes de aprobar
    EXPIRED = "expired"          # Expirada sin respuesta
    EXECUTING = "executing"      # En ejecución
    COMPLETED = "completed"      # Ejecutada exitosamente
    FAILED = "failed"            # Falló durante ejecución


class ProposalType(str, Enum):
    """Tipos de propuesta según el área."""
    COBRANZA = "cobranza"           # Gestión de cobros
    INVENTARIO = "inventario"       # Gestión de inventario
    COMPRAS = "compras"             # Órdenes de compra
    VENTAS = "ventas"               # Gestión de ventas
    CONTABILIDAD = "contabilidad"   # Asientos contables
    RRHH = "rrhh"                   # Recursos humanos
    GENERAL = "general"             # Propósito general


class ProposalAction(str, Enum):
    """Acciones que puede proponer un agente."""
    # Cobranza
    SEND_REMINDER = "send_reminder"           # Enviar recordatorio
    SEND_PAYMENT_REQUEST = "send_payment"     # Enviar solicitud de pago
    APPLY_LATE_FEE = "apply_late_fee"         # Aplicar cargo por mora
    BLOCK_CREDIT = "block_credit"             # Bloquear crédito
    SCHEDULE_CALL = "schedule_call"           # Programar llamada
    
    # Inventario
    CREATE_PURCHASE_ORDER = "create_po"       # Crear orden de compra
    ADJUST_STOCK = "adjust_stock"             # Ajustar inventario
    TRANSFER_STOCK = "transfer_stock"         # Transferir entre almacenes
    
    # Ventas
    CREATE_QUOTATION = "create_quotation"     # Crear cotización
    APPLY_DISCOUNT = "apply_discount"         # Aplicar descuento
    
    # General
    CREATE_RECORD = "create_record"           # Crear registro
    UPDATE_RECORD = "update_record"           # Actualizar registro
    DELETE_RECORD = "delete_record"           # Eliminar registro
    EXECUTE_ACTION = "execute_action"         # Ejecutar acción


class Priority(str, Enum):
    """Prioridades de propuesta."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Proposal(BaseModel):
    """
    Propuesta de acción generada por un agente.
    
    Una propuesta representa una acción que el agente quiere ejecutar
    pero que requiere aprobación humana antes de proceder.
    
    Ejemplo:
        proposal = Proposal(
            agent_id="cobranza_agent",
            type=ProposalType.COBRANZA,
            action=ProposalAction.SEND_REMINDER,
            title="Enviar recordatorio de pago",
            description="Cliente XYZ tiene factura vencida por $5,000",
            target_model="account.move",
            target_ids=[123],
            payload={"template_id": 5, "partner_id": 42}
        )
    """
    
    # Identificación
    id: UUID = Field(default_factory=uuid4, description="ID único de la propuesta")
    agent_id: str = Field(..., description="ID del agente que genera la propuesta")
    
    # Clasificación
    type: ProposalType = Field(..., description="Tipo/área de la propuesta")
    action: ProposalAction = Field(..., description="Acción propuesta")
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Prioridad de la propuesta"
    )
    
    # Descripción
    title: str = Field(..., min_length=5, max_length=200, description="Título corto")
    description: str = Field(..., min_length=10, description="Descripción detallada")
    
    # Contexto detallado
    situation_summary: Optional[str] = Field(
        default=None,
        description="Resumen de la situación detectada"
    )
    proposed_action_detail: Optional[str] = Field(
        default=None,
        description="Detalle de la acción propuesta"
    )
    
    # Contexto Odoo
    target_model: Optional[str] = Field(
        default=None,
        description="Modelo de Odoo afectado"
    )
    target_ids: list[int] = Field(
        default_factory=list,
        description="IDs de registros afectados"
    )
    
    # Método Odoo a ejecutar
    odoo_method: Optional[str] = Field(
        default=None,
        description="Método de Odoo a llamar"
    )
    odoo_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros para el método de Odoo"
    )
    
    # Datos para ejecución
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Datos necesarios para ejecutar la acción"
    )
    
    # Datos de soporte y alternativas
    supporting_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Datos de soporte para la decisión"
    )
    alternatives: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Acciones alternativas disponibles"
    )
    
    # Estado
    status: ProposalStatus = Field(
        default=ProposalStatus.PENDING,
        description="Estado actual de la propuesta"
    )
    
    # Metadatos de riesgo
    risk_level: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Nivel de riesgo (1=bajo, 5=crítico)"
    )
    reversible: bool = Field(
        default=True,
        description="Indica si la acción es reversible"
    )
    estimated_impact: Optional[str] = Field(
        default=None,
        description="Descripción del impacto estimado"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Fecha de creación"
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de expiración"
    )
    reviewed_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de revisión"
    )
    executed_at: Optional[datetime] = Field(
        default=None,
        description="Fecha de ejecución"
    )
    
    # Respuesta humana
    reviewer_notes: Optional[str] = Field(
        default=None,
        description="Notas del revisor"
    )
    resolved_by: Optional[str] = Field(
        default=None,
        description="Quién resolvió la propuesta"
    )
    
    # Resultado
    execution_result: Optional[dict[str, Any]] = Field(
        default=None,
        description="Resultado de la ejecución"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Mensaje de error si falló"
    )
    
    class Config:
        """Configuración del modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
    
    @computed_field
    @property
    def short_id(self) -> str:
        """Retorna los primeros 8 caracteres del ID."""
        return str(self.id)[:8]
    
    @computed_field
    @property
    def priority_emoji(self) -> str:
        """Retorna emoji según prioridad."""
        emoji_map = {
            Priority.LOW: "🟢",
            Priority.MEDIUM: "🟡",
            Priority.HIGH: "🟠",
            Priority.CRITICAL: "🔴",
        }
        return emoji_map.get(self.priority, "⚪")
    
    @computed_field
    @property
    def risk_emoji(self) -> str:
        """Retorna emoji según nivel de riesgo."""
        return "🟢🟡🟠🔴🚨"[self.risk_level - 1]
    
    def approve(self, notes: Optional[str] = None, by: str = "admin") -> "Proposal":
        """Marca la propuesta como aprobada."""
        self.status = ProposalStatus.APPROVED
        self.reviewed_at = datetime.now()
        self.resolved_by = by
        if notes:
            self.reviewer_notes = notes
        return self
    
    def reject(self, notes: Optional[str] = None, by: str = "admin") -> "Proposal":
        """Marca la propuesta como rechazada."""
        self.status = ProposalStatus.REJECTED
        self.reviewed_at = datetime.now()
        self.resolved_by = by
        if notes:
            self.reviewer_notes = notes
        return self
    
    def mark_executing(self) -> "Proposal":
        """Marca la propuesta como en ejecución."""
        self.status = ProposalStatus.EXECUTING
        return self
    
    def mark_completed(self, result: Optional[dict] = None) -> "Proposal":
        """Marca la propuesta como completada."""
        self.status = ProposalStatus.COMPLETED
        self.executed_at = datetime.now()
        if result:
            self.execution_result = result
        return self
    
    def mark_failed(self, error: str) -> "Proposal":
        """Marca la propuesta como fallida."""
        self.status = ProposalStatus.FAILED
        self.executed_at = datetime.now()
        self.error_message = error
        return self
    
    def is_pending(self) -> bool:
        """Indica si la propuesta está pendiente."""
        return self.status == ProposalStatus.PENDING
    
    def is_actionable(self) -> bool:
        """Indica si la propuesta puede ejecutarse."""
        return self.status == ProposalStatus.APPROVED
    
    def to_notification_text(self) -> str:
        """Genera texto para notificación (formato Telegram/Markdown)."""
        reversible_text = "✅ Reversible" if self.reversible else "⚠️ Irreversible"
        
        text = f"""
{self.priority_emoji} *{self.title}*

🆔 ID: `{self.short_id}`
🤖 Agente: {self.agent_id}
📋 Tipo: {self.type.value.title()}
🎯 Acción: {self.action.value}
{reversible_text}

📝 *Descripción:*
{self.description}
""".strip()

        if self.situation_summary:
            text += f"\n\n📊 *Situación:*\n```\n{self.situation_summary}\n```"
        
        if self.proposed_action_detail:
            text += f"\n\n💡 *Acción propuesta:*\n{self.proposed_action_detail}"
        
        if self.target_model:
            text += f"\n\n🔗 Afecta: `{self.target_model}` (IDs: {self.target_ids or 'N/A'})"
        
        text += f"\n\n⏰ Creado: {self.created_at.strftime('%Y-%m-%d %H:%M')}"
        
        return text
    
    def to_short_text(self) -> str:
        """Genera texto corto para listas."""
        return f"{self.priority_emoji} `{self.short_id}` - *{self.agent_id}*: {self.title}"
