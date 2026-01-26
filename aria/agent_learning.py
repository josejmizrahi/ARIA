"""
Sistema de Aprendizaje para Agentes.

Los agentes aprenden de:
- Logs de ejecuciones anteriores
- Errores y soluciones exitosas
- Patrones en los datos
- Decisiones tomadas anteriormente
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

from pydantic import BaseModel, Field

from aria.config import settings
from aria.utils.logger import get_logger

logger = get_logger("aria.agent_learning")


class LearningPattern(BaseModel):
    """Patrón aprendido por un agente."""
    
    pattern_type: str  # "field_mapping", "error_solution", "data_pattern"
    agent_name: str
    context: dict[str, Any]
    solution: dict[str, Any]
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class AgentLearning:
    """Sistema de aprendizaje para agentes."""
    
    def __init__(self):
        self.learning_file = Path(settings.log_dir) / "agent_learning.json"
        self.patterns: dict[str, list[LearningPattern]] = defaultdict(list)
        self._load_learning()
    
    def _load_learning(self) -> None:
        """Carga patrones aprendidos."""
        if self.learning_file.exists():
            try:
                with open(self.learning_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for agent_name, patterns_data in data.get("patterns", {}).items():
                        self.patterns[agent_name] = [
                            LearningPattern(**p) for p in patterns_data
                        ]
            except Exception as e:
                logger.warning(f"Error cargando aprendizaje: {e}")
    
    def _save_learning(self) -> None:
        """Guarda patrones aprendidos."""
        try:
            self.learning_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.learning_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "patterns": {
                        agent: [p.model_dump() for p in patterns]
                        for agent, patterns in self.patterns.items()
                    },
                    "last_updated": datetime.now().isoformat(),
                }, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Error guardando aprendizaje: {e}")
    
    def learn_from_logs(self, agent_name: str, log_file: Path) -> None:
        """
        Aprende de los logs de un agente.
        
        Extrae:
        - Errores comunes y sus soluciones
        - Campos que no existen y alternativas
        - Patrones de datos exitosos
        """
        if not log_file.exists():
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = f.read()
            
            # Buscar errores de campos
            field_errors = re.findall(
                r"Campo ['\"]([\w_]+)['\"] no existe|Field ['\"](\w+)['\"] does not exist",
                logs,
                re.IGNORECASE
            )
            
            for error_match in field_errors:
                field_name = error_match[0] or error_match[1]
                # Buscar si hay sugerencias en el log
                suggestion_match = re.search(
                    rf"Campo '{field_name}'.*?Sugerencia: usar '(\w+)'",
                    logs,
                    re.IGNORECASE
                )
                
                if suggestion_match:
                    suggestion = suggestion_match.group(1)
                    self.add_pattern(
                        agent_name=agent_name,
                        pattern_type="field_mapping",
                        context={"field": field_name},
                        solution={"use_field": suggestion},
                    )
            
            # Buscar soluciones exitosas
            success_patterns = re.findall(
                r"Usando solo campos válidos: \[(.*?)\]",
                logs,
            )
            
            for pattern in success_patterns:
                fields = [f.strip().strip("'\"") for f in pattern.split(",")]
                self.add_pattern(
                    agent_name=agent_name,
                    pattern_type="valid_fields",
                    context={"model": "unknown"},
                    solution={"valid_fields": fields},
                )
                
        except Exception as e:
            logger.warning(f"Error aprendiendo de logs de {agent_name}: {e}")
    
    def add_pattern(
        self,
        agent_name: str,
        pattern_type: str,
        context: dict[str, Any],
        solution: dict[str, Any],
    ) -> None:
        """Agrega un patrón aprendido."""
        # Buscar si ya existe un patrón similar
        existing = self.find_similar_pattern(agent_name, pattern_type, context)
        
        if existing:
            existing.success_count += 1
            existing.last_used = datetime.now()
        else:
            pattern = LearningPattern(
                pattern_type=pattern_type,
                agent_name=agent_name,
                context=context,
                solution=solution,
                success_count=1,
            )
            self.patterns[agent_name].append(pattern)
        
        self._save_learning()
    
    def find_similar_pattern(
        self,
        agent_name: str,
        pattern_type: str,
        context: dict[str, Any],
    ) -> Optional[LearningPattern]:
        """Encuentra un patrón similar."""
        for pattern in self.patterns.get(agent_name, []):
            if pattern.pattern_type != pattern_type:
                continue
            
            # Comparar contexto (simplificado)
            if pattern.context.get("field") == context.get("field"):
                return pattern
            if pattern.context.get("model") == context.get("model"):
                return pattern
        
        return None
    
    def get_solution(
        self,
        agent_name: str,
        problem_type: str,
        context: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Obtiene una solución aprendida para un problema."""
        pattern = self.find_similar_pattern(agent_name, problem_type, context)
        
        if pattern and pattern.success_count > pattern.failure_count:
            return pattern.solution
        
        return None
    
    def record_success(self, agent_name: str, pattern_type: str, context: dict) -> None:
        """Registra un éxito usando un patrón."""
        pattern = self.find_similar_pattern(agent_name, pattern_type, context)
        if pattern:
            pattern.success_count += 1
            pattern.last_used = datetime.now()
            self._save_learning()
    
    def record_failure(self, agent_name: str, pattern_type: str, context: dict) -> None:
        """Registra un fracaso usando un patrón."""
        pattern = self.find_similar_pattern(agent_name, pattern_type, context)
        if pattern:
            pattern.failure_count += 1
            self._save_learning()


# Instancia global
_agent_learning: Optional[AgentLearning] = None


def get_learning() -> AgentLearning:
    """Obtiene la instancia global del sistema de aprendizaje."""
    global _agent_learning
    if _agent_learning is None:
        _agent_learning = AgentLearning()
    return _agent_learning
