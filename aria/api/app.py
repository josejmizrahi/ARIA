"""
ARIA REST API - FastAPI application.

Proporciona endpoints para:
- Gestión de agentes
- Ejecución de tareas
- Aprobación de propuestas
- Dashboard en tiempo real
- WebSocket para notificaciones
- Generación de reportes PDF
"""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

from aria import __version__
from aria.agents import initialize_all_agents
from aria.agents.registry import agent_registry
from aria.approval_engine import approval_engine
from aria.scheduler import task_scheduler
from aria.reports.scheduler import report_scheduler
from aria.utils.logger import get_logger

logger = get_logger("aria.api")


# ==================== Pydantic Models ====================

class AgentInfo(BaseModel):
    """Información de un agente."""
    name: str
    description: str
    tasks: list[dict]
    active: bool


class TaskRunRequest(BaseModel):
    """Request para ejecutar una tarea."""
    dry_run: bool = False


class ProposalAction(BaseModel):
    """Acción sobre una propuesta."""
    reason: str = ""
    approved_by: str = "api"


class HealthResponse(BaseModel):
    """Respuesta de health check."""
    status: str
    version: str
    agents_count: int
    uptime_seconds: float


# ==================== Application Lifecycle ====================

startup_time: datetime | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    global startup_time
    
    logger.info("Iniciando ARIA API...")
    
    # Inicializar agentes
    initialize_all_agents()
    
    # Iniciar todos los agentes
    await agent_registry.start_all()
    
    # Iniciar scheduler (opcional, puede estar deshabilitado)
    # await task_scheduler.start()
    
    startup_time = datetime.now()
    logger.info(f"ARIA API iniciada - {len(agent_registry.list_all())} agentes registrados")
    
    yield
    
    # Cleanup
    logger.info("Deteniendo ARIA API...")
    # await task_scheduler.stop()
    await agent_registry.stop_all()
    logger.info("ARIA API detenida")


