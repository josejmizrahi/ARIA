# 🤖 ARIA - Autonomous Resource Intelligence Agent

Sistema de agentes autónomos para gestión inteligente de Odoo ERP.

## 📋 Descripción

ARIA es un framework de agentes de IA que supervisan y optimizan operaciones de ERP Odoo, proponiendo acciones al humano para su aprobación antes de ejecutarlas.

### Características Principales

- 🔍 **Análisis Inteligente**: Los agentes analizan datos del ERP continuamente
- 📋 **Sistema de Propuestas**: Las acciones requieren aprobación humana
- 🔔 **Notificaciones Multi-canal**: Telegram, Email, Console
- 🤖 **Bot de Telegram**: Aprueba/rechaza con comandos o botones
- 🗄️ **Almacenamiento Redis**: Propuestas persistentes
- 🛡️ **Seguridad First**: Nada se ejecuta sin aprobación explícita
- 📊 **Logging Estructurado**: Trazabilidad completa de operaciones
- ⏰ **Scheduler Integrado**: Tareas programadas con cron expressions
- 🏢 **8 Agentes Especializados**: CEO, Cobranza, Ventas, Compras, Finanzas, Contabilidad, Inventario, RRHH
- 🌐 **Dashboard Web**: React + Vite + Tailwind CSS
- 📄 **Reportes PDF**: Generación automática con WeasyPrint

## 🚀 Instalación

### Requisitos

- Python 3.11+
- Redis (para almacenamiento de propuestas)
- Acceso a servidor Odoo
- (Opcional) Bot de Telegram para notificaciones

### Instalación Rápida

```bash
# Clonar repositorio
git clone https://github.com/tu-org/aria.git
cd aria

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -e .

# O para desarrollo:
pip install -e ".[dev]"
```

### Iniciar Redis

```bash
# Con Docker
cd docker
docker-compose -f docker-compose.dev.yml up -d

# Verificar
docker-compose -f docker-compose.dev.yml ps
```

### Configuración

1. Copia el archivo de configuración de ejemplo:

```bash
cp env.example .env
```

2. Edita `.env` con tus credenciales:

```env
# Odoo Connection
ODOO_URL=http://tu-servidor-odoo:8069
ODOO_DB=nombre_base_datos
ODOO_USER=usuario
ODOO_PASSWORD=contraseña

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot (opcional pero recomendado)
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_ADMIN_CHAT_ID=tu_chat_id

# ARIA Settings
ARIA_ENV=development
ARIA_DEBUG=true
ARIA_LOG_LEVEL=INFO
```

### Configurar Telegram Bot

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram
2. Crea un nuevo bot: `/newbot`
3. Copia el token al `.env` como `TELEGRAM_BOT_TOKEN`
4. Envía cualquier mensaje a tu nuevo bot
5. Visita: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Busca `"chat":{"id":` y copia el número al `.env` como `TELEGRAM_ADMIN_CHAT_ID`

## 🎯 Uso

### Comandos CLI

```bash
# Ver versión
aria version

# Verificar configuración y conexión
aria check
aria check --verbose

# Explorar estructura del ERP
aria introspect --all              # Listar todos los modelos
aria introspect --model res.partner # Ver detalles de un modelo

# ===== Agentes =====
aria agent list                    # Listar agentes disponibles
aria agent info cobranza           # Ver detalles de un agente
aria agent run cobranza            # Ejecutar todas las tareas del agente
aria agent run cobranza -t check_overdue  # Ejecutar tarea específica
aria agent run cobranza --dry-run  # Simular sin ejecutar
aria agent status                  # Ver estado de todos los agentes

# ===== Scheduler =====
aria scheduler list                # Ver tareas programadas
aria scheduler run cobranza aging_analysis  # Ejecutar tarea manualmente

# ===== Propuestas =====
aria proposal list                 # Listar propuestas pendientes
aria proposal list --status approved  # Filtrar por estado
aria proposal show abc123          # Ver detalles de propuesta
aria proposal approve abc123       # Aprobar y ejecutar
aria proposal approve abc123 --no-execute  # Solo aprobar
aria proposal reject abc123 -r "No autorizado"  # Rechazar
aria proposal stats                # Ver estadísticas

# ===== Servicios =====
aria serve                         # Iniciar ARIA con scheduler
aria serve --no-scheduler          # Sin scheduler
aria bot                           # Iniciar bot de Telegram
```

