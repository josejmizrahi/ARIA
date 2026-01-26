"""
ARIA - Motor de Aprobaciones
=============================

Gestiona el ciclo de vida de propuestas:
1. Registro de propuesta pendiente
2. Almacenamiento en Redis (o archivo JSON como fallback)
3. Aprobación/Rechazo/Modificación
4. Disparo de ejecución

Redis estructura:
- proposal:{id} -> JSON de la propuesta
- proposals:pending -> Lista de IDs pendientes
- proposals:agent:{name} -> Lista de IDs por agente

Fallback (sin Redis):
- .aria/proposals.json -> Todas las propuestas
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from aria.config import settings
from aria.models.proposal import Proposal, ProposalStatus, Priority
from aria.utils.logger import get_logger

logger = get_logger("aria.approval_engine")

# Archivo de persistencia local
PROPOSALS_FILE = Path(".aria/proposals.json")


class ApprovalEngineError(Exception):
    """Error en el motor de aprobaciones."""
    pass


class ApprovalEngine:
    """
    Motor de aprobaciones basado en Redis.
    
    Gestiona propuestas pendientes y su ciclo de vida.
    Soporta callbacks para cuando una propuesta es aprobada.
    
    Uso:
        from aria.approval_engine import approval_engine
        
        # Registrar propuesta
        await approval_engine.register(proposal)
        
        # Aprobar
        await approval_engine.approve("abc123")
        
        # Rechazar
        await approval_engine.reject("abc123", "No es prioritario")
        
        # Obtener pendientes
        pending = await approval_engine.get_pending()
    """
    
    _instance: Optional["ApprovalEngine"] = None
    
    def __new__(cls) -> "ApprovalEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._redis = None
        self._callbacks: dict[str, Callable] = {}
        self._local_storage: dict[str, Proposal] = {}
        self._use_redis = settings.redis.enabled
        self._initialized = True
        
        # Cargar propuestas desde archivo si existe (fallback local)
        self._load_local_storage()
        
        logger.info(
            f"ApprovalEngine inicializado (Redis: {self._use_redis})"
        )
    
    def _load_local_storage(self) -> None:
        """Carga propuestas desde archivo local."""
        if PROPOSALS_FILE.exists():
            try:
                data = json.loads(PROPOSALS_FILE.read_text())
                for pid, pdata in data.items():
                    self._local_storage[pid] = Proposal.model_validate(pdata)
                logger.debug(f"Cargadas {len(self._local_storage)} propuestas desde archivo")
            except Exception as e:
                logger.warning(f"Error cargando propuestas locales: {e}")
    
    def _save_local_storage(self) -> None:
        """Guarda propuestas a archivo local."""
        try:
            PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                pid: p.model_dump(mode="json")
                for pid, p in self._local_storage.items()
            }
            PROPOSALS_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Error guardando propuestas locales: {e}")
    
    async def _get_redis(self):
        """Obtiene conexión Redis (lazy loading)."""
        if not self._use_redis:
            return None
        
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,  # 2 segundos timeout
                )
                # Verificar conexión con ping
                await self._redis.ping()
                logger.info("Conectado a Redis")
            except ImportError:
                logger.warning("Módulo redis no instalado. Usando almacenamiento local.")
                self._use_redis = False
                return None
            except Exception as e:
                logger.warning(f"Redis no disponible: {e}. Usando almacenamiento local.")
                self._use_redis = False
                self._redis = None
                return None
        
        return self._redis
    
    async def close(self) -> None:
        """Cierra conexión Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    # ==================== Registro de Propuestas ====================
    
    async def register(self, proposal: Proposal) -> str:
        """
        Registra una nueva propuesta pendiente.
        
        Args:
            proposal: Propuesta a registrar
        
        Returns:
            ID de la propuesta
        """
        r = await self._get_redis()
        
        if r:
            # Usar Redis
            data = proposal.model_dump_json()
            
            # Guardar con TTL de 7 días
            key = f"proposal:{proposal.id}"
            await r.setex(key, timedelta(days=7), data)
            
            # Agregar a lista de pendientes
            await r.lpush("proposals:pending", str(proposal.id))
            
            # Agregar a lista del agente
            await r.lpush(f"proposals:agent:{proposal.agent_id}", str(proposal.id))
        else:
            # Usar almacenamiento local con persistencia
            self._local_storage[str(proposal.id)] = proposal
            self._save_local_storage()
        
        logger.info(f"Propuesta registrada: {proposal.short_id} - {proposal.title}")
        
        return str(proposal.id)
    
    async def get(self, proposal_id: str) -> Optional[Proposal]:
        """
        Obtiene una propuesta por ID (completo o parcial).
        
        Args:
            proposal_id: ID completo o primeros 8 caracteres
        
        Returns:
            Proposal o None si no existe
        """
        r = await self._get_redis()
        
        if r:
            # Buscar en Redis
            if len(proposal_id) < 36:
                # ID parcial, buscar
                keys = await r.keys(f"proposal:{proposal_id}*")
                if not keys:
                    return None
                key = keys[0]
            else:
                key = f"proposal:{proposal_id}"
            
            data = await r.get(key)
            
            if not data:
                return None
            
            return Proposal.model_validate_json(data)
        else:
            # Buscar en almacenamiento local
            if len(proposal_id) < 36:
                # ID parcial
                for pid, p in self._local_storage.items():
                    if pid.startswith(proposal_id):
                        return p
                return None
            else:
                return self._local_storage.get(proposal_id)
    
    async def get_pending(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Proposal]:
        """
        Obtiene propuestas pendientes.
        
        Args:
            agent_id: Filtrar por agente (opcional)
            limit: Máximo de resultados
        
        Returns:
            Lista de propuestas pendientes
        """
        r = await self._get_redis()
        
        if r:
            # Obtener IDs de Redis
            if agent_id:
                ids = await r.lrange(f"proposals:agent:{agent_id}", 0, limit - 1)
            else:
                ids = await r.lrange("proposals:pending", 0, limit - 1)
            
            # Obtener cada propuesta
            proposals = []
            for pid in ids:
                proposal = await self.get(pid)
                if proposal and proposal.status == ProposalStatus.PENDING:
                    proposals.append(proposal)
        else:
            # Filtrar de almacenamiento local
            proposals = [
                p for p in self._local_storage.values()
                if p.status == ProposalStatus.PENDING
                and (agent_id is None or p.agent_id == agent_id)
            ][:limit]
        
        # Ordenar por prioridad y fecha
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        
        proposals.sort(
            key=lambda p: (
                priority_order.get(p.priority, 2),
                p.created_at
            )
        )
        
        return proposals
    
    async def get_all(
        self,
        status: Optional[ProposalStatus] = None,
        limit: int = 100
    ) -> list[Proposal]:
        """Obtiene todas las propuestas, opcionalmente filtradas por estado."""
        r = await self._get_redis()
        
        if r:
            # Obtener todas las keys de propuestas
            keys = await r.keys("proposal:*")
            
            proposals = []
            for key in keys[:limit]:
                data = await r.get(key)
                if data:
                    proposal = Proposal.model_validate_json(data)
                    if status is None or proposal.status == status:
                        proposals.append(proposal)
        else:
            proposals = [
                p for p in self._local_storage.values()
                if status is None or p.status == status
            ][:limit]
        
        return proposals
    
    # ==================== Acciones ====================
    
    async def approve(
        self,
        proposal_id: str,
        approved_by: str = "admin",
        notes: Optional[str] = None
    ) -> Proposal:
        """
        Aprueba una propuesta.
        
        Args:
            proposal_id: ID de la propuesta
            approved_by: Quién aprobó
            notes: Notas opcionales
        
        Returns:
            Propuesta actualizada
        """
        proposal = await self.get(proposal_id)
        if not proposal:
            raise ApprovalEngineError(f"Propuesta no encontrada: {proposal_id}")
        
        if proposal.status != ProposalStatus.PENDING:
            raise ApprovalEngineError(f"Propuesta no está pendiente: {proposal.status}")
        
        # Actualizar
        proposal.approve(notes=notes, by=approved_by)
        
        await self._save(proposal)
        await self._remove_from_pending(proposal)
        
        logger.info(f"Propuesta aprobada: {proposal.short_id} por {approved_by}")
        
        # Disparar callback si existe
        await self._trigger_callback(proposal)
        
        return proposal
    
    async def reject(
        self,
        proposal_id: str,
        reason: str = "",
        rejected_by: str = "admin"
    ) -> Proposal:
        """
        Rechaza una propuesta.
        
        Args:
            proposal_id: ID de la propuesta
            reason: Razón del rechazo
            rejected_by: Quién rechazó
        
        Returns:
            Propuesta actualizada
        """
        proposal = await self.get(proposal_id)
        if not proposal:
            raise ApprovalEngineError(f"Propuesta no encontrada: {proposal_id}")
        
        if proposal.status != ProposalStatus.PENDING:
            raise ApprovalEngineError(f"Propuesta no está pendiente: {proposal.status}")
        
        # Actualizar
        proposal.reject(notes=reason, by=rejected_by)
        
        await self._save(proposal)
        await self._remove_from_pending(proposal)
        
        logger.info(f"Propuesta rechazada: {proposal.short_id} - {reason}")
        
        return proposal
    
    async def modify(
        self,
        proposal_id: str,
        modifications: dict[str, Any],
        modified_by: str = "admin"
    ) -> Proposal:
        """
        Modifica una propuesta antes de aprobarla.
        
        Args:
            proposal_id: ID de la propuesta
            modifications: Cambios a aplicar
            modified_by: Quién modificó
        
        Returns:
            Propuesta modificada (aún pendiente)
        """
        proposal = await self.get(proposal_id)
        if not proposal:
            raise ApprovalEngineError(f"Propuesta no encontrada: {proposal_id}")
        
        # Aplicar modificaciones
        if "payload" in modifications:
            proposal.payload.update(modifications["payload"])
        
        if "odoo_params" in modifications:
            proposal.odoo_params.update(modifications["odoo_params"])
        
        if "proposed_action_detail" in modifications:
            proposal.proposed_action_detail = modifications["proposed_action_detail"]
        
        proposal.status = ProposalStatus.MODIFIED
        proposal.reviewer_notes = f"Modificado por {modified_by}: {modifications}"
        
        await self._save(proposal)
        
        logger.info(f"Propuesta modificada: {proposal.short_id}")
        
        return proposal
    
    async def mark_executed(
        self,
        proposal_id: str,
        result: dict[str, Any]
    ) -> Proposal:
        """Marca una propuesta como ejecutada."""
        proposal = await self.get(proposal_id)
        if not proposal:
            raise ApprovalEngineError(f"Propuesta no encontrada: {proposal_id}")
        
        proposal.mark_completed(result)
        
        await self._save(proposal)
        
        logger.info(f"Propuesta ejecutada: {proposal.short_id}")
        
        return proposal
    
    async def mark_failed(
        self,
        proposal_id: str,
        error: str
    ) -> Proposal:
        """Marca una propuesta como fallida."""
        proposal = await self.get(proposal_id)
        if not proposal:
            raise ApprovalEngineError(f"Propuesta no encontrada: {proposal_id}")
        
        proposal.mark_failed(error)
        
        await self._save(proposal)
        
        logger.error(f"Propuesta falló: {proposal.short_id} - {error}")
        
        return proposal
    
    # ==================== Callbacks ====================
    
    def register_callback(
        self,
        agent_id: str,
        callback: Callable
    ) -> None:
        """
        Registra callback para cuando se apruebe una propuesta.
        
        Args:
            agent_id: ID del agente
            callback: Función async a llamar con la propuesta aprobada
        """
        self._callbacks[agent_id] = callback
        logger.debug(f"Callback registrado para agente: {agent_id}")
    
    async def _trigger_callback(self, proposal: Proposal) -> None:
        """Dispara callback del agente si existe."""
        if proposal.agent_id in self._callbacks:
            try:
                callback = self._callbacks[proposal.agent_id]
                await callback(proposal)
            except Exception as e:
                logger.error(f"Error en callback de {proposal.agent_id}: {e}")
    
    # ==================== Helpers ====================
    
    async def _save(self, proposal: Proposal) -> None:
        """Guarda propuesta."""
        r = await self._get_redis()
        
        if r:
            key = f"proposal:{proposal.id}"
            await r.setex(key, timedelta(days=7), proposal.model_dump_json())
        else:
            self._local_storage[str(proposal.id)] = proposal
            self._save_local_storage()
    
    async def _remove_from_pending(self, proposal: Proposal) -> None:
        """Remueve propuesta de listas de pendientes."""
        r = await self._get_redis()
        
        if r:
            await r.lrem("proposals:pending", 0, str(proposal.id))
            await r.lrem(f"proposals:agent:{proposal.agent_id}", 0, str(proposal.id))
    
    async def get_stats(self) -> dict[str, int]:
        """Obtiene estadísticas de propuestas."""
        all_proposals = await self.get_all()
        
        stats = {
            "total": len(all_proposals),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "completed": 0,
            "failed": 0,
        }
        
        for p in all_proposals:
            status_key = p.status.value
            if status_key in stats:
                stats[status_key] += 1
        
        return stats


# Singleton global
approval_engine = ApprovalEngine()
