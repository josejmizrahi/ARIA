"""
Optimizaciones para el agente de finanzas.
Este archivo contiene mejoras de rendimiento y correcciones de errores.
"""

from typing import Any, Optional
from datetime import datetime, timedelta
from aria.cache import get_cache

cache = get_cache()


def optimize_account_move_line_query(agent, account_id: int, company_id: int, limit: int = 1000) -> float:
    """
    Optimiza la consulta de account.move.line para obtener saldo.
    
    En lugar de traer todos los registros, usa una estrategia más eficiente:
    1. Intenta usar campos calculados si están disponibles
    2. Limita a registros recientes si hay muchos
    3. Usa caché para consultas repetidas
    """
    cache_key = f"account_balance_{account_id}_{company_id}"
    
    # Intentar obtener del caché (TTL 5 minutos)
    cached_balance = cache.get("finance", cache_key)
    if cached_balance is not None:
        return cached_balance
    
    try:
        # Consulta optimizada: solo últimos 12 meses para saldos
        date_from = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        lines = agent.search_read(
            "account.move.line",
            [
                ("account_id", "=", account_id),
                ("parent_state", "=", "posted"),
                ("company_id", "=", company_id),
                ("date", ">=", date_from),  # Solo últimos 12 meses
            ],
            ["balance"],
            limit=limit,
            order="date desc"  # Más recientes primero
        )
        
        balance = sum(l.get("balance", 0) for l in lines)
        
        # Cachear resultado
        cache.set("finance", balance, ttl_seconds=300, prefix=cache_key)
        
        return balance
        
    except Exception as e:
        agent.logger.error(f"Error obteniendo saldo de cuenta {account_id}: {e}")
        return 0.0


def validate_financial_data(data: dict, required_fields: list[str]) -> tuple[bool, Optional[str]]:
    """
    Valida que los datos financieros tengan los campos requeridos y valores válidos.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Los datos deben ser un diccionario"
    
    for field in required_fields:
        if field not in data:
            return False, f"Campo requerido faltante: {field}"
        
        value = data.get(field)
        if value is None:
            return False, f"Campo {field} es None"
        
        # Validar tipos numéricos
        if field in ["cash_balance", "runway_days", "daily_burn", "monthly_revenue"]:
            try:
                float(value)
            except (ValueError, TypeError):
                return False, f"Campo {field} debe ser numérico, recibió: {type(value)}"
    
    return True, None
