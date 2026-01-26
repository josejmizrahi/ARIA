"""
ARIA - Modelos de Datos
========================

Modelos Pydantic para representar entidades del sistema.
"""

from aria.models.notification import (
    Notification,
    NotificationPriority,
    NotificationStatus,
    NotificationType,
)
from aria.models.proposal import (
    Priority,
    Proposal,
    ProposalAction,
    ProposalStatus,
    ProposalType,
)
from aria.models.task import (
    Task,
    TaskDefinition,
    TaskPriority,
    TaskResult,
    TaskStatus,
    TaskType,
)

__all__ = [
    # Proposal
    "Proposal",
    "ProposalAction",
    "ProposalStatus",
    "ProposalType",
    "Priority",
    # Task
    "Task",
    "TaskDefinition",
    "TaskResult",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
    # Notification
    "Notification",
    "NotificationStatus",
    "NotificationPriority",
    "NotificationType",
]
