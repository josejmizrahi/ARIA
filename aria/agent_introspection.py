"""
Sistema de Introspección Inteligente para Agentes.

Antes de hacer consultas críticas, los agentes verifican:
- Qué modelos existen en Odoo
- Qué campos están disponibles
- Qué relaciones existen
- Validan que los datos sean correctos
"""

from typing import Any, Optional
from functools import lru_cache

from aria.odoo_client import OdooClient
from aria.utils.logger import get_logger

logger = get_logger("aria.agent_introspection")


class ModelIntrospection:
    """Introspección de un modelo de Odoo."""
    
    def __init__(self, model_name: str, odoo_client: OdooClient):
        self.model_name = model_name
        self.odoo = odoo_client
        self._fields_cache: Optional[dict] = None
        self._exists_cache: Optional[bool] = None
    
    def exists(self) -> bool:
        """Verifica si el modelo existe en Odoo."""
        if self._exists_cache is not None:
            return self._exists_cache
        
        try:
            self.odoo.execute(self.model_name, "check_access_rights", ["read"], {"raise_exception": False})
            self._exists_cache = True
            return True
        except Exception:
            self._exists_cache = False
            return False
    
    def get_fields(self) -> dict[str, Any]:
        """Obtiene todos los campos del modelo."""
        if self._fields_cache is not None:
            return self._fields_cache
        
        if not self.exists():
            self._fields_cache = {}
            return {}
        
        try:
            self._fields_cache = self.odoo.fields_get(self.model_name, attributes=['string', 'type', 'relation', 'required'])
            return self._fields_cache
        except Exception as e:
            logger.warning(f"Error obteniendo campos de {self.model_name}: {e}")
            self._fields_cache = {}
            return {}
    
    def field_exists(self, field_name: str) -> bool:
        """Verifica si un campo existe en el modelo."""
        fields = self.get_fields()
        return field_name in fields
    
    def validate_fields(self, field_names: list[str]) -> dict[str, bool]:
        """Valida qué campos existen."""
        fields = self.get_fields()
        return {field: field in fields for field in field_names}
    
    def get_field_type(self, field_name: str) -> Optional[str]:
        """Obtiene el tipo de un campo."""
        fields = self.get_fields()
        field_info = fields.get(field_name, {})
        return field_info.get("type")
    
    def get_field_relation(self, field_name: str) -> Optional[str]:
        """Obtiene el modelo relacionado de un campo many2one/one2many/many2many."""
        fields = self.get_fields()
        field_info = fields.get(field_name, {})
        return field_info.get("relation")


class AgentIntrospection:
    """Sistema de introspección para agentes."""
    
    def __init__(self, odoo_client: OdooClient):
        self.odoo = odoo_client
        self._model_cache: dict[str, ModelIntrospection] = {}
    
    @lru_cache(maxsize=100)
    def get_model(self, model_name: str) -> ModelIntrospection:
        """Obtiene introspección de un modelo (con cache)."""
        if model_name not in self._model_cache:
            self._model_cache[model_name] = ModelIntrospection(model_name, self.odoo)
        return self._model_cache[model_name]
    
    def validate_query(
        self,
        model_name: str,
        fields: list[str],
        domain: Optional[list] = None,
    ) -> dict[str, Any]:
        """
        Valida una consulta antes de ejecutarla.
        
        Returns:
            {
                "valid": bool,
                "model_exists": bool,
                "fields_valid": dict[str, bool],
                "missing_fields": list[str],
                "suggestions": dict[str, str],  # Sugerencias de campos alternativos
            }
        """
        model = self.get_model(model_name)
        
        result = {
            "valid": True,
            "model_exists": model.exists(),
            "fields_valid": {},
            "missing_fields": [],
            "suggestions": {},
        }
        
        if not result["model_exists"]:
            result["valid"] = False
            logger.warning(f"Modelo {model_name} no existe en Odoo")
            return result
        
        # Validar campos
        result["fields_valid"] = model.validate_fields(fields)
        result["missing_fields"] = [
            field for field, exists in result["fields_valid"].items()
            if not exists
        ]
        
        if result["missing_fields"]:
            result["valid"] = False
            logger.warning(
                f"Campos faltantes en {model_name}: {result['missing_fields']}"
            )
            
            # Intentar sugerir campos alternativos
            all_fields = model.get_fields()
            for missing_field in result["missing_fields"]:
                # Buscar campos similares
                suggestions = [
                    name for name in all_fields.keys()
                    if missing_field.lower() in name.lower() or name.lower() in missing_field.lower()
                ]
                if suggestions:
                    result["suggestions"][missing_field] = suggestions[0]
        
        return result
    
    def safe_search_read(
        self,
        model_name: str,
        domain: Optional[list] = None,
        fields: Optional[list[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Ejecuta search_read con validación previa.
        
        Returns:
            {
                "success": bool,
                "data": list[dict],
                "validation": dict,
                "error": Optional[str],
            }
        """
        fields = fields or []
        
        # Validar antes de ejecutar
        validation = self.validate_query(model_name, fields, domain)
        
        if not validation["valid"]:
            # Intentar con campos válidos solamente
            valid_fields = [
                field for field, valid in validation["fields_valid"].items()
                if valid
            ]
            
            if not valid_fields:
                return {
                    "success": False,
                    "data": [],
                    "validation": validation,
                    "error": f"Modelo {model_name} no existe o ningún campo es válido",
                }
            
            logger.warning(
                f"Usando solo campos válidos: {valid_fields} "
                f"(faltantes: {validation['missing_fields']})"
            )
            fields = valid_fields
        
        # Ejecutar consulta
        try:
            data = self.odoo.search_read(
                model_name,
                domain or [],
                fields=fields,
                limit=limit,
                offset=offset,
                order=order
            )
            
            return {
                "success": True,
                "data": data,
                "validation": validation,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error en search_read de {model_name}: {e}")
            return {
                "success": False,
                "data": [],
                "validation": validation,
                "error": str(e),
            }
    
    def get_available_models(self, pattern: Optional[str] = None) -> list[str]:
        """
        Obtiene lista de modelos disponibles (limitado a modelos comunes).
        
        Nota: Obtener todos los modelos puede ser costoso, así que
        retornamos solo modelos comunes conocidos.
        """
        common_models = [
            "account.move",
            "account.move.line",
            "account.payment",
            "account.account",
            "account.journal",
            "account.budget",
            "account.budget.line",
            "res.partner",
            "res.company",
            "product.product",
            "product.template",
            "sale.order",
            "purchase.order",
            "stock.move",
            "stock.picking",
            "hr.employee",
        ]
        
        if pattern:
            pattern_lower = pattern.lower()
            return [m for m in common_models if pattern_lower in m.lower()]
        
        return common_models


# Instancia global por cliente Odoo
_introspection_cache: dict[str, AgentIntrospection] = {}


def get_introspection(odoo_client: Optional[OdooClient] = None) -> AgentIntrospection:
    """Obtiene instancia de introspección."""
    if odoo_client is None:
        from aria.odoo_client import OdooClient
        odoo_client = OdooClient.get_instance()
    
    # Usar URL como clave para cache
    cache_key = f"{odoo_client._url}_{odoo_client._db}"
    
    if cache_key not in _introspection_cache:
        _introspection_cache[cache_key] = AgentIntrospection(odoo_client)
    
    return _introspection_cache[cache_key]
