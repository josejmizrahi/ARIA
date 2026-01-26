"""
ARIA - Sistema de Notificaciones Multicanal
============================================

Canales soportados:
- Telegram (principal): Notificaciones instantáneas con botones de acción
- Email (fallback): Cuando Telegram falla o para reportes
- Console (desarrollo): Para pruebas locales

Prioridad determina canales:
- CRITICAL: Telegram + Email
- HIGH: Telegram
- MEDIUM/LOW: Console o Telegram según configuración
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

from aria.config import settings, NotificationChannel
from aria.models.proposal import Proposal, Priority
from aria.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from aria.utils.logger import get_logger

logger = get_logger("aria.notifications")


class NotificationError(Exception):
    """Error en envío de notificación."""
    pass


class TelegramNotifier:
    """Cliente para envío de notificaciones por Telegram."""
    
    def __init__(self) -> None:
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_admin_chat_id
        self.enabled = settings.telegram_enabled
        self._base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: Optional[dict] = None,
        disable_notification: bool = False,
    ) -> dict:
        """
        Envía mensaje por Telegram.
        
        Args:
            text: Texto del mensaje (soporta Markdown)
            parse_mode: Formato del texto (Markdown o HTML)
            reply_markup: Botones inline opcionales
            disable_notification: Si True, no hace sonido
        
        Returns:
            Respuesta de la API de Telegram
        """
        if not self.enabled:
            logger.warning("Telegram no configurado, mensaje no enviado")
            return {"ok": False, "error": "Telegram not configured"}
        
        # Telegram tiene límite de 4096 caracteres
        if len(text) > 4000:
            text = text[:3997] + "..."
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }
        
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/sendMessage",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()
                    
                    if result.get("ok"):
                        logger.info(f"Telegram enviado: {text[:50]}...")
                    else:
                        logger.error(f"Error Telegram: {result}")
                    
                    return result
                    
        except asyncio.TimeoutError:
            logger.error("Timeout enviando a Telegram")
            raise NotificationError("Telegram timeout")
        except Exception as e:
            logger.error(f"Error enviando Telegram: {e}")
            raise NotificationError(f"Telegram error: {e}")
    
    async def send_proposal(self, proposal: Proposal) -> dict:
        """
        Envía una propuesta con botones de acción.
        
        Args:
            proposal: Propuesta a enviar
        
        Returns:
            Respuesta de Telegram
        """
        # Construir mensaje
        message = proposal.to_notification_text()
        
        # Botones inline para acciones rápidas
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Aprobar",
                        "callback_data": f"approve:{proposal.short_id}"
                    },
                    {
                        "text": "❌ Rechazar", 
                        "callback_data": f"reject:{proposal.short_id}"
                    }
                ],
                [
                    {
                        "text": "📋 Ver detalles",
                        "callback_data": f"details:{proposal.short_id}"
                    },
                    {
                        "text": "⏸️ Posponer",
                        "callback_data": f"postpone:{proposal.short_id}"
                    }
                ]
            ]
        }
        
        return await self.send_message(
            text=message,
            reply_markup=keyboard,
            disable_notification=(proposal.priority == Priority.LOW)
        )
    
    async def send_execution_result(
        self,
        proposal: Proposal,
        success: bool,
        details: str = ""
    ) -> dict:
        """Notifica resultado de ejecución de una acción."""
        
        emoji = "✅" if success else "❌"
        status = "ejecutada exitosamente" if success else "falló"
        
        message = f"""
{emoji} *Acción {status}*

🆔 `{proposal.short_id}`
📋 {proposal.title}

