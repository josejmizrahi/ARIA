"""
Inspector Contextual del Sistema.

Analiza salud del sistema en 4 niveles:
1. Vista general: Conexiones, crons, usuarios
2. Por categorías: Por módulo, tipo de error
3. Detalles: Crons fallidos, usuarios sin actividad
4. Anomalías: Permisos incorrectos, secuencias con huecos
"""

from datetime import datetime, timedelta

from .context_inspector import BaseContextInspector
from .models import (
    AgentDependency,
    AreaContext,
    ImpactLevel,
    ImpactType,
)


class SystemInspector(BaseContextInspector):
    """Inspector contextual para Salud del Sistema."""
    
    AGENT_NAME = "sistema"
    AREA_NAME = "Salud del Sistema"
    
    # Sistema es transversal - todos dependen de él
    UPSTREAM_DEPENDENCIES = []
    
    DOWNSTREAM_DEPENDENCIES = [
        AgentDependency(
            agent_name="*",  # Todos los agentes
            dependency_type="downstream",
            data_flow="Funcionamiento del sistema",
            criticality=ImpactLevel.CRITICAL,
            description="Todos los agentes dependen del sistema"
        ),
    ]
    
    def __init__(self) -> None:
        super().__init__()
    
    def _get_area_context(self) -> AreaContext:
        """Obtiene contexto de salud del sistema."""
        
        # Verificar conexión a Odoo
        try:
            user_count = self._search_count("res.users", [("active", "=", True)])
            connection_ok = True
        except Exception:
            user_count = 0
            connection_ok = False
        
        # Crons activos
        cron_count = self._search_count("ir.cron", [("active", "=", True)])
        
        health = 100 if connection_ok else 0
        
        return AreaContext(
            area_name=self.AREA_NAME,
            total_records=user_count,
            total_value=0,
            health_score=health,
            status="healthy" if connection_ok else "critical",
            summary={
                "connection": "ok" if connection_ok else "failed",
                "active_users": user_count,
                "active_crons": cron_count,
            }
        )
    
    def _inspect_level_1_overview(self) -> None:
        """Nivel 1: Estado general del sistema."""
        
        summary = self._context.summary if self._context else {}
        
        # Conexión a Odoo
        connection = summary.get("connection", "unknown")
        
        if connection == "ok":
            self._add_finding(
                level=1,
                category="Conexión",
                title="✅ Conexión a Odoo: OK",
                description="El sistema puede comunicarse con Odoo correctamente",
                severity=ImpactLevel.INFO,
            )
        else:
            self._add_finding(
                level=1,
                category="Conexión",
                title="🔴 Error de conexión a Odoo",
                description="No se puede conectar al servidor de Odoo",
                severity=ImpactLevel.CRITICAL,
                impacts=[
                    self._blocks_agent(
                        "*",
                        "Sin conexión a Odoo",
                        "Ningún agente puede funcionar",
                        "Verificar configuración y servidor"
                    )
                ],
                solution="Verificar URL, credenciales y estado del servidor Odoo"
            )
            return  # No continuar si no hay conexión
        
        # Usuarios activos
        users = summary.get("active_users", 0)
        crons = summary.get("active_crons", 0)
        
        self._add_finding(
            level=1,
            category="Sistema",
            title=f"Usuarios activos: {users} | Crons activos: {crons}",
            description="Estado general del sistema Odoo",
            severity=ImpactLevel.INFO,
        )
    
    def _inspect_level_2_categories(self) -> None:
        """Nivel 2: Por módulo y tipo."""
        
        # Crons por estado
        crons = self._search_read(
            "ir.cron",
            [],
            ["name", "active", "nextcall"],  # numbercall removed in Odoo 19
            limit=200
        )
        
        active = [c for c in crons if c.get("active")]
        inactive = [c for c in crons if not c.get("active")]
        
        self._add_finding(
            level=2,
            category="Crons",
            title=f"Tareas programadas: {len(active)} activas, {len(inactive)} inactivas",
            description="Estado de tareas programadas en Odoo",
            severity=ImpactLevel.INFO,
            sample_data=[
                {"name": c.get("name"), "next": c.get("nextcall")}
                for c in sorted(active, key=lambda x: x.get("nextcall") or "")[:10]
            ],
        )
        
        # Usuarios por tipo
        users = self._search_read(
            "res.users",
            [("active", "=", True)],
            ["login", "share"],
            limit=500
        )
        
        internal = len([u for u in users if not u.get("share")])
        portal = len([u for u in users if u.get("share")])
        
        self._add_finding(
            level=2,
            category="Usuarios",
            title=f"Usuarios: {internal} internos, {portal} portal",
            description="Distribución de usuarios por tipo",
            severity=ImpactLevel.INFO,
        )
    
    def _inspect_level_3_details(self) -> None:
        """Nivel 3: Detalles específicos."""
        
        # Crons que no se han ejecutado recientemente
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        
        stale_crons = self._search_read(
            "ir.cron",
            [
                ("active", "=", True),
                ("lastcall", "<", week_ago),
            ],
            ["name", "lastcall", "nextcall"],
            limit=50
        )
        
        if stale_crons:
            self._add_finding(
                level=3,
                category="Crons Inactivos",
                title=f"⚠️ {len(stale_crons)} crons sin ejecutar > 7 días",
                description="Tareas programadas que no se han ejecutado recientemente",
                severity=ImpactLevel.MEDIUM,
                affected_records=len(stale_crons),
                sample_data=[
                    {
                        "name": c.get("name"),
                        "last_run": c.get("lastcall"),
                        "next_run": c.get("nextcall"),
                    }
                    for c in stale_crons[:10]
                ],
                solution="Verificar si los crons deben estar activos"
            )
        
        # Usuarios sin login reciente
        if self._model_exists("res.users.log"):
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Esto es una aproximación - depende de cómo Odoo registra logins
            all_users = self._search_read(
                "res.users",
                [("active", "=", True), ("share", "=", False)],
                ["login", "login_date"],
                limit=200
            )
            
            inactive_users = [
                u for u in all_users
                if not u.get("login_date") or str(u.get("login_date"))[:10] < month_ago
            ]
            
            if len(inactive_users) > 5:
                self._add_finding(
                    level=3,
                    category="Usuarios Inactivos",
                    title=f"{len(inactive_users)} usuarios sin login > 30 días",
                    description="Usuarios internos que no han ingresado recientemente",
                    severity=ImpactLevel.LOW,
                    affected_records=len(inactive_users),
                    sample_data=[
                        {"user": u.get("login"), "last_login": u.get("login_date")}
                        for u in inactive_users[:10]
                    ],
                    solution="Revisar si deben desactivarse"
                )
    
    def _inspect_level_4_anomalies(self) -> None:
        """Nivel 4: Errores e inconsistencias."""
        
        # Verificar modelos críticos
        critical_models = [
            "res.partner",
            "product.product",
            "account.move",
            "sale.order",
            "purchase.order",
        ]
        
        missing_models = []
        for model in critical_models:
            if not self._model_exists(model):
                missing_models.append(model)
        
        if missing_models:
            self._add_finding(
                level=4,
                category="Modelos",
                title=f"🔴 {len(missing_models)} modelos críticos no encontrados",
                description=f"Modelos: {', '.join(missing_models)}",
                severity=ImpactLevel.CRITICAL,
                affected_records=len(missing_models),
                solution="Verificar instalación de módulos"
            )
        
        # Verificar secuencias (si tienen huecos puede indicar problemas)
        sequences = self._search_read(
            "ir.sequence",
            [("use_date_range", "=", False)],
            ["name", "number_next_actual", "number_increment"],
            limit=50
        )
        
        # Buscar secuencias con number_next muy alto o irregular
        suspicious_sequences = [
            s for s in sequences
            if s.get("number_next_actual", 0) > 100000
        ]
        
        if suspicious_sequences:
            self._add_finding(
                level=4,
                category="Secuencias",
                title=f"ℹ️ {len(suspicious_sequences)} secuencias con numeración alta",
                description="Secuencias que pueden tener huecos o uso intensivo",
                severity=ImpactLevel.INFO,
                affected_records=len(suspicious_sequences),
                sample_data=[
                    {"name": s.get("name"), "next": s.get("number_next_actual")}
                    for s in suspicious_sequences[:10]
                ],
            )
        
        # Verificar configuración de compañía
        company = self._search_read(
            "res.company",
            [("id", "=", self.company_id)],
            ["name", "currency_id", "partner_id"],
            limit=1
        )
        
        if not company:
            self._add_finding(
                level=4,
                category="Configuración",
                title=f"🔴 Compañía ID={self.company_id} no encontrada",
                description="La compañía configurada no existe",
                severity=ImpactLevel.CRITICAL,
                solution="Verificar ODOO_COMPANY_ID en .env"
            )
        elif company:
            comp = company[0]
            if not comp.get("currency_id"):
                self._add_finding(
                    level=4,
                    category="Configuración",
                    title="⚠️ Compañía sin moneda configurada",
                    description="La moneda de la compañía no está definida",
                    severity=ImpactLevel.HIGH,
                    solution="Configurar moneda en la compañía"
                )
