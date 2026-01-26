"""
ARIA - Programador de Tareas
=============================

Programador de tareas para los agentes de ARIA.

Usa APScheduler para ejecutar tareas según su schedule cron.
Integra con el AgentRegistry para ejecutar tareas de todos los agentes.
"""

from datetime import datetime
from typing import Optional

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("aria.scheduler")


class TaskScheduler:
    """
    Programador de tareas basado en APScheduler.
    
    Ejecuta las tareas de los agentes según su schedule cron definido.
    
    Uso:
        from aria.scheduler import task_scheduler
        
        # Iniciar scheduler
        await task_scheduler.start()
        
        # Ejecutar tarea manualmente
        await task_scheduler.run_task_now("cobranza", "check_overdue")
        
        # Ver próximas ejecuciones
        schedule = task_scheduler.get_schedule()
        
        # Detener
        await task_scheduler.stop()
    """
    
    _instance: Optional["TaskScheduler"] = None
    
    def __new__(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._scheduler = None
        self.is_running = False
        self._initialized = True
    
    def _get_scheduler(self):
        """Obtiene el scheduler de APScheduler (lazy loading)."""
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                
                self._scheduler = AsyncIOScheduler(
                    job_defaults={
                        "coalesce": True,  # Combinar ejecuciones perdidas
                        "max_instances": 1,  # Solo una instancia por tarea
                        "misfire_grace_time": 60 * 5,  # 5 minutos de gracia
                    }
                )
            except ImportError:
                logger.error("APScheduler no instalado. Ejecuta: pip install apscheduler")
                raise
        return self._scheduler
    
    async def start(self, include_inspection: bool = True) -> None:
        """
        Inicia el scheduler y programa todas las tareas.
        
        Args:
            include_inspection: Si incluir inspección diaria automática
        """
        if self.is_running:
            logger.warning("Scheduler ya está corriendo")
            return
        
        from aria.agents.registry import agent_registry
        
        logger.info("Iniciando scheduler...")
        
        scheduler = self._get_scheduler()
        
        # Programar tareas de todos los agentes
        for agent in agent_registry.list_all():
            self._schedule_agent_tasks(agent)
        
        # Programar inspección diaria automática
        if include_inspection:
            self._schedule_daily_inspection()
        
        # Iniciar APScheduler
        scheduler.start()
        self.is_running = True
        
        jobs_count = len(scheduler.get_jobs())
        logger.info(f"Scheduler iniciado con {jobs_count} tareas")
    
    async def stop(self) -> None:
        """Detiene el scheduler."""
        if not self.is_running:
            return
        
        if self._scheduler:
            self._scheduler.shutdown(wait=True)
        
        self.is_running = False
        logger.info("Scheduler detenido")
    
    def _schedule_agent_tasks(self, agent: "BaseAgent") -> None:
        """Programa todas las tareas de un agente."""
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = self._get_scheduler()
        
        for task in agent.tasks:
            if not task.enabled:
                continue
            
            job_id = f"{agent.name}:{task.name}"
            
            # Parsear cron expression
            try:
                trigger = CronTrigger.from_crontab(task.schedule)
            except Exception as e:
                logger.error(f"Error en schedule de {job_id}: {e}")
                continue
            
            # Agregar job
            scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=job_id,
                name=f"{agent.name} - {task.description}",
                args=[agent.name, task.name],
                replace_existing=True,
            )
            
            # Calcular próxima ejecución
            try:
                from croniter import croniter
                cron = croniter(task.schedule, datetime.now())
                task.next_run = cron.get_next(datetime)
            except ImportError:
                pass
            
            logger.debug(f"Tarea programada: {job_id} -> {task.schedule}")
    
    def _schedule_daily_inspection(self) -> None:
        """Programa la inspección diaria automática."""
        from apscheduler.triggers.cron import CronTrigger
        
        scheduler = self._get_scheduler()
        
        # Inspección diaria a las 7:00 AM
        scheduler.add_job(
            self._execute_daily_inspection,
            trigger=CronTrigger(hour=7, minute=0),
            id="aria:daily_inspection",
            name="ARIA - Inspección Diaria",
            replace_existing=True,
        )
        
        # Inspección de alertas cada 4 horas
        scheduler.add_job(
            self._execute_alert_inspection,
            trigger=CronTrigger(hour="*/4", minute=30),
            id="aria:alert_inspection",
            name="ARIA - Inspección de Alertas",
            replace_existing=True,
        )
        
        logger.info("Inspección diaria programada: 07:00 y cada 4 horas")
    
    async def _execute_daily_inspection(self) -> None:
        """Ejecuta la inspección diaria completa."""
        from aria.inspection.scheduled_inspection import scheduled_inspection
        
        logger.info("Ejecutando inspección diaria programada...")
        
        try:
            await scheduled_inspection.run_daily_inspection(
                max_level=3,
                create_proposals=True,
                notify_telegram=True,
            )
        except Exception as e:
            logger.error(f"Error en inspección diaria: {e}")
    
    async def _execute_alert_inspection(self) -> None:
        """Ejecuta inspección rápida para alertas."""
        from aria.inspection.scheduled_inspection import scheduled_inspection
        
        logger.info("Ejecutando inspección de alertas...")
        
        try:
            summary = await scheduled_inspection.run_and_alert()
            
            # Solo loggear si hay críticos
            if summary["critical_count"] > 0:
                logger.warning(
                    f"Inspección detectó {summary['critical_count']} críticos"
                )
        except Exception as e:
            logger.error(f"Error en inspección de alertas: {e}")
    
    async def _execute_task(self, agent_name: str, task_name: str) -> None:
        """Ejecuta una tarea específica."""
        from aria.agents.registry import agent_registry
        
        agent = agent_registry.get(agent_name)
        
        if not agent:
            logger.error(f"Agente no encontrado: {agent_name}")
            return
        
        if not agent.is_running:
            logger.warning(f"Agente {agent_name} no está corriendo, saltando tarea")
            return
        
        task = agent.get_task(task_name)
        if not task:
            logger.error(f"Tarea no encontrada: {agent_name}.{task_name}")
            return
        
        await agent.run_task(task)
    
    async def run_task_now(self, agent_name: str, task_name: str) -> "TaskResult":
        """
        Ejecuta una tarea inmediatamente (fuera del schedule).
        
        Args:
            agent_name: Nombre del agente
            task_name: Nombre de la tarea
        
        Returns:
            Resultado de la ejecución
        """
        from aria.agents.registry import agent_registry
        from aria.models.task import TaskResult
        
        agent = agent_registry.get(agent_name)
        
        if not agent:
            raise ValueError(f"Agente no encontrado: {agent_name}")
        
        task = agent.get_task(task_name)
        if not task:
            raise ValueError(f"Tarea no encontrada: {task_name}")
        
        logger.info(f"Ejecutando tarea manual: {agent_name}.{task_name}")
        
        return await agent.run_task(task)
    
    def get_schedule(self) -> list[dict]:
        """
        Retorna el calendario de tareas programadas.
        
        Returns:
            Lista de tareas con próxima ejecución
        """
        from aria.agents.registry import agent_registry
        
        schedule = []
        
        for agent in agent_registry.list_all():
            for task in agent.tasks:
                job_id = f"{agent.name}:{task.name}"
                
                next_run = None
                if self._scheduler:
                    job = self._scheduler.get_job(job_id)
                    if job and job.next_run_time:
                        next_run = job.next_run_time.isoformat()
                
                schedule.append({
                    "agent": agent.name,
                    "task": task.name,
                    "description": task.description,
                    "schedule": task.schedule,
                    "enabled": task.enabled,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "next_run": next_run,
                    "last_success": task.last_result.success if task.last_result else None,
                })
        
        # Ordenar por próxima ejecución
        schedule.sort(key=lambda x: x.get("next_run") or "9999")
        
        return schedule
    
    def pause_task(self, agent_name: str, task_name: str) -> None:
        """Pausa una tarea."""
        job_id = f"{agent_name}:{task_name}"
        if self._scheduler:
            self._scheduler.pause_job(job_id)
            logger.info(f"Tarea pausada: {job_id}")
    
    def resume_task(self, agent_name: str, task_name: str) -> None:
        """Resume una tarea pausada."""
        job_id = f"{agent_name}:{task_name}"
        if self._scheduler:
            self._scheduler.resume_job(job_id)
            logger.info(f"Tarea resumida: {job_id}")


# Singleton global
task_scheduler = TaskScheduler()


# Import para type hints
from aria.agents.base import BaseAgent  # noqa: E402
from aria.models.task import TaskResult  # noqa: E402
