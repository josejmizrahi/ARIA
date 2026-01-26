"""
Tests para el módulo de configuración.
"""

import pytest

from aria.config import (
    Environment,
    LogLevel,
    NotificationChannel,
    OdooSettings,
    Settings,
    get_settings,
)


class TestOdooSettings:
    """Tests para OdooSettings."""
    
    def test_default_values(self):
        """Verifica valores por defecto."""
        settings = OdooSettings()
        assert settings.url == "http://localhost:8069"
        assert settings.db == "odoo"
        assert settings.user == "admin"
        assert settings.timeout == 30
    
    def test_url_validation_strips_trailing_slash(self):
        """La URL debe normalizar slashes finales."""
        settings = OdooSettings(url="http://localhost:8069/")
        assert settings.url == "http://localhost:8069"
    
    def test_url_validation_requires_protocol(self):
        """La URL debe tener protocolo http/https."""
        with pytest.raises(ValueError, match="http://"):
            OdooSettings(url="localhost:8069")


class TestSettings:
    """Tests para Settings principal."""
    
    def test_default_environment(self):
        """Entorno por defecto es development."""
        settings = Settings()
        assert settings.env == Environment.DEVELOPMENT
        assert settings.is_development
        assert not settings.is_production
    
    def test_log_level_default(self):
        """Nivel de log por defecto es INFO."""
        settings = Settings()
        assert settings.log_level == LogLevel.INFO
    
    def test_has_odoo_settings(self):
        """Debe incluir configuración de Odoo."""
        settings = Settings()
        assert hasattr(settings, "odoo")
        assert isinstance(settings.odoo, OdooSettings)
    
    def test_get_settings_returns_cached(self):
        """get_settings debe retornar instancia cacheada."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestEnums:
    """Tests para enumeraciones."""
    
    def test_environment_values(self):
        """Verifica valores de Environment."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
    
    def test_notification_channel_values(self):
        """Verifica canales de notificación."""
        assert NotificationChannel.CONSOLE.value == "console"
        assert NotificationChannel.TELEGRAM.value == "telegram"
        assert NotificationChannel.SLACK.value == "slack"
        assert NotificationChannel.EMAIL.value == "email"
