#!/usr/bin/env python3
"""
Script para verificar modelos de presupuestos disponibles en Odoo.

Verifica qué modelos relacionados con presupuestos están disponibles
y muestra su estructura de campos.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aria.odoo_client import OdooClient
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# Modelos de presupuestos comunes en Odoo
BUDGET_MODELS = [
    "account.budget",
    "account.budget.line",
    "account.budget.post",
    "crossovered.budget",  # Versión antigua
    "crossovered.budget.lines",  # Versión antigua
    "account.analytic.account",  # Cuentas analíticas (usadas en presupuestos)
    "account.analytic.line",  # Líneas analíticas
]


def check_model_exists(odoo_client, model_name: str) -> tuple[bool, dict]:
    """
    Verifica si un modelo existe y obtiene información básica.
    
    Returns:
        (exists: bool, info: dict)
    """
    try:
        # Intentar obtener campos del modelo
        fields_info = odoo_client.fields_get(model_name, attributes=['string', 'type', 'relation', 'required'])
        
        # Intentar obtener algunos registros para ver estructura
        try:
            count = odoo_client.search_count(model_name, [])
        except:
            count = 0
        
        return True, {
            "exists": True,
            "fields_count": len(fields_info),
            "records_count": count,
            "fields": fields_info,
        }
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg.lower() or "model not found" in error_msg.lower():
            return False, {"exists": False, "error": "Modelo no existe"}
        else:
            return False, {"exists": False, "error": error_msg[:200]}


def get_model_fields_summary(fields_info: dict) -> list[tuple]:
    """Extrae campos importantes del modelo."""
    important_fields = []
    
    for field_name, field_info in fields_info.items():
        field_type = field_info.get('type', '')
        field_string = field_info.get('string', field_name)
        
        # Filtrar campos importantes
        if field_name in ['id', 'name', 'date_from', 'date_to', 'company_id', 
                         'amount', 'planned_amount', 'account_id', 'budget_id',
                         'state', 'active']:
            important_fields.append((field_name, field_string, field_type))
        elif field_type in ['many2one', 'one2many', 'many2many']:
            important_fields.append((field_name, field_string, field_type))
    
    return important_fields


def main():
    console.print("\n[bold cyan]🔍 Verificando modelos de presupuestos en Odoo...[/bold cyan]\n")
    
    try:
        odoo = OdooClient.get_instance()
        uid = odoo.authenticate()
        console.print(f"[green]✅ Conectado a Odoo (UID: {uid})[/green]\n")
    except Exception as e:
        console.print(f"[red]❌ Error conectando a Odoo: {e}[/red]")
        sys.exit(1)
    
    results = {}
    
    # Verificar cada modelo
    for model_name in BUDGET_MODELS:
        exists, info = check_model_exists(odoo, model_name)
        results[model_name] = info
    
    # Mostrar resultados
    console.print("=" * 80)
    console.print("[bold green]📊 RESULTADOS DE VERIFICACIÓN[/bold green]")
    console.print("=" * 80)
    console.print()
    
    # Tabla resumen
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Modelo", style="cyan", width=30)
    table.add_column("Estado", justify="center", width=15)
    table.add_column("Campos", justify="right", width=10)
    table.add_column("Registros", justify="right", width=12)
    table.add_column("Notas", style="dim", width=20)
    
    for model_name, info in results.items():
        if info.get("exists"):
            status = "[green]✅ Disponible[/green]"
            fields_count = str(info.get("fields_count", 0))
            records_count = str(info.get("records_count", 0))
            notes = "Módulo instalado"
        else:
            status = "[red]❌ No disponible[/red]"
            fields_count = "-"
            records_count = "-"
            notes = info.get("error", "No encontrado")
        
        table.add_row(model_name, status, fields_count, records_count, notes)
    
    console.print(table)
    console.print()
    
    # Detalles de modelos disponibles
    available_models = {name: info for name, info in results.items() if info.get("exists")}
    
    if available_models:
        console.print("=" * 80)
        console.print("[bold green]📋 DETALLES DE MODELOS DISPONIBLES[/bold green]")
        console.print("=" * 80)
        console.print()
        
        for model_name, info in available_models.items():
            console.print(f"\n[bold cyan]📦 {model_name}[/bold cyan]")
            console.print(f"   Campos totales: {info.get('fields_count', 0)}")
            console.print(f"   Registros: {info.get('records_count', 0)}")
            
            # Mostrar campos importantes
            fields_info = info.get("fields", {})
            important_fields = get_model_fields_summary(fields_info)
            
            if important_fields:
                console.print(f"   [yellow]Campos importantes:[/yellow]")
                for field_name, field_string, field_type in important_fields[:10]:  # Limitar a 10
                    console.print(f"      • {field_name} ({field_type}): {field_string}")
                if len(important_fields) > 10:
                    console.print(f"      ... y {len(important_fields) - 10} más")
    
    # Recomendaciones
    console.print("\n" + "=" * 80)
    console.print("[bold yellow]💡 RECOMENDACIONES[/bold yellow]")
    console.print("=" * 80)
    console.print()
    
    if "account.budget" in available_models:
        console.print("[green]✅[/green] El módulo de presupuestos está instalado.")
        console.print("   Puedes usar 'account.budget' y 'account.budget.line' para presupuestos.")
    elif "crossovered.budget" in available_models:
        console.print("[yellow]⚠️[/yellow] Versión antigua de presupuestos detectada.")
        console.print("   Considera actualizar a 'account.budget'.")
    else:
        console.print("[red]❌[/red] No se encontraron módulos de presupuestos instalados.")
        console.print("   Opciones:")
        console.print("   1. Instalar módulo 'account_budget' en Odoo")
        console.print("   2. Usar configuración manual desde el dashboard")
        console.print("   3. Usar cálculo automático desde histórico")
    
    console.print()


if __name__ == "__main__":
    main()
