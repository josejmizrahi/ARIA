"""
ARIA - Autonomous Resource Intelligence Agent
=============================================

Sistema de agentes autónomos para gestión de ERP Odoo.

Módulos principales:
- config: Configuración centralizada
- odoo_client: Cliente Odoo con retry y singleton
- models: Modelos de datos (Proposal, Task, Notification)
- utils: Utilidades (logger, helpers)
- agents: Agentes especializados

Fase 1:
- notification_manager: Sistema de notificaciones multicanal
- approval_engine: Motor de aprobaciones con Redis
- action_executor: Ejecutor de acciones aprobadas
- telegram_bot: Bot de Telegram interactivo
"""

__version__ = "0.2.0"
__author__ = "ARIA Team"

from aria.config import settings

__all__ = [
    "settings",
    "__version__",
]

# Lazy imports para evitar dependencias circulares
def get_odoo_client():
    """Obtiene cliente Odoo."""
    from aria.odoo_client import OdooClient
    return OdooClient.get_instance()

def get_notification_manager():
    """Obtiene gestor de notificaciones."""
    from aria.notification_manager import notification_manager
    return notification_manager

def get_approval_engine():
    """Obtiene motor de aprobaciones."""
    from aria.approval_engine import approval_engine
    return approval_engine

def get_action_executor():
    """Obtiene ejecutor de acciones."""
    from aria.action_executor import action_executor
    return action_executor

def get_telegram_bot():
    """Obtiene bot de Telegram."""
    from aria.telegram_bot import telegram_bot
    return telegram_bot