### Bot de Telegram

Una vez iniciado el bot (`aria bot`), puedes usar estos comandos:

```
/start              - Mensaje de bienvenida
/help               - Ver comandos disponibles
/status             - Estado del sistema
/pending            - Propuestas pendientes
/aprobar <id>       - Aprobar propuesta
/rechazar <id> [razón] - Rechazar propuesta
/detalles <id>      - Ver detalles de propuesta
```

También puedes usar los **botones inline** que aparecen en las notificaciones de propuestas.

## 🤖 Agentes Disponibles

### CEO Agent (ceo)
Vista ejecutiva consolidada del negocio.

**Tareas:**
| Tarea | Schedule | Descripción |
|-------|----------|-------------|
| `daily_dashboard` | 7:00 AM | Dashboard ejecutivo diario |
| `critical_alerts` | Cada 30 min | Alertas críticas pendientes |
| `weekly_report` | Lunes 8:00 AM | Reporte semanal |
| `budget_comparison` | Día 1 del mes | Comparativo vs presupuesto |

### Receivables Agent (cobranza)
Gestión de cuentas por cobrar y recuperación de cartera.

**Tareas:**
| Tarea | Schedule | Descripción |
|-------|----------|-------------|
| `check_overdue` | 8:00 AM | Facturas vencidas y escalamiento |
| `aging_analysis` | Lunes 9:00 AM | Análisis de antigüedad |
| `payment_patterns` | Lunes 10:00 AM | Patrones de pago deteriorados |
| `credit_limits` | Cada 4 horas | Verificar límites de crédito |
| `project_collections` | Viernes 8:00 AM | Proyección de cobranza semanal |

### Sales Agent (ventas)
Gestión comercial y seguimiento de clientes.

**Tareas:**
| Tarea | Schedule | Descripción |
|-------|----------|-------------|
| `check_new_orders` | Cada 2 horas | Pedidos nuevos e inusuales |
| `inactive_customers` | Lunes 9:00 AM | Clientes inactivos |
| `profitability_analysis` | Día 1 del mes | Rentabilidad por cliente |
| `sales_concentration` | Día 1 del mes | Alertar concentración de ventas |
| `weekly_summary` | Viernes 5:00 PM | Resumen semanal de ventas |

## 📊 Uso Programático

### Crear un nuevo agente

```python
from aria.agents import BaseAgent
from aria.models import Priority
from aria.models.task import TaskDefinition, TaskResult

class PurchaseAgent(BaseAgent):
    """Agente de compras."""
    
    def __init__(self):
        super().__init__(
            name="compras",
            description="Gestión de órdenes de compra"
        )
    
    def _register_tasks(self):
        self.register_task(TaskDefinition(
            name="check_pending_orders",
            method="check_pending_orders",
            schedule="0 9 * * *",  # 9:00 AM diario
            description="Revisa órdenes de compra pendientes"
        ))
    
    async def check_pending_orders(self) -> TaskResult:
        # Buscar órdenes pendientes
        orders = self.search_read(
            "purchase.order",
            [("state", "=", "draft")],
            ["name", "partner_id", "amount_total"]
        )
        
        if orders:
            # Crear propuesta
            await self.propose(
                title=f"{len(orders)} órdenes pendientes de aprobar",
                description="Órdenes de compra en borrador",
                priority=Priority.MEDIUM,
                supporting_data={"orders": orders},
            )
        
        return TaskResult(
            task_name="check_pending_orders",
            agent_name=self.name,
            success=True,
            records_processed=len(orders)
        )
    
    async def get_status_summary(self):
        return {
            "status": "ok",
            "pending_orders": self.search_count(
                "purchase.order", 
                [("state", "=", "draft")]
            ),
        }
```

