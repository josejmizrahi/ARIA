#!/usr/bin/env python3
"""
ARIA - Script de Prueba de Agentes
===================================

Script para probar los agentes de ARIA.

Uso:
    python scripts/test_agents.py                    # Mostrar estado
    python scripts/test_agents.py cobranza           # Probar agente
    python scripts/test_agents.py cobranza aging     # Probar tarea específica

Ejemplos:
    # Ver agentes disponibles
    python scripts/test_agents.py
    
    # Ejecutar todas las tareas del agente de cobranza
    python scripts/test_agents.py cobranza
    
    # Ejecutar solo el análisis de antigüedad
    python scripts/test_agents.py cobranza aging_analysis
"""

import asyncio
import sys
from pathlib import Path

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from aria.agents import (
    agent_registry,
    initialize_all_agents,
    get_agent,
)
from aria.config import settings
from aria.utils.logger import setup_logging

console = Console()


async def test_single_task(agent_name: str, task_name: str) -> None:
    """Prueba una tarea específica."""
    agent = get_agent(agent_name)
    
    if not agent:
        console.print(f"[red]Agente no encontrado: {agent_name}[/red]")
        console.print("\n[dim]Agentes disponibles:[/dim]")
        for name in agent_registry.list_names():
            console.print(f"  - {name}")
        return
    
    task = agent.get_task(task_name)
    
    if not task:
        console.print(f"[red]Tarea no encontrada: {task_name}[/red]")
        console.print(f"\n[dim]Tareas disponibles en {agent_name}:[/dim]")
        for t in agent.tasks:
            console.print(f"  - {t.name}: {t.description}")
        return
    
    console.print(f"\n[bold]Ejecutando {agent_name}.{task_name}...[/bold]")
    console.print(f"[dim]{task.description}[/dim]\n")
    
    await agent.start()
    result = await agent.run_task(task)
    
    # Mostrar resultado
    success_icon = "✅" if result.success else "❌"
    
    console.print(Panel(
        f"""
{success_icon} **{result.task_name}**

- Duración: {result.duration_seconds:.2f}s
- Propuestas creadas: {result.proposals_created}
- Registros procesados: {result.records_processed}
        """.strip(),
        title=f"Resultado de {agent_name}.{task_name}",
        border_style="green" if result.success else "red"
    ))
    
    if result.error:
        console.print(f"\n[red]Error:[/red] {result.error}")
        if result.error_traceback:
            console.print(f"\n[dim]{result.error_traceback}[/dim]")
    
    if result.data:
        console.print("\n[bold]Datos del resultado:[/bold]")
        import json
        console.print(json.dumps(result.data, indent=2, default=str))


async def test_agent(agent_name: str) -> None:
    """Prueba todas las tareas de un agente."""
    agent = get_agent(agent_name)
    
    if not agent:
        console.print(f"[red]Agente no encontrado: {agent_name}[/red]")
        return
    
    console.print(f"\n[bold cyan]═══ Probando agente: {agent.name} ═══[/bold cyan]")
    console.print(f"[dim]{agent.description}[/dim]")
    console.print(f"[dim]Tareas: {len(agent.tasks)}[/dim]\n")
    
    # Mostrar tareas
    table = Table(title="Tareas del agente", show_header=True)
    table.add_column("Nombre", style="cyan")
    table.add_column("Schedule", style="green")
    table.add_column("Descripción", style="white")
    
    for task in agent.tasks:
        table.add_row(task.name, task.schedule, task.description)
    
    console.print(table)
    
    # Ejecutar todas las tareas
    console.print("\n[bold]Ejecutando tareas...[/bold]\n")
    
    await agent.start()
    results = await agent.run_all_tasks()
    
    # Mostrar resultados
    results_table = Table(title="Resultados", show_header=True)
    results_table.add_column("Tarea", style="cyan")
    results_table.add_column("Estado")
    results_table.add_column("Duración")
    results_table.add_column("Propuestas")
    results_table.add_column("Registros")
    
    for result in results:
        status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
        results_table.add_row(
            result.task_name,
            status,
            f"{result.duration_seconds:.2f}s",
            str(result.proposals_created),
            str(result.records_processed)
        )
    
    console.print(results_table)
    
    # Resumen
    success_count = sum(1 for r in results if r.success)
    console.print(f"\n[bold]Resumen:[/bold] {success_count}/{len(results)} tareas exitosas")