def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI."""
    
    application = FastAPI(
        title="ARIA API",
        description="Autonomous Resource Intelligence Agent - REST API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return application


app = create_app()


# ==================== Health & Root ====================

@app.get("/", tags=["Health"])
async def root():
    """Información básica de la API."""
    return {
        "name": "ARIA",
        "description": "Autonomous Resource Intelligence Agent",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"], response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    uptime = (datetime.now() - startup_time).total_seconds() if startup_time else 0
    
    return HealthResponse(
        status="healthy",
        version=__version__,
        agents_count=len(agent_registry.list_all()),
        uptime_seconds=uptime,
    )


# ==================== Agents ====================

@app.get("/api/agents", tags=["Agents"])
async def list_agents():
    """Lista todos los agentes registrados."""
    agents = []
    
    for name, agent in agent_registry.list_all().items():
        info = agent.get_info()
        agents.append({
            "name": name,
            "description": info.get("description", ""),
            "tasks_count": len(info.get("tasks", [])),
            "active": info.get("active", False),
        })
    
    return {"agents": agents, "total": len(agents)}


@app.get("/api/agents/{name}", tags=["Agents"])
async def get_agent(name: str):
    """Obtiene información detallada de un agente."""
    agent = agent_registry.get(name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{name}' no encontrado")
    
    return agent.get_info()


@app.get("/api/agents/{name}/summary", tags=["Agents"])
async def agent_summary(name: str):
    """Obtiene el resumen de estado de un agente."""
    agent = agent_registry.get(name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{name}' no encontrado")
    
    try:
        summary = await agent.get_status_summary()
        return summary
    except Exception as e:
        logger.error(f"Error obteniendo summary de {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{name}/start", tags=["Agents"])
async def start_agent(name: str):
    """Inicia un agente."""
    agent = agent_registry.get(name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{name}' no encontrado")
    
    await agent.start()
    return {"status": "started", "agent": name}


@app.post("/api/agents/{name}/stop", tags=["Agents"])
async def stop_agent(name: str):
    """Detiene un agente."""
    agent = agent_registry.get(name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{name}' no encontrado")
    
    await agent.stop()
    return {"status": "stopped", "agent": name}


# ==================== Tasks ====================

@app.get("/api/tasks", tags=["Tasks"])
async def list_tasks():
    """Lista todas las tareas programadas."""
    tasks = []
    
    for name, agent in agent_registry.list_all().items():
        info = agent.get_info()
        for task in info.get("tasks", []):
            tasks.append({
                "agent": name,
                "task": task.get("name"),
                "schedule": task.get("schedule"),
                "description": task.get("description"),
                "last_run": task.get("last_run"),
            })
    
    return {"tasks": tasks, "total": len(tasks)}


@app.get("/api/tasks/{agent_name}", tags=["Tasks"])
async def list_agent_tasks(agent_name: str):
    """Lista las tareas de un agente específico."""
    agent = agent_registry.get(agent_name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_name}' no encontrado")
    
    info = agent.get_info()
    return {"agent": agent_name, "tasks": info.get("tasks", [])}


@app.post("/api/tasks/{agent_name}/{task_name}/run", tags=["Tasks"])
async def run_task(agent_name: str, task_name: str, request: TaskRunRequest = None):
    """Ejecuta una tarea de un agente."""
    agent = agent_registry.get(agent_name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_name}' no encontrado")
    
    try:
        result = await agent.run_task(task_name)
        
        return {
            "success": result.success,
            "task": task_name,
            "agent": agent_name,
            "duration_seconds": (result.completed_at - result.started_at).total_seconds(),
            "proposals_created": result.proposals_created,
            "records_processed": result.records_processed,
            "data": result.data,
            "error": result.error,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error ejecutando tarea {agent_name}.{task_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Proposals ====================

@app.get("/api/proposals", tags=["Proposals"])
async def list_proposals(
    status: str = Query(None, description="Filtrar por estado: pending, approved, rejected"),
    agent: str = Query(None, description="Filtrar por agente"),
    limit: int = Query(100, ge=1, le=500),
):
    """Lista propuestas."""
    if status == "pending" or status is None:
        proposals = await approval_engine.get_pending()
    else:
        # TODO: Implementar filtrado por otros estados
        proposals = await approval_engine.get_pending()
    
    # Filtrar por agente si se especifica
    if agent:
        proposals = [p for p in proposals if p.agent_name == agent]
    
    return {
        "proposals": [p.model_dump() for p in proposals[:limit]],
        "total": len(proposals),
    }


@app.get("/api/proposals/{proposal_id}", tags=["Proposals"])
async def get_proposal(proposal_id: str):
    """Obtiene una propuesta específica."""
    proposal = await approval_engine.get(proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Propuesta '{proposal_id}' no encontrada")
    
    return proposal.model_dump()


@app.post("/api/proposals/{proposal_id}/approve", tags=["Proposals"])
async def approve_proposal(proposal_id: str, action: ProposalAction = None):
    """Aprueba una propuesta."""
    action = action or ProposalAction()
    
    try:
        proposal = await approval_engine.approve(
            proposal_id,
            approved_by=action.approved_by,
        )
        
        return {
            "status": "approved",
            "proposal_id": proposal_id,
            "proposal": proposal.model_dump() if proposal else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error aprobando propuesta {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/proposals/{proposal_id}/reject", tags=["Proposals"])
async def reject_proposal(proposal_id: str, action: ProposalAction = None):
    """Rechaza una propuesta."""
    action = action or ProposalAction()
    
    try:
        proposal = await approval_engine.reject(
            proposal_id,
            reason=action.reason,
            rejected_by=action.approved_by,
        )
        
        return {
            "status": "rejected",
            "proposal_id": proposal_id,
            "reason": action.reason,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error rechazando propuesta {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Dashboard ====================

@app.get("/api/dashboard", tags=["Dashboard"])
async def dashboard():
    """Obtiene datos consolidados para el dashboard."""
    
    # Propuestas pendientes
    pending = await approval_engine.get_pending()
    
    # Agrupar por prioridad
    by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for p in pending:
        priority = p.priority.value if hasattr(p.priority, 'value') else str(p.priority)
        if priority in by_priority:
            by_priority[priority] += 1
    
    # Resúmenes de agentes (excluyendo CEO para evitar recursión)
    agent_summaries = {}
    for name, agent in agent_registry.list_all().items():
        if name != "ceo":
            try:
                agent_summaries[name] = await agent.get_status_summary()
            except Exception as e:
                agent_summaries[name] = {"status": "error", "error": str(e)}
    
    return {
        "timestamp": datetime.now().isoformat(),
        "pending_proposals": {
            "total": len(pending),
            "by_priority": by_priority,
        },
        "agents": agent_summaries,
    }


@app.get("/api/finance/metrics", tags=["Finance"])
async def finance_metrics():
    """Obtiene métricas financieras avanzadas del agente de finanzas."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        # Obtener resumen básico
        summary = await agent.get_status_summary()
        
        # Obtener resultados de tareas recientes si están disponibles
        metrics = {
            "summary": summary,
            "ratios": {},
            "budget": {},
            "profitability": {},
            "forecast": {},
        }
        
        # Intentar obtener datos de tareas ejecutadas recientemente
        # Esto requiere que las tareas hayan sido ejecutadas al menos una vez
        # Por ahora retornamos el resumen y estructura para métricas futuras
        
        return metrics
    except Exception as e:
        logger.error(f"Error obteniendo métricas financieras: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/finance/ratios", tags=["Finance"])
