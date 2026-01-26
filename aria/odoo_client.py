"""
ARIA - Cliente Odoo
====================

Cliente robusto para conexión a Odoo ERP.
Implementa:
- Patrón Singleton
- Retry automático con backoff exponencial
- Logging estructurado
- Manejo de errores
"""

import xmlrpc.client
from contextlib import contextmanager
from typing import Any, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger(__name__)


class OdooConnectionError(Exception):
    """Error de conexión a Odoo."""
    pass


class OdooAuthenticationError(Exception):
    """Error de autenticación en Odoo."""
    pass


class OdooOperationError(Exception):
    """Error durante operación en Odoo."""
    pass


class OdooClient:
    """
    Cliente Odoo con soporte para XML-RPC.
    
    Implementa patrón Singleton para reutilizar conexión.
    
    Uso:
        client = OdooClient.get_instance()
        partners = client.search_read("res.partner", [("is_company", "=", True)])
    """
    
    _instance: Optional["OdooClient"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "OdooClient":
        """Implementación Singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Inicializa el cliente (solo la primera vez)."""
        if self._initialized:
            return
        
        self._url = settings.odoo.url
        self._db = settings.odoo.db
        self._user = settings.odoo.user
        self._password = settings.odoo.password
        self._timeout = settings.odoo.timeout
        
        self._uid: Optional[int] = None
        self._common: Optional[xmlrpc.client.ServerProxy] = None
        self._models: Optional[xmlrpc.client.ServerProxy] = None
        
        self._initialized = True
        logger.info(
            "Cliente Odoo inicializado",
            url=self._url,
            db=self._db,
            user=self._user
        )
    
    @classmethod
    def get_instance(cls) -> "OdooClient":
        """Obtiene la instancia singleton del cliente."""
        return cls()
    
    @classmethod
    def reset_instance(cls) -> None:
        """Resetea la instancia (útil para tests)."""
        cls._instance = None
        cls._initialized = False
    
    @property
    def uid(self) -> int:
        """Retorna el UID del usuario autenticado."""
        if self._uid is None:
            self.authenticate()
        return self._uid  # type: ignore
    
    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def authenticate(self) -> int:
        """
        Autentica con Odoo y obtiene el UID.
        
        Returns:
            int: UID del usuario autenticado.
            
        Raises:
            OdooAuthenticationError: Si la autenticación falla.
        """
        logger.debug("Autenticando con Odoo...")
        
        try:
            self._common = xmlrpc.client.ServerProxy(
                f"{self._url}/xmlrpc/2/common",
                allow_none=True
            )
            
            self._uid = self._common.authenticate(
                self._db,
                self._user,
                self._password,
                {}
            )
            
            if not self._uid:
                raise OdooAuthenticationError(
                    f"Autenticación fallida para usuario '{self._user}'"
                )
            
            self._models = xmlrpc.client.ServerProxy(
                f"{self._url}/xmlrpc/2/object",
                allow_none=True
            )
            
            logger.info(
                "Autenticación exitosa",
                uid=self._uid,
                user=self._user
            )
            return self._uid
            
        except xmlrpc.client.Fault as e:
            logger.error("Error XML-RPC durante autenticación", error=str(e))
            raise OdooAuthenticationError(f"Error XML-RPC: {e}")
        except Exception as e:
            logger.error("Error de conexión a Odoo", error=str(e))
            raise OdooConnectionError(f"No se pudo conectar a Odoo: {e}")
    
    def _ensure_connection(self) -> None:
        """Asegura que hay una conexión activa."""
        if self._uid is None or self._models is None:
            self.authenticate()
    
    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def execute(
        self,
        model: str,
        method: str,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Ejecuta un método en un modelo de Odoo.
        
        Args:
            model: Nombre del modelo (ej: "res.partner")
            method: Método a ejecutar (ej: "search", "read")
            *args: Argumentos posicionales
            **kwargs: Argumentos nombrados
            
        Returns:
            Resultado de la operación.
            
        Raises:
            OdooOperationError: Si la operación falla.
        """
        self._ensure_connection()
        
        logger.debug(
            "Ejecutando operación Odoo",
            model=model,
            method=method,
            args=args[:2] if args else None  # Log parcial para no exponer datos
        )
        
        try:
            result = self._models.execute_kw(  # type: ignore
                self._db,
                self._uid,
                self._password,
                model,
                method,
                list(args),
                kwargs
            )
            return result
            
        except xmlrpc.client.Fault as e:
            logger.error(
                "Error en operación Odoo",
                model=model,
                method=method,
                error=str(e)
            )
            raise OdooOperationError(f"Error en {model}.{method}: {e}")
    
    # ==========================================
    # Métodos de conveniencia
    # ==========================================
    
    def search(
        self,
        model: str,
        domain: list,
        offset: int = 0,
        limit: Optional[int] = None,
        order: Optional[str] = None
    ) -> list[int]:
        """
        Busca registros por dominio.
        
        Args:
            model: Modelo a buscar
            domain: Dominio de búsqueda
            offset: Offset para paginación
            limit: Límite de registros
            order: Ordenamiento
            
        Returns:
            Lista de IDs encontrados.
        """
        kwargs: dict[str, Any] = {"offset": offset}
        if limit:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        
        return self.execute(model, "search", domain, **kwargs)
    
    def read(
        self,
        model: str,
        ids: list[int],
        fields: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Lee registros por IDs.
        
        Args:
            model: Modelo a leer
            ids: Lista de IDs
            fields: Campos a retornar
            
        Returns:
            Lista de diccionarios con los datos.
        """
        return self.execute(model, "read", ids, fields or [])
    
    def search_read(
        self,
        model: str,
        domain: list,
        fields: Optional[list[str]] = None,
        offset: int = 0,
        limit: Optional[int] = None,
        order: Optional[str] = None
    ) -> list[dict]:
        """
        Busca y lee registros en una sola llamada.
        
        Args:
            model: Modelo a buscar
            domain: Dominio de búsqueda
            fields: Campos a retornar
            offset: Offset para paginación
            limit: Límite de registros
            order: Ordenamiento
            
        Returns:
            Lista de diccionarios con los datos.
        """
        kwargs: dict[str, Any] = {"offset": offset}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        
        return self.execute(model, "search_read", domain, **kwargs)
    
    def create(self, model: str, values: dict) -> int:
        """
        Crea un nuevo registro.
        
        Args:
            model: Modelo donde crear
            values: Valores del registro
            
        Returns:
            ID del registro creado.
        """
        return self.execute(model, "create", values)
    
    def write(self, model: str, ids: list[int], values: dict) -> bool:
        """
        Actualiza registros existentes.
        
        Args:
            model: Modelo a actualizar
            ids: IDs a actualizar
            values: Valores a escribir
            
        Returns:
            True si fue exitoso.
        """
        return self.execute(model, "write", ids, values)
    
    def unlink(self, model: str, ids: list[int]) -> bool:
        """
        Elimina registros.
        
        Args:
            model: Modelo donde eliminar
            ids: IDs a eliminar
            
        Returns:
            True si fue exitoso.
        """
        return self.execute(model, "unlink", ids)
    
    def search_count(self, model: str, domain: list) -> int:
        """
        Cuenta registros que coinciden con el dominio.
        
        Args:
            model: Modelo a contar
            domain: Dominio de búsqueda
            
        Returns:
            Número de registros.
        """
        return self.execute(model, "search_count", domain)
    
    def fields_get(
        self,
        model: str,
        attributes: Optional[list[str]] = None
    ) -> dict:
        """
        Obtiene información de los campos de un modelo.
        
        Args:
            model: Modelo a inspeccionar
            attributes: Atributos a retornar
            
        Returns:
            Diccionario con información de campos.
        """
        return self.execute(
            model,
            "fields_get",
            allfields=[],
            attributes=attributes or ["string", "type", "required", "readonly"]
        )
    
    # ==========================================
    # Introspección
    # ==========================================
    
    def get_models(self) -> list[dict]:
        """
        Lista todos los modelos disponibles en Odoo.
        
        Returns:
            Lista de modelos con su información.
        """
        return self.search_read(
            "ir.model",
            [],
            fields=["model", "name", "state", "transient"],
            order="model"
        )
    
    def get_model_info(self, model_name: str) -> dict:
        """
        Obtiene información detallada de un modelo.
        
        Args:
            model_name: Nombre técnico del modelo
            
        Returns:
            Información del modelo incluyendo campos.
        """
        models = self.search_read(
            "ir.model",
            [("model", "=", model_name)],
            fields=["model", "name", "state", "info"]
        )
        
        if not models:
            raise OdooOperationError(f"Modelo '{model_name}' no encontrado")
        
        model_info = models[0]
        model_info["fields"] = self.fields_get(model_name)
        
        return model_info
    
    def check_connection(self) -> dict:
        """
        Verifica la conexión y retorna información del servidor.
        
        Returns:
            Diccionario con información de versión.
        """
        try:
            self._common = xmlrpc.client.ServerProxy(
                f"{self._url}/xmlrpc/2/common",
                allow_none=True
            )
            version = self._common.version()
            logger.info("Conexión verificada", version=version.get("server_version"))
            return version
        except Exception as e:
            logger.error("Error verificando conexión", error=str(e))
            raise OdooConnectionError(f"No se pudo verificar conexión: {e}")


@contextmanager
def odoo_client():
    """
    Context manager para usar el cliente Odoo.
    
    Uso:
        with odoo_client() as client:
            partners = client.search_read("res.partner", [])
    """
    client = OdooClient.get_instance()
    try:
        yield client
    except Exception as e:
        logger.error("Error en contexto Odoo", error=str(e))
        raise