async def test_all_agents() -> None:
    """Prueba todos los agentes."""
    console.print("\n[bold magenta]═══════════════════════════════════════[/bold magenta]")
    console.print("[bold magenta]   🤖 Probando todos los agentes ARIA[/bold magenta]")
    console.print("[bold magenta]═══════════════════════════════════════[/bold magenta]\n")
    
    agents = agent_registry.list_all()
    
    for agent in agents:
        await test_agent(agent.name)
        console.print("\n" + "─" * 50 + "\n")
    
    console.print("[bold green]✓ Pruebas completadas[/bold green]")


async def show_status() -> None:
    """Muestra estado de todos los agentes."""
    console.print("\n[bold]📊 Estado de Agentes ARIA[/bold]\n")
    
    table = Table(show_header=True)
    table.add_column("Nombre", style="cyan")
    table.add_column("Estado")
    table.add_column("Tareas")
    table.add_column("Descripción", style="dim")
    
    for agent in agent_registry.list_all():
        status = "[green]● Activo[/green]" if agent.is_running else "[dim]○ Inactivo[/dim]"
        table.add_row(
            agent.name,
            status,
            str(len(agent.tasks)),
            agent.description[:45] + ("..." if len(agent.description) > 45 else "")
        )
    
    console.print(table)
    
    # Mostrar tareas de cada agente
    console.print("\n[bold]Tareas por agente:[/bold]\n")
    
    for agent in agent_registry.list_all():
        console.print(f"[cyan]{agent.name}:[/cyan]")
        for task in agent.tasks:
            enabled = "[green]✓[/green]" if task.enabled else "[dim]✗[/dim]"
            console.print(f"  {enabled} {task.name}: {task.schedule} - {task.description}")
        console.print()


async def main() -> None:
    """Función principal."""
    # Configurar logging
    setup_logging(settings.log_level.value)
    
    # Inicializar agentes
    console.print("[bold]Inicializando agentes ARIA...[/bold]")
    initialize_all_agents()
    
    agents = agent_registry.list_names()
    console.print(f"[green]Agentes registrados:[/green] {', '.join(agents)}")
    
    # Parsear argumentos
    args = sys.argv[1:]
    
    if len(args) == 0:
        # Sin argumentos: mostrar estado
        await show_status()
        
        console.print("\n[bold]¿Qué deseas hacer?[/bold]")
        console.print("1. Probar todos los agentes")
        console.print("2. Probar un agente específico")
        console.print("3. Probar una tarea específica")
        console.print("4. Salir")
        
        try:
            choice = input("\nOpción [1-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Saliendo...[/dim]")
            return
        
        if choice == "1":
            await test_all_agents()
        elif choice == "2":
            agent_name = input("Nombre del agente: ").strip()
            await test_agent(agent_name)
        elif choice == "3":
            agent_name = input("Nombre del agente: ").strip()
            task_name = input("Nombre de la tarea: ").strip()
            await test_single_task(agent_name, task_name)
        
    elif len(args) == 1:
        # Un argumento: nombre de agente
        await test_agent(args[0])
        
    elif len(args) == 2:
        # Dos argumentos: agente y tarea
        await test_single_task(args[0], args[1])
    
    else:
        console.print("[red]Uso: python test_agents.py [agent_name] [task_name][/red]")
        console.print("\n[dim]Ejemplos:[/dim]")
        console.print("  python test_agents.py              # Mostrar estado")
        console.print("  python test_agents.py cobranza     # Probar agente")
        console.print("  python test_agents.py cobranza aging_analysis  # Probar tarea")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrumpido[/yellow]")
