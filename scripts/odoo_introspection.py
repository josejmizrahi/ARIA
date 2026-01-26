#!/usr/bin/env python3
"""
ARIA - Script de Introspección Odoo.

Verifica todos los modelos y campos usados por los agentes ARIA
contra la instancia de Odoo configurada.

Uso:
    python scripts/odoo_introspection.py
    python scripts/odoo_introspection.py --json
    python scripts/odoo_introspection.py --output report.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aria.odoo_client import OdooClient
from rich.console import Console
from rich.table import Table

console = Console()

# ============================================================
# MAPEO DE MODELOS Y CAMPOS USADOS POR ARIA
# Actualizado para Odoo 19
# ============================================================
ARIA_MODELS_FIELDS = {
    # Base
    "res.users": {
        "fields": ["id", "name", "login", "partner_id"],
        "agents": ["system_agent"],
        "required": True,
    },
    "res.partner": {
        "fields": [
            "id", "name", "email", "phone", "credit_limit", "total_due",
            "total_invoiced", "customer_rank", "supplier_rank", "user_id", "active"
        ],
        "agents": ["receivables_agent", "sales_agent", "system_agent"],
        "required": True,
    },
    "res.company": {
        "fields": ["id", "name", "currency_id"],
        "agents": ["base"],
        "required": True,
    },
    
    # Contabilidad
    "account.move": {
        "fields": [
            "id", "name", "ref", "partner_id", "amount_total", "amount_residual",
            "amount_total_signed", "currency_id", "date", "invoice_date",
            "invoice_date_due", "state", "move_type", "journal_id", "company_id"
        ],
        "agents": ["accounting_agent", "ceo_agent", "finance_agent", "receivables_agent", "sales_agent"],
        "required": True,
    },
    "account.move.line": {
        "fields": ["id", "balance", "account_id", "date", "company_id", "currency_id"],
        "agents": ["finance_agent"],
        "required": True,
    },
    "account.payment": {
        "fields": ["id", "name", "amount", "currency_id", "date", "partner_id", "state"],
        "agents": ["finance_agent"],
        "required": True,
    },
    "account.account": {
        "fields": ["id", "name", "code", "account_type"],
        "odoo19_changes": {"company_id": "company_ids (many2many)"},
        "agents": ["finance_agent"],
        "required": True,
    },
    "account.journal": {
        "fields": ["id", "name", "type", "company_id"],
        "agents": ["accounting_agent"],
        "required": True,
    },
    
    # Ventas
    "sale.order": {
        "fields": ["id", "name", "partner_id", "amount_total", "date_order", "state", "user_id", "company_id"],
        "agents": ["sales_agent"],
        "required": True,
    },
    
    # Compras
    "purchase.order": {
        "fields": ["id", "name", "partner_id", "amount_total", "date_order", "date_planned", "state", "company_id"],
        "agents": ["purchase_agent"],
        "required": True,
    },
    
    # Inventario
    "product.product": {
        "fields": [
            "id", "name", "default_code", "qty_available", "type", "categ_id",
            "standard_price", "list_price", "uom_id", "active", "sale_ok"
        ],
        "agents": ["inventory_agent", "system_agent"],
        "required": True,
    },
    "product.template": {
        "fields": ["id", "name", "default_code", "categ_id"],
        "agents": ["inventory_agent"],
        "required": True,
    },
    "stock.move": {
        "fields": ["id", "reference", "product_id", "product_uom_qty", "date", "state", "location_id", "location_dest_id"],
        "odoo19_changes": {"name": "reference o display_name"},
        "agents": ["inventory_agent"],
        "required": True,
    },
    "stock.lot": {
        "fields": ["id", "name", "product_id", "product_qty"],
        "odoo19_changes": {"expiration_date": "requiere módulo product_expiry"},
        "agents": ["inventory_agent"],
        "required": False,  # Opcional
    },
    "stock.picking": {
        "fields": ["id", "name", "partner_id", "scheduled_date", "date_done", "state", "picking_type_id"],
        "agents": ["purchase_agent"],
        "required": True,
    },
    "stock.warehouse.orderpoint": {
        "fields": ["id", "product_id", "product_min_qty", "product_max_qty", "qty_to_order"],
        "agents": ["purchase_agent"],
        "required": True,
    },
    "stock.scrap": {
        "fields": ["id", "name", "product_id", "scrap_qty", "origin"],
        "agents": ["manufacturing_agent"],
        "required": False,
    },
    
    # RRHH
    "hr.employee": {
        "fields": ["id", "name", "department_id", "birthday", "active"],
        "odoo19_changes": {"remaining_leaves": "allocation_remaining_display"},
        "agents": ["hr_agent"],
        "required": True,
    },
    "hr.contract": {
        "fields": ["id", "name", "employee_id", "date_start", "date_end", "wage", "state"],
        "agents": ["hr_agent"],
        "required": False,  # Módulo opcional
        "module": "hr_contract",
    },
    "hr.attendance": {
        "fields": ["id", "employee_id", "check_in", "check_out"],
        "agents": ["hr_agent"],
        "required": False,
        "module": "hr_attendance",
    },
    "hr.leave": {
        "fields": ["id", "employee_id", "date_from", "date_to", "state", "holiday_status_id"],
        "agents": ["hr_agent"],
        "required": False,
        "module": "hr_holidays",
    },
    "hr.appraisal": {
        "fields": ["id", "employee_id", "date_close", "state"],
        "agents": ["hr_agent"],
        "required": False,
        "module": "hr_appraisal",
    },
    
    # Manufactura (MRP)
    "mrp.production": {
        "fields": ["id", "name", "product_id", "product_qty", "qty_produced", "state", "date_start", "date_finished", "date_deadline"],
        "agents": ["manufacturing_agent"],
        "required": False,
        "module": "mrp",
    },
    "mrp.workcenter": {
        "fields": ["id", "name", "working_state", "time_efficiency", "workcenter_load"],
        "agents": ["manufacturing_agent"],
        "required": False,
        "module": "mrp",
    },
    "mrp.workorder": {
        "fields": ["id", "name", "workcenter_id", "duration", "duration_expected", "production_id", "state"],
        "agents": ["manufacturing_agent"],
        "required": False,
        "module": "mrp",
    },
    "mrp.bom": {
        "fields": ["id", "product_id", "product_tmpl_id", "product_qty"],
        "agents": ["manufacturing_agent"],
        "required": False,
        "module": "mrp",
    },
    "mrp.routing.workcenter": {
        "fields": ["id", "name", "workcenter_id", "time_cycle", "time_mode"],
        "agents": ["manufacturing_agent"],
        "required": False,
        "module": "mrp",
    },
    
    # Mantenimiento
    "maintenance.request": {
        "fields": ["id", "name", "equipment_id", "schedule_date", "maintenance_type"],
        "agents": ["manufacturing_agent"],
        "required": False,
        "module": "maintenance",
    },
}


def run_introspection(output_json: bool = False, output_file: str = None) -> dict:
    """Ejecuta la introspección completa."""
    
    if not output_json:
        console.print("\n[bold cyan]🔌 Conectando a Odoo...[/bold cyan]")
    
    odoo = OdooClient.get_instance()
    uid = odoo.authenticate()
    
    if not output_json:
        console.print(f"[green]✅ Conectado (UID: {uid})[/green]\n")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "odoo_url": odoo._url,
        "odoo_db": odoo._db,
        "models": {
            "ok": [],
            "missing_fields": [],
            "not_found": [],
        },
        "summary": {
            "total_models": len(ARIA_MODELS_FIELDS),
            "ok": 0,
            "warnings": 0,
            "errors": 0,
        }
    }
    
    for model_name, config in sorted(ARIA_MODELS_FIELDS.items()):
        expected_fields = config["fields"]
        is_required = config.get("required", True)
        
        try:
            fields_info = odoo.fields_get(model_name, attributes=['string', 'type'])
            existing_fields = set(fields_info.keys())
            expected_set = set(expected_fields)
            
            missing = expected_set - existing_fields
            
            if missing:
                results["models"]["missing_fields"].append({
                    "model": model_name,
                    "missing": list(missing),
                    "available_fields": len(existing_fields),
                    "agents": config["agents"],
                    "required": is_required,
                    "odoo19_changes": config.get("odoo19_changes", {}),
                })
                results["summary"]["warnings"] += 1
            else:
                results["models"]["ok"].append({
                    "model": model_name,
                    "fields_count": len(existing_fields),
                    "agents": config["agents"],
                })
                results["summary"]["ok"] += 1
                
        except Exception as e:
            error_msg = str(e)
            results["models"]["not_found"].append({
                "model": model_name,
                "error": error_msg[:200],
                "module": config.get("module", "unknown"),
                "required": is_required,
                "agents": config["agents"],
            })
            if is_required:
                results["summary"]["errors"] += 1
            else:
                results["summary"]["warnings"] += 1
    
    # Output
    if output_json:
        print(json.dumps(results, indent=2))
    elif output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]📄 Reporte guardado en: {output_file}[/green]")
    else:
        _print_results(results)
    
    return results


def _print_results(results: dict):
    """Imprime los resultados formateados."""
    
    # Modelos OK
    console.print("=" * 80)
    console.print("[bold green]✅ MODELOS OK - Todos los campos verificados[/bold green]")
    console.print("=" * 80)
    
    table_ok = Table(show_header=True, header_style="bold green")
    table_ok.add_column("Modelo", style="cyan")
    table_ok.add_column("Campos", justify="right")
    table_ok.add_column("Agentes", style="dim")
    
    for item in results["models"]["ok"]:
        agents_str = ", ".join(item["agents"][:2])
        if len(item["agents"]) > 2:
            agents_str += f" (+{len(item['agents'])-2})"
        table_ok.add_row(item["model"], str(item["fields_count"]), agents_str)
    
    console.print(table_ok)
    console.print(f"\n[green]Total: {len(results['models']['ok'])} modelos OK[/green]\n")
    
    # Modelos no encontrados
    if results["models"]["not_found"]:
        console.print("=" * 80)
        console.print("[bold red]❌ MODELOS NO ENCONTRADOS (módulo no instalado)[/bold red]")
        console.print("=" * 80)
        
        for item in results["models"]["not_found"]:
            status = "🔴" if item["required"] else "🟡"
            console.print(f"  {status} [red]{item['model']}[/red]")
            console.print(f"      Módulo: {item.get('module', 'unknown')}")
            console.print(f"      Agentes afectados: {', '.join(item['agents'])}")
        console.print()
    
    # Campos faltantes
    if results["models"]["missing_fields"]:
        console.print("=" * 80)
        console.print("[bold yellow]⚠️ MODELOS CON CAMPOS FALTANTES[/bold yellow]")
        console.print("=" * 80)
        
        for item in results["models"]["missing_fields"]:
            console.print(f"\n[cyan]📦 {item['model']}[/cyan]")
            console.print(f"   Campos faltantes: [red]{', '.join(item['missing'])}[/red]")
            console.print(f"   Campos disponibles: {item['available_fields']}")
            
            if item.get("odoo19_changes"):
                console.print(f"   [yellow]💡 Cambios Odoo 19:[/yellow]")
                for old, new in item["odoo19_changes"].items():
                    console.print(f"      {old} → {new}")
        console.print()
    
    # Resumen
    console.print("=" * 80)
    console.print("[bold]RESUMEN FINAL[/bold]")
    console.print("=" * 80)
    console.print(f"[green]✅ Modelos OK:[/green] {results['summary']['ok']}")
    console.print(f"[yellow]⚠️ Con advertencias:[/yellow] {results['summary']['warnings']}")
    console.print(f"[red]❌ Errores críticos:[/red] {results['summary']['errors']}")


def main():
    parser = argparse.ArgumentParser(description="Introspección de modelos Odoo para ARIA")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--output", "-o", help="Guardar reporte en archivo")
    args = parser.parse_args()
    
    results = run_introspection(output_json=args.json, output_file=args.output)
    
    # Exit code basado en errores
    if results["summary"]["errors"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
