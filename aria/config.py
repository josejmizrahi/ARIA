"""
ARIA - Sistema de Configuración
================================

Configuración centralizada usando Pydantic Settings.
Soporta variables de entorno y archivos .env
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Entornos de ejecución disponibles."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Niveles de log disponibles."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class NotificationChannel(str, Enum):
    """Canales de notificación disponibles."""
    CONSOLE = "console"
    TELEGRAM = "telegram"
    SLACK = "slack"
    EMAIL = "email"
    WEBSOCKET = "websocket"


class OdooSettings(BaseSettings):
    """Configuración de conexión a Odoo."""
    
    model_config = SettingsConfigDict(
        env_prefix="ODOO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    url: str = Field(
        default="http://localhost:8069",
        description="URL del servidor Odoo"
    )
    db: str = Field(
        default="odoo",
        description="Nombre de la base de datos"
    )
    user: str = Field(
        default="admin",
        description="Usuario de Odoo"
    )
    password: str = Field(
        default="admin",
        description="Contraseña de Odoo"
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout de conexión en segundos"
    )
    company_id: int = Field(
        default=1,
        ge=1,
        description="ID de la compañía en Odoo"
    )
    default_currency: str = Field(
        default="MXN",
        description="Divisa por defecto para reportes"
    )
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Valida y normaliza la URL de Odoo."""
        v = v.rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL debe comenzar con http:// o https://")
        return v


class TelegramSettings(BaseSettings):
    """Configuración de Telegram."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    bot_token: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_BOT_TOKEN",
        description="Token del bot de Telegram"
    )
    admin_chat_id: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_ADMIN_CHAT_ID",
        description="Chat ID del administrador"
    )
    
    @property
    def enabled(self) -> bool:
        """Indica si Telegram está configurado."""
        return bool(self.bot_token and self.admin_chat_id)


class EmailSettings(BaseSettings):
    """Configuración de Email."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: Optional[str] = Field(default=None, alias="SMTP_FROM")
    admin_email: Optional[str] = Field(
        default=None,
        alias="ADMIN_EMAIL",
        description="Email del administrador"
    )
    
    @property
    def enabled(self) -> bool:
        """Indica si Email está configurado."""
        return bool(self.smtp_host and self.smtp_user and self.admin_email)


class RedisSettings(BaseSettings):
    """Configuración de Redis."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        description="URL de conexión a Redis"
    )
    
    @property
    def enabled(self) -> bool:
        """Indica si Redis está configurado."""
        return bool(self.url)


class NotificationSettings(BaseSettings):
    """Configuración de notificaciones."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    default_channel: NotificationChannel = Field(
        default=NotificationChannel.CONSOLE,
        alias="NOTIFICATION_CHANNEL"
    )
    
    # Sub-configuraciones
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    
    @property
    def telegram_enabled(self) -> bool:
        return self.telegram.enabled
    
    @property
    def email_enabled(self) -> bool:
        return self.email.enabled


class FinanceBudgetSettings(BaseSettings):
    """Configuración de presupuestos financieros."""
    
    model_config = SettingsConfigDict(
        env_prefix="FINANCE_BUDGET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    monthly_revenue: float = Field(
        default=24_500_000,
        ge=0,
        description="Presupuesto mensual de ingresos"
    )
    monthly_expenses: float = Field(
        default=17_150_000,
        ge=0,
        description="Presupuesto mensual de gastos (70% de ingresos por defecto)"
    )
    
    # Presupuestos por categoría (opcional, formato JSON en env)
    # Ejemplo: FINANCE_BUDGET_BY_CATEGORY='{"Ventas": 20000000, "Marketing": 2000000, "Operaciones": 5000000}'
    by_category: Optional[str] = Field(
        default=None,
        description="Presupuestos por categoría en formato JSON"
    )
    
    def get_category_budgets(self) -> dict[str, float]:
        """Retorna presupuestos por categoría como diccionario."""
        if not self.by_category:
            return {}
        try:
            import json
            return json.loads(self.by_category)
        except Exception:
            return {}


class AgentSettings(BaseSettings):
    """Configuración de agentes."""
    
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Número máximo de reintentos"
    )
    retry_delay: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Delay entre reintentos en segundos"
    )
    approval_timeout_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Timeout para aprobaciones en horas"
    )


class Settings(BaseSettings):
    """
    Configuración principal de ARIA.
    
    Carga configuración desde:
    1. Variables de entorno
    2. Archivo .env (si existe)
    
    Uso:
        from aria.config import settings
        print(settings.odoo.url)
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )
    
    # Configuración general
    env: Environment = Field(
        default=Environment.DEVELOPMENT,
        alias="ARIA_ENV"
    )
    debug: bool = Field(
        default=False,
        alias="ARIA_DEBUG"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        alias="ARIA_LOG_LEVEL"
    )
    log_dir: Path = Field(
        default=Path("./logs"),
        alias="ARIA_LOG_DIR"
    )
    
    # Sub-configuraciones
    odoo: OdooSettings = Field(default_factory=OdooSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    finance_budget: FinanceBudgetSettings = Field(default_factory=FinanceBudgetSettings)
    
    # Accesos directos para compatibilidad
    @property
    def telegram_enabled(self) -> bool:
        """Indica si Telegram está habilitado."""
        return self.notifications.telegram_enabled
    
    @property
    def telegram_bot_token(self) -> Optional[str]:
        """Token del bot de Telegram."""
        return self.notifications.telegram.bot_token
    
    @property
    def telegram_admin_chat_id(self) -> Optional[str]:
        """Chat ID del administrador."""
        return self.notifications.telegram.admin_chat_id
    
    @property
    def email_enabled(self) -> bool:
        """Indica si Email está habilitado."""
        return self.notifications.email_enabled
    
    @property
    def redis_url(self) -> str:
        """URL de Redis."""
        return self.redis.url
    
    @property
    def is_production(self) -> bool:
        """Indica si está en modo producción."""
        return self.env == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Indica si está en modo desarrollo."""
        return self.env == Environment.DEVELOPMENT
    
    def get_log_file_path(self) -> Path:
        """Retorna la ruta del archivo de log."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        return self.log_dir / "aria.log"


@lru_cache
def get_settings() -> Settings:
    """
    Factory function para obtener configuración (singleton).
    
    Returns:
        Settings: Instancia de configuración cacheada.
    """
    return Settings()


# Instancia global de configuración
settings = get_settings()