async def finance_ratios():
    """Ejecuta análisis de ratios financieros y retorna resultados."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        # Ejecutar tarea de análisis financiero
        result = await agent.run_task("financial_analysis")
        
        return {
            "success": result.success,
            "data": result.data,
            "executed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
    except Exception as e:
        logger.error(f"Error ejecutando análisis de ratios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/finance/budget", tags=["Finance"])
async def finance_budget():
    """Ejecuta comparación vs presupuesto y retorna resultados."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        result = await agent.run_task("budget_comparison")
        
        return {
            "success": result.success,
            "data": result.data,
            "executed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
    except Exception as e:
        logger.error(f"Error ejecutando comparación de presupuesto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/finance/profitability", tags=["Finance"])
async def finance_profitability():
    """Ejecuta análisis de rentabilidad y retorna resultados."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        result = await agent.run_task("profitability_analysis")
        
        return {
            "success": result.success,
            "data": result.data,
            "executed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
    except Exception as e:
        logger.error(f"Error ejecutando análisis de rentabilidad: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/finance/forecast", tags=["Finance"])
async def finance_forecast():
    """Ejecuta proyecciones anuales y retorna resultados."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        result = await agent.run_task("annual_forecast")
        
        return {
            "success": result.success,
            "data": result.data,
            "executed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
    except Exception as e:
        logger.error(f"Error ejecutando proyecciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/finance/budgets", tags=["Finance"])
async def get_budgets():
    """Obtiene presupuestos actuales desde todas las fuentes."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        from aria.budget_manager import get_budget_manager
        from aria.config import settings
        
        budget_manager = get_budget_manager(settings.odoo.company_id)
        budgets = budget_manager.get_budgets(agent.odoo)
        
        return {
            "budgets": budgets,
            "monthly_revenue": budgets.get("monthly_revenue", 0),
            "monthly_expenses": budgets.get("monthly_expenses", 0),
            "by_category": budgets.get("by_category", {}),
            "source": budgets.get("source", "unknown"),
        }
    except Exception as e:
        logger.error(f"Error obteniendo presupuestos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BudgetUpdate(BaseModel):
    """Request para actualizar presupuestos."""
    monthly_revenue: Optional[float] = None
    monthly_expenses: Optional[float] = None
    by_category: Optional[dict[str, float]] = None


@app.post("/api/finance/budgets", tags=["Finance"])
async def update_budgets(budget_update: BudgetUpdate):
    """Actualiza presupuestos manualmente (se guardan en archivo JSON)."""
    agent = agent_registry.get("finanzas")
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente de finanzas no encontrado")
    
    try:
        from aria.budget_manager import get_budget_manager
        from aria.config import settings
        
        budget_manager = get_budget_manager(settings.odoo.company_id)
        
        updated = budget_manager.set_budgets(
            monthly_revenue=budget_update.monthly_revenue,
            monthly_expenses=budget_update.monthly_expenses,
            by_category=budget_update.by_category,
        )
        
        # Invalidar cache del agente
        agent._budgets_cache = None
        
        return {
            "success": True,
            "budgets": updated,
            "message": "Presupuestos actualizados correctamente",
        }
    except Exception as e:
        logger.error(f"Error actualizando presupuestos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Reports ====================

@app.get("/api/reports", tags=["Reports"])
async def list_reports():
    """Lista reportes programados disponibles."""
    return {
        "reports": report_scheduler.get_schedule(),
        "total": len(report_scheduler.reports),
    }


@app.post("/api/reports/{report_name}/generate", tags=["Reports"])
async def generate_report(report_name: str):
    """Genera y envía un reporte."""
    if report_name not in report_scheduler.reports:
        raise HTTPException(status_code=404, detail=f"Reporte '{report_name}' no encontrado")
    
    try:
        success = await report_scheduler.generate_and_send(report_name)
        
        if success:
            return {"status": "generated", "report": report_name}
        else:
            raise HTTPException(status_code=500, detail="Error generando reporte")
    except Exception as e:
        logger.error(f"Error generando reporte {report_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/{report_name}/preview", tags=["Reports"], response_class=HTMLResponse)
async def preview_report(report_name: str):
    """Previsualiza un reporte en HTML."""
    if report_name not in report_scheduler.reports:
        raise HTTPException(status_code=404, detail=f"Reporte '{report_name}' no encontrado")
    
    try:
        html = await report_scheduler.generate_html(report_name)
        
        if html:
            return HTMLResponse(content=html)
        else:
            raise HTTPException(status_code=500, detail="Error renderizando reporte")
    except Exception as e:
        logger.error(f"Error previsualizando reporte {report_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reports/{report_name}/enable", tags=["Reports"])
async def enable_report(report_name: str):
    """Habilita un reporte programado."""
    if report_scheduler.enable(report_name):
        return {"status": "enabled", "report": report_name}
    raise HTTPException(status_code=404, detail=f"Reporte '{report_name}' no encontrado")


@app.post("/api/reports/{report_name}/disable", tags=["Reports"])
async def disable_report(report_name: str):
    """Deshabilita un reporte programado."""
    if report_scheduler.disable(report_name):
        return {"status": "disabled", "report": report_name}
    raise HTTPException(status_code=404, detail=f"Reporte '{report_name}' no encontrado")


# ==================== Inspección Contextual ====================

@app.get("/api/inspection", tags=["Inspection"])
async def list_inspectors():
    """Lista los inspectores disponibles."""
    from aria.inspection import get_all_inspectors
    
    inspectors = get_all_inspectors()
    
    return {
        "inspectors": [
            {
                "agent": name,
                "area": inspector.AREA_NAME,
                "upstream": [d.agent_name for d in inspector.UPSTREAM_DEPENDENCIES],
                "downstream": [d.agent_name for d in inspector.DOWNSTREAM_DEPENDENCIES],
            }
            for name, inspector in inspectors.items()
        ],
        "total": len(inspectors),
    }


@app.get("/api/inspection/{agent_name}", tags=["Inspection"])
async def run_inspection(
    agent_name: str,
    max_level: int = Query(4, ge=1, le=4, description="Nivel máximo de inspección"),
    create_proposals: bool = Query(
        False,
        description="Crear propuestas automáticas para hallazgos HIGH/CRITICAL"
    ),
    min_severity: str = Query(
        "high",
        description="Severidad mínima para crear propuestas (critical, high, medium)"
    ),
):
    """
    Ejecuta inspección contextual de un agente.
    
    Niveles:
    - 1: Vista general (KPIs, tendencias)
    - 2: Por categorías (vendedor, almacén, etc.)
    - 3: Detalles (registros específicos)
    - 4: Anomalías (errores, inconsistencias)
    
    Propuestas:
    - Si create_proposals=true, crea propuestas para hallazgos graves
    - Las propuestas se pueden ver/aprobar en /api/proposals
    """
    from aria.inspection import get_inspector
    from aria.inspection.models import ImpactLevel
    
    # Mapear severidad
    severity_map = {
        "critical": ImpactLevel.CRITICAL,
        "high": ImpactLevel.HIGH,
        "medium": ImpactLevel.MEDIUM,
        "low": ImpactLevel.LOW,
    }
    min_sev = severity_map.get(min_severity.lower(), ImpactLevel.HIGH)
    
    try:
        inspector = get_inspector(agent_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    report = inspector.inspect(
        max_level=max_level,
        create_proposals=create_proposals,
        min_severity_for_proposal=min_sev,
    )
    
    return report.to_dict()


@app.get("/api/inspection/all/summary", tags=["Inspection"])
async def run_all_inspections(
    max_level: int = Query(3, ge=1, le=4, description="Nivel máximo de inspección"),
    create_proposals: bool = Query(
        False,
        description="Crear propuestas automáticas para hallazgos HIGH/CRITICAL"
    ),
    min_severity: str = Query(
        "high",
        description="Severidad mínima para crear propuestas (critical, high, medium)"
    ),
):
    """
    Ejecuta inspección de todos los agentes y retorna resumen consolidado.
    
    Si create_proposals=true, también crea propuestas para hallazgos graves.
    """
    from aria.inspection import run_all_inspections as _run_all
    from aria.inspection.models import ImpactLevel
    
    # Mapear severidad
    severity_map = {
        "critical": ImpactLevel.CRITICAL,
        "high": ImpactLevel.HIGH,
        "medium": ImpactLevel.MEDIUM,
    }
    min_sev = severity_map.get(min_severity.lower(), ImpactLevel.HIGH)
    
    reports = _run_all(
        max_level=max_level,
        create_proposals=create_proposals,
        min_severity_for_proposal=min_sev,
    )
    
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_agents": len(reports),
        "agents": {},
        "critical_findings": [],
        "impacted_agents": set(),
        "total_proposals_created": 0,
    }
    
    for name, report in reports.items():
        summary["agents"][name] = {
            "status": report.context.status,
            "health_score": report.context.health_score,
            "findings_count": len(report.findings),
            "critical_count": report.critical_count,
            "high_count": report.high_count,
            "proposals_created": report.proposals_created,
        }
        summary["total_proposals_created"] += report.proposals_created
        
        # Recolectar hallazgos críticos
        for f in report.findings_by_severity.get("critical", []):
            summary["critical_findings"].append({
                "agent": name,
                "title": f.title,
                "description": f.description,
                "affected_records": f.affected_records,
                "affected_amount": f.affected_amount,
                "impacts": [i.agent_name for i in f.impacts],
            })
            summary["impacted_agents"].update(i.agent_name for i in f.impacts)
    
    summary["impacted_agents"] = list(summary["impacted_agents"])
    
    return summary


@app.get("/api/inspection/impacts", tags=["Inspection"])
async def get_impact_map():
    """Retorna el mapa de dependencias e impactos entre agentes."""
    from aria.inspection import get_all_inspectors
    
    inspectors = get_all_inspectors()
    
    nodes = []
    edges = []
    
    for name, inspector in inspectors.items():
        nodes.append({
            "id": name,
            "area": inspector.AREA_NAME,
        })
        
        # Agregar edges de dependencias
        for dep in inspector.UPSTREAM_DEPENDENCIES:
            edges.append({
                "from": dep.agent_name,
                "to": name,
                "type": "feeds",
                "criticality": dep.criticality.value,
                "data_flow": dep.data_flow,
            })
        
        for dep in inspector.DOWNSTREAM_DEPENDENCIES:
            edges.append({
                "from": name,
                "to": dep.agent_name,
                "type": "feeds",
                "criticality": dep.criticality.value,
                "data_flow": dep.data_flow,
            })
    
    return {
        "nodes": nodes,
        "edges": edges,
    }


# ==================== WebSocket ====================

# Conexiones activas de WebSocket
active_connections: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para notificaciones en tiempo real."""
    await websocket.accept()
    active_connections.append(websocket)
    
    logger.info(f"WebSocket conectado. Total conexiones: {len(active_connections)}")
    
    try:
        while True:
            # Recibir mensajes del cliente
            data = await websocket.receive_text()
            
            # Procesar comandos
            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
            elif data == "status":
                pending = await approval_engine.get_pending()
                await websocket.send_json({
                    "type": "status",
                    "pending_count": len(pending),
                    "timestamp": datetime.now().isoformat(),
                })
            else:
                await websocket.send_json({"type": "error", "message": "Comando no reconocido"})
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket desconectado. Total conexiones: {len(active_connections)}")


async def broadcast_notification(notification: dict[str, Any]):
    """Envía una notificación a todos los clientes WebSocket conectados."""
    for connection in active_connections:
        try:
            await connection.send_json({
                "type": "notification",
                "data": notification,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error(f"Error enviando notificación WebSocket: {e}")


# ==================== Error Handlers ====================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Manejador global de excepciones."""
    logger.error(f"Error no manejado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "error": str(exc)},
    )
