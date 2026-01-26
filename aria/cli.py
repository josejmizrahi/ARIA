"""
ARIA - Command Line Interface
==============================

CLI principal usando Typer.

Comandos:
    aria version           - Ver versión
    aria check             - Verificar configuración
    aria introspect        - Descubrir estructura del ERP
    aria serve             - Iniciar servidor
    aria agent             - Gestionar agentes
    aria proposal          - Gestionar propuestas
    aria bot               - Iniciar bot de Telegram
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aria import __version__
from aria.config import settings
from aria.utils.logger import (
    console,
    print_banner,
    print_error,
    print_info,
    print_success,
    print_warning,
    setup_logging,
)

# CLI principal
app = typer.Typer(
    name="aria",
    help="ARIA - Autonomous Resource Intelligence Agent para Odoo ERP",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Sub-comandos
agent_app = typer.Typer(help="Gestión de agentes")
app.add_typer(agent_app, name="agent")

proposal_app = typer.Typer(help="Gestión de propuestas")
app.add_typer(proposal_app, name="proposal")

scheduler_app = typer.Typer(help="Gestión del scheduler")
app.add_typer(scheduler_app, name="scheduler")


@app.command()
def version() -> None:
    """Muestra la versión de ARIA."""
    print_banner()


@app.command()
def check(
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Mostrar información detallada"
    )
) -> None:
    """Verifica la configuración y conexión a Odoo."""
    print_banner()
    console.print("\n[bold]Verificando configuración...[/bold]\n")
    
    # Mostrar configuración
    table = Table(title="Configuración ARIA", show_header=True)
    table.add_column("Parámetro", style="cyan")
    table.add_column("Valor", style="green")
    
    table.add_row("Entorno", settings.env.value)
    table.add_row("Debug", "✓" if settings.debug else "✗")
    table.add_row("Log Level", settings.log_level.value)
    table.add_row("Log Dir", str(settings.log_dir))
    table.add_row("Telegram", "✓" if settings.telegram_enabled else "✗")
    table.add_row("Email", "✓" if settings.email_enabled else "✗")
    table.add_row("Redis", settings.redis_url)
    
    console.print(table)
    console.print()
    
    # Verificar Odoo
    console.print("[bold]Verificando conexión a Odoo...[/bold]")
    
    odoo_table = Table(show_header=True)
    odoo_table.add_column("Parámetro", style="cyan")
    odoo_table.add_column("Valor", style="yellow")
    
    odoo_table.add_row("URL", settings.odoo.url)
    odoo_table.add_row("Base de datos", settings.odoo.db)
    odoo_table.add_row("Usuario", settings.odoo.user)
    odoo_table.add_row("Timeout", f"{settings.odoo.timeout}s")
    
    console.print(odoo_table)
    console.print()
    
    # Intentar conexión
    try:
        from aria.odoo_client import OdooClient
        
        client = OdooClient.get_instance()
        version_info = client.check_connection()
        
        print_success(
            f"Conexión exitosa - Odoo {version_info.get('server_version', 'desconocido')}"
        )
        
        if verbose:
            console.print("\n[dim]Información del servidor:[/dim]")
            for key, value in version_info.items():
                console.print(f"  [cyan]{key}:[/cyan] {value}")
        
        # Verificar autenticación
        uid = client.authenticate()
        print_success(f"Autenticación exitosa (UID: {uid})")
        
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        raise typer.Exit(code=1)
    
    console.print("\n[green bold]✓ Todas las verificaciones pasaron[/green bold]")


@app.command()
def introspect(
    all_models: bool = typer.Option(
        False, "--all", "-a",
        help="Listar todos los modelos disponibles"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Mostrar información de un modelo específico"
    ),
    limit: int = typer.Option(
        50, "--limit", "-l",
        help="Límite de modelos a mostrar"
    )
) -> None:
    """Descubre la estructura del ERP Odoo."""
    setup_logging(settings.log_level.value)
    
    from aria.odoo_client import OdooClient
    
    console.print("[bold]Introspección de Odoo[/bold]\n")
    
    try:
        client = OdooClient.get_instance()
        client.authenticate()
        
        if model:
            # Información de modelo específico
            console.print(f"[bold cyan]Modelo: {model}[/bold cyan]\n")
            
            model_info = client.get_model_info(model)
            
            console.print(f"[yellow]Nombre:[/yellow] {model_info.get('name', 'N/A')}")
            console.print(f"[yellow]Estado:[/yellow] {model_info.get('state', 'N/A')}")
            console.print()
            
            # Campos
            fields = model_info.get("fields", {})
            
            table = Table(title=f"Campos de {model}", show_header=True)
            table.add_column("Campo", style="cyan")
            table.add_column("Tipo", style="yellow")
            table.add_column("Requerido", style="green")
            table.add_column("Descripción", style="dim")
            
            for field_name, field_info in sorted(fields.items()):
                required = "✓" if field_info.get("required") else ""
                table.add_row(
                    field_name,
                    field_info.get("type", "?"),
                    required,
                    field_info.get("string", "")[:40]
                )
            
            console.print(table)
            
        elif all_models:
            # Listar todos los modelos
            console.print("[bold]Listando modelos disponibles...[/bold]\n")
            
            models = client.get_models()[:limit]
            
            table = Table(title=f"Modelos Odoo (primeros {limit})", show_header=True)
            table.add_column("#", style="dim")
            table.add_column("Modelo", style="cyan")
            table.add_column("Nombre", style="yellow")
            table.add_column("Estado", style="green")
            
            for i, m in enumerate(models, 1):
                table.add_row(
                    str(i),
                    m.get("model", "?"),
                    m.get("name", "?")[:40],
                    m.get("state", "?")
                )
            
            console.print(table)
            console.print(f"\n[dim]Total: {len(models)} modelos mostrados[/dim]")
            
        else:
            # Mostrar modelos comunes
            common_models = [
                "res.partner",
                "res.users",
                "account.move",
                "account.move.line",
                "sale.order",
                "purchase.order",
                "stock.picking",
                "product.product",
                "product.template",
            ]
            
            console.print("[bold]Modelos comunes de Odoo:[/bold]\n")
            
            table = Table(show_header=True)
            table.add_column("Modelo", style="cyan")
            table.add_column("Registros", style="yellow", justify="right")
            
            for model_name in common_models:
                try:
                    count = client.search_count(model_name, [])
                    table.add_row(model_name, str(count))
                except Exception:
                    table.add_row(model_name, "[red]N/A[/red]")
            
            console.print(table)
            console.print("\n[dim]Usa --all para ver todos los modelos[/dim]")
            console.print("[dim]Usa --model <nombre> para ver detalles de un modelo[/dim]")
            
    except Exception as e:
        print_error(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h",
        help="Host para el servidor"
    ),
    port: int = typer.Option(
        8080, "--port", "-p",
        help="Puerto para el servidor"
    ),
    reload: bool = typer.Option(
        False, "--reload", "-r",
        help="Activar auto-reload (desarrollo)"
    ),
    with_scheduler: bool = typer.Option(
        True, "--scheduler/--no-scheduler",
        help="Iniciar scheduler de tareas"
    )
) -> None:
    """Inicia el servidor ARIA con agentes y scheduler."""
    print_banner()
    setup_logging(settings.log_level.value)
    
    console.print(f"\n[bold green]Iniciando servidor ARIA...[/bold green]")
    console.print(f"[cyan]URL:[/cyan] http://{host}:{port}")
    console.print(f"[cyan]Entorno:[/cyan] {settings.env.value}")
    console.print(f"[cyan]Scheduler:[/cyan] {'Activo' if with_scheduler else 'Desactivado'}")
    
    if settings.is_development:
        print_warning("Modo desarrollo activo")
    
    async def _serve():
        from aria.agents import initialize_all_agents, agent_registry
        from aria.scheduler import task_scheduler
        
        # Inicializar agentes
        console.print("\n[bold]Inicializando agentes...[/bold]")
        initialize_all_agents()
        
        agents = agent_registry.list_names()
        console.print(f"[green]Agentes registrados:[/green] {', '.join(agents)}")
        
        # Iniciar agentes
        await agent_registry.start_all()
        
        # Iniciar scheduler si está habilitado
        if with_scheduler:
            console.print("\n[bold]Iniciando scheduler...[/bold]")
            await task_scheduler.start()
            
            schedule = task_scheduler.get_schedule()
            console.print(f"[green]Tareas programadas:[/green] {len(schedule)}")
        
        console.print("\n[bold green]✓ ARIA está corriendo[/bold green]")
        console.print("[dim]Presiona Ctrl+C para detener[/dim]\n")
        
        # TODO: Integrar con FastAPI
        # Por ahora, mantener el loop corriendo
        try:
            while True:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        finally:
            console.print("\n[yellow]Deteniendo ARIA...[/yellow]")
            if with_scheduler:
                await task_scheduler.stop()
            await agent_registry.stop_all()
            console.print("[green]ARIA detenido[/green]")
    
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass


@app.command()
def bot() -> None:
    """Inicia el bot de Telegram."""
    print_banner()
    setup_logging(settings.log_level.value)
    
    if not settings.telegram_enabled:
        print_error("Telegram no configurado")
        console.print("\n[dim]Configura las siguientes variables en .env:[/dim]")
        console.print("  - TELEGRAM_BOT_TOKEN")
        console.print("  - TELEGRAM_ADMIN_CHAT_ID")
        raise typer.Exit(code=1)
    
    console.print("\n[bold green]Iniciando bot de Telegram...[/bold green]")
    console.print(f"[cyan]Chat ID:[/cyan] {settings.telegram_admin_chat_id}")
    console.print("\n[dim]Presiona Ctrl+C para detener[/dim]\n")
    
    from aria.telegram_bot import get_telegram_bot
    
    bot = get_telegram_bot()
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Deteniendo bot...[/yellow]")
        asyncio.run(bot.stop())


# ==========================================
# Comandos de Propuestas
# ==========================================

@proposal_app.command("list")
def proposal_list(
    status: Optional[str] = typer.Option(
        None, "--status", "-s",
        help="Filtrar por estado (pending, approved, rejected)"
    ),
    limit: int = typer.Option(
        20, "--limit", "-l",
        help="Límite de propuestas a mostrar"
    )
) -> None:
    """Lista las propuestas."""
    from aria.approval_engine import approval_engine
    from aria.models.proposal import ProposalStatus
    
    async def _list():
        if status:
            try:
                status_enum = ProposalStatus(status)
                proposals = await approval_engine.get_all(status=status_enum, limit=limit)
            except ValueError:
                print_error(f"Estado inválido: {status}")
                return
        else:
            proposals = await approval_engine.get_pending(limit=limit)
        
        if not proposals:
            print_info("No hay propuestas" + (f" con estado '{status}'" if status else " pendientes"))
            return
        
        table = Table(title=f"Propuestas ({len(proposals)})", show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("Prioridad", style="yellow")
        table.add_column("Agente", style="green")
        table.add_column("Título", style="white")
        table.add_column("Estado", style="magenta")
        
        for p in proposals:
            table.add_row(
                p.short_id,
                f"{p.priority_emoji} {p.priority.value}",
                p.agent_id,
                p.title[:40] + ("..." if len(p.title) > 40 else ""),
                p.status.value
            )
        
        console.print(table)
        await approval_engine.close()
    
    asyncio.run(_list())


@proposal_app.command("show")
def proposal_show(
    proposal_id: str = typer.Argument(..., help="ID de la propuesta (completo o parcial)")
) -> None:
    """Muestra detalles de una propuesta."""
    from aria.approval_engine import approval_engine
    
    async def _show():
        proposal = await approval_engine.get(proposal_id)
        
        if not proposal:
            print_error(f"Propuesta no encontrada: {proposal_id}")
            return
        
        console.print(Panel(
            proposal.to_notification_text(),
            title=f"Propuesta {proposal.short_id}",
            border_style="cyan"
        ))
        
        if proposal.supporting_data:
            import json
            console.print("\n[bold]Datos de soporte:[/bold]")
            console.print(json.dumps(proposal.supporting_data, indent=2, default=str))
        
        await approval_engine.close()
    
    asyncio.run(_show())


@proposal_app.command("approve")
def proposal_approve(
    proposal_id: str = typer.Argument(..., help="ID de la propuesta"),
    execute: bool = typer.Option(
        True, "--execute/--no-execute",
        help="Ejecutar la acción después de aprobar"
    ),
    notes: Optional[str] = typer.Option(
        None, "--notes", "-n",
        help="Notas de aprobación"
    )
) -> None:
    """Aprueba una propuesta."""
    from aria.approval_engine import approval_engine
    from aria.action_executor import action_executor
    
    async def _approve():
        try:
            proposal = await approval_engine.approve(
                proposal_id,
                approved_by="cli",
                notes=notes
            )
            print_success(f"Propuesta aprobada: {proposal.short_id}")
            
            if execute:
                console.print("[dim]Ejecutando acción...[/dim]")
                try:
                    result = await action_executor.execute(proposal)
                    print_success(f"Acción ejecutada: {result}")
                except Exception as e:
                    print_error(f"Error ejecutando: {e}")
                    
        except Exception as e:
            print_error(str(e))
        finally:
            await approval_engine.close()
    
    asyncio.run(_approve())


@proposal_app.command("reject")
def proposal_reject(
    proposal_id: str = typer.Argument(..., help="ID de la propuesta"),
    reason: Optional[str] = typer.Option(
        None, "--reason", "-r",
        help="Razón del rechazo"
    )
) -> None:
    """Rechaza una propuesta."""
    from aria.approval_engine import approval_engine
    
    async def _reject():
        try:
            proposal = await approval_engine.reject(
                proposal_id,
                reason=reason or "",
                rejected_by="cli"
            )
            print_success(f"Propuesta rechazada: {proposal.short_id}")
        except Exception as e:
            print_error(str(e))
        finally:
            await approval_engine.close()
    
    asyncio.run(_reject())


@proposal_app.command("stats")
def proposal_stats() -> None:
    """Muestra estadísticas de propuestas."""
    from aria.approval_engine import approval_engine
    
    async def _stats():
        stats = await approval_engine.get_stats()
        
        table = Table(title="Estadísticas de Propuestas", show_header=True)
        table.add_column("Métrica", style="cyan")
        table.add_column("Valor", style="yellow", justify="right")
        
        for key, value in stats.items():
            table.add_row(key.title(), str(value))
        
        console.print(table)
        await approval_engine.close()
    
    asyncio.run(_stats())


# ==========================================
# Comandos de Agentes
# ==========================================

@agent_app.command("list")
def agent_list() -> None:
    """Lista los agentes disponibles."""
    from aria.agents import initialize_all_agents, agent_registry
    
    console.print("[bold]Agentes ARIA disponibles:[/bold]\n")
    
    # Inicializar agentes
    initialize_all_agents()
    
    agents = agent_registry.list_all()
    
    table = Table(show_header=True)
    table.add_column("Nombre", style="cyan")
    table.add_column("Descripción", style="yellow")
    table.add_column("Tareas", style="green", justify="right")
    table.add_column("Estado", style="magenta")
    
    for agent in agents:
        status = "[green]Activo[/green]" if agent.is_running else "[dim]Inactivo[/dim]"
        table.add_row(
            agent.name,
            agent.description[:50] + ("..." if len(agent.description) > 50 else ""),
            str(len(agent.tasks)),
            status
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(agents)} agentes[/dim]")


@agent_app.command("info")
def agent_info(
    agent_name: str = typer.Argument(..., help="Nombre del agente")
) -> None:
    """Muestra información detallada de un agente."""
    from aria.agents import initialize_all_agents, get_agent
    
    initialize_all_agents()
    
    agent = get_agent(agent_name)
    
    if not agent:
        print_error(f"Agente no encontrado: {agent_name}")
        raise typer.Exit(code=1)
    
    info = agent.get_info()
    
    console.print(Panel(
        f"[bold]{info['name']}[/bold]\n{info['description']}",
        title="Agente",
        border_style="cyan"
    ))
    
    # Tareas
    table = Table(title="Tareas del Agente", show_header=True)
    table.add_column("Nombre", style="cyan")
    table.add_column("Schedule", style="yellow")
    table.add_column("Descripción", style="white")
    table.add_column("Última ejecución", style="dim")
    table.add_column("Estado", style="green")
    
    for task in info["tasks"]:
        last_run = task["last_run"][:16] if task["last_run"] else "Nunca"
        status = "✓" if task.get("last_success", True) else "✗"
        if not task["enabled"]:
            status = "[dim]Deshabilitada[/dim]"
        
        table.add_row(
            task["name"],
            task["schedule"],
            task["description"][:40],
            last_run,
            status
        )
    
    console.print(table)


@agent_app.command("run")
def agent_run(
    agent_name: str = typer.Argument(..., help="Nombre del agente"),
    task: Optional[str] = typer.Option(
        None, "--task", "-t",
        help="Ejecutar solo una tarea específica"
    ),
    once: bool = typer.Option(
        True, "--once", "-1",
        help="Ejecutar solo una vez"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Simular sin ejecutar acciones reales"
    )
) -> None:
    """Ejecuta un agente o una tarea específica."""
    setup_logging(settings.log_level.value)
    
    from aria.agents import initialize_all_agents, get_agent
    
    initialize_all_agents()
    
    agent = get_agent(agent_name)
    
    if not agent:
        print_error(f"Agente no encontrado: {agent_name}")
        console.print("\n[dim]Agentes disponibles:[/dim]")
        from aria.agents import agent_registry
        for name in agent_registry.list_names():
            console.print(f"  - {name}")
        raise typer.Exit(code=1)
    
    if dry_run:
        print_warning("Modo dry-run: No se ejecutarán acciones reales")
    
    async def _run():
        await agent.start()
        
        if task:
            # Ejecutar tarea específica
            task_def = agent.get_task(task)
            if not task_def:
                print_error(f"Tarea no encontrada: {task}")
                console.print("\n[dim]Tareas disponibles:[/dim]")
                for t in agent.tasks:
                    console.print(f"  - {t.name}")
                return
            
            console.print(f"\n[bold]Ejecutando {agent_name}.{task}...[/bold]\n")
            result = await agent.run_task(task_def)
            
        else:
            # Ejecutar todas las tareas
            console.print(f"\n[bold]Ejecutando todas las tareas de {agent_name}...[/bold]\n")
            results = await agent.run_all_tasks()
            result = results[-1] if results else None
        
        # Mostrar resultado
        if result:
            console.print(f"\n[bold]Resultado:[/bold]")
            console.print(f"  Éxito: {'[green]✓[/green]' if result.success else '[red]✗[/red]'}")
            console.print(f"  Duración: {result.duration_seconds:.2f}s")
            console.print(f"  Propuestas creadas: {result.proposals_created}")
            console.print(f"  Registros procesados: {result.records_processed}")
            
            if result.error:
                console.print(f"  [red]Error: {result.error}[/red]")
            
            if result.data:
                import json
                console.print(f"\n[dim]Datos:[/dim]")
                console.print(json.dumps(result.data, indent=2, default=str))
        
        await agent.stop()
    
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrumpido[/yellow]")


@agent_app.command("status")
def agent_status() -> None:
    """Muestra el estado de todos los agentes."""
    from aria.agents import initialize_all_agents, agent_registry
    
    initialize_all_agents()
    
    async def _status():
        console.print("[bold]Estado de Agentes ARIA[/bold]\n")
        
        for agent in agent_registry.list_all():
            status = "[green]●[/green]" if agent.is_running else "[dim]○[/dim]"
            console.print(f"{status} [bold]{agent.name}[/bold]")
            
            try:
                summary = await agent.get_status_summary()
                agent_status = summary.get("status", "unknown")
                
                status_colors = {
                    "ok": "green",
                    "warning": "yellow",
                    "critical": "red",
                    "error": "red",
                }
                color = status_colors.get(agent_status, "white")
                
                console.print(f"    Estado: [{color}]{agent_status}[/{color}]")
                
                # Mostrar métricas principales
                for key, value in summary.items():
                    if key not in ["status", "last_updated"]:
                        if isinstance(value, (dict, list)):
                            continue
                        console.print(f"    {key}: {value}")
                        
            except Exception as e:
                console.print(f"    [red]Error obteniendo estado: {e}[/red]")
            
            console.print()
    
    asyncio.run(_status())


# ==========================================
# Comandos del Scheduler
# ==========================================

@scheduler_app.command("list")
def scheduler_list() -> None:
    """Lista todas las tareas programadas."""
    from aria.agents import initialize_all_agents
    from aria.scheduler import task_scheduler
    
    initialize_all_agents()
    
    schedule = task_scheduler.get_schedule()
    
    if not schedule:
        print_info("No hay tareas programadas")
        return
    
    table = Table(title="Tareas Programadas", show_header=True)
    table.add_column("Agente", style="cyan")
    table.add_column("Tarea", style="yellow")
    table.add_column("Schedule", style="green")
    table.add_column("Descripción", style="white")
    table.add_column("Última", style="dim")
    table.add_column("Próxima", style="magenta")
    
    for task in schedule:
        last_run = task["last_run"][:16] if task["last_run"] else "-"
        next_run = task["next_run"][:16] if task["next_run"] else "-"
        
        table.add_row(
            task["agent"],
            task["task"],
            task["schedule"],
            task["description"][:30],
            last_run,
            next_run
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(schedule)} tareas[/dim]")


@scheduler_app.command("start")
def scheduler_start(
    with_inspection: bool = typer.Option(
        True, "--inspect/--no-inspect",
        help="Incluir inspección automática diaria"
    ),
    foreground: bool = typer.Option(
        False, "--foreground", "-f",
        help="Ejecutar en primer plano (no terminar)"
    ),
) -> None:
    """
    Inicia el scheduler de ARIA con todas las tareas.
    
    Por defecto incluye:
    - Tareas de todos los agentes según su cron
    - Inspección diaria a las 7:00 AM
    - Inspección de alertas cada 4 horas
    """
    setup_logging(settings.log_level.value)
    
    from aria.agents import initialize_all_agents
    from aria.scheduler import task_scheduler
    
    initialize_all_agents()
    
    async def _start():
        from aria.agents import agent_registry
        
        # Iniciar todos los agentes
        for agent in agent_registry.list_all():
            await agent.start()
        
        # Iniciar scheduler
        await task_scheduler.start(include_inspection=with_inspection)
        
        console.print("\n[green bold]✓ Scheduler iniciado[/green bold]")
        console.print(f"  Inspección automática: {'Sí' if with_inspection else 'No'}")
        
        if with_inspection:
            console.print("  • Inspección completa: 07:00 diario")
            console.print("  • Alertas: cada 4 horas")
        
        if foreground:
            console.print("\n[dim]Presiona Ctrl+C para detener...[/dim]")
            try:
                # Mantener corriendo
                while True:
                    await asyncio.sleep(3600)
            except KeyboardInterrupt:
                console.print("\n[yellow]Deteniendo scheduler...[/yellow]")
                await task_scheduler.stop()
    
    asyncio.run(_start())


@scheduler_app.command("run")
def scheduler_run(
    agent_name: str = typer.Argument(..., help="Nombre del agente"),
    task_name: str = typer.Argument(..., help="Nombre de la tarea")
) -> None:
    """Ejecuta una tarea inmediatamente (fuera del schedule)."""
    setup_logging(settings.log_level.value)
    
    from aria.agents import initialize_all_agents
    from aria.scheduler import task_scheduler
    
    initialize_all_agents()
    
    async def _run():
        from aria.agents import agent_registry
        
        agent = agent_registry.get(agent_name)
        if agent:
            await agent.start()
        
        try:
            result = await task_scheduler.run_task_now(agent_name, task_name)
            
            console.print(f"\n[bold]Resultado de {agent_name}.{task_name}:[/bold]")
            console.print(f"  Éxito: {'[green]✓[/green]' if result.success else '[red]✗[/red]'}")
            console.print(f"  Duración: {result.duration_seconds:.2f}s")
            console.print(f"  Propuestas: {result.proposals_created}")
            
            if result.error:
                console.print(f"  [red]Error: {result.error}[/red]")
                
        except ValueError as e:
            print_error(str(e))
    
    asyncio.run(_run())


# ==========================================
# Diagnóstico
# ==========================================

@app.command()
def diagnose(
    agent: Optional[str] = typer.Option(
        None, "--agent", "-a",
        help="Diagnosticar solo un agente específico"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Mostrar información detallada"
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Salida en formato JSON"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Guardar reporte en archivo"
    ),
) -> None:
    """Ejecuta diagnóstico completo del sistema ARIA."""
    import json
    import sys
    import os
    
    # Importar el diagnóstico
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from scripts.diagnostico_aria import ARIADiagnostic
    
    async def _diagnose():
        diagnostic = ARIADiagnostic(verbose=verbose)
        
        if agent:
            console.print(f"\n[bold]Diagnosticando agente: {agent}[/bold]\n")
            result = await diagnostic.run_agent_diagnostic(agent)
        else:
            result = await diagnostic.run_full_diagnostic()
        
        if json_output and result:
            print(json.dumps(result, indent=2, default=str))
        
        if output_file and result:
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2, default=str)
            console.print(f"\n[green]📄 Reporte guardado en: {output_file}[/green]")
    
    asyncio.run(_diagnose())


# ==========================================
# Inspección Contextual
# ==========================================

inspect_app = typer.Typer(help="Sistema de inspección contextual")
app.add_typer(inspect_app, name="inspect")


@inspect_app.command("run")
def inspect_run(
    agent_name: str = typer.Argument(..., help="Nombre del agente a inspeccionar"),
    level: int = typer.Option(
        4, "--level", "-l",
        help="Nivel máximo de inspección (1-4)"
    ),
    propose: bool = typer.Option(
        False, "--propose", "-p",
        help="Crear propuestas automáticas para hallazgos HIGH/CRITICAL"
    ),
    min_severity: str = typer.Option(
        "high", "--min-severity", "-s",
        help="Severidad mínima para crear propuestas (high, critical)"
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Salida en formato JSON"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Guardar reporte en archivo"
    ),
) -> None:
    """
    Ejecuta inspección contextual de un agente.
    
    Detecta problemas, determina impactos y opcionalmente crea propuestas.
    
    Ejemplos:
    
        aria inspect run inventario
        
        aria inspect run cobranza --level 2
        
        aria inspect run ventas --propose
        
        aria inspect run finanzas --propose --min-severity critical
    """
    import json
    
    setup_logging(settings.log_level.value)
    
    from aria.inspection import get_inspector, InspectionReport
    from aria.inspection.models import ImpactLevel
    
    # Mapear severidad de string a enum
    severity_map = {
        "critical": ImpactLevel.CRITICAL,
        "high": ImpactLevel.HIGH,
        "medium": ImpactLevel.MEDIUM,
        "low": ImpactLevel.LOW,
    }
    min_sev = severity_map.get(min_severity.lower(), ImpactLevel.HIGH)
    
    console.print(f"\n[bold]Inspeccionando: {agent_name}[/bold]")
    console.print(f"[dim]Nivel máximo: {level}[/dim]")
    if propose:
        console.print(f"[cyan]Generando propuestas para severidad >= {min_severity}[/cyan]")
    console.print()
    
    try:
        inspector = get_inspector(agent_name)
    except ValueError as e:
        print_error(str(e))
        console.print("\n[dim]Agentes disponibles:[/dim]")
        valid_agents = [
            "inventario", "cobranza", "ventas", "compras",
            "finanzas", "produccion", "rrhh", "costos",
            "crm", "contabilidad", "ceo", "sistema"
        ]
        for name in valid_agents:
            console.print(f"  - {name}")
        raise typer.Exit(code=1)
    
    # Ejecutar inspección con o sin propuestas
    report = inspector.inspect(
        max_level=level,
        create_proposals=propose,
        min_severity_for_proposal=min_sev,
    )
    
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        # Mostrar resumen visual
        _display_inspection_report(report)
        
        # Mostrar info de propuestas creadas
        if propose and report.proposals_created > 0:
            console.print(f"\n[green bold]✓ {report.proposals_created} propuestas creadas[/green bold]")
            console.print("[dim]Ver propuestas con: aria proposal list[/dim]")
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2, default=str)
        console.print(f"\n[green]📄 Reporte guardado en: {output_file}[/green]")


@inspect_app.command("all")
def inspect_all(
    level: int = typer.Option(
        3, "--level", "-l",
        help="Nivel máximo de inspección (1-4)"
    ),
    propose: bool = typer.Option(
        False, "--propose", "-p",
        help="Crear propuestas automáticas para hallazgos HIGH/CRITICAL"
    ),
    min_severity: str = typer.Option(
        "high", "--min-severity", "-s",
        help="Severidad mínima para crear propuestas (high, critical)"
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Salida en formato JSON"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Guardar reporte consolidado en archivo"
    ),
) -> None:
    """
    Ejecuta inspección de todos los agentes.
    
    Ejemplo completo con propuestas:
    
        aria inspect all --propose --level 4 --output report.json
    """
    import json
    
    setup_logging(settings.log_level.value)
    
    from aria.inspection import run_all_inspections
    from aria.inspection.models import ImpactLevel
    
    # Mapear severidad
    severity_map = {
        "critical": ImpactLevel.CRITICAL,
        "high": ImpactLevel.HIGH,
        "medium": ImpactLevel.MEDIUM,
    }
    min_sev = severity_map.get(min_severity.lower(), ImpactLevel.HIGH)
    
    console.print(f"\n[bold]Inspección completa del sistema[/bold]")
    console.print(f"[dim]Nivel máximo: {level}[/dim]")
    if propose:
        console.print(f"[cyan]Generando propuestas para severidad >= {min_severity}[/cyan]")
    console.print()
    
    reports = run_all_inspections(
        max_level=level,
        create_proposals=propose,
        min_severity_for_proposal=min_sev,
    )
    
    if json_output:
        result = {name: r.to_dict() for name, r in reports.items()}
        print(json.dumps(result, indent=2, default=str))
    else:
        # Mostrar resumen de cada agente
        table = Table(title="Resumen de Inspección", show_header=True)
        table.add_column("Agente", style="cyan")
        table.add_column("Estado", style="yellow")
        table.add_column("Health", style="green", justify="right")
        table.add_column("Críticos", style="red", justify="right")
        table.add_column("Altos", style="yellow", justify="right")
        table.add_column("Total", style="white", justify="right")
        if propose:
            table.add_column("Propuestas", style="magenta", justify="right")
        
        total_proposals = 0
        for name, report in reports.items():
            status_colors = {
                "healthy": "[green]●[/green]",
                "warning": "[yellow]●[/yellow]",
                "critical": "[red]●[/red]",
                "error": "[red]✗[/red]",
            }
            status_icon = status_colors.get(report.context.status, "[dim]?[/dim]")
            
            row = [
                name,
                f"{status_icon} {report.context.status}",
                f"{report.context.health_score:.0f}%",
                str(report.critical_count),
                str(report.high_count),
                str(len(report.findings)),
            ]
            if propose:
                row.append(str(report.proposals_created))
                total_proposals += report.proposals_created
            
            table.add_row(*row)
        
        console.print(table)
        
        # Mostrar total de propuestas
        if propose and total_proposals > 0:
            console.print(f"\n[green bold]✓ {total_proposals} propuestas creadas en total[/green bold]")
            console.print("[dim]Ver propuestas con: aria proposal list[/dim]")
        
        # Hallazgos críticos
        all_critical = []
        for name, report in reports.items():
            for f in report.findings_by_severity.get("critical", []):
                all_critical.append((name, f))
        
        if all_critical:
            console.print(f"\n[bold red]🔴 {len(all_critical)} Hallazgos Críticos:[/bold red]\n")
            for agent, finding in all_critical[:10]:
                console.print(f"  [cyan]{agent}[/cyan]: {finding.title}")
                if finding.impacts:
                    for impact in finding.impacts[:2]:
                        console.print(f"    → Impacta a [yellow]{impact.agent_name}[/yellow]: {impact.description}")
    
    if output_file:
        result = {name: r.to_dict() for name, r in reports.items()}
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"\n[green]📄 Reporte guardado en: {output_file}[/green]")


@inspect_app.command("impacts")
def inspect_impacts() -> None:
    """Muestra el mapa de impactos entre agentes."""
    from aria.inspection import get_all_inspectors
    
    console.print("\n[bold]Mapa de Impactos entre Agentes ARIA[/bold]\n")
    
    inspectors = get_all_inspectors()
    
    # Mostrar dependencias upstream
    console.print("[bold cyan]Dependencias Upstream (me alimentan):[/bold cyan]")
    for name, inspector in inspectors.items():
        if inspector.UPSTREAM_DEPENDENCIES:
            console.print(f"\n  [yellow]{name}[/yellow] depende de:")
            for dep in inspector.UPSTREAM_DEPENDENCIES:
                criticality_colors = {
                    "critical": "red",
                    "high": "yellow",
                    "medium": "white",
                    "low": "dim",
                }
                color = criticality_colors.get(dep.criticality.value, "white")
                console.print(f"    ← [{color}]{dep.agent_name}[/{color}] ({dep.criticality.value}): {dep.data_flow}")
    
    # Mostrar dependencias downstream
    console.print("\n\n[bold cyan]Dependencias Downstream (dependen de mí):[/bold cyan]")
    for name, inspector in inspectors.items():
        if inspector.DOWNSTREAM_DEPENDENCIES:
            console.print(f"\n  [yellow]{name}[/yellow] alimenta a:")
            for dep in inspector.DOWNSTREAM_DEPENDENCIES:
                criticality_colors = {
                    "critical": "red",
                    "high": "yellow",
                    "medium": "white",
                    "low": "dim",
                }
                color = criticality_colors.get(dep.criticality.value, "white")
                console.print(f"    → [{color}]{dep.agent_name}[/{color}] ({dep.criticality.value}): {dep.data_flow}")


def _display_inspection_report(report) -> None:
    """Muestra un reporte de inspección de forma visual."""
    from aria.inspection import ImpactLevel
    
    # Header
    status_colors = {
        "healthy": "green",
        "warning": "yellow",
        "critical": "red",
    }
    color = status_colors.get(report.context.status, "white")
    
    console.print(Panel(
        f"[bold]{report.context.area_name}[/bold]\n"
        f"Estado: [{color}]{report.context.status.upper()}[/{color}]\n"
        f"Health Score: [{color}]{report.context.health_score:.0f}%[/{color}]\n"
        f"Registros: {report.context.total_records:,}\n"
        f"Hallazgos: {len(report.findings)} ({report.critical_count} críticos, {report.high_count} altos)",
        title=f"Inspección: {report.agent_name}",
        border_style=color
    ))
    
    # Hallazgos por nivel
    for level in [1, 2, 3, 4]:
        findings = report.findings_by_level.get(level, [])
        if not findings:
            continue
        
        level_names = {1: "Vista General", 2: "Por Categorías", 3: "Detalles", 4: "Anomalías"}
        console.print(f"\n[bold]Nivel {level}: {level_names.get(level)}[/bold]")
        
        for f in findings:
            severity_icons = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
                "info": "ℹ️",
            }
            icon = severity_icons.get(f.severity.value, "•")
            
            console.print(f"\n  {icon} [bold]{f.title}[/bold]")
            console.print(f"     [dim]{f.description}[/dim]")
            
            if f.affected_records > 0:
                console.print(f"     Afectados: {f.affected_records:,} registros")
            if f.affected_amount > 0:
                console.print(f"     Monto: ${f.affected_amount:,.2f}")
            
            if f.impacts:
                console.print("     [yellow]Impactos:[/yellow]")
                for impact in f.impacts[:3]:
                    console.print(f"       → {impact.agent_name}: {impact.description}")
            
            if f.solution:
                console.print(f"     [green]Solución:[/green] {f.solution}")


# ==========================================
# API REST
# ==========================================

@app.command()
def api(
    host: str = typer.Option(
        "0.0.0.0", "--host", "-h",
        help="Host para el servidor"
    ),
    port: int = typer.Option(
        8000, "--port", "-p",
        help="Puerto para el servidor"
    ),
    reload: bool = typer.Option(
        False, "--reload", "-r",
        help="Recargar automáticamente en cambios (desarrollo)"
    ),
) -> None:
    """Inicia la API REST de ARIA."""
    import uvicorn
    
    print_banner()
    console.print(f"\n[bold green]Iniciando ARIA API en http://{host}:{port}[/bold green]")
    console.print(f"[dim]Documentación: http://{host}:{port}/docs[/dim]\n")
    
    uvicorn.run(
        "aria.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command("serve-all")
def serve_all(
    host: str = typer.Option(
        "0.0.0.0", "--host", "-h",
        help="Host para el servidor"
    ),
    port: int = typer.Option(
        8000, "--port", "-p",
        help="Puerto para la API"
    ),
    scheduler: bool = typer.Option(
        True, "--scheduler/--no-scheduler",
        help="Iniciar scheduler de tareas"
    ),
    telegram: bool = typer.Option(
        False, "--telegram/--no-telegram",
        help="Iniciar bot de Telegram"
    ),
) -> None:
    """Inicia ARIA completo: API + Scheduler + Telegram."""
    import uvicorn
    
    print_banner()
    
    components = ["API REST"]
    if scheduler:
        components.append("Scheduler")
    if telegram:
        components.append("Telegram Bot")
    
    console.print(f"\n[bold green]Iniciando ARIA: {', '.join(components)}[/bold green]")
    console.print(f"[dim]API: http://{host}:{port}[/dim]")
    console.print(f"[dim]Docs: http://{host}:{port}/docs[/dim]\n")
    
    # TODO: Integrar Telegram y scheduler en el mismo proceso
    uvicorn.run(
        "aria.api.app:app",
        host=host,
        port=port,
        log_level="info",
    )


# ==========================================
# Punto de entrada
# ==========================================

def main() -> None:
    """Punto de entrada principal."""
    app()


if __name__ == "__main__":
    main()
