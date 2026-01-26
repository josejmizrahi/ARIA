"""
Sistema de Inspección Contextual para ARIA.

Este módulo proporciona inspectores que analizan cada área del negocio
en 4 niveles de profundidad, identificando hallazgos con sus impactos
en otros agentes y proponiendo soluciones coordinadas.

Uso:
    from aria.inspection import InventoryInspector
    
    inspector = InventoryInspector()
    report = inspector.inspect()
    
    print(report.get_markdown_summary())
"""

from .models import (
    AgentDependency,
    AgentImpact,
    AreaContext,
    Finding,
    ImpactLevel,
    ImpactType,
    InspectionReport,
)
from .context_inspector import BaseContextInspector

# Inspectores se importan bajo demanda para evitar dependencias circulares
__all__ = [
    # Modelos
    "AgentDependency",
    "AgentImpact",
    "AreaContext",
    "Finding",
    "ImpactLevel",
    "ImpactType",
    "InspectionReport",
    # Base
    "BaseContextInspector",
]


def get_inspector(agent_name: str) -> BaseContextInspector:
    """
    Factory para obtener el inspector de un agente.
    
    Args:
        agent_name: Nombre del agente (ej: "inventario", "cobranza")
        
    Returns:
        Instancia del inspector correspondiente
        
    Raises:
        ValueError: Si el agente no tiene inspector definido
    """
    inspectors = {
        "inventario": "InventoryInspector",
        "cobranza": "ReceivablesInspector",
        "ventas": "SalesInspector",
        "compras": "PurchaseInspector",
        "finanzas": "FinanceInspector",
        "produccion": "ManufacturingInspector",
        "rrhh": "HRInspector",
        "costos": "CostInspector",
        "crm": "CRMInspector",
        "contabilidad": "AccountingInspector",
        "ceo": "CEOInspector",
        "sistema": "SystemInspector",
    }
    
    if agent_name not in inspectors:
        raise ValueError(f"No existe inspector para el agente: {agent_name}")
    
    class_name = inspectors[agent_name]
    module_map = {
        "InventoryInspector": "inventory_inspector",
        "ReceivablesInspector": "receivables_inspector",
        "SalesInspector": "sales_inspector",
        "PurchaseInspector": "purchase_inspector",
        "FinanceInspector": "finance_inspector",
        "ManufacturingInspector": "manufacturing_inspector",
        "HRInspector": "hr_inspector",
        "CostInspector": "cost_inspector",
        "CRMInspector": "crm_inspector",
        "AccountingInspector": "accounting_inspector",
        "CEOInspector": "ceo_inspector",
        "SystemInspector": "system_inspector",
    }
    
    module_name = module_map[class_name]
    
    # Import dinámico
    import importlib
    module = importlib.import_module(f".{module_name}", package="aria.inspection")
    inspector_class = getattr(module, class_name)
    
    return inspector_class()


def get_all_inspectors() -> dict[str, BaseContextInspector]:
    """
    Obtiene todos los inspectores disponibles.
    
    Returns:
        Diccionario {nombre_agente: instancia_inspector}
    """
    agent_names = [
        "inventario", "cobranza", "ventas", "compras",
        "finanzas", "produccion", "rrhh", "costos",
        "crm", "contabilidad", "ceo", "sistema",
    ]
    
    inspectors = {}
    for name in agent_names:
        try:
            inspectors[name] = get_inspector(name)
        except (ImportError, AttributeError) as e:
            # El inspector aún no está implementado
            pass
    
    return inspectors


def run_all_inspections(
    max_level: int = 4,
    create_proposals: bool = False,
    min_severity_for_proposal: ImpactLevel = ImpactLevel.HIGH,
) -> dict[str, InspectionReport]:
    """
    Ejecuta todos los inspectores disponibles.
    
    Args:
        max_level: Nivel máximo de inspección (1-4)
        create_proposals: Si True, crea propuestas para hallazgos graves
        min_severity_for_proposal: Severidad mínima para crear propuestas
        
    Returns:
        Diccionario {nombre_agente: reporte}
    """
    inspectors = get_all_inspectors()
    reports = {}
    total_proposals = 0
    
    for name, inspector in inspectors.items():
        try:
            reports[name] = inspector.inspect(
                max_level=max_level,
                create_proposals=create_proposals,
                min_severity_for_proposal=min_severity_for_proposal,
            )
            total_proposals += reports[name].proposals_created
        except Exception as e:
            # Crear reporte de error
            reports[name] = InspectionReport(
                inspector_name=inspector.__class__.__name__,
                agent_name=name,
                context=AreaContext(area_name=name, status="error"),
                findings=[
                    Finding(
                        level=4,
                        category="Error",
                        title=f"Error ejecutando inspector de {name}",
                        description=str(e),
                        severity=ImpactLevel.CRITICAL,
                    )
                ],
            )
    
    if create_proposals and total_proposals > 0:
        from aria.utils.logger import get_logger
        logger = get_logger("inspection")
        logger.info(f"Total de propuestas creadas: {total_proposals}")
    
    return reports
