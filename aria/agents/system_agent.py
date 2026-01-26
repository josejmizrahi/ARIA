"""
Agente de Sistema - Monitoreo y Diagnóstico.

Responsabilidades:
- Ejecutar diagnósticos periódicos del sistema
- Monitorear salud de conexiones (Odoo, Redis)
- Verificar calidad de datos
- Alertar sobre problemas detectados
- Generar reportes de estado
"""

from datetime import datetime
from typing import Any

from aria.agents.base import BaseAgent
from aria.config import settings
from aria.models.proposal import Priority
from aria.models.task import TaskDefinition, TaskResult


class SystemAgent(BaseAgent):
    """
    Agente autónomo para monitoreo del sistema ARIA.
    
    Ejecuta diagnósticos, verifica conexiones y alerta sobre problemas.
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="sistema",
            description="Monitoreo, diagnóstico y salud del sistema ARIA"
        )
        
        # Umbrales de alerta
        self.data_quality_warning_threshold = 0.7  # 70% mínimo de calidad
        self.connection_timeout_seconds = 30
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de sistema."""
        
        # Verificación de salud diaria
        self.register_task(TaskDefinition(
            name="daily_health_check",
            method="check_system_health",
            schedule="0 6 * * *",  # 6:00 AM diario
            description="Verificación diaria de salud del sistema"
        ))
        
        # Monitoreo de conexiones cada 4 horas
        self.register_task(TaskDefinition(
            name="connection_monitor",
            method="check_connections",
            schedule="0 */4 * * *",  # Cada 4 horas
            description="Verificar conexiones a Odoo y Redis"
        ))
        
        # Análisis de calidad de datos semanal
        self.register_task(TaskDefinition(
            name="data_quality_check",
            method="check_data_quality",
            schedule="0 7 * * 1",  # Lunes 7:00 AM
            description="Análisis de calidad de datos en Odoo"
        ))
        
        # Reporte de estado de agentes
        self.register_task(TaskDefinition(
            name="agents_status_report",
            method="report_agents_status",
            schedule="0 8 * * 1-5",  # 8:00 AM L-V
            description="Reporte de estado de todos los agentes"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado del sistema."""
        from aria.agents.registry import agent_registry
        
        # Contar agentes
        all_agents = agent_registry.list_all()
        running = sum(1 for a in all_agents.values() if a.is_running)
        
        # Verificar conexión Odoo
        odoo_ok = self._check_odoo_connection()
        
        # Verificar Redis
        redis_ok = await self._check_redis_connection()
        
        # Determinar estado general
        if not odoo_ok:
            status = "critical"
        elif not redis_ok:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "odoo_connected": odoo_ok,
            "redis_connected": redis_ok,
            "agents_total": len(all_agents),
            "agents_running": running,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_system_health(self) -> TaskResult:
        """Verificación completa de salud del sistema."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Ejecutando verificación de salud del sistema...")
        
        issues = []
        warnings = []
        
        # 1. Verificar Odoo
        odoo_ok = self._check_odoo_connection()
        if not odoo_ok:
            issues.append("❌ Conexión a Odoo fallida")
        
        # 2. Verificar Redis
        redis_ok = await self._check_redis_connection()
        if not redis_ok:
            warnings.append("⚠️ Redis no disponible (propuestas no persistirán)")
        
        # 3. Verificar agentes
        from aria.agents.registry import agent_registry
        
        agents_status = {}
        for name, agent in agent_registry.list_all().items():
            if name == self.name:
                continue
            try:
                summary = await agent.get_status_summary()
                status = summary.get("status", "unknown")
                agents_status[name] = status
                
                if status == "critical":
                    issues.append(f"❌ Agente {name}: estado crítico")
                elif status == "warning":
                    warnings.append(f"⚠️ Agente {name}: advertencias")
            except Exception as e:
                issues.append(f"❌ Agente {name}: error obteniendo estado ({e})")
        
        # 4. Generar mensaje
        total_agents = len(agents_status)
        ok_agents = sum(1 for s in agents_status.values() if s == "ok")
        
        message = f"""
*🔍 Verificación de Salud del Sistema*

*Conexiones:*
• Odoo: {'✅ OK' if odoo_ok else '❌ FALLO'}
• Redis: {'✅ OK' if redis_ok else '⚠️ No disponible'}

*Agentes:* {ok_agents}/{total_agents} saludables
"""
        
        if issues:
            message += "\n*❌ Problemas críticos:*\n"
            for issue in issues[:5]:
                message += f"  {issue}\n"
            
            # Crear propuesta para problemas críticos
            await self.propose(
                title="🚨 Problemas críticos en el sistema",
                description=f"{len(issues)} problemas detectados",
                priority=Priority.CRITICAL,
                situation_summary="\n".join(issues),
                proposed_action_detail="Revisar y corregir los problemas detectados",
            )
            proposals_created += 1
        
        if warnings:
            message += "\n*⚠️ Advertencias:*\n"
            for warning in warnings[:5]:
                message += f"  {warning}\n"
        
        if not issues and not warnings:
            message += "\n✅ *Todo funcionando correctamente*"
        
        # Enviar notificación
        priority = Priority.CRITICAL if issues else Priority.MEDIUM if warnings else Priority.LOW
        
        await self.notify(
            title=f"{'🚨' if issues else '⚠️' if warnings else '✅'} Estado del Sistema",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="daily_health_check",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=len(issues) == 0,
            proposals_created=proposals_created,
            data={
                "odoo_ok": odoo_ok,
                "redis_ok": redis_ok,
                "issues": len(issues),
                "warnings": len(warnings),
                "agents_status": agents_status,
            }
        )
    
    async def check_connections(self) -> TaskResult:
        """Verifica conexiones a servicios externos."""
        started_at = datetime.now()
        
        self.logger.info("Verificando conexiones...")
        
        # Verificar Odoo
        odoo_ok = self._check_odoo_connection()
        
        # Verificar Redis
        redis_ok = await self._check_redis_connection()
        
        if not odoo_ok:
            await self.notify(
                title="🚨 Conexión a Odoo perdida",
                message="No se puede conectar a Odoo. Verificar URL, credenciales y disponibilidad del servidor.",
                priority=Priority.CRITICAL,
            )
        
        return TaskResult(
            task_name="connection_monitor",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=odoo_ok,
            data={"odoo_ok": odoo_ok, "redis_ok": redis_ok}
        )
    
    async def check_data_quality(self) -> TaskResult:
        """Analiza calidad de datos en Odoo."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Analizando calidad de datos...")
        
        issues = []
        
        # 1. Productos sin categoría
        try:
            products_no_categ = len(self.search_read(
                "product.product",
                [("categ_id", "=", False), ("active", "=", True)],
                ["id"],
                limit=1000
            ))
            if products_no_categ > 0:
                issues.append(f"📦 {products_no_categ} productos sin categoría")
        except Exception:
            pass
        
        # 2. Clientes sin vendedor
        try:
            customers_no_sales = len(self.search_read(
                "res.partner",
                [("customer_rank", ">", 0), ("user_id", "=", False), ("active", "=", True)],
                ["id"],
                limit=1000
            ))
            if customers_no_sales > 0:
                issues.append(f"👥 {customers_no_sales} clientes sin vendedor asignado")
        except Exception:
            pass
        
        # 3. Contactos sin email
        try:
            contacts_no_email = len(self.search_read(
                "res.partner",
                ["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0),
                 ("email", "=", False), ("active", "=", True)],
                ["id"],
                limit=2000
            ))
            total_contacts = len(self.search_read(
                "res.partner",
                ["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0), ("active", "=", True)],
                ["id"],
                limit=2000
            ))
            if contacts_no_email > 0:
                pct = (contacts_no_email / total_contacts * 100) if total_contacts > 0 else 0
                issues.append(f"📧 {contacts_no_email} contactos sin email ({pct:.0f}%)")
        except Exception:
            pass
        
        # 4. Productos con costo >= precio
        try:
            products = self.search_read(
                "product.product",
                [("sale_ok", "=", True), ("active", "=", True), ("list_price", ">", 0)],
                ["standard_price", "list_price"],
                limit=1000
            )
            margin_issues = sum(1 for p in products if p.get("standard_price", 0) >= p.get("list_price", 0))
            if margin_issues > 0:
                issues.append(f"💰 {margin_issues} productos con costo >= precio")
        except Exception:
            pass
        
        if issues:
            message = "*📊 Problemas de Calidad de Datos*\n\n"
            for issue in issues:
                message += f"• {issue}\n"
            
            message += "\n_Estos problemas pueden afectar reportes y análisis._"
            
            # Crear propuesta si hay muchos problemas
            if len(issues) >= 3:
                await self.propose(
                    title="📊 Limpieza de datos requerida",
                    description=f"{len(issues)} categorías de datos con problemas",
                    priority=Priority.MEDIUM,
                    situation_summary=message,
                    proposed_action_detail="Revisar y corregir datos en Odoo",
                )
                proposals_created += 1
            
            await self.notify(
                title=f"📊 {len(issues)} problemas de calidad de datos",
                message=message,
                priority=Priority.MEDIUM,
            )
        else:
            await self.notify(
                title="✅ Calidad de datos OK",
                message="No se detectaron problemas significativos en los datos.",
                priority=Priority.LOW,
            )
        
        return TaskResult(
            task_name="data_quality_check",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"issues": issues}
        )
    
    async def report_agents_status(self) -> TaskResult:
        """Genera reporte de estado de todos los agentes."""
        started_at = datetime.now()
        
        self.logger.info("Generando reporte de estado de agentes...")
        
        from aria.agents.registry import agent_registry
        
        agents_data = []
        
        for name, agent in agent_registry.list_all().items():
            if name == self.name:
                continue
            
            try:
                summary = await agent.get_status_summary()
                status = summary.get("status", "unknown")
                agents_data.append({
                    "name": name,
                    "status": status,
                    "running": agent.is_running,
                    "tasks": len(agent.tasks),
                })
            except Exception as e:
                agents_data.append({
                    "name": name,
                    "status": "error",
                    "error": str(e),
                })
        
        # Contar por estado
        status_counts = {"ok": 0, "warning": 0, "critical": 0, "error": 0}
        for a in agents_data:
            status = a.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
        
        message = f"""
*📋 Estado de Agentes ARIA*

*Resumen:*
• ✅ OK: {status_counts['ok']}
• ⚠️ Warning: {status_counts['warning']}
• 🔴 Critical: {status_counts['critical']}
• ❌ Error: {status_counts['error']}

*Detalle:*
"""
        
        status_emoji = {"ok": "✅", "warning": "⚠️", "critical": "🔴", "error": "❌"}
        for a in agents_data:
            emoji = status_emoji.get(a.get("status"), "❓")
            message += f"{emoji} {a['name']}: {a.get('status', 'unknown')}\n"
        
        priority = Priority.LOW
        if status_counts["critical"] > 0:
            priority = Priority.HIGH
        elif status_counts["warning"] > 0 or status_counts["error"] > 0:
            priority = Priority.MEDIUM
        
        await self.notify(
            title=f"📋 Estado: {status_counts['ok']}/{len(agents_data)} agentes OK",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="agents_status_report",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"agents": agents_data, "counts": status_counts}
        )
    
    # ==================== Helpers ====================
    
    def _check_odoo_connection(self) -> bool:
        """Verifica conexión a Odoo."""
        try:
            self.search_read("res.users", [("id", "=", 1)], ["id"], limit=1)
            return True
        except Exception:
            return False
    
    async def _check_redis_connection(self) -> bool:
        """Verifica conexión a Redis."""
        try:
            import redis.asyncio as redis
            r = redis.from_url(settings.redis.url)
            await r.ping()
            await r.close()
            return True
        except Exception:
            return False


def create_system_agent() -> SystemAgent:
    """Crea y retorna el agente de sistema."""
    return SystemAgent()
