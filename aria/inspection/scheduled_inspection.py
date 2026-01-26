"""
Inspección Programada para ARIA.

Este módulo permite ejecutar inspecciones de forma automática
y enviar alertas de hallazgos críticos vía Telegram.
"""

import asyncio
from datetime import datetime
from typing import Optional

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("aria.inspection.scheduled")


class ScheduledInspection:
    """
    Gestiona la ejecución programada de inspecciones.
    
    Uso:
        from aria.inspection.scheduled_inspection import scheduled_inspection
        
        # Ejecutar inspección y notificar
        await scheduled_inspection.run_daily_inspection()
        
        # Ejecutar solo si hay críticos, notificar
        await scheduled_inspection.run_and_alert()
    """
    
    _instance: Optional["ScheduledInspection"] = None
    
    def __new__(cls) -> "ScheduledInspection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._initialized = True
        self._last_run: Optional[datetime] = None
        self._last_report: Optional[dict] = None
    
    async def run_daily_inspection(
        self,
        max_level: int = 3,
        create_proposals: bool = True,
        notify_telegram: bool = True,
    ) -> dict:
        """
        Ejecuta inspección diaria completa.
        
        Args:
            max_level: Nivel máximo de inspección (1-4)
            create_proposals: Si crear propuestas automáticamente
            notify_telegram: Si enviar notificaciones a Telegram
            
        Returns:
            Resumen de la inspección
        """
        from aria.inspection import run_all_inspections
        from aria.inspection.models import ImpactLevel
        
        logger.info("Iniciando inspección diaria programada...")
        self._last_run = datetime.now()
        
        # Ejecutar todas las inspecciones
        reports = run_all_inspections(
            max_level=max_level,
            create_proposals=create_proposals,
            min_severity_for_proposal=ImpactLevel.HIGH,
        )
        
        # Compilar resumen
        summary = {
            "timestamp": self._last_run.isoformat(),
            "total_agents": len(reports),
            "total_findings": 0,
            "critical_count": 0,
            "high_count": 0,
            "proposals_created": 0,
            "agents_critical": [],
            "agents_warning": [],
            "agents_healthy": [],
            "critical_findings": [],
        }
        
        for name, report in reports.items():
            summary["total_findings"] += len(report.findings)
            summary["critical_count"] += report.critical_count
            summary["high_count"] += report.high_count
            summary["proposals_created"] += report.proposals_created
            
            if report.context.status == "critical":
                summary["agents_critical"].append({
                    "name": name,
                    "health": report.context.health_score,
                    "findings": len(report.findings),
                })
            elif report.context.status == "warning":
                summary["agents_warning"].append({
                    "name": name,
                    "health": report.context.health_score,
                })
            else:
                summary["agents_healthy"].append(name)
            
            # Recolectar hallazgos críticos
            for f in report.findings_by_severity.get("critical", []):
                summary["critical_findings"].append({
                    "agent": name,
                    "title": f.title,
                    "description": f.description[:200],
                    "affected_amount": f.affected_amount,
                    "impacts": [i.agent_name for i in f.impacts],
                })
        
        self._last_report = summary
        
        logger.info(
            f"Inspección completada: {summary['total_findings']} hallazgos, "
            f"{summary['critical_count']} críticos, "
            f"{summary['proposals_created']} propuestas"
        )
        
        # Notificar a Telegram si hay críticos
        if notify_telegram and summary["critical_count"] > 0:
            await self._send_telegram_alert(summary)
        
        return summary
    
    async def run_and_alert(self) -> dict:
        """
        Ejecuta inspección rápida (nivel 2) y alerta solo si hay críticos.
        
        Ideal para ejecutar cada hora.
        """
        return await self.run_daily_inspection(
            max_level=2,
            create_proposals=True,
            notify_telegram=True,
        )
    
    async def _send_telegram_alert(self, summary: dict) -> None:
        """Envía alerta a Telegram con resumen de hallazgos críticos."""
        try:
            from aria.telegram_bot import telegram_bot
            
            if not telegram_bot.enabled or not telegram_bot.bot:
                logger.warning("Telegram no habilitado, saltando notificación")
                return
            
            # Construir mensaje
            text = self._build_alert_message(summary)
            
            # Enviar al admin
            await telegram_bot.bot.send_message(
                telegram_bot.admin_chat_id,
                text,
            )
            
            logger.info("Alerta de inspección enviada a Telegram")
            
        except Exception as e:
            logger.error(f"Error enviando alerta a Telegram: {e}")
    
    def _build_alert_message(self, summary: dict) -> str:
        """Construye el mensaje de alerta para Telegram."""
        # Emoji según gravedad
        if summary["critical_count"] >= 5:
            header_emoji = "🚨🚨🚨"
        elif summary["critical_count"] >= 2:
            header_emoji = "🚨🚨"
        else:
            header_emoji = "🚨"
        
        text = (
            f"{header_emoji} *ALERTA: Inspección ARIA*\n\n"
            f"📅 {summary['timestamp'][:16].replace('T', ' ')}\n\n"
        )
        
        # Resumen rápido
        text += (
            f"*Resumen:*\n"
            f"🔴 Críticos: {summary['critical_count']}\n"
            f"🟠 Altos: {summary['high_count']}\n"
            f"📋 Propuestas creadas: {summary['proposals_created']}\n\n"
        )
        
        # Agentes en estado crítico
        if summary["agents_critical"]:
            text += "*⚠️ Agentes en estado CRÍTICO:*\n"
            for agent in summary["agents_critical"]:
                text += f"  • {agent['name']}: {agent['health']:.0f}% ({agent['findings']} hallazgos)\n"
            text += "\n"
        
        # Hallazgos críticos (max 5)
        if summary["critical_findings"]:
            text += "*🔴 Hallazgos Críticos:*\n"
            for f in summary["critical_findings"][:5]:
                text += f"\n*{f['agent'].upper()}*: {f['title']}\n"
                if f['affected_amount']:
                    text += f"   💰 ${f['affected_amount']:,.2f}\n"
                if f['impacts']:
                    text += f"   → Impacta: {', '.join(f['impacts'])}\n"
            
            if len(summary["critical_findings"]) > 5:
                text += f"\n_...y {len(summary['critical_findings']) - 5} más_\n"
        
        text += "\n_Usa /pending para ver propuestas pendientes_"
        
        return text
    
    def get_last_report(self) -> Optional[dict]:
        """Retorna el último reporte de inspección."""
        return self._last_report
    
    def get_last_run(self) -> Optional[datetime]:
        """Retorna la fecha de la última inspección."""
        return self._last_run


# Singleton global
scheduled_inspection = ScheduledInspection()
