"""
Agente CRM - Gestión de Oportunidades y Pipeline de Ventas.

Responsabilidades:
- Monitorear pipeline de ventas
- Detectar oportunidades estancadas
- Analizar conversión y cierre
- Alertar sobre oportunidades por vencer
- Evaluar rendimiento de vendedores
- Detectar oportunidades de upselling
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class CRMAgent(BaseAgent):
    """
    Agente autónomo para gestión de CRM.
    
    Monitorea oportunidades, analiza pipeline y optimiza conversiones.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="crm",
            description="Gestión de oportunidades y pipeline de ventas"
        )
        
        self.company_id = settings.odoo.company_id
        
        # Configuración
        self.stale_days = 14  # Días sin actividad para considerar estancada
        self.deadline_warning_days = 7  # Días antes del cierre esperado
        self.high_value_threshold = 100000  # Umbral para oportunidad de alto valor
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente CRM."""
        
        # Pipeline diario
        self.register_task(TaskDefinition(
            name="daily_pipeline",
            method="analyze_pipeline",
            schedule="0 8 * * 1-5",  # 8:00 AM L-V
            description="Análisis diario del pipeline de ventas"
        ))
        
        # Oportunidades estancadas
        self.register_task(TaskDefinition(
            name="stale_opportunities",
            method="check_stale_opportunities",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Detectar oportunidades sin movimiento"
        ))
        
        # Oportunidades por vencer
        self.register_task(TaskDefinition(
            name="expiring_opportunities",
            method="check_expiring_opportunities",
            schedule="0 8 * * *",  # Diario 8:00 AM
            description="Oportunidades próximas a fecha límite"
        ))
        
        # Rendimiento de vendedores
        self.register_task(TaskDefinition(
            name="sales_performance",
            method="analyze_sales_performance",
            schedule="0 9 1 * *",  # Día 1 del mes
            description="Análisis de rendimiento por vendedor"
        ))
        
        # Análisis de conversión
        self.register_task(TaskDefinition(
            name="conversion_analysis",
            method="analyze_conversions",
            schedule="0 10 * * 1",  # Lunes 10:00 AM
            description="Análisis de tasas de conversión"
        ))
        
        # Oportunidades de alto valor
        self.register_task(TaskDefinition(
            name="high_value_check",
            method="check_high_value_opportunities",
            schedule="0 9 * * *",  # Diario 9:00 AM
            description="Monitorear oportunidades de alto valor"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado del CRM."""
        
        # Total oportunidades activas
        active_leads = self.search_count(
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)]
        )
        
        # Valor total del pipeline
        opportunities = self.search_read(
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)],
            ["expected_revenue", "probability"],
            limit=5000
        )
        
        total_pipeline = sum(o.get("expected_revenue", 0) for o in opportunities)
        weighted_pipeline = sum(
            o.get("expected_revenue", 0) * (o.get("probability", 0) / 100)
            for o in opportunities
        )
        
        # Oportunidades estancadas
        stale_date = (datetime.now() - timedelta(days=self.stale_days)).strftime("%Y-%m-%d")
        stale_count = self.search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("write_date", "<", stale_date),
            ]
        )
        
        # Determinar estado
        if stale_count > active_leads * 0.3:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "active_opportunities": active_leads,
            "total_pipeline": total_pipeline,
            "weighted_pipeline": weighted_pipeline,
            "stale_opportunities": stale_count,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def analyze_pipeline(self) -> TaskResult:
        """Analiza el pipeline de ventas diario."""
        started_at = datetime.now()
        
        self.logger.info("Analizando pipeline de ventas...")
        
        # Obtener etapas
        stages = self.search_read(
            "crm.stage",
            [],
            ["id", "name", "sequence", "is_won"],
            order="sequence asc"
        )
        
        stage_map = {s["id"]: s for s in stages}
        
        # Obtener oportunidades por etapa
        opportunities = self.search_read(
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)],
            ["stage_id", "expected_revenue", "probability", "user_id", "date_deadline"],
            limit=5000
        )
        
        # Agrupar por etapa
        by_stage = {}
        total_value = 0
        weighted_value = 0
        
        for opp in opportunities:
            stage_id = opp["stage_id"][0] if opp.get("stage_id") else None
            stage_name = opp["stage_id"][1] if opp.get("stage_id") else "Sin etapa"
            
            if stage_name not in by_stage:
                by_stage[stage_name] = {"count": 0, "value": 0, "weighted": 0}
            
            revenue = opp.get("expected_revenue", 0)
            prob = opp.get("probability", 0)
            
            by_stage[stage_name]["count"] += 1
            by_stage[stage_name]["value"] += revenue
            by_stage[stage_name]["weighted"] += revenue * (prob / 100)
            
            total_value += revenue
            weighted_value += revenue * (prob / 100)
        
        # Generar mensaje
        message = f"""
*📊 Pipeline de Ventas*

*Total oportunidades:* {len(opportunities)}
*Valor total:* {self.format_currency(total_value)}
*Valor ponderado:* {self.format_currency(weighted_value)}

*Por etapa:*
"""
        
        for stage_name, data in by_stage.items():
            pct = (data["value"] / total_value * 100) if total_value > 0 else 0
            message += f"• {stage_name}: {data['count']} ({self.format_currency(data['value'])}) - {pct:.0f}%\n"
        
        await self.notify(
            title=f"📊 Pipeline: {self.format_currency(weighted_value)} ponderado",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="daily_pipeline",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_opportunities": len(opportunities),
                "total_value": total_value,
                "weighted_value": weighted_value,
                "by_stage": by_stage,
            }
        )
    
    async def check_stale_opportunities(self) -> TaskResult:
        """Detecta oportunidades sin movimiento."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Buscando oportunidades estancadas...")
        
        stale_date = (datetime.now() - timedelta(days=self.stale_days)).strftime("%Y-%m-%d %H:%M:%S")
        
        stale = self.search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("write_date", "<", stale_date),
            ],
            ["name", "partner_id", "expected_revenue", "user_id", "stage_id", "write_date"],
            limit=100,
            order="expected_revenue desc"
        )
        
        if stale:
            # Agrupar por vendedor
            by_user = {}
            total_value = 0
            
            for opp in stale:
                user_name = opp["user_id"][1] if opp.get("user_id") else "Sin asignar"
                if user_name not in by_user:
                    by_user[user_name] = {"count": 0, "value": 0, "opportunities": []}
                
                by_user[user_name]["count"] += 1
                by_user[user_name]["value"] += opp.get("expected_revenue", 0)
                by_user[user_name]["opportunities"].append(opp)
                total_value += opp.get("expected_revenue", 0)
            
            message = f"""
