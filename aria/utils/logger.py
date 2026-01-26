"""
ARIA - Logger Estructurado
===========================

Sistema de logging con:
- Rich console output (coloreado y formateado)
- Archivos de log rotativos
- Logging estructurado con structlog
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Tema personalizado para Rich
ARIA_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "critical": "red bold reverse",
    "success": "green",
    "debug": "dim",
    "timestamp": "dim cyan",
    "agent": "magenta bold",
    "model": "blue",
})

console = Console(theme=ARIA_THEME)

# Flag para evitar múltiples configuraciones
_logging_configured = False


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path | str = "./logs",
    log_to_file: bool = True,
    json_logs: bool = False
) -> None:
    """
    Configura el sistema de logging.
    
    Args:
        log_level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio para archivos de log
        log_to_file: Si debe escribir a archivos
        json_logs: Si debe usar formato JSON (para producción)
    """
    global _logging_configured
    
    if _logging_configured:
        return
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar nivel
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Handlers
    handlers: list[logging.Handler] = []
    
    # Rich handler para consola
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    rich_handler.setLevel(level)
    handlers.append(rich_handler)
    
    # File handler
    if log_to_file:
        log_file = log_dir / "aria.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    
    # Configurar logging básico
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )
    
    # Configurar structlog
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_logs:
        # JSON para producción
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Console para desarrollo
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback
            )
        )
    
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    _logging_configured = True


def get_logger(name: str = "aria") -> structlog.stdlib.BoundLogger:
    """
    Obtiene un logger estructurado.
    
    Args:
        name: Nombre del logger (usualmente __name__)
        
    Returns:
        Logger estructurado listo para usar.
        
    Uso:
        logger = get_logger(__name__)
        logger.info("Mensaje", extra_field="valor")
    """
    # Asegurar que logging esté configurado
    if not _logging_configured:
        setup_logging()
    
    return structlog.get_logger(name)


class AriaLogger:
    """
    Logger con métodos de conveniencia para ARIA.
    
    Proporciona métodos adicionales para logging de agentes,
    propuestas y notificaciones.
    """
    
    def __init__(self, name: str = "aria"):
        self._logger = get_logger(name)
    
    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log nivel DEBUG."""
        self._logger.debug(msg, **kwargs)
    
    def info(self, msg: str, **kwargs: Any) -> None:
        """Log nivel INFO."""
        self._logger.info(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log nivel WARNING."""
        self._logger.warning(msg, **kwargs)
    
    def error(self, msg: str, **kwargs: Any) -> None:
        """Log nivel ERROR."""
        self._logger.error(msg, **kwargs)
    
    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log nivel CRITICAL."""
        self._logger.critical(msg, **kwargs)
    
    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log de excepción con traceback."""
        self._logger.exception(msg, **kwargs)
    
    # Métodos específicos de ARIA
    
    def agent_start(self, agent_id: str, **kwargs: Any) -> None:
        """Log de inicio de agente."""
        self._logger.info(
            f"🤖 Agente iniciado: {agent_id}",
            agent_id=agent_id,
            event="agent_start",
            **kwargs
        )
    
    def agent_stop(self, agent_id: str, **kwargs: Any) -> None:
        """Log de parada de agente."""
        self._logger.info(
            f"🛑 Agente detenido: {agent_id}",
            agent_id=agent_id,
            event="agent_stop",
            **kwargs
        )
    
    def proposal_created(
        self,
        proposal_id: str,
        agent_id: str,
        action: str,
        **kwargs: Any
    ) -> None:
        """Log de propuesta creada."""
        self._logger.info(
            f"📋 Propuesta creada: {action}",
            proposal_id=proposal_id,
            agent_id=agent_id,
            action=action,
            event="proposal_created",
            **kwargs
        )
    
    def proposal_approved(self, proposal_id: str, **kwargs: Any) -> None:
        """Log de propuesta aprobada."""
        self._logger.info(
            f"✅ Propuesta aprobada: {proposal_id}",
            proposal_id=proposal_id,
            event="proposal_approved",
            **kwargs
        )
    
    def proposal_rejected(self, proposal_id: str, **kwargs: Any) -> None:
        """Log de propuesta rechazada."""
        self._logger.warning(
            f"❌ Propuesta rechazada: {proposal_id}",
            proposal_id=proposal_id,
            event="proposal_rejected",
            **kwargs
        )
    
    def task_start(self, task_id: str, task_name: str, **kwargs: Any) -> None:
        """Log de inicio de tarea."""
        self._logger.info(
            f"▶️ Tarea iniciada: {task_name}",
            task_id=task_id,
            task_name=task_name,
            event="task_start",
            **kwargs
        )
    
    def task_complete(
        self,
        task_id: str,
        task_name: str,
        duration: float,
        **kwargs: Any
    ) -> None:
        """Log de tarea completada."""
        self._logger.info(
            f"✔️ Tarea completada: {task_name} ({duration:.2f}s)",
            task_id=task_id,
            task_name=task_name,
            duration=duration,
            event="task_complete",
            **kwargs
        )
    
    def task_failed(
        self,
        task_id: str,
        task_name: str,
        error: str,
        **kwargs: Any
    ) -> None:
        """Log de tarea fallida."""
        self._logger.error(
            f"💥 Tarea fallida: {task_name}",
            task_id=task_id,
            task_name=task_name,
            error=error,
            event="task_failed",
            **kwargs
        )
    
    def odoo_operation(
        self,
        model: str,
        method: str,
        count: int | None = None,
        **kwargs: Any
    ) -> None:
        """Log de operación Odoo."""
        msg = f"🔄 Odoo: {model}.{method}"
        if count is not None:
            msg += f" ({count} registros)"
        self._logger.debug(
            msg,
            model=model,
            method=method,
            count=count,
            event="odoo_operation",
            **kwargs
        )


def print_banner() -> None:
    """Imprime el banner de ARIA."""
    from aria import __version__
    
    banner = f"""
[bold cyan]
     █████╗ ██████╗ ██╗ █████╗ 
    ██╔══██╗██╔══██╗██║██╔══██╗
    ███████║██████╔╝██║███████║
    ██╔══██║██╔══██╗██║██╔══██║
    ██║  ██║██║  ██║██║██║  ██║
    ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
[/bold cyan]
[dim]Autonomous Resource Intelligence Agent[/dim]
[dim cyan]Version {__version__}[/dim cyan]
"""
    console.print(banner)


def print_success(message: str) -> None:
    """Imprime mensaje de éxito."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Imprime mensaje de error."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Imprime advertencia."""
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    """Imprime información."""
    console.print(f"[cyan]ℹ[/cyan] {message}")
