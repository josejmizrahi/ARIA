"""
ARIA - Sistema de Caché
======================

Sistema de caché simple en memoria para mejorar el rendimiento.
Usa Redis si está disponible, sino usa caché en memoria.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
import hashlib
import json

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """Entrada de caché con TTL."""
    
    def __init__(self, value: Any, ttl_seconds: int = 60):
        self.value = value
        self.created_at = datetime.now()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds


class MemoryCache:
    """Caché simple en memoria."""
    
    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = 1000  # Máximo de entradas
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Genera una clave única para el caché."""
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, prefix: str, *args, **kwargs) -> Optional[Any]:
        """Obtiene un valor del caché."""
        key = self._make_key(prefix, *args, **kwargs)
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if entry.is_expired():
            del self._cache[key]
            return None
        
        return entry.value
    
    def set(self, prefix: str, value: Any, ttl_seconds: int = 60, *args, **kwargs) -> None:
        """Almacena un valor en el caché."""
        # Limpiar entradas expiradas si el caché está lleno
        if len(self._cache) >= self._max_size:
            self._clean_expired()
        
        # Si aún está lleno después de limpiar, eliminar la entrada más antigua
        if len(self._cache) >= self._max_size:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
            del self._cache[oldest_key]
        
        key = self._make_key(prefix, *args, **kwargs)
        self._cache[key] = CacheEntry(value, ttl_seconds)
    
    def delete(self, prefix: str, *args, **kwargs) -> None:
        """Elimina una entrada del caché."""
        key = self._make_key(prefix, *args, **kwargs)
        if key in self._cache:
            del self._cache[key]
    
    def clear(self, prefix: Optional[str] = None) -> None:
        """Limpia el caché."""
        if prefix is None:
            self._cache.clear()
        else:
            # Eliminar todas las entradas que empiecen con el prefijo
            keys_to_delete = [
                k for k in self._cache.keys()
                if k.startswith(prefix)
            ]
            for key in keys_to_delete:
                del self._cache[key]
    
    def _clean_expired(self) -> None:
        """Limpia entradas expiradas."""
        expired_keys = [
            k for k, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
    
    def get_stats(self) -> dict:
        """Retorna estadísticas del caché."""
        self._clean_expired()
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "usage_percent": (len(self._cache) / self._max_size) * 100
        }


# Instancia global del caché
_memory_cache: Optional[MemoryCache] = None


def get_cache() -> MemoryCache:
    """Obtiene la instancia del caché."""
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = MemoryCache()
    return _memory_cache


def cache_result(ttl_seconds: int = 60, prefix: str = "default"):
    """
    Decorador para cachear resultados de funciones.
    
    Uso:
        @cache_result(ttl_seconds=300, prefix="finance")
        async def get_financial_data():
            # ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Intentar obtener del caché
            cached_value = cache.get(prefix, func.__name__, *args, **kwargs)
            if cached_value is not None:
                logger.debug(f"Cache hit: {prefix}.{func.__name__}")
                return cached_value
            
            # Ejecutar función y cachear resultado
            logger.debug(f"Cache miss: {prefix}.{func.__name__}")
            result = await func(*args, **kwargs)
            cache.set(prefix, result, ttl_seconds, func.__name__, *args, **kwargs)
            
            return result
        
        return wrapper
    return decorator