*⚠️ {len(stale)} Oportunidades Estancadas*
(Sin movimiento en {self.stale_days} días)

*Valor total en riesgo:* {self.format_currency(total_value)}

*Por vendedor:*
"""
            for user, data in sorted(by_user.items(), key=lambda x: x[1]["value"], reverse=True):
                message += f"• {user}: {data['count']} opp ({self.format_currency(data['value'])})\n"
            
            message += f"\n*Top 5 por valor:*\n"
            for opp in stale[:5]:
                partner = opp["partner_id"][1] if opp.get("partner_id") else "Sin cliente"
                message += f"• {opp['name'][:30]} - {partner[:20]} ({self.format_currency(opp.get('expected_revenue', 0))})\n"
            
            # Crear propuesta si hay muchas estancadas
            if len(stale) > 10 or total_value > self.high_value_threshold:
                await self.propose(
                    title=f"⚠️ {len(stale)} oportunidades estancadas",
                    description=f"Valor en riesgo: {self.format_currency(total_value)}",
                    priority=Priority.HIGH if total_value > self.high_value_threshold else Priority.MEDIUM,
                    situation_summary=message,
                    proposed_action_detail="Revisar y actualizar oportunidades o marcarlas como perdidas",
                )
                proposals_created += 1
            
            await self.notify(
                title=f"⚠️ {len(stale)} oportunidades estancadas",
                message=message,
                priority=Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="stale_opportunities",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"stale_count": len(stale) if stale else 0}
        )
    
    async def check_expiring_opportunities(self) -> TaskResult:
        """Revisa oportunidades próximas a vencer."""
        started_at = datetime.now()
        
        self.logger.info("Buscando oportunidades por vencer...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        deadline = (datetime.now() + timedelta(days=self.deadline_warning_days)).strftime("%Y-%m-%d")
        
        expiring = self.search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("date_deadline", ">=", today),
                ("date_deadline", "<=", deadline),
            ],
            ["name", "partner_id", "expected_revenue", "probability", "user_id", "date_deadline"],
            limit=50,
            order="date_deadline asc"
        )
        
        # También oportunidades vencidas
        overdue = self.search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("date_deadline", "<", today),
            ],
            ["name", "partner_id", "expected_revenue", "probability", "user_id", "date_deadline"],
            limit=50,
            order="expected_revenue desc"
        )
        
        if expiring or overdue:
            message = ""
            
            if overdue:
                overdue_value = sum(o.get("expected_revenue", 0) for o in overdue)
                message += f"*🔴 {len(overdue)} oportunidades VENCIDAS ({self.format_currency(overdue_value)})*\n"
                for opp in overdue[:5]:
                    partner = opp["partner_id"][1] if opp.get("partner_id") else "N/A"
                    message += f"  • {opp['name'][:25]} - {partner[:15]}\n"
                message += "\n"
            
            if expiring:
                expiring_value = sum(o.get("expected_revenue", 0) for o in expiring)
                message += f"*🟡 {len(expiring)} por vencer esta semana ({self.format_currency(expiring_value)})*\n"
                for opp in expiring[:5]:
                    partner = opp["partner_id"][1] if opp.get("partner_id") else "N/A"
                    deadline_str = opp.get("date_deadline", "")[:10]
                    message += f"  • {opp['name'][:25]} ({deadline_str})\n"
            
            priority = Priority.HIGH if overdue else Priority.MEDIUM
            
            await self.notify(
                title=f"📅 {len(overdue or [])} vencidas, {len(expiring or [])} por vencer",
                message=message,
                priority=priority,
            )
        
        return TaskResult(
            task_name="expiring_opportunities",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "expiring": len(expiring) if expiring else 0,
                "overdue": len(overdue) if overdue else 0,
            }
        )
    
    async def analyze_sales_performance(self) -> TaskResult:
        """Analiza rendimiento por vendedor."""
        started_at = datetime.now()
        
        self.logger.info("Analizando rendimiento de vendedores...")
        
        # Último mes
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Oportunidades ganadas
        won = self.search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("won_status", "=", "won"),
                ("date_closed", ">=", month_ago),
            ],
            ["user_id", "expected_revenue"],
            limit=5000
        )
        
        # Oportunidades perdidas
        lost = self.search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("won_status", "=", "lost"),
                ("date_closed", ">=", month_ago),
            ],
            ["user_id", "expected_revenue"],
            limit=5000
        )
        
        # Agrupar por vendedor
        by_user = {}
        
        for opp in won:
            user_name = opp["user_id"][1] if opp.get("user_id") else "Sin asignar"
            if user_name not in by_user:
                by_user[user_name] = {"won": 0, "won_value": 0, "lost": 0, "lost_value": 0}
            by_user[user_name]["won"] += 1
            by_user[user_name]["won_value"] += opp.get("expected_revenue", 0)
        
        for opp in lost:
            user_name = opp["user_id"][1] if opp.get("user_id") else "Sin asignar"
            if user_name not in by_user:
                by_user[user_name] = {"won": 0, "won_value": 0, "lost": 0, "lost_value": 0}
            by_user[user_name]["lost"] += 1
            by_user[user_name]["lost_value"] += opp.get("expected_revenue", 0)
        
        # Calcular tasas de conversión
        for user in by_user:
            total = by_user[user]["won"] + by_user[user]["lost"]
            by_user[user]["conversion_rate"] = (by_user[user]["won"] / total * 100) if total > 0 else 0
        
        # Ordenar por valor ganado
        sorted_users = sorted(by_user.items(), key=lambda x: x[1]["won_value"], reverse=True)
        
        total_won = sum(d["won_value"] for _, d in sorted_users)
        total_lost = sum(d["lost_value"] for _, d in sorted_users)
        
        message = f"""