{details if details else "Sin detalles adicionales."}
        """.strip()
        
        return await self.send_message(message)


class EmailNotifier:
    """Cliente para envío de notificaciones por Email."""
    
    def __init__(self) -> None:
        self.host = settings.notifications.email.smtp_host
        self.port = settings.notifications.email.smtp_port
        self.user = settings.notifications.email.smtp_user
        self.password = settings.notifications.email.smtp_password
        self.from_addr = settings.notifications.email.smtp_from or self.user
        self.admin_email = settings.notifications.email.admin_email
        self.enabled = settings.email_enabled
    
    async def send_email(
        self,
        subject: str,
        body: str,
        to: Optional[str] = None,
        html: bool = False,
    ) -> bool:
        """
        Envía email.
        
        Args:
            subject: Asunto del email
            body: Cuerpo del mensaje
            to: Destinatario (default: admin)
            html: Si True, body es HTML
        
        Returns:
            True si se envió correctamente
        """
        if not self.enabled:
            logger.warning("Email no configurado, mensaje no enviado")
            return False
        
        to = to or self.admin_email
        
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Construir mensaje
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[ARIA] {subject}"
            msg["From"] = self.from_addr
            msg["To"] = to
            
            # Agregar cuerpo
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))
            
            # Enviar
            async with aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                use_tls=False,
                start_tls=True,
            ) as smtp:
                await smtp.login(self.user, self.password)
                await smtp.send_message(msg)
            
            logger.info(f"Email enviado a {to}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email: {e}")
            return False
    
    async def send_proposal(self, proposal: Proposal) -> bool:
        """Envía propuesta por email."""
        
        subject = f"{proposal.priority_emoji} {proposal.agent_id}: {proposal.title}"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>{proposal.priority_emoji} {proposal.title}</h2>
            
            <p><strong>Agente:</strong> {proposal.agent_id}</p>
            <p><strong>ID:</strong> <code>{proposal.short_id}</code></p>
            <p><strong>Prioridad:</strong> {proposal.priority.value}</p>
            
            <h3>📋 Descripción</h3>
            <p>{proposal.description}</p>
            
            {f'<h3>📊 Situación</h3><pre style="background: #f5f5f5; padding: 15px; border-radius: 5px;">{proposal.situation_summary}</pre>' if proposal.situation_summary else ''}
            
            {f'<h3>💡 Acción propuesta</h3><p style="background: #e3f2fd; padding: 15px; border-radius: 5px;">{proposal.proposed_action_detail}</p>' if proposal.proposed_action_detail else ''}
            
            <hr>
            <p style="color: #666; font-size: 12px;">
                Para responder, usa Telegram o el dashboard de ARIA.<br>
                Comandos: <code>/aprobar {proposal.short_id}</code> | 
                <code>/rechazar {proposal.short_id}</code>
            </p>
        </body>
        </html>
        """
        
        return await self.send_email(subject, body, html=True)


class ConsoleNotifier:
    """Notificador para consola (desarrollo)."""
    
    async def send_message(self, text: str) -> bool:
        """Muestra mensaje en consola con formato Rich."""
        from aria.utils.logger import console, print_info
        
        console.print("\n" + "=" * 50)
        console.print("[bold cyan]📬 NOTIFICACIÓN ARIA[/bold cyan]")
        console.print("=" * 50)
        console.print(text)
        console.print("=" * 50 + "\n")
        
        return True
    
    async def send_proposal(self, proposal: Proposal) -> bool:
        """Muestra propuesta en consola."""
        from aria.utils.logger import console
        
        console.print("\n" + "=" * 60)
        console.print(f"[bold yellow]🔔 PROPUESTA PENDIENTE DE APROBACIÓN[/bold yellow]")
        console.print("=" * 60)
        console.print(f"\n[cyan]ID:[/cyan] {proposal.short_id}")
        console.print(f"[cyan]Agente:[/cyan] {proposal.agent_id}")
        console.print(f"[cyan]Prioridad:[/cyan] {proposal.priority_emoji} {proposal.priority.value}")
        console.print(f"\n[bold]{proposal.title}[/bold]")
        console.print(f"\n{proposal.description}")
        
        if proposal.situation_summary:
            console.print(f"\n[dim]Situación:[/dim]\n{proposal.situation_summary}")
        
        console.print("\n" + "-" * 60)
        console.print("[green]Comandos: aria proposal approve {id} | aria proposal reject {id}[/green]")
        console.print("=" * 60 + "\n")
        
        return True


