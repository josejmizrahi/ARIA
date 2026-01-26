"""
ARIA - Agente CEO
==================

Agente CEO - Dirección General

El agente CEO:
- Consolida información de todos los demás agentes
- Genera dashboard ejecutivo diario
- Detecta situaciones críticas que afectan múltiples áreas
- Proporciona visión integral del negocio
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.models.proposal import Priority, ProposalType
from aria.models.task import TaskDefinition, TaskResult


class CEOAgent(BaseAgent):
    """
    Agente de Dirección General.
    
    Responsabilidades:
    - Dashboard ejecutivo consolidado
    - Alertas críticas del sistema
    - KPIs principales del negocio
    - Comparativo vs presupuesto
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="ceo",
            description="Agente de Dirección General - Vista ejecutiva consolidada"
        )
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente CEO."""
        
        # Dashboard diario matutino
        self.register_task(TaskDefinition(
            name="daily_dashboard",
            method="generate_daily_dashboard",
            schedule="0 7 * * *",  # 7:00 AM todos los días
            description="Genera resumen ejecutivo diario"
        ))
        
        # Monitoreo de alertas críticas
        self.register_task(TaskDefinition(
            name="critical_alerts",
            method="check_critical_alerts",
            schedule="*/30 * * * *",  # Cada 30 minutos
            description="Revisa alertas críticas del sistema"
        ))
        
        # Reporte semanal
        self.register_task(TaskDefinition(
            name="weekly_report",
            method="generate_weekly_report",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Genera reporte semanal ejecutivo"
        ))
        
        # Comparativo vs presupuesto
        self.register_task(TaskDefinition(
            name="budget_comparison",
            method="compare_vs_budget",
            schedule="0 9 1 * *",  # Día 1 de cada mes
            description="Compara resultados vs presupuesto"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen ejecutivo del negocio."""
        from aria.agents.registry import agent_registry
        
        # Obtener resúmenes de otros agentes (excluyendo CEO para evitar recursión)
        agents_status = {}
        for name, agent in agent_registry.list_all().items():
            if name != "ceo":  # Evitar recursión infinita
                try:
                    summary = await agent.get_status_summary()
                    agents_status[name] = summary.get("status", "unknown")
                except Exception as e:
                    agents_status[name] = f"error: {str(e)}"
        
        # Calcular métricas principales
        pending_approvals = await self.approvals.get_pending()
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "pending_approvals": len(pending_approvals),
            "critical_items": len([
                p for p in pending_approvals 
                if p.priority == Priority.CRITICAL
            ]),
            "agents_status": agents_status,
        }
    
    # ==================== Tareas ====================
    
    async def generate_daily_dashboard(self) -> TaskResult:
        """
        Genera y envía dashboard ejecutivo diario.
        
        Incluye:
        - Estado de cada área
        - Alertas pendientes
        - KPIs principales
        """
        started_at = datetime.now()
        
        self.logger.info("Generando dashboard diario...")
        
        try:
            from aria.agents.registry import agent_registry
            
            # Obtener datos de cada área
            summaries = await agent_registry.get_all_summaries()
            pending = await self.approvals.get_pending()
            
            # Agrupar pendientes por prioridad
            by_priority: dict[str, list] = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            }
            
            for p in pending:
                by_priority[p.priority.value].append(p)
            
            # Construir mensaje del dashboard
            message = self._build_dashboard_message(summaries, by_priority)
            
            # Enviar notificación
            await self.notify(
                title="📊 Dashboard Ejecutivo",
                message=message,
                priority=Priority.MEDIUM,
                data={"summaries": summaries, "pending_count": len(pending)}
            )
            
            return TaskResult(
                task_name="daily_dashboard",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"pending_count": len(pending)}
            )
            
        except Exception as e:
            self.logger.error(f"Error generando dashboard: {e}")
            raise
    
    async def check_critical_alerts(self) -> TaskResult:
        """
        Revisa alertas críticas que requieren atención inmediata.
        """
        started_at = datetime.now()
        
        # Obtener propuestas críticas pendientes
        pending = await self.approvals.get_pending()
        critical = [p for p in pending if p.priority == Priority.CRITICAL]
        
        # Verificar si hay críticos sin atender por más de 1 hora
        now = datetime.now()
        urgent = []
        
        for p in critical:
            age_hours = (now - p.created_at).total_seconds() / 3600
            if age_hours > 1:
                urgent.append(p)
        
        # Si hay urgentes, enviar recordatorio
        if urgent:
            message = f"⚠️ *{len(urgent)} alertas críticas sin atender*\n\n"
            
            for p in urgent[:5]:
                age = (now - p.created_at).total_seconds() / 3600
                message += f"🔴 `{p.short_id}` - {p.agent_id}: {p.title} ({age:.1f}h)\n"
            
            if len(urgent) > 5:
                message += f"\n... y {len(urgent) - 5} más"
            
            await self.notify(
                title="🚨 Alertas Críticas Pendientes",
                message=message,
                priority=Priority.CRITICAL,
            )
        
        return TaskResult(
            task_name="critical_alerts",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"critical_count": len(critical), "urgent_count": len(urgent)}
        )
    
    async def generate_weekly_report(self) -> TaskResult:
        """Genera reporte semanal ejecutivo."""
        started_at = datetime.now()
        
        self.logger.info("Generando reporte semanal...")
        
        # Obtener estadísticas de aprobaciones
        stats = await self.approvals.get_stats()
        
        message = f"""
📈 *Reporte Semanal Ejecutivo*
_{datetime.now().strftime('%d/%m/%Y')}_

*Actividad de la semana:*
- Total propuestas: {stats['total']}
- Aprobadas: {stats.get('approved', 0)}
- Rechazadas: {stats.get('rejected', 0)}
- Completadas: {stats.get('completed', 0)}
- Pendientes: {stats.get('pending', 0)}

{await self._get_weekly_by_area()}

_Usa /pending para ver propuestas pendientes_
        """.strip()
        
        await self.notify(
            title="📊 Reporte Semanal",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="weekly_report",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"stats": stats}
        )
    
    async def compare_vs_budget(self) -> TaskResult:
        """Compara resultados del mes vs presupuesto."""
        started_at = datetime.now()
        
        self.logger.info("Comparando vs presupuesto...")
        
        # Obtener datos de ventas del mes
        first_day = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        
        try:
            # Facturas del mes
            invoices = self.search_read(
                "account.move",
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("invoice_date", ">=", first_day),
                ],
                ["amount_total_signed"],
                limit=5000
            )
            
            total_invoiced = sum(inv.get("amount_total_signed", 0) for inv in invoices)
            
            # Presupuesto mensual (configurar según empresa)
            monthly_budget = 24_500_000  # Ejemplo: $24.5M MXN
            
            variance = total_invoiced - monthly_budget
            variance_pct = (variance / monthly_budget * 100) if monthly_budget else 0
            
            # Determinar prioridad
            if variance_pct < -20:
                priority = Priority.CRITICAL
                emoji = "🔴"
            elif variance_pct < -10:
                priority = Priority.HIGH
                emoji = "🟠"
            elif variance_pct < 0:
                priority = Priority.MEDIUM
                emoji = "🟡"
            else:
                priority = Priority.LOW
                emoji = "🟢"
            
            message = f"""
{emoji} *Comparativo vs Presupuesto*

*Facturado del mes:* {self.format_currency(total_invoiced)}
*Presupuesto:* {self.format_currency(monthly_budget)}
*Variación:* {self.format_currency(variance)} ({variance_pct:+.1f}%)

{"⚠️ Se requiere acción para alcanzar meta" if variance < 0 else "✅ Cumpliendo presupuesto"}
            """.strip()
            
            await self.notify(
                title="📊 Comparativo Mensual",
                message=message,
                priority=priority,
                data={
                    "invoiced": total_invoiced,
                    "budget": monthly_budget,
                    "variance_pct": variance_pct,
                }
            )
            
            return TaskResult(
                task_name="budget_comparison",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                data={"variance_pct": variance_pct}
            )
            
        except Exception as e:
            self.logger.error(f"Error comparando presupuesto: {e}")
            raise
    
    # ==================== Helpers ====================
    
    def _build_dashboard_message(
        self,
        summaries: dict[str, dict],
        by_priority: dict[str, list]
    ) -> str:
        """Construye el mensaje del dashboard."""
        
        date_str = datetime.now().strftime("%A %d de %B, %Y")
        message = f"*{date_str}*\n\n"
        
        # Resumen de pendientes
        total_pending = sum(len(items) for items in by_priority.values())
        
        message += f"*📋 Pendientes de aprobación: {total_pending}*\n"
        
        if by_priority["critical"]:
            message += f"🔴 Críticos: {len(by_priority['critical'])}\n"
        if by_priority["high"]:
            message += f"🟠 Altos: {len(by_priority['high'])}\n"
        if by_priority["medium"]:
            message += f"🟡 Medios: {len(by_priority['medium'])}\n"
        if by_priority["low"]:
            message += f"🟢 Bajos: {len(by_priority['low'])}\n"
        
        message += "\n"
        
        # Items críticos
        if by_priority["critical"]:
            message += "*🚨 Requieren atención inmediata:*\n"
            for p in by_priority["critical"][:3]:
                message += f"• `{p.short_id}` {p.agent_id}: {p.title}\n"
            message += "\n"
        
        # Estado por área
        message += "*📊 Estado por área:*\n"
        
        status_emojis = {
            "ok": "✅",
            "warning": "⚠️",
            "critical": "🔴",
            "error": "❌",
            "unknown": "❓",
        }
        
        for name, summary in summaries.items():
            if name == "ceo":
                continue
            
            status = summary.get("status", "unknown")
            emoji = status_emojis.get(status, "❓")
            message += f"{emoji} {name.capitalize()}\n"
        
        message += "\n_Usa /pending para ver detalles_"
        
        return message
    
    async def _get_weekly_by_area(self) -> str:
        """Obtiene resumen semanal por área."""
        from aria.agents.registry import agent_registry
        
        lines = ["*Por área:*"]
        
        for name, agent in agent_registry.list_all().items():
            if name == "ceo":
                continue
            
            # Contar tareas ejecutadas esta semana
            tasks_run = sum(
                1 for t in agent.tasks
                if t.last_run and t.last_run > datetime.now() - timedelta(days=7)
            )
            
            lines.append(f"• {name.capitalize()}: {tasks_run} tareas ejecutadas")
        
        return "\n".join(lines) if len(lines) > 1 else ""


def create_ceo_agent() -> CEOAgent:
    """Crea y retorna el agente CEO."""
    return CEOAgent()
