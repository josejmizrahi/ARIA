"""
ARIA - Registro de Agentes
===========================

Registro central de agentes de ARIA.

Permite:
- Registrar agentes dinámicamente
- Obtener agentes por nombre
- Iniciar/detener todos los agentes
- Listar agentes disponibles
"""

from typing import Optional

from aria.utils.logger import get_logger

logger = get_logger("aria.agents.registry")


class AgentRegistry:
    """
    Registro singleton de todos los agentes del sistema.
    
    Uso:
        from aria.agents.registry import agent_registry
        
        # Registrar un agente
        agent_registry.register(MyAgent())
        
        # Obtener agente
        agent = agent_registry.get("mi_agente")
        
        # Listar todos
        agents = agent_registry.list_all()
        
        # Iniciar todos
        await agent_registry.start_all()
    """
    
    _instance: Optional["AgentRegistry"] = None
    
    def __new__(cls) -> "AgentRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._agents: dict[str, "BaseAgent"] = {}
        self._initialized = True
        logger.info("AgentRegistry inicializado")
    
    def register(self, agent: "BaseAgent") -> None:
        """
        Registra un agente en el sistema.
        
        Args:
            agent: Instancia del agente a registrar
        """
        if agent.name in self._agents:
            logger.warning(f"Agente {agent.name} ya registrado, reemplazando")
        
        self._agents[agent.name] = agent
        logger.info(f"Agente registrado: {agent.name}")
    
    def unregister(self, name: str) -> Optional["BaseAgent"]:
        """
        Elimina un agente del registro.
        
        Args:
            name: Nombre del agente
        
        Returns:
            Agente eliminado o None
        """
        agent = self._agents.pop(name, None)
        if agent:
            logger.info(f"Agente eliminado: {name}")
        return agent
    
    def get(self, name: str) -> Optional["BaseAgent"]:
        """
        Obtiene un agente por nombre.
        
        Args:
            name: Nombre del agente
        
        Returns:
            Agente o None si no existe
        """
        return self._agents.get(name)
    
    def list_all(self) -> dict[str, "BaseAgent"]:
        """Retorna diccionario de todos los agentes registrados (nombre -> agente)."""
        return dict(self._agents)
    
    def list_agents(self) -> list["BaseAgent"]:
        """Retorna lista de todos los agentes registrados."""
        return list(self._agents.values())
    
    def list_names(self) -> list[str]:
        """Retorna lista de nombres de agentes."""
        return list(self._agents.keys())
    
    async def start_all(self) -> None:
        """Inicia todos los agentes registrados."""
        logger.info(f"Iniciando {len(self._agents)} agentes...")
        
        for agent in self._agents.values():
            await agent.start()
        
        logger.info("Todos los agentes iniciados")
    
    async def stop_all(self) -> None:
        """Detiene todos los agentes."""
        logger.info("Deteniendo agentes...")
        
        for agent in self._agents.values():
            await agent.stop()
        
        logger.info("Todos los agentes detenidos")
    
    def get_status(self) -> dict[str, dict]:
        """Retorna estado de todos los agentes."""
        return {
            name: agent.get_info()
            for name, agent in self._agents.items()
        }
    
    async def get_all_summaries(self, exclude: list[str] | None = None) -> dict[str, dict]:
        """
        Obtiene resumen de estado de todos los agentes.
        
        Args:
            exclude: Lista de nombres de agentes a excluir (para evitar recursión)
        """
        exclude = exclude or []
        summaries = {}
        
        for name, agent in self._agents.items():
            if name in exclude:
                continue
            try:
                summaries[name] = await agent.get_status_summary()
            except Exception as e:
                summaries[name] = {"error": str(e), "status": "error"}
        
        return summaries
    
    def clear(self) -> None:
        """Limpia todos los agentes registrados."""
        self._agents.clear()
        logger.info("Registry limpiado")


# Singleton global
agent_registry = AgentRegistry()


def register_agent(agent: "BaseAgent") -> None:
    """Atajo para registrar un agente."""
    agent_registry.register(agent)


def get_agent(name: str) -> Optional["BaseAgent"]:
    """Atajo para obtener un agente."""
    return agent_registry.get(name)


# Importar BaseAgent para type hints
from aria.agents.base import BaseAgent  # noqa: E402