### Registrar y ejecutar agente

```python
import asyncio
from aria.agents import register_agent, agent_registry, initialize_all_agents

async def main():
    # Inicializar agentes existentes
    initialize_all_agents()
    
    # Registrar nuevo agente
    from my_agents import PurchaseAgent
    register_agent(PurchaseAgent())
    
    # Iniciar todos
    await agent_registry.start_all()
    
    # Ejecutar tarea específica
    agent = agent_registry.get("compras")
    result = await agent.run_task(agent.get_task("check_pending_orders"))
    
    print(f"Resultado: {result.success}")

asyncio.run(main())
```

## 🏗️ Arquitectura

```
ARIA/
├── aria/
│   ├── __init__.py              # Package principal (v0.2.0)
│   ├── config.py                # Configuración (Pydantic Settings)
│   ├── cli.py                   # CLI (Typer)
│   ├── odoo_client.py           # Cliente Odoo (XML-RPC)
│   ├── notification_manager.py  # Notificaciones multicanal
│   ├── approval_engine.py       # Motor de aprobaciones (Redis)
│   ├── action_executor.py       # Ejecutor de acciones
│   ├── telegram_bot.py          # Bot de Telegram
│   ├── scheduler.py             # Programador de tareas (APScheduler)
│   ├── models/                  # Modelos de datos
│   │   ├── proposal.py          # Propuestas de acción
│   │   ├── task.py              # Tareas de agentes
│   │   └── notification.py      # Notificaciones
│   ├── utils/
│   │   └── logger.py            # Logging estructurado
│   └── agents/                  # Agentes especializados
│       ├── base.py              # Clase base de agentes
│       ├── registry.py          # Registro de agentes
│       ├── ceo_agent.py         # Agente CEO
│       ├── receivables_agent.py # Agente de Cobranza
│       └── sales_agent.py       # Agente de Ventas
├── scripts/
│   ├── test_agents.py           # Script de prueba de agentes
│   ├── test_notifications.py    # Script de pruebas de notificaciones
│   └── run_telegram_bot.py      # Ejecutar bot standalone
├── docker/
│   └── docker-compose.dev.yml   # Redis para desarrollo
├── tests/                       # Tests
├── pyproject.toml               # Configuración del proyecto
├── requirements.txt             # Dependencias
└── README.md                    # Esta documentación
```

## 📊 Flujo de Propuestas

```
┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐
│    Agente    │───▶│  ApprovalEngine   │───▶│ NotificationMgr  │
│  (Análisis)  │    │   (Registrar)     │    │   (Telegram)     │
└──────────────┘    └───────────────────┘    └──────────────────┘
                              │                        │
                              ▼                        ▼
                    ┌──────────────────┐      ┌──────────────┐
                    │      Redis       │      │   Humano     │
                    │   (Almacenar)    │      │  (Revisar)   │
                    └──────────────────┘      └──────────────┘
                              │                        │
                              │         Aprobar        │
                              ◀────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐    ┌──────────────────┐
                    │  ActionExecutor  │───▶│      Odoo        │
                    │   (Ejecutar)     │    │   (Acción)       │
                    └──────────────────┘    └──────────────────┘
```

## 🔧 Configuración Avanzada

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `ODOO_URL` | URL del servidor Odoo | `http://localhost:8069` |
| `ODOO_DB` | Nombre de la base de datos | `odoo` |
| `ODOO_USER` | Usuario de Odoo | `admin` |
| `ODOO_PASSWORD` | Contraseña | `admin` |
| `REDIS_URL` | URL de Redis | `redis://localhost:6379/0` |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | - |
| `TELEGRAM_ADMIN_CHAT_ID` | Chat ID del administrador | - |
| `ARIA_ENV` | Entorno (development/staging/production) | `development` |
| `ARIA_DEBUG` | Modo debug | `false` |
| `ARIA_LOG_LEVEL` | Nivel de log | `INFO` |