class NotificationManager:
    """
    Gestor central de notificaciones de ARIA.
    
    Coordina envío a múltiples canales según prioridad.
    Implementa fallback automático si un canal falla.
    
    Uso:
        from aria.notification_manager import notification_manager
        
        # Enviar notificación simple
        await notification_manager.notify(
            title="Alerta",
            message="Algo pasó",
            priority=NotificationPriority.HIGH
        )
        
        # Enviar propuesta de acción
        await notification_manager.send_proposal(proposal)
    """
    
    _instance: Optional["NotificationManager"] = None
    
    def __new__(cls) -> "NotificationManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self.telegram = TelegramNotifier()
        self.email = EmailNotifier()
        self.console = ConsoleNotifier()
        
        self._initialized = True
        logger.info("NotificationManager inicializado")
    
    def _get_channels_for_priority(
        self,
        priority: NotificationPriority
    ) -> list[NotificationChannel]:
        """Determina canales según prioridad."""
        
        # Si estamos en desarrollo y no hay Telegram, usar consola
        if settings.is_development and not self.telegram.enabled:
            return [NotificationChannel.CONSOLE]
        
        if priority == NotificationPriority.CRITICAL:
            channels = [NotificationChannel.TELEGRAM]
            if self.email.enabled:
                channels.append(NotificationChannel.EMAIL)
            return channels
        
        if priority == NotificationPriority.HIGH:
            return [NotificationChannel.TELEGRAM]
        
        # MEDIUM y LOW
        if self.telegram.enabled:
            return [NotificationChannel.TELEGRAM]
        
        return [NotificationChannel.CONSOLE]
    
    async def notify(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        agent_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> Notification:
        """
        Envía notificación por los canales apropiados según prioridad.
        
        Args:
            title: Título de la notificación
            message: Mensaje completo
            priority: Nivel de prioridad
            agent_id: Agente que origina la notificación
            data: Datos adicionales
        
        Returns:
            Objeto Notification con estado de envío
        """
        notification = Notification(
            title=title,
            message=message,
            priority=priority,
            agent_id=agent_id,
            data=data or {},
        )
        
        channels = self._get_channels_for_priority(priority)
        sent_channels: list[str] = []
        
        for channel in channels:
            try:
                success = await self._send_to_channel(channel, notification)
                if success:
                    sent_channels.append(channel.value)
            except Exception as e:
                logger.error(f"Error en canal {channel}: {e}")
        
        notification.mark_sent(",".join(sent_channels) if sent_channels else "none")
        
        return notification
    
    async def send_proposal(self, proposal: Proposal) -> Notification:
        """
        Envía una propuesta de acción para aprobación.
        
        Usa prioridad de la propuesta para determinar canales.
        Incluye botones de acción en Telegram.
        
        Args:
            proposal: Propuesta a enviar
        
        Returns:
            Notification con estado de envío
        """
        # Mapear prioridad de propuesta a notificación
        priority_map = {
            Priority.LOW: NotificationPriority.LOW,
            Priority.MEDIUM: NotificationPriority.MEDIUM,
            Priority.HIGH: NotificationPriority.HIGH,
            Priority.CRITICAL: NotificationPriority.CRITICAL,
        }
        priority = priority_map.get(proposal.priority, NotificationPriority.MEDIUM)
        
        notification = Notification(
            type=NotificationType.APPROVAL_REQUEST,
            title=proposal.title,
            message=proposal.description,
            priority=priority,
            agent_id=proposal.agent_id,
            proposal_id=str(proposal.id),
        )
        
        channels = self._get_channels_for_priority(priority)
        sent_channels: list[str] = []
        
        # Intentar Telegram primero (con botones)
        if NotificationChannel.TELEGRAM in channels and self.telegram.enabled:
            try:
                await self.telegram.send_proposal(proposal)
                sent_channels.append("telegram")
            except Exception as e:
                logger.error(f"Error enviando propuesta a Telegram: {e}")
                # Fallback a email
                if self.email.enabled:
                    try:
                        await self.email.send_proposal(proposal)
                        sent_channels.append("email")
                    except Exception as e2:
                        logger.error(f"Error en fallback a email: {e2}")
        
        # Email si está en los canales
        if NotificationChannel.EMAIL in channels and "email" not in sent_channels:
            if self.email.enabled:
                try:
                    await self.email.send_proposal(proposal)
                    sent_channels.append("email")
                except Exception as e:
                    logger.error(f"Error enviando email: {e}")
        
        # Console para desarrollo
        if NotificationChannel.CONSOLE in channels:
            await self.console.send_proposal(proposal)
            sent_channels.append("console")
        
        notification.mark_sent(",".join(sent_channels) if sent_channels else "none")
        
        logger.info(
            f"Propuesta {proposal.short_id} enviada por: {sent_channels}"
        )
        
        return notification
    
    async def send_execution_result(
        self,
        proposal: Proposal,
        success: bool,
        details: str = ""
    ) -> None:
        """Notifica el resultado de una acción ejecutada."""
        
        if self.telegram.enabled:
            try:
                await self.telegram.send_execution_result(proposal, success, details)
            except Exception as e:
                logger.error(f"Error notificando resultado: {e}")
        
        # También mostrar en consola si está en desarrollo
        if settings.is_development:
            emoji = "✅" if success else "❌"
            status = "ÉXITO" if success else "FALLO"
            from aria.utils.logger import console
            console.print(f"\n{emoji} [bold]Ejecución {status}:[/bold] {proposal.short_id}")
            if details:
                console.print(f"   {details}\n")
    
    async def _send_to_channel(
        self,
        channel: NotificationChannel,
        notification: Notification
    ) -> bool:
        """Envía notificación a un canal específico."""
        
        text = f"*{notification.title}*\n\n{notification.message}"
        
        if channel == NotificationChannel.TELEGRAM:
            if not self.telegram.enabled:
                return False
            result = await self.telegram.send_message(text)
            return result.get("ok", False)
        
        if channel == NotificationChannel.EMAIL:
            if not self.email.enabled:
                return False
            return await self.email.send_email(
                subject=notification.title,
                body=notification.message,
            )
        
        if channel == NotificationChannel.CONSOLE:
            return await self.console.send_message(text)
        
        return False


# Singleton global
notification_manager = NotificationManager()
