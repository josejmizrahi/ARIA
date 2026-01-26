"""
Gestor de Presupuestos Financieros.

Gestiona presupuestos desde múltiples fuentes:
1. Módulo de presupuestos de Odoo (account.budget) si está disponible
2. Almacenamiento local (JSON) para configuración manual
3. Cálculo automático basado en histórico si no hay presupuestos configurados
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("aria.budget_manager")


class BudgetManager:
    """Gestor de presupuestos financieros."""
    
    def __init__(self, company_id: int):
        """
        Inicializa el gestor de presupuestos.
        
        Args:
            company_id: ID de la compañía en Odoo
        """
        self.company_id = company_id
        self.budget_file = Path(settings.log_dir) / "budgets.json"
        self._budgets_cache: Optional[dict] = None
        
    def _load_budgets_from_file(self) -> dict:
        """Carga presupuestos desde archivo JSON."""
        if self.budget_file.exists():
            try:
                with open(self.budget_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando presupuestos desde archivo: {e}")
        return {}
    
    def _save_budgets_to_file(self, budgets: dict) -> None:
        """Guarda presupuestos en archivo JSON."""
        try:
            self.budget_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.budget_file, 'w', encoding='utf-8') as f:
                json.dump(budgets, f, indent=2, ensure_ascii=False)
            self._budgets_cache = None  # Invalidar cache
        except Exception as e:
            logger.error(f"Error guardando presupuestos: {e}")
    
    def _check_budget_models_available(self, odoo_client) -> dict[str, bool]:
        """
        Verifica qué modelos de presupuestos están disponibles en Odoo.
        
        Returns:
            Dict con modelos disponibles: {"account.budget": True, ...}
        """
        available = {}
        models_to_check = [
            "account.budget",
            "account.budget.line",
            "account.budget.post",
            "crossovered.budget",  # Versión antigua
            "crossovered.budget.lines",
        ]
        
        for model_name in models_to_check:
            try:
                odoo_client.execute(model_name, "check_access_rights", ["read"], {"raise_exception": False})
                available[model_name] = True
            except Exception:
                available[model_name] = False
        
        return available
    
    def _load_budgets_from_odoo(self, odoo_client) -> Optional[dict]:
        """
        Intenta cargar presupuestos desde módulos de presupuestos de Odoo.
        
        Prioridad:
        1. account.budget (módulo moderno)
        2. crossovered.budget (versión antigua)
        
        Returns:
            Dict con presupuestos o None si ningún módulo está disponible
        """
        # Verificar qué modelos están disponibles
        available_models = self._check_budget_models_available(odoo_client)
        
        # Intentar con account.budget primero (versión moderna)
        if available_models.get("account.budget"):
            return self._load_from_account_budget(odoo_client)
        
        # Intentar con crossovered.budget (versión antigua)
        if available_models.get("crossovered.budget"):
            return self._load_from_crossovered_budget(odoo_client)
        
        logger.debug("No se encontraron módulos de presupuestos en Odoo")
        return None
    
    def _load_from_account_budget(self, odoo_client) -> Optional[dict]:
        """Carga presupuestos desde account.budget (módulo moderno)."""
        try:
            # Obtener año actual
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            # Buscar presupuestos activos para el año/mes actual
            budget_ids = odoo_client.search(
                "account.budget",
                [
                    ("company_id", "=", self.company_id),
                    ("date_from", "<=", f"{current_year}-{current_month:02d}-01"),
                    ("date_to", ">=", f"{current_year}-{current_month:02d}-28"),
                ],
                limit=1
            )
            
            if not budget_ids:
                logger.debug("No se encontraron presupuestos activos en account.budget")
                return None
            
            # Leer presupuesto
            budgets = odoo_client.read("account.budget", budget_ids, [
                "name", "date_from", "date_to", "budget_line_ids"
            ])
            
            if not budgets:
                return None
            
            budget = budgets[0]
            
            # Procesar líneas de presupuesto
            result = {
                "source": "odoo_account_budget",
                "budget_id": budget["id"],
                "name": budget.get("name", ""),
                "monthly_revenue": 0,
                "monthly_expenses": 0,
                "by_category": {},
            }
            
            # Leer líneas de presupuesto
            if budget.get("budget_line_ids"):
                lines = odoo_client.read("account.budget.line", budget["budget_line_ids"], [
                    "account_id", "planned_amount", "date_from", "date_to"
                ])
                
                for line in lines:
                    account_id = line.get("account_id")
                    if account_id:
                        account_id_value = account_id[0] if isinstance(account_id, list) else account_id
                        account_name = account_id[1] if isinstance(account_id, list) else "Sin nombre"
                        amount = abs(line.get("planned_amount", 0))
                        
                        # Determinar si es ingreso o gasto basado en tipo de cuenta
                        try:
                            account_info = odoo_client.read("account.account", [account_id_value], ["account_type"])
                            if account_info:
                                account_type = account_info[0].get("account_type", "")
                                
                                if account_type in ["income", "income_other"]:
                                    result["monthly_revenue"] += amount
                                elif account_type in ["expense", "expense_depreciation", "expense_direct_cost"]:
                                    result["monthly_expenses"] += amount
                                    result["by_category"][account_name] = amount
                        except Exception:
                            # Si no se puede determinar, asumir gasto
                            result["monthly_expenses"] += amount
                            result["by_category"][account_name] = amount
            
            logger.info(f"Presupuestos cargados desde account.budget: {result['name']}")
            return result
            
        except Exception as e:
            logger.debug(f"Error cargando desde account.budget: {e}")
            return None
    
    def _load_from_crossovered_budget(self, odoo_client) -> Optional[dict]:
        """Carga presupuestos desde crossovered.budget (versión antigua)."""
        try:
            # Obtener año actual
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            # Buscar presupuestos activos
            budget_ids = odoo_client.search(
                "crossovered.budget",
                [
                    ("company_id", "=", self.company_id),
                    ("date_from", "<=", f"{current_year}-{current_month:02d}-01"),
                    ("date_to", ">=", f"{current_year}-{current_month:02d}-28"),
                    ("state", "=", "done"),  # Solo presupuestos confirmados
                ],
                limit=1
            )
            
            if not budget_ids:
                logger.debug("No se encontraron presupuestos activos en crossovered.budget")
                return None
            
            # Leer presupuesto
            budgets = odoo_client.read("crossovered.budget", budget_ids, [
                "name", "date_from", "date_to", "crossovered_budget_line_ids"
            ])
            
            if not budgets:
                return None
            
            budget = budgets[0]
            
            result = {
                "source": "odoo_crossovered_budget",
                "budget_id": budget["id"],
                "name": budget.get("name", ""),
                "monthly_revenue": 0,
                "monthly_expenses": 0,
                "by_category": {},
            }
            
            # Leer líneas de presupuesto
            if budget.get("crossovered_budget_line_ids"):
                lines = odoo_client.read("crossovered.budget.lines", budget["crossovered_budget_line_ids"], [
                    "general_budget_id", "date_from", "date_to", "planned_amount", "account_id"
                ])
                
                for line in lines:
                    amount = abs(line.get("planned_amount", 0))
                    account_id = line.get("account_id")
                    
                    if account_id:
                        account_id_value = account_id[0] if isinstance(account_id, list) else account_id
                        account_name = account_id[1] if isinstance(account_id, list) else "Sin nombre"
                        
                        try:
                            account_info = odoo_client.read("account.account", [account_id_value], ["account_type"])
                            if account_info:
                                account_type = account_info[0].get("account_type", "")
                                
                                if account_type in ["income", "income_other"]:
                                    result["monthly_revenue"] += amount
                                elif account_type in ["expense", "expense_depreciation", "expense_direct_cost"]:
                                    result["monthly_expenses"] += amount
                                    result["by_category"][account_name] = amount
                        except Exception:
                            result["monthly_expenses"] += amount
                            result["by_category"][account_name] = amount
            
            logger.info(f"Presupuestos cargados desde crossovered.budget: {result['name']}")
            return result
            
        except Exception as e:
            logger.debug(f"Error cargando desde crossovered.budget: {e}")
            return None
    
    def _calculate_budgets_from_history(self, odoo_client, months: int = 6) -> dict:
        """
        Calcula presupuestos automáticamente basado en histórico.
        
        Args:
            odoo_client: Cliente de Odoo
            months: Número de meses históricos a considerar
            
        Returns:
            Dict con presupuestos calculados
        """
        logger.info(f"Calculando presupuestos desde histórico ({months} meses)")
        
        monthly_revenues = []
        monthly_expenses = []
        expenses_by_category = {}
        
        for i in range(months):
            month_start = (datetime.now() - timedelta(days=30*(i+1))).strftime("%Y-%m-%d")
            month_end = (datetime.now() - timedelta(days=30*i)).strftime("%Y-%m-%d")
            
            # Ingresos del mes
            invoices = odoo_client.search_read(
                "account.move",
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("invoice_date", ">=", month_start),
                    ("invoice_date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["amount_total"],
                limit=1000
            )
            revenue = sum(i.get("amount_total", 0) for i in invoices)
            monthly_revenues.append(revenue)
            
            # Gastos del mes
            expenses = odoo_client.search_read(
                "account.payment",
                [
                    ("payment_type", "=", "outbound"),
                    ("state", "=", "posted"),
                    ("date", ">=", month_start),
                    ("date", "<=", month_end),
                    ("company_id", "=", self.company_id),
                ],
                ["amount"],
                limit=1000
            )
            expenses_total = sum(e.get("amount", 0) for e in expenses)
            monthly_expenses.append(expenses_total)
            
            # Gastos por categoría
            # Verificar si account.account tiene company_id antes de filtrar
            from aria.agent_introspection import get_introspection
            introspection = get_introspection(odoo_client)
            account_model = introspection.get_model("account.account")
            
            # Construir dominio sin company_id si el campo no existe
            domain = [
                ("account_type", "in", ["expense", "expense_depreciation", "expense_direct_cost"]),
            ]
            if account_model.field_exists("company_id"):
                domain.append(("company_id", "=", self.company_id))
            
            expense_accounts = odoo_client.search_read(
                "account.account",
                domain,
                ["id", "name"],
                limit=50
            )
            
            for account in expense_accounts:
                account_id = account["id"]
                account_name = account.get("name", "Sin nombre")
                
                # Verificar si account.move.line tiene company_id antes de filtrar
                move_line_model = introspection.get_model("account.move.line")
                move_line_domain = [
                    ("account_id", "=", account_id),
                    ("parent_state", "=", "posted"),
                    ("date", ">=", month_start),
                    ("date", "<=", month_end),
                ]
                if move_line_model.field_exists("company_id"):
                    move_line_domain.append(("company_id", "=", self.company_id))
                
                lines = odoo_client.search_read(
                    "account.move.line",
                    move_line_domain,
                    ["balance"],
                    limit=1000
                )
                
                total = abs(sum(l.get("balance", 0) for l in lines))
                if total > 0:
                    if account_name not in expenses_by_category:
                        expenses_by_category[account_name] = []
                    expenses_by_category[account_name].append(total)
        
        # Calcular promedios
        avg_revenue = sum(monthly_revenues) / len(monthly_revenues) if monthly_revenues else 0
        avg_expenses = sum(monthly_expenses) / len(monthly_expenses) if monthly_expenses else 0
        
        # Promedio por categoría
        avg_by_category = {
            cat: sum(amounts) / len(amounts)
            for cat, amounts in expenses_by_category.items()
            if amounts
        }
        
        return {
            "source": "calculated",
            "monthly_revenue": avg_revenue,
            "monthly_expenses": avg_expenses,
            "by_category": avg_by_category,
            "calculated_at": datetime.now().isoformat(),
            "months_used": months,
        }
    
    def get_budgets(self, odoo_client) -> dict:
        """
        Obtiene presupuestos desde la mejor fuente disponible.
        
        Prioridad:
        1. Odoo account.budget (si está disponible)
        2. Archivo JSON (configuración manual)
        3. Cálculo automático desde histórico
        
        Args:
            odoo_client: Cliente de Odoo
            
        Returns:
            Dict con presupuestos
        """
        # Intentar desde Odoo primero
        odoo_budgets = self._load_budgets_from_odoo(odoo_client)
        if odoo_budgets:
            return odoo_budgets
        
        # Intentar desde archivo
        file_budgets = self._load_budgets_from_file()
        if file_budgets.get("monthly_revenue") or file_budgets.get("monthly_expenses"):
            return {**file_budgets, "source": file_budgets.get("source", "file")}
        
        # Calcular desde histórico
        return self._calculate_budgets_from_history(odoo_client)
    
    def set_budgets(
        self,
        monthly_revenue: Optional[float] = None,
        monthly_expenses: Optional[float] = None,
        by_category: Optional[dict[str, float]] = None,
    ) -> dict:
        """
        Establece presupuestos manualmente (se guardan en archivo JSON).
        
        Args:
            monthly_revenue: Presupuesto mensual de ingresos
            monthly_expenses: Presupuesto mensual de gastos
            by_category: Presupuestos por categoría
            
        Returns:
            Dict con presupuestos guardados
        """
        budgets = self._load_budgets_from_file()
        
        if monthly_revenue is not None:
            budgets["monthly_revenue"] = monthly_revenue
        if monthly_expenses is not None:
            budgets["monthly_expenses"] = monthly_expenses
        if by_category is not None:
            budgets["by_category"] = by_category
        
        budgets["source"] = "manual"
        budgets["updated_at"] = datetime.now().isoformat()
        
        self._save_budgets_to_file(budgets)
        logger.info("Presupuestos guardados manualmente")
        
        return budgets
    
    def get_monthly_revenue(self, odoo_client) -> float:
        """Obtiene presupuesto mensual de ingresos."""
        budgets = self.get_budgets(odoo_client)
        return budgets.get("monthly_revenue", 0)
    
    def get_monthly_expenses(self, odoo_client) -> float:
        """Obtiene presupuesto mensual de gastos."""
        budgets = self.get_budgets(odoo_client)
        return budgets.get("monthly_expenses", 0)
    
    def get_category_budgets(self, odoo_client) -> dict[str, float]:
        """Obtiene presupuestos por categoría."""
        budgets = self.get_budgets(odoo_client)
        return budgets.get("by_category", {})


# Instancia global (se inicializa con company_id cuando se necesite)
_budget_manager: Optional[BudgetManager] = None


def get_budget_manager(company_id: int) -> BudgetManager:
    """Obtiene instancia del gestor de presupuestos."""
    global _budget_manager
    if _budget_manager is None or _budget_manager.company_id != company_id:
        _budget_manager = BudgetManager(company_id)
    return _budget_manager