*🏆 Rendimiento de Vendedores (últimos 30 días)*

*Total ganado:* {self.format_currency(total_won)}
*Total perdido:* {self.format_currency(total_lost)}

*Por vendedor:*
"""
        
        for user, data in sorted_users[:10]:
            message += f"""
• *{user}*
  Ganadas: {data['won']} ({self.format_currency(data['won_value'])})
  Perdidas: {data['lost']} ({self.format_currency(data['lost_value'])})
  Conversión: {data['conversion_rate']:.0f}%
"""
        
        await self.notify(
            title=f"🏆 Rendimiento: {self.format_currency(total_won)} ganado",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="sales_performance",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "total_won": total_won,
                "total_lost": total_lost,
                "by_user": dict(sorted_users),
            }
        )
    
    async def analyze_conversions(self) -> TaskResult:
        """Analiza tasas de conversión."""
        started_at = datetime.now()
        
        self.logger.info("Analizando conversiones...")
        
        # Últimos 90 días
        period_start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # Total creadas
        created = self.search_count(
            "crm.lead",
            [("type", "=", "opportunity"), ("create_date", ">=", period_start)]
        )
        
        # Ganadas
        won = self.search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("won_status", "=", "won"),
                ("date_closed", ">=", period_start),
            ]
        )
        
        # Perdidas
        lost = self.search_count(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("won_status", "=", "lost"),
                ("date_closed", ">=", period_start),
            ]
        )
        
        # Activas
        active = self.search_count(
            "crm.lead",
            [("type", "=", "opportunity"), ("active", "=", True)]
        )
        
        closed = won + lost
        conversion_rate = (won / closed * 100) if closed > 0 else 0
        
        message = f"""