## 🌐 Dashboard Web

El dashboard web proporciona una vista en tiempo real de todos los agentes y propuestas.

### Instalación del Dashboard

```bash
cd dashboard
npm install
```

### Desarrollo

```bash
# Iniciar API (en una terminal)
aria api

# Iniciar dashboard (en otra terminal)
cd dashboard
npm run dev
```

El dashboard estará disponible en http://localhost:5173

### Características del Dashboard

- 📊 KPIs en tiempo real
- 🤖 Estado de todos los agentes
- ⚡ Propuestas pendientes con acciones rápidas
- 🔄 Actualización automática cada 30 segundos
- 📱 Diseño responsive

## 📄 Reportes PDF

ARIA puede generar reportes PDF automáticamente usando WeasyPrint.

### Requisitos adicionales

```bash
# macOS
brew install pango

# Ubuntu/Debian
sudo apt install libpango-1.0-0 libpangocairo-1.0-0
```

### Templates disponibles

- `aging_report.html` - Antigüedad de saldos
- `executive_dashboard.html` - Dashboard ejecutivo
- `inventory_report.html` - Reporte de inventario

### Uso programático

```python
from aria.reports import report_generator

data = {
    'total': 1500000,
    'overdue_total': 350000,
    # ... más datos
}

# Generar PDF
pdf_path = report_generator.generate('aging_report.html', data)

# Solo HTML (para previsualización)
html = report_generator.render_html('aging_report.html', data)
```

## 🧪 Testing

```bash
# Probar agentes
python scripts/test_agents.py              # Mostrar estado
python scripts/test_agents.py cobranza     # Probar agente
python scripts/test_agents.py cobranza aging_analysis  # Probar tarea

# Probar sistema de notificaciones
python scripts/test_notifications.py

# Solo Telegram
python scripts/test_notifications.py --telegram

# Solo propuestas
python scripts/test_notifications.py --proposal

# Ejecutar tests unitarios
pytest

# Con cobertura
pytest --cov=aria
```

## 📈 Roadmap

### Fase 0 ✅
- [x] Estructura del proyecto
- [x] Sistema de configuración
- [x] Cliente Odoo robusto
- [x] Modelos de datos
- [x] Logger estructurado
- [x] CLI básico

### Fase 1 ✅
- [x] NotificationManager multicanal
- [x] ApprovalEngine con Redis
- [x] ActionExecutor
- [x] Bot de Telegram interactivo
- [x] CLI extendido con comandos de propuestas

### Fase 2 ✅
- [x] BaseAgent mejorado con ciclo de vida
- [x] AgentRegistry para registro dinámico
- [x] TaskScheduler con APScheduler
- [x] CEO Agent (Dashboard ejecutivo)
- [x] Receivables Agent (Cobranza completa)
- [x] Sales Agent (Gestión comercial)
- [x] CLI con comandos de agentes y scheduler

### Fase 3 ✅
- [x] Purchase Agent (Compras)
- [x] Finance Agent (Finanzas/Tesorería)
- [x] Accounting Agent (Contabilidad)
- [x] API REST completa (FastAPI)
- [x] WebSocket para tiempo real

### Fase 4 ✅ (Actual)
- [x] Inventory Agent (Control de stock)
- [x] HR Agent (Recursos Humanos)
- [x] Sistema de reportes PDF (WeasyPrint + Jinja2)
- [x] Programador de reportes automáticos
- [x] Dashboard Web (React + Vite + Tailwind)
- [x] Endpoints API para reportes

### Fase 5 (Próxima)
- [ ] Integración con IA/LLM para análisis
- [ ] Predicción de demanda
- [ ] Alertas proactivas con ML
- [ ] Multi-empresa (multi-tenant)

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-caracteristica`)
3. Commit tus cambios (`git commit -am 'Agregar característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

## 📄 Licencia

Proprietary - Todos los derechos reservados.

---

Desarrollado con ❤️ para automatizar tu ERP de manera segura.
