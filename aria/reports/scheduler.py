"""
Programador de reportes automáticos.
"""

import asyncio
from datetime import datetime
from typing import Any, Callable

from aria.config import settings
from aria.notification_manager import notification_manager
from aria.reports.generator import report_generator
from aria.utils.logger import get_logger

logger = get_logger("report_scheduler")


class ScheduledReport:
    """Definición de un reporte programado."""
    
    def __init__(
        self,
        name: str,
        template: str,
        data_provider: Callable[[], dict[str, Any]],
        schedule: str,  # cron expression
        recipients: list[str] | None = None,
        channels: list[str] | None = None,  # telegram, email
        enabled: bool = True,
        description: str = "",
    ):
        self.name = name
        self.template = template
        self.data_provider = data_provider
        self.schedule = schedule
        self.recipients = recipients or []
        self.channels = channels or ["telegram"]
        self.enabled = enabled
        self.description = description
        self.last_run: datetime | None = None
        self.last_error: str | None = None


class ReportScheduler:
    """
    Programador de reportes automáticos.
    
    Genera y envía reportes según programación.
    """
    
    def __init__(self):
        self.reports: dict[str, ScheduledReport] = {}
        self._running = False
    
    def register(self, report: ScheduledReport) -> None:
        """Registra un reporte programado."""
        self.reports[report.name] = report
        logger.info(f"Reporte registrado: {report.name} ({report.schedule})")
    
    def unregister(self, report_name: str) -> bool:
        """Elimina un reporte programado."""
        if report_name in self.reports:
            del self.reports[report_name]
            logger.info(f"Reporte eliminado: {report_name}")
            return True
        return False
    
    async def generate_and_send(self, report_name: str) -> bool:
        """
        Genera y envía un reporte.
        
        Args:
            report_name: Nombre del reporte
            
        Returns:
            True si fue exitoso
        """
        if report_name not in self.reports:
            logger.error(f"Reporte no encontrado: {report_name}")
            return False
        
        report = self.reports[report_name]
        
        if not report.enabled:
            logger.info(f"Reporte deshabilitado: {report_name}")
            return False
        
        try:
            logger.info(f"Generando reporte: {report_name}")
            
            # Obtener datos
            data = await self._get_data(report.data_provider)
            
            # Generar PDF
            pdf_path = report_generator.generate(
                template_name=report.template,
                data=data,
            )
            
            # Enviar por canales configurados
            for channel in report.channels:
                if channel == "telegram":
                    await self._send_telegram(report, pdf_path)
                elif channel == "email":
                    await self._send_email(report, pdf_path)
            
            report.last_run = datetime.now()
            report.last_error = None
            
            logger.info(f"Reporte enviado: {report_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error generando reporte {report_name}: {e}")
            report.last_error = str(e)
            return False
    
    async def generate_html(self, report_name: str) -> str | None:
        """
        Genera un reporte como HTML (para previsualización).
        
        Args:
            report_name: Nombre del reporte
            
        Returns:
            HTML del reporte o None si falla
        """
        if report_name not in self.reports:
            return None
        
        report = self.reports[report_name]
        
        try:
            data = await self._get_data(report.data_provider)
            return report_generator.render_html(report.template, data)
        except Exception as e:
            logger.error(f"Error renderizando reporte {report_name}: {e}")
            return None
    
    async def _get_data(self, data_provider: Callable) -> dict[str, Any]:
        """Obtiene datos del provider (sync o async)."""
        if asyncio.iscoroutinefunction(data_provider):
            return await data_provider()
        return data_provider()
    
    async def _send_telegram(self, report: ScheduledReport, pdf_path: str) -> None:
        """Envía reporte por Telegram."""
        try:
            # Usar el notification_manager para enviar documento
            await notification_manager.send_document(
                document_path=pdf_path,
                caption=f"📊 {report.name}\nGenerado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            )
        except Exception as e:
            logger.error(f"Error enviando reporte por Telegram: {e}")
            raise
    
    async def _send_email(self, report: ScheduledReport, pdf_path: str) -> None:
        """Envía reporte por email."""
        if not report.recipients:
            logger.warning(f"No hay destinatarios para reporte {report.name}")
            return
        
        try:
            await notification_manager.send_email(
                to=report.recipients,
                subject=f"[ARIA] {report.name} - {datetime.now().strftime('%d/%m/%Y')}",
                body=f"Adjunto el reporte {report.name} generado automáticamente por ARIA.",
                attachments=[pdf_path],
            )
        except Exception as e:
            logger.error(f"Error enviando reporte por email: {e}")
            raise
    
    def get_schedule(self) -> list[dict]:
        """Retorna lista de reportes programados."""
        return [
            {
                "name": r.name,
                "description": r.description,
                "template": r.template,
                "schedule": r.schedule,
                "channels": r.channels,
                "recipients": r.recipients,
                "enabled": r.enabled,
                "last_run": r.last_run.isoformat() if r.last_run else None,
                "last_error": r.last_error,
            }
            for r in self.reports.values()
        ]
    
    def enable(self, report_name: str) -> bool:
        """Habilita un reporte."""
        if report_name in self.reports:
            self.reports[report_name].enabled = True
            return True
        return False
    
    def disable(self, report_name: str) -> bool:
        """Deshabilita un reporte."""
        if report_name in self.reports:
            self.reports[report_name].enabled = False
            return True
        return False


# Instancia global
report_scheduler = ReportScheduler()
