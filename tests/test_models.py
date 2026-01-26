"""
Tests para los modelos de datos.
"""

from datetime import datetime
from uuid import UUID

import pytest

from aria.models import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
    Proposal,
    ProposalAction,
    ProposalStatus,
    ProposalType,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)


class TestProposal:
    """Tests para el modelo Proposal."""
    
    def test_create_proposal(self):
        """Crear propuesta con valores mínimos."""
        proposal = Proposal(
            agent_id="test_agent",
            type=ProposalType.COBRANZA,
            action=ProposalAction.SEND_REMINDER,
            title="Test proposal title",
            description="Test proposal description with details"
        )
        
        assert proposal.agent_id == "test_agent"
        assert proposal.type == ProposalType.COBRANZA
        assert proposal.action == ProposalAction.SEND_REMINDER
        assert proposal.status == ProposalStatus.PENDING
        assert isinstance(proposal.id, UUID)
    
    def test_proposal_approve(self):
        """Aprobar propuesta cambia estado."""
        proposal = Proposal(
            agent_id="test",
            type=ProposalType.GENERAL,
            action=ProposalAction.CREATE_RECORD,
            title="Test title here",
            description="Test description here"
        )
        
        proposal.approve(notes="Aprobado por admin")
        
        assert proposal.status == ProposalStatus.APPROVED
        assert proposal.reviewer_notes == "Aprobado por admin"
        assert proposal.reviewed_at is not None
    
    def test_proposal_reject(self):
        """Rechazar propuesta cambia estado."""
        proposal = Proposal(
            agent_id="test",
            type=ProposalType.GENERAL,
            action=ProposalAction.DELETE_RECORD,
            title="Test title here",
            description="Test description here"
        )
        
        proposal.reject(notes="No autorizado")
        
        assert proposal.status == ProposalStatus.REJECTED
        assert proposal.reviewer_notes == "No autorizado"
    
    def test_proposal_is_pending(self):
        """Verificar estado pendiente."""
        proposal = Proposal(
            agent_id="test",
            type=ProposalType.GENERAL,
            action=ProposalAction.UPDATE_RECORD,
            title="Test title here",
            description="Test description here"
        )
        
        assert proposal.is_pending()
        proposal.approve()
        assert not proposal.is_pending()
    
    def test_proposal_risk_level_bounds(self):
        """Risk level debe estar entre 1-5."""
        # Válido
        proposal = Proposal(
            agent_id="test",
            type=ProposalType.GENERAL,
            action=ProposalAction.EXECUTE_ACTION,
            title="Test title here",
            description="Test description here",
            risk_level=5
        )
        assert proposal.risk_level == 5
        
        # Inválido
        with pytest.raises(ValueError):
            Proposal(
                agent_id="test",
                type=ProposalType.GENERAL,
                action=ProposalAction.EXECUTE_ACTION,
                title="Test title",
                description="Test description",
                risk_level=10
            )


class TestTask:
    """Tests para el modelo Task."""
    
    def test_create_task(self):
        """Crear tarea con valores mínimos."""
        task = Task(
            agent_id="test_agent",
            name="Test Task Name"
        )
        
        assert task.agent_id == "test_agent"
        assert task.name == "Test Task Name"
        assert task.status == TaskStatus.PENDING
        assert task.type == TaskType.ONE_TIME
        assert task.priority == TaskPriority.NORMAL
    
    def test_task_lifecycle(self):
        """Ciclo de vida de tarea: start -> complete."""
        task = Task(agent_id="test", name="Lifecycle test")
        
        assert task.is_runnable()
        assert task.execution_count == 0
        
        task.start()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        assert task.execution_count == 1
        
        task.complete(result={"processed": 10}, proposals_count=2)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.result == {"processed": 10}
        assert task.proposals_generated == 2
    
    def test_task_fail(self):
        """Tarea que falla."""
        task = Task(agent_id="test", name="Fail test")
        task.start()
        task.fail("Error de conexión")
        
        assert task.status == TaskStatus.FAILED
        assert task.error == "Error de conexión"
    
    def test_priority_order(self):
        """Orden numérico de prioridades."""
        low = Task(agent_id="t", name="L", priority=TaskPriority.LOW)
        normal = Task(agent_id="t", name="N", priority=TaskPriority.NORMAL)
        critical = Task(agent_id="t", name="C", priority=TaskPriority.CRITICAL)
        
        assert low.priority_order < normal.priority_order < critical.priority_order


class TestNotification:
    """Tests para el modelo Notification."""
    
    def test_create_notification(self):
        """Crear notificación básica."""
        notification = Notification(
            title="Test Notification",
            message="This is a test message"
        )
        
        assert notification.title == "Test Notification"
        assert notification.type == NotificationType.INFO
        assert notification.status == NotificationStatus.PENDING
    
    def test_notification_mark_sent(self):
        """Marcar notificación como enviada."""
        notification = Notification(
            title="Test",
            message="Test message"
        )
        
        notification.mark_sent("telegram")
        
        assert notification.status == NotificationStatus.SENT
        assert notification.channel == "telegram"
        assert notification.sent_at is not None
    
    def test_approval_request(self):
        """Notificación de solicitud de aprobación."""
        notification = Notification(
            type=NotificationType.APPROVAL_REQUEST,
            priority=NotificationPriority.HIGH,
            title="Aprobación requerida",
            message="El agente necesita tu aprobación"
        )
        
        assert notification.is_approval_request()
        assert notification.requires_action()
        
        notification.set_response("approved")
        assert not notification.requires_action()
    
    def test_get_emoji(self):
        """Emojis correctos según tipo."""
        info = Notification(title="T", message="M", type=NotificationType.INFO)
        success = Notification(title="T", message="M", type=NotificationType.SUCCESS)
        error = Notification(title="T", message="M", type=NotificationType.ERROR)
        
        assert info.get_emoji() == "ℹ️"
        assert success.get_emoji() == "✅"
        assert error.get_emoji() == "❌"