*📈 Análisis de Conversión (90 días)*

*Oportunidades creadas:* {created}
*Cerradas:* {closed}
  • Ganadas: {won} ✅
  • Perdidas: {lost} ❌
*Activas:* {active}

*Tasa de conversión:* {conversion_rate:.1f}%
"""
        
        await self.notify(
            title=f"📈 Conversión: {conversion_rate:.1f}%",
            message=message,
            priority=Priority.LOW,
        )
        
        return TaskResult(
            task_name="conversion_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "created": created,
                "won": won,
                "lost": lost,
                "active": active,
                "conversion_rate": conversion_rate,
            }
        )
    
    async def check_high_value_opportunities(self) -> TaskResult:
        """Monitorea oportunidades de alto valor."""
        started_at = datetime.now()
        
        self.logger.info("Monitoreando oportunidades de alto valor...")
        
        high_value = self.search_read(
            "crm.lead",
            [
                ("type", "=", "opportunity"),
                ("active", "=", True),
                ("expected_revenue", ">=", self.high_value_threshold),
            ],
            ["name", "partner_id", "expected_revenue", "probability", "user_id", "stage_id", "date_deadline"],
            order="expected_revenue desc",
            limit=20
        )
        
        if high_value:
            total_value = sum(o.get("expected_revenue", 0) for o in high_value)
            weighted = sum(
                o.get("expected_revenue", 0) * (o.get("probability", 0) / 100)
                for o in high_value
            )
            
            message = f"""
*💎 {len(high_value)} Oportunidades de Alto Valor*
(> {self.format_currency(self.high_value_threshold)})

*Valor total:* {self.format_currency(total_value)}
*Valor ponderado:* {self.format_currency(weighted)}

*Detalle:*
"""
            
            for opp in high_value[:10]:
                partner = opp["partner_id"][1] if opp.get("partner_id") else "N/A"
                stage = opp["stage_id"][1] if opp.get("stage_id") else "N/A"
                user = opp["user_id"][1] if opp.get("user_id") else "N/A"
                prob = opp.get("probability", 0)
                
                message += f"""
• *{opp['name'][:35]}*
  Cliente: {partner[:25]}
  Valor: {self.format_currency(opp.get('expected_revenue', 0))} ({prob:.0f}%)
  Etapa: {stage} | Vendedor: {user}
"""
            
            await self.notify(
                title=f"💎 {len(high_value)} oportunidades de alto valor",
                message=message,
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="high_value_check",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"high_value_count": len(high_value) if high_value else 0}
        )


def create_crm_agent() -> CRMAgent:
    """Crea y retorna el agente CRM."""
    return CRMAgent()
