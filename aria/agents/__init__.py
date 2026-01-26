"""
ARIA - Agentes
===============

Agentes autónomos de ARIA.

Cada agente monitorea un área específica del negocio
y propone acciones cuando detecta situaciones relevantes.

Agentes disponibles:
- CEO: Vista ejecutiva consolidada
- Cobranza: Gestión de cuentas por cobrar
- Ventas: Gestión comercial
- Compras: Gestión de abastecimiento
- Finanzas: Tesorería y flujo de caja
- Contabilidad: Cierre y cumplimiento fiscal
- Inventario: Control de stock y almacenes
- RRHH: Recursos humanos
- Producción: Control de manufactura y MRP
- Costos: Control de costos y márgenes
- CRM: Gestión de oportunidades
- Sistema: Monitoreo del sistema
"""

from aria.agents.base import BaseAgent
from aria.agents.registry import (
    AgentRegistry,
    agent_registry,
    get_agent,
    register_agent,
)

# Agentes
from aria.agents.ceo_agent import CEOAgent, create_ceo_agent
from aria.agents.receivables_agent import ReceivablesAgent, create_receivables_agent
from aria.agents.sales_agent import SalesAgent, create_sales_agent
from aria.agents.purchase_agent import PurchaseAgent, create_purchase_agent
from aria.agents.finance_agent import FinanceAgent, create_finance_agent
from aria.agents.accounting_agent import AccountingAgent, create_accounting_agent
from aria.agents.inventory_agent import InventoryAgent, create_inventory_agent
from aria.agents.hr_agent import HRAgent, create_hr_agent
from aria.agents.manufacturing_agent import ManufacturingAgent, create_manufacturing_agent
from aria.agents.system_agent import SystemAgent, create_system_agent
from aria.agents.crm_agent import CRMAgent, create_crm_agent
from aria.agents.cost_agent import CostAgent, create_cost_agent

__all__ = [
    # Base
    "BaseAgent",
    
    # Registry
    "AgentRegistry",
    "agent_registry",
    "register_agent",
    "get_agent",
    
    # Agents
    "CEOAgent",
    "create_ceo_agent",
    "ReceivablesAgent",
    "create_receivables_agent",
    "SalesAgent",
    "create_sales_agent",
    "PurchaseAgent",
    "create_purchase_agent",
    "FinanceAgent",
    "create_finance_agent",
    "AccountingAgent",
    "create_accounting_agent",
    "InventoryAgent",
    "create_inventory_agent",
    "HRAgent",
    "create_hr_agent",
    "ManufacturingAgent",
    "create_manufacturing_agent",
    "SystemAgent",
    "create_system_agent",
    "CRMAgent",
    "create_crm_agent",
    "CostAgent",
    "create_cost_agent",
    
    # Helpers
    "initialize_all_agents",
    "get_available_agents",
]


def initialize_all_agents() -> None:
    """
    Inicializa y registra todos los agentes disponibles.
    
    Llamar esta función al iniciar la aplicación.
    """
    from aria.utils.logger import get_logger
    logger = get_logger("aria.agents")
    
    # Funciones de creación de agentes
    agent_factories = [
        ("ceo", create_ceo_agent),
        ("cobranza", create_receivables_agent),
        ("ventas", create_sales_agent),
        ("compras", create_purchase_agent),
        ("finanzas", create_finance_agent),
        ("contabilidad", create_accounting_agent),
        ("inventario", create_inventory_agent),
        ("rrhh", create_hr_agent),
        ("produccion", create_manufacturing_agent),
        ("sistema", create_system_agent),
        ("crm", create_crm_agent),
        ("costos", create_cost_agent),
    ]
    
    # Crear y registrar agentes
    for name, create_fn in agent_factories:
        try:
            agent = create_fn()
            register_agent(agent)
        except Exception as e:
            logger.error(f"Error registrando agente {name}: {e}")


def get_available_agents() -> list[str]:
    """Retorna lista de nombres de agentes disponibles."""
    return agent_registry.list_names()
