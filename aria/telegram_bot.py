"""
ARIA - Bot de Telegram
=======================

Bot de Telegram para interacción con ARIA.

Permite al administrador:
- Recibir notificaciones de propuestas
- Aprobar/rechazar con comandos o botones
- Ver estado del sistema
- Ejecutar inspecciones y recibir alertas
- Ejecutar acciones rápidas

Comandos:
- /start - Mensaje de bienvenida
- /status - Estado del sistema
- /pending - Lista propuestas pendientes
- /aprobar <id> - Aprobar propuesta
- /rechazar <id> [razón] - Rechazar propuesta
- /detalles <id> - Ver detalles de propuesta
- /inspect [agente] - Ejecutar inspección
- /alertas - Ver último reporte de inspección
- /help - Ayuda
"""

import asyncio
from typing import Optional

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("aria.telegram_bot")


class AriaTelegramBot:
    """
    Bot de Telegram para interacción con ARIA.
    
    Uso:
        from aria.telegram_bot import telegram_bot
        
        # Iniciar bot
        await telegram_bot.start()
        
        # Detener bot
        await telegram_bot.stop()
    """
    
    def __init__(self) -> None:
        if not settings.telegram_enabled:
            logger.warning("Telegram no configurado")
            self.enabled = False
            self.bot = None
            self.dp = None
            return
        
        self.enabled = True
        self.admin_chat_id = settings.telegram_admin_chat_id
        
        # Importar aiogram solo si está habilitado
        try:
            from aiogram import Bot, Dispatcher, F
            from aiogram.enums import ParseMode
            from aiogram.client.default import DefaultBotProperties
            
            self.bot = Bot(
                token=settings.telegram_bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
            )
            self.dp = Dispatcher()
            self._F = F
            
            self._register_handlers()
            
        except ImportError:
            logger.error("aiogram no instalado. Ejecuta: pip install aiogram")
            self.enabled = False
            self.bot = None
            self.dp = None
    
    def _register_handlers(self) -> None:
        """Registra handlers de comandos y callbacks."""
        from aiogram.filters import Command, CommandStart
        
        # Comandos
        self.dp.message.register(self._cmd_start, CommandStart())
        self.dp.message.register(self._cmd_help, Command("help", "ayuda"))
        self.dp.message.register(self._cmd_status, Command("status", "estado"))
        self.dp.message.register(self._cmd_pending, Command("pending", "pendientes"))
        self.dp.message.register(self._cmd_approve, Command("aprobar", "approve"))
        self.dp.message.register(self._cmd_reject, Command("rechazar", "reject"))
        self.dp.message.register(self._cmd_details, Command("detalles", "details"))
        self.dp.message.register(self._cmd_inspect, Command("inspect", "inspeccionar"))
        self.dp.message.register(self._cmd_alerts, Command("alertas", "alerts"))
        
        # Callbacks de botones inline
        self.dp.callback_query.register(
            self._callback_approve, 
            self._F.data.startswith("approve:")
        )
        self.dp.callback_query.register(
            self._callback_reject, 
            self._F.data.startswith("reject:")
        )
        self.dp.callback_query.register(
            self._callback_details, 
            self._F.data.startswith("details:")
        )
        self.dp.callback_query.register(
            self._callback_postpone, 
            self._F.data.startswith("postpone:")
        )
    
    async def start(self) -> None:
        """Inicia el bot."""
        if not self.enabled:
            logger.warning("Bot de Telegram deshabilitado")
            return
        
        logger.info("Iniciando bot de Telegram...")
        
        # Enviar mensaje de inicio al admin
        try:
            await self.bot.send_message(
                self.admin_chat_id,
                "🤖 *ARIA Bot iniciado*\n\n"
                "Estoy listo para recibir comandos.\n"
                "Usa /help para ver los comandos disponibles."
            )
        except Exception as e:
            logger.error(f"Error enviando mensaje de inicio: {e}")
        
        await self.dp.start_polling(self.bot)
    
    async def stop(self) -> None:
        """Detiene el bot."""
        if self.enabled and self.dp:
            await self.dp.stop_polling()
            if self.bot:
                await self.bot.session.close()
    
    # ==================== Comandos ====================
    
    async def _cmd_start(self, message) -> None:
        """Comando /start"""
        await message.answer(
            "🤖 *ARIA - Autonomous Resource Intelligence Agent*\n\n"
            "Soy tu asistente de gestión empresarial. Te notificaré sobre "
            "situaciones que requieren tu atención y ejecutaré las acciones que apruebes.\n\n"
            "Usa /help para ver los comandos disponibles."
        )
    
    async def _cmd_help(self, message) -> None:
        """Comando /help"""
        await message.answer(
            "*📚 Comandos disponibles:*\n\n"
            "*Propuestas:*\n"
            "📋 `/pending` - Propuestas pendientes\n"
            "✅ `/aprobar <id>` - Aprobar propuesta\n"
            "❌ `/rechazar <id> [razón]` - Rechazar propuesta\n"
            "🔍 `/detalles <id>` - Ver detalles\n\n"
            "*Inspección:*\n"
            "🔎 `/inspect [agente]` - Ejecutar inspección\n"
            "🚨 `/alertas` - Ver último reporte\n\n"
            "*Sistema:*\n"
            "📊 `/status` - Estado del sistema\n"
            "❓ `/help` - Esta ayuda\n\n"
            "_También puedes usar los botones en las notificaciones._"
        )
    
    async def _cmd_status(self, message) -> None:
        """Comando /status"""
        from aria.approval_engine import approval_engine
        
        try:
            stats = await approval_engine.get_stats()
            
            await message.answer(
                "📊 *Estado de ARIA*\n\n"
                f"📋 Total propuestas: {stats['total']}\n"
                f"⏳ Pendientes: {stats['pending']}\n"
                f"✅ Aprobadas: {stats['approved']}\n"
                f"❌ Rechazadas: {stats['rejected']}\n"
                f"▶️ Completadas: {stats['completed']}\n"
                f"⚠️ Fallidas: {stats['failed']}"
            )
        except Exception as e:
            await message.answer(f"❌ Error obteniendo estado: {e}")
    
    async def _cmd_pending(self, message) -> None:
        """Comando /pending"""
        from aria.approval_engine import approval_engine
        
        try:
            pending = await approval_engine.get_pending(limit=10)
            
            if not pending:
                await message.answer("✅ No hay propuestas pendientes")
                return
            
            text = f"*📋 Propuestas pendientes ({len(pending)}):*\n\n"
            
            for p in pending:
                text += f"{p.priority_emoji} `{p.short_id}` - *{p.agent_id}*\n"
                text += f"   {p.title[:50]}{'...' if len(p.title) > 50 else ''}\n\n"
            
            text += "_Usa /detalles <id> para más información_"
            
            await message.answer(text)
            
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
    
    async def _cmd_approve(self, message) -> None:
        """Comando /aprobar <id>"""
        from aria.approval_engine import approval_engine
        from aria.action_executor import action_executor
        
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer("❌ Uso: `/aprobar <id>`")
            return
        
        proposal_id = args[1].strip()
        
        try:
            proposal = await approval_engine.approve(proposal_id, approved_by="telegram")
            
            await message.answer(
                f"✅ *Propuesta aprobada*\n\n"
                f"🆔 `{proposal.short_id}`\n"
                f"📋 {proposal.title}\n\n"
                f"_Ejecutando acción..._"
            )
            
            # Ejecutar acción
            try:
                result = await action_executor.execute(proposal)
                await message.answer(
                    f"✅ *Acción ejecutada*\n\n"
                    f"```json\n{result}\n```"
                )
            except Exception as e:
                await message.answer(f"⚠️ Error ejecutando: {e}")
                
        except Exception as e:
            await message.answer(f"❌ {e}")
    
    async def _cmd_reject(self, message) -> None:
        """Comando /rechazar <id> [razón]"""
        from aria.approval_engine import approval_engine
        
        args = message.text.split(maxsplit=2)
        
        if len(args) < 2:
            await message.answer("❌ Uso: `/rechazar <id> [razón]`")
            return
        
        proposal_id = args[1].strip()
        reason = args[2].strip() if len(args) > 2 else ""
        
        try:
            proposal = await approval_engine.reject(
                proposal_id,
                reason=reason,
                rejected_by="telegram"
            )
            
            await message.answer(
                f"❌ *Propuesta rechazada*\n\n"
                f"🆔 `{proposal.short_id}`\n"
                f"📋 {proposal.title}\n"
                f"📝 Razón: {reason or 'No especificada'}"
            )
            
        except Exception as e:
            await message.answer(f"❌ {e}")
    
    async def _cmd_details(self, message) -> None:
        """Comando /detalles <id>"""
        from aria.approval_engine import approval_engine
        
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.answer("❌ Uso: `/detalles <id>`")
            return
        
        proposal_id = args[1].strip()
        
        try:
            proposal = await approval_engine.get(proposal_id)
            
            if not proposal:
                await message.answer("❌ Propuesta no encontrada")
                return
            
            text = (
                f"{proposal.priority_emoji} *{proposal.title}*\n\n"
                f"🆔 ID: `{proposal.short_id}`\n"
                f"🤖 Agente: {proposal.agent_id}\n"
                f"📊 Estado: {proposal.status.value}\n"
                f"📅 Creada: {proposal.created_at.strftime('%d/%m/%Y %H:%M')}\n\n"
                f"*📝 Descripción:*\n{proposal.description}\n"
            )
            
            if proposal.situation_summary:
                text += f"\n*📊 Situación:*\n```\n{proposal.situation_summary}\n```\n"
            
            if proposal.proposed_action_detail:
                text += f"\n*💡 Acción propuesta:*\n{proposal.proposed_action_detail}"
            
            if proposal.alternatives:
                text += "\n\n*🔄 Alternativas:*\n"
                for alt in proposal.alternatives:
                    text += f"• {alt.get('description', alt)}\n"
            
            # Truncar si es muy largo
            if len(text) > 4000:
                text = text[:3997] + "..."
            
            await message.answer(text)
            
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
    
    async def _cmd_inspect(self, message) -> None:
        """Comando /inspect [agente]"""
        args = message.text.split(maxsplit=1)
        
        await message.answer("🔎 *Ejecutando inspección...*\n\n_Esto puede tomar unos segundos._")
        
        try:
            if len(args) > 1:
                # Inspección de un agente específico
                agent_name = args[1].strip().lower()
                
                from aria.inspection import get_inspector
                from aria.inspection.models import ImpactLevel
                
                try:
                    inspector = get_inspector(agent_name)
                except ValueError:
                    valid = ["inventario", "cobranza", "ventas", "compras", "finanzas", 
                             "produccion", "rrhh", "costos", "crm", "contabilidad", "ceo", "sistema"]
                    await message.answer(
                        f"❌ Agente no encontrado: {agent_name}\n\n"
                        f"*Agentes válidos:*\n" + "\n".join(f"• {a}" for a in valid)
                    )
                    return
                
                report = inspector.inspect(
                    max_level=3,
                    create_proposals=True,
                    min_severity_for_proposal=ImpactLevel.HIGH,
                )
                
                # Construir respuesta
                status_emoji = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}.get(
                    report.context.status, "⚪"
                )
                
                text = (
                    f"*🔎 Inspección: {agent_name.upper()}*\n\n"
                    f"{status_emoji} Estado: {report.context.status.upper()}\n"
                    f"📊 Health Score: {report.context.health_score:.0f}%\n"
                    f"📋 Hallazgos: {len(report.findings)}\n"
                    f"🔴 Críticos: {report.critical_count}\n"
                    f"🟠 Altos: {report.high_count}\n"
                )
                
                if report.proposals_created > 0:
                    text += f"✅ Propuestas creadas: {report.proposals_created}\n"
                
                # Mostrar hallazgos críticos
                critical = report.findings_by_severity.get("critical", [])
                if critical:
                    text += "\n*🔴 Hallazgos Críticos:*\n"
                    for f in critical[:3]:
                        text += f"• {f.title}\n"
                    if len(critical) > 3:
                        text += f"_...y {len(critical) - 3} más_\n"
                
                # Mostrar hallazgos altos
                high = report.findings_by_severity.get("high", [])
                if high:
                    text += "\n*🟠 Hallazgos Altos:*\n"
                    for f in high[:3]:
                        text += f"• {f.title}\n"
                    if len(high) > 3:
                        text += f"_...y {len(high) - 3} más_\n"
                
                await message.answer(text)
                
            else:
                # Inspección completa
                from aria.inspection.scheduled_inspection import scheduled_inspection
                
                summary = await scheduled_inspection.run_daily_inspection(
                    max_level=2,
                    create_proposals=True,
                    notify_telegram=False,  # No notificar de nuevo
                )
                
                # Construir respuesta
                text = (
                    f"*🔎 Inspección Completa*\n\n"
                    f"📅 {summary['timestamp'][:16].replace('T', ' ')}\n\n"
                    f"*Resumen:*\n"
                    f"📋 Total hallazgos: {summary['total_findings']}\n"
                    f"🔴 Críticos: {summary['critical_count']}\n"
                    f"🟠 Altos: {summary['high_count']}\n"
                    f"✅ Propuestas: {summary['proposals_created']}\n\n"
                )
                
                if summary["agents_critical"]:
                    text += "*⚠️ Agentes CRÍTICOS:*\n"
                    for a in summary["agents_critical"]:
                        text += f"• {a['name']}: {a['health']:.0f}%\n"
                    text += "\n"
                
                if summary["agents_warning"]:
                    text += "*🟡 Agentes WARNING:*\n"
                    for a in summary["agents_warning"]:
                        text += f"• {a['name']}: {a['health']:.0f}%\n"
                    text += "\n"
                
                text += f"*🟢 Saludables:* {len(summary['agents_healthy'])}\n"
                
                await message.answer(text)
                
        except Exception as e:
            logger.error(f"Error en inspección: {e}")
            await message.answer(f"❌ Error: {e}")
    
    async def _cmd_alerts(self, message) -> None:
        """Comando /alertas - Muestra último reporte de inspección"""
        try:
            from aria.inspection.scheduled_inspection import scheduled_inspection
            
            report = scheduled_inspection.get_last_report()
            last_run = scheduled_inspection.get_last_run()
            
            if not report:
                await message.answer(
                    "📭 *No hay reportes recientes*\n\n"
                    "Ejecuta `/inspect` para generar uno."
                )
                return
            
            text = (
                f"*🚨 Último Reporte de Inspección*\n\n"
                f"📅 {last_run.strftime('%Y-%m-%d %H:%M') if last_run else 'N/A'}\n\n"
                f"*Resumen:*\n"
                f"🔴 Críticos: {report['critical_count']}\n"
                f"🟠 Altos: {report['high_count']}\n"
                f"📋 Total: {report['total_findings']}\n"
                f"✅ Propuestas: {report['proposals_created']}\n\n"
            )
            
            if report["critical_findings"]:
                text += "*🔴 Hallazgos Críticos:*\n"
                for f in report["critical_findings"][:5]:
                    text += f"\n*{f['agent']}*: {f['title']}\n"
                    if f.get("affected_amount"):
                        text += f"   💰 ${f['affected_amount']:,.2f}\n"
            
            await message.answer(text)
            
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
    
    # ==================== Callbacks de Botones ====================
    
    async def _callback_approve(self, callback) -> None:
        """Callback para botón Aprobar"""
        from aria.approval_engine import approval_engine
        from aria.action_executor import action_executor
        
        proposal_id = callback.data.split(":")[1]
        
        try:
            proposal = await approval_engine.approve(proposal_id, approved_by="telegram")
            
            await callback.answer("✅ Aprobado")
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ *APROBADO*",
                reply_markup=None
            )
            
            # Ejecutar
            try:
                await action_executor.execute(proposal)
            except Exception as e:
                await callback.message.answer(f"⚠️ Error ejecutando: {e}")
                
        except Exception as e:
            await callback.answer(f"Error: {e}", show_alert=True)
    
    async def _callback_reject(self, callback) -> None:
        """Callback para botón Rechazar"""
        from aria.approval_engine import approval_engine
        
        proposal_id = callback.data.split(":")[1]
        
        try:
            await approval_engine.reject(proposal_id, rejected_by="telegram")
            
            await callback.answer("❌ Rechazado")
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ *RECHAZADO*",
                reply_markup=None
            )
            
        except Exception as e:
            await callback.answer(f"Error: {e}", show_alert=True)
    
    async def _callback_details(self, callback) -> None:
        """Callback para botón Ver detalles"""
        from aria.approval_engine import approval_engine
        import json
        
        proposal_id = callback.data.split(":")[1]
        
        try:
            proposal = await approval_engine.get(proposal_id)
            
            if proposal and proposal.supporting_data:
                details = (
                    f"*📊 Datos adicionales:*\n\n"
                    f"```json\n{json.dumps(proposal.supporting_data, indent=2, default=str)[:3500]}\n```"
                )
                await callback.message.answer(details)
            else:
                await callback.message.answer("No hay datos adicionales disponibles.")
            
            await callback.answer()
            
        except Exception as e:
            await callback.answer(f"Error: {e}", show_alert=True)
    
    async def _callback_postpone(self, callback) -> None:
        """Callback para botón Posponer"""
        await callback.answer("⏸️ Propuesta pospuesta")
        await callback.message.answer(
            "La propuesta ha sido pospuesta. "
            "Aparecerá nuevamente en la lista de pendientes.\n\n"
            "Usa `/pending` para ver todas las propuestas pendientes."
        )


# Singleton global
_telegram_bot: Optional[AriaTelegramBot] = None


def get_telegram_bot() -> AriaTelegramBot:
    """Obtiene instancia del bot de Telegram."""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = AriaTelegramBot()
    return _telegram_bot


# Para importación directa
telegram_bot = get_telegram_bot()
