#!/usr/bin/env python3
"""
ARIA - Sistema de Diagnóstico y Validación
==========================================

Este script verifica que:
1. Conexión a Odoo funciona
2. Conexión a Redis funciona
3. Cada agente puede leer sus modelos
4. Los datos que analiza cada agente son correctos
5. Las consultas retornan información válida
6. No hay problemas de configuración

Uso:
    python scripts/diagnostico_aria.py
    python scripts/diagnostico_aria.py --agente cobranza
    python scripts/diagnostico_aria.py --verbose
    python scripts/diagnostico_aria.py --json
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

# Agregar path de ARIA
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aria.config import settings
from aria.odoo_client import OdooClient
from aria.utils.logger import get_logger

logger = get_logger(__name__)


class TestStatus(str, Enum):
    """Estado de cada prueba."""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️ WARN"
    SKIP = "⏭️ SKIP"
    INFO = "ℹ️ INFO"


@dataclass
class TestResult:
    """Resultado de una prueba individual."""
    name: str
    status: TestStatus
    message: str
    details: Optional[dict] = None
    duration_ms: float = 0
    fix_suggestion: Optional[str] = None


@dataclass
class AgentDiagnostic:
    """Diagnóstico de un agente."""
    agent_name: str
    tests: list[TestResult] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.PASS)
    
    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.FAIL)
    
    @property
    def warnings(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.WARN)
    
    @property
    def is_healthy(self) -> bool:
        return self.failed == 0


class ARIADiagnostic:
    """
    Sistema de diagnóstico completo para ARIA.
    
    Verifica conexiones, datos y configuración de cada agente.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.odoo: Optional[OdooClient] = None
        self.results: dict[str, AgentDiagnostic] = {}
        self.start_time: Optional[datetime] = None
        self.company_id = settings.odoo.company_id
    
    async def run_full_diagnostic(self) -> dict:
        """Ejecuta diagnóstico completo de todo el sistema."""
        self.start_time = datetime.now()
        
        print("\n" + "=" * 70)
        print("🔍 ARIA - DIAGNÓSTICO DEL SISTEMA")
        print("=" * 70)
        print(f"Fecha: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Company ID: {self.company_id}")
        print(f"Odoo URL: {settings.odoo.url}")
        print("=" * 70 + "\n")
        
        # 1. Verificar conexiones base
        await self._test_connections()
        
        if not self.odoo:
            return self._generate_report()
        
        # 2. Verificar cada agente
        await self._test_agent_ceo()
        await self._test_agent_cobranza()
        await self._test_agent_ventas()
        await self._test_agent_compras()
        await self._test_agent_inventario()
        await self._test_agent_finanzas()
        await self._test_agent_rrhh()
        await self._test_agent_produccion()
        await self._test_agent_contabilidad()
        
        # 3. Pruebas de calidad de datos
        await self._test_data_quality_general()
        
        # 4. Generar reporte
        return self._generate_report()
    
    async def run_agent_diagnostic(self, agent_name: str) -> AgentDiagnostic:
        """Ejecuta diagnóstico de un agente específico."""
        await self._test_connections()
        
        if not self.odoo:
            return self.results.get("sistema")
        
        method_name = f"_test_agent_{agent_name}"
        if hasattr(self, method_name):
            await getattr(self, method_name)()
        else:
            print(f"❌ Agente '{agent_name}' no reconocido")
            print(f"   Agentes disponibles: ceo, cobranza, ventas, compras, inventario, finanzas, rrhh, produccion, contabilidad")
        
        return self.results.get(agent_name)
    
    # =========================================================================
    # PRUEBAS DE CONEXIÓN
    # =========================================================================
    
    async def _test_connections(self):
        """Verifica conexiones a Odoo y Redis."""
        diag = AgentDiagnostic(agent_name="sistema")
        
        print("📡 Verificando conexiones...")
        print("-" * 40)
        
        # Test Odoo
        start = datetime.now()
        try:
            self.odoo = OdooClient()
            # Verificar conexión con una consulta simple
            self.odoo.search_read("res.users", [("id", "=", 1)], ["id"], limit=1)
            duration = (datetime.now() - start).total_seconds() * 1000
            
            diag.tests.append(TestResult(
                name="Conexión Odoo",
                status=TestStatus.PASS,
                message=f"Conectado a Odoo ({settings.odoo.url})",
                details={"url": settings.odoo.url, "db": settings.odoo.db},
                duration_ms=duration
            ))
            print(f"  ✅ Odoo: Conectado ({duration:.0f}ms)")
            
        except Exception as e:
            diag.tests.append(TestResult(
                name="Conexión Odoo",
                status=TestStatus.FAIL,
                message=str(e),
                fix_suggestion="Verificar ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD en .env"
            ))
            print(f"  ❌ Odoo: {e}")
            self.results["sistema"] = diag
            return  # No continuar sin Odoo
        
        # Test Redis
        start = datetime.now()
        try:
            import redis.asyncio as redis
            r = redis.from_url(settings.redis.url)
            await r.ping()
            await r.close()
            duration = (datetime.now() - start).total_seconds() * 1000
            
            diag.tests.append(TestResult(
                name="Conexión Redis",
                status=TestStatus.PASS,
                message="Redis disponible",
                details={"url": settings.redis.url},
                duration_ms=duration
            ))
            print(f"  ✅ Redis: Conectado ({duration:.0f}ms)")
            
        except Exception as e:
            diag.tests.append(TestResult(
                name="Conexión Redis",
                status=TestStatus.WARN,
                message=str(e),
                fix_suggestion="Iniciar Redis con: docker-compose -f docker/docker-compose.dev.yml up -d"
            ))
            print(f"  ⚠️ Redis: {e} (propuestas no persistirán)")
        
        # Test Usuario Odoo
        try:
            user = self.odoo.search_read(
                "res.users",
                [("id", "=", self.odoo.uid)],
                ["name", "login", "groups_id"]
            )
            if user:
                user = user[0]
                diag.tests.append(TestResult(
                    name="Usuario Odoo",
                    status=TestStatus.PASS,
                    message=f"Usuario: {user['name']} ({user['login']})",
                    details={"groups_count": len(user.get("groups_id", []))}
                ))
                print(f"  ✅ Usuario: {user['name']}")
        except Exception as e:
            diag.tests.append(TestResult(
                name="Usuario Odoo",
                status=TestStatus.FAIL,
                message=str(e)
            ))
        
        # Test Company
        try:
            company = self.odoo.search_read(
                "res.company",
                [("id", "=", self.company_id)],
                ["name", "currency_id"]
            )
            if company:
                company = company[0]
                diag.tests.append(TestResult(
                    name="Compañía",
                    status=TestStatus.PASS,
                    message=f"Compañía: {company['name']}",
                    details={"currency": company.get("currency_id", [None, "N/A"])[1]}
                ))
                print(f"  ✅ Compañía: {company['name']}")
        except Exception as e:
            diag.tests.append(TestResult(
                name="Compañía",
                status=TestStatus.WARN,
                message=str(e)
            ))
        
        self.results["sistema"] = diag
        print()
    
    # =========================================================================
    # PRUEBAS POR AGENTE
    # =========================================================================
    
    async def _test_agent_ceo(self):
        """Diagnóstico del Agente CEO."""
        diag = AgentDiagnostic(agent_name="ceo")
        print("👔 Agente CEO")
        print("-" * 40)
        
        # Test: Acceso a datos de ventas del período
        await self._test_model_access(
            diag, 
            "Ventas del mes",
            "sale.order",
            [("state", "in", ["sale", "done"]), 
             ("date_order", ">=", (datetime.now().replace(day=1)).strftime("%Y-%m-%d")),
             ("company_id", "=", self.company_id)],
            ["name", "amount_total", "partner_id", "state"],
            expected_fields=["name", "amount_total"]
        )
        
        # Test: Acceso a facturas
        await self._test_model_access(
            diag,
            "Facturas del mes",
            "account.move",
            [("move_type", "=", "out_invoice"),
             ("invoice_date", ">=", (datetime.now().replace(day=1)).strftime("%Y-%m-%d")),
             ("company_id", "=", self.company_id)],
            ["name", "amount_total_signed", "state", "partner_id"],
            expected_fields=["amount_total_signed"]
        )
        
        # Test: Acceso a pagos recibidos
        await self._test_model_access(
            diag,
            "Pagos recibidos",
            "account.payment",
            [("payment_type", "=", "inbound"), ("state", "=", "posted"),
             ("company_id", "=", self.company_id)],
            ["name", "amount", "partner_id", "date"],
            expected_fields=["amount"]
        )
        
        # Test: Métricas consolidadas
        await self._test_kpi_calculation(diag)
        
        self.results["ceo"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_cobranza(self):
        """Diagnóstico del Agente de Cobranza."""
        diag = AgentDiagnostic(agent_name="cobranza")
        print("💰 Agente Cobranza")
        print("-" * 40)
        
        # Test: Facturas por cobrar
        await self._test_model_access(
            diag,
            "Facturas por cobrar",
            "account.move",
            [("move_type", "=", "out_invoice"), 
             ("state", "=", "posted"),
             ("payment_state", "in", ["not_paid", "partial"]),
             ("company_id", "=", self.company_id)],
            ["name", "partner_id", "amount_residual", "invoice_date_due", "invoice_date"],
            expected_fields=["amount_residual", "invoice_date_due"]
        )
        
        # Test: Facturas vencidas
        today = datetime.now().strftime("%Y-%m-%d")
        await self._test_model_access(
            diag,
            "Facturas vencidas",
            "account.move",
            [("move_type", "=", "out_invoice"),
             ("state", "=", "posted"),
             ("payment_state", "in", ["not_paid", "partial"]),
             ("invoice_date_due", "<", today),
             ("company_id", "=", self.company_id)],
            ["name", "partner_id", "amount_residual", "invoice_date_due"],
            expected_fields=["amount_residual"]
        )
        
        # Test: Clientes con límite de crédito
        await self._test_model_access(
            diag,
            "Clientes con límite de crédito",
            "res.partner",
            [("credit_limit", ">", 0), ("customer_rank", ">", 0)],
            ["name", "credit_limit", "credit", "debit"],
            expected_fields=["credit_limit", "credit"]
        )
        
        # Test: Verificar cálculo de antigüedad
        await self._test_aging_calculation(diag)
        
        self.results["cobranza"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_ventas(self):
        """Diagnóstico del Agente de Ventas."""
        diag = AgentDiagnostic(agent_name="ventas")
        print("🛒 Agente Ventas")
        print("-" * 40)
        
        # Test: Pedidos de venta
        await self._test_model_access(
            diag,
            "Pedidos de venta",
            "sale.order",
            [("state", "in", ["draft", "sent", "sale"]),
             ("company_id", "=", self.company_id)],
            ["name", "partner_id", "amount_total", "state", "date_order", "user_id"],
            expected_fields=["amount_total", "state"]
        )
        
        # Test: Cotizaciones pendientes
        await self._test_model_access(
            diag,
            "Cotizaciones pendientes",
            "sale.order",
            [("state", "in", ["draft", "sent"]),
             ("company_id", "=", self.company_id)],
            ["name", "partner_id", "amount_total", "validity_date"],
            expected_fields=["validity_date"]
        )
        
        # Test: Clientes
        await self._test_model_access(
            diag,
            "Clientes activos",
            "res.partner",
            [("customer_rank", ">", 0), ("active", "=", True)],
            ["name", "email", "phone", "credit_limit", "user_id"],
            expected_fields=["name"]
        )
        
        # Test: Vendedores
        await self._test_model_access(
            diag,
            "Vendedores",
            "res.users",
            [("share", "=", False), ("active", "=", True)],
            ["name", "login", "email"],
            expected_fields=["name"]
        )
        
        self.results["ventas"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_compras(self):
        """Diagnóstico del Agente de Compras."""
        diag = AgentDiagnostic(agent_name="compras")
        print("📦 Agente Compras")
        print("-" * 40)
        
        # Test: Órdenes de compra
        await self._test_model_access(
            diag,
            "Órdenes de compra",
            "purchase.order",
            [("company_id", "=", self.company_id)],
            ["name", "partner_id", "amount_total", "state", "date_order", "date_planned"],
            expected_fields=["amount_total", "state"]
        )
        
        # Test: Proveedores
        await self._test_model_access(
            diag,
            "Proveedores",
            "res.partner",
            [("supplier_rank", ">", 0)],
            ["name", "email", "phone"],
            expected_fields=["name"]
        )
        
        # Test: Info de proveedores por producto
        await self._test_model_access(
            diag,
            "Precios de proveedores",
            "product.supplierinfo",
            [("company_id", "=", self.company_id)],
            ["partner_id", "product_tmpl_id", "price", "delay", "min_qty"],
            expected_fields=["price", "delay"]
        )
        
        # Test: Recepciones pendientes
        await self._test_model_access(
            diag,
            "Recepciones pendientes",
            "stock.picking",
            [("picking_type_code", "=", "incoming"), 
             ("state", "not in", ["done", "cancel"]),
             ("company_id", "=", self.company_id)],
            ["name", "partner_id", "scheduled_date", "state"],
            expected_fields=["scheduled_date"]
        )
        
        self.results["compras"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_inventario(self):
        """Diagnóstico del Agente de Inventario."""
        diag = AgentDiagnostic(agent_name="inventario")
        print("📋 Agente Inventario")
        print("-" * 40)
        
        # Test: Productos almacenables
        await self._test_model_access(
            diag,
            "Productos almacenables",
            "product.product",
            [("type", "=", "product"), ("active", "=", True)],
            ["name", "default_code", "qty_available", "virtual_available", "uom_id"],
            expected_fields=["qty_available"]
        )
        
        # Test: Quants (stock por ubicación)
        await self._test_model_access(
            diag,
            "Stock por ubicación",
            "stock.quant",
            [("location_id.usage", "=", "internal"),
             ("company_id", "=", self.company_id)],
            ["product_id", "location_id", "quantity", "reserved_quantity"],
            expected_fields=["quantity"]
        )
        
        # Test: Almacenes
        await self._test_model_access(
            diag,
            "Almacenes",
            "stock.warehouse",
            [("company_id", "=", self.company_id)],
            ["name", "code", "lot_stock_id"],
            expected_fields=["name"]
        )
        
        # Test: Movimientos de stock
        await self._test_model_access(
            diag,
            "Movimientos pendientes",
            "stock.move",
            [("state", "not in", ["done", "cancel"]),
             ("company_id", "=", self.company_id)],
            ["product_id", "product_uom_qty", "location_id", "location_dest_id", "state"],
            expected_fields=["product_uom_qty"]
        )
        
        # Test: Reglas de reabastecimiento
        await self._test_model_access(
            diag,
            "Reglas de reabastecimiento",
            "stock.warehouse.orderpoint",
            [("active", "=", True), ("company_id", "=", self.company_id)],
            ["product_id", "product_min_qty", "product_max_qty", "qty_to_order"],
            expected_fields=["product_min_qty"]
        )
        
        self.results["inventario"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_finanzas(self):
        """Diagnóstico del Agente de Finanzas."""
        diag = AgentDiagnostic(agent_name="finanzas")
        print("💵 Agente Finanzas")
        print("-" * 40)
        
        # Test: Cuentas bancarias
        await self._test_model_access(
            diag,
            "Cuentas bancarias",
            "account.journal",
            [("type", "in", ["bank", "cash"]),
             ("company_id", "=", self.company_id)],
            ["name", "type", "code", "default_account_id"],
            expected_fields=["type"]
        )
        
        # Test: Saldos bancarios
        await self._test_bank_balances(diag)
        
        # Test: Pagos pendientes
        await self._test_model_access(
            diag,
            "Pagos a proveedores pendientes",
            "account.move",
            [("move_type", "=", "in_invoice"),
             ("state", "=", "posted"),
             ("payment_state", "in", ["not_paid", "partial"]),
             ("company_id", "=", self.company_id)],
            ["name", "partner_id", "amount_residual", "invoice_date_due"],
            expected_fields=["amount_residual"]
        )
        
        # Test: Extractos bancarios (Odoo 19 no tiene campo 'state')
        await self._test_model_access(
            diag,
            "Extractos bancarios",
            "account.bank.statement",
            [("company_id", "=", self.company_id)],
            ["name", "date", "balance_start", "balance_end_real", "is_complete"],
            expected_fields=["balance_end_real"]
        )
        
        self.results["finanzas"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_rrhh(self):
        """Diagnóstico del Agente de RRHH."""
        diag = AgentDiagnostic(agent_name="rrhh")
        print("👥 Agente RRHH")
        print("-" * 40)
        
        # Test: Módulo HR instalado
        hr_installed = await self._check_module_installed("hr")
        if not hr_installed:
            diag.tests.append(TestResult(
                name="Módulo HR",
                status=TestStatus.SKIP,
                message="Módulo 'hr' no instalado",
                fix_suggestion="Instalar módulo de Recursos Humanos en Odoo"
            ))
            print(f"  ⏭️ Módulo HR no instalado")
            self.results["rrhh"] = diag
            self._print_agent_summary(diag)
            return
        
        # Test: Empleados
        await self._test_model_access(
            diag,
            "Empleados",
            "hr.employee",
            [("active", "=", True), ("company_id", "=", self.company_id)],
            ["name", "job_id", "department_id", "work_email", "user_id"],
            expected_fields=["name"]
        )
        
        # Test: Departamentos
        await self._test_model_access(
            diag,
            "Departamentos",
            "hr.department",
            [("company_id", "=", self.company_id)],
            ["name", "manager_id", "parent_id"],
            expected_fields=["name"]
        )
        
        # Test: Contratos (si existe el módulo)
        if await self._check_module_installed("hr_contract"):
            await self._test_model_access(
                diag,
                "Contratos",
                "hr.contract",
                [("company_id", "=", self.company_id)],
                ["name", "employee_id", "state", "date_start", "date_end", "wage"],
                expected_fields=["wage", "state"]
            )
        
        # Test: Asistencias (si existe el módulo)
        if await self._check_module_installed("hr_attendance"):
            await self._test_model_access(
                diag,
                "Asistencias",
                "hr.attendance",
                [],
                ["employee_id", "check_in", "check_out"],
                expected_fields=["check_in"]
            )
        
        # Test: Ausencias (si existe el módulo)
        if await self._check_module_installed("hr_holidays"):
            await self._test_model_access(
                diag,
                "Ausencias",
                "hr.leave",
                [],
                ["employee_id", "holiday_status_id", "date_from", "date_to", "state"],
                expected_fields=["state"]
            )
        
        self.results["rrhh"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_produccion(self):
        """Diagnóstico del Agente de Producción."""
        diag = AgentDiagnostic(agent_name="produccion")
        print("🏭 Agente Producción")
        print("-" * 40)
        
        # Test: Módulo MRP instalado
        mrp_installed = await self._check_module_installed("mrp")
        if not mrp_installed:
            diag.tests.append(TestResult(
                name="Módulo MRP",
                status=TestStatus.SKIP,
                message="Módulo 'mrp' no instalado",
                fix_suggestion="Instalar módulo de Manufactura en Odoo"
            ))
            print(f"  ⏭️ Módulo MRP no instalado")
            self.results["produccion"] = diag
            self._print_agent_summary(diag)
            return
        
        # Test: Órdenes de producción
        await self._test_model_access(
            diag,
            "Órdenes de producción",
            "mrp.production",
            [("company_id", "=", self.company_id)],
            ["name", "product_id", "product_qty", "state", "date_start", "date_finished"],
            expected_fields=["product_qty", "state"]
        )
        
        # Test: Órdenes en progreso
        await self._test_model_access(
            diag,
            "Órdenes en progreso",
            "mrp.production",
            [("state", "=", "progress"), ("company_id", "=", self.company_id)],
            ["name", "product_id", "product_qty", "qty_produced"],
            expected_fields=["qty_produced"]
        )
        
        # Test: Órdenes retrasadas
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = await self._test_model_access(
            diag,
            "Órdenes retrasadas",
            "mrp.production",
            [("date_finished", "<", now),
             ("state", "in", ["confirmed", "progress"]),
             ("company_id", "=", self.company_id)],
            ["name", "product_id", "date_finished"],
            expected_fields=["date_finished"]
        )
        
        # Test: Centros de trabajo (Odoo 19 no tiene campo 'capacity')
        await self._test_model_access(
            diag,
            "Centros de trabajo",
            "mrp.workcenter",
            [("company_id", "=", self.company_id)],
            ["name", "time_efficiency", "workcenter_load", "working_state"],
            expected_fields=["time_efficiency"]
        )
        
        # Test: BOMs
        await self._test_model_access(
            diag,
            "Listas de materiales",
            "mrp.bom",
            [("active", "=", True), ("company_id", "=", self.company_id)],
            ["product_tmpl_id", "product_qty", "type"],
            expected_fields=["product_qty"]
        )
        
        self.results["produccion"] = diag
        self._print_agent_summary(diag)
    
    async def _test_agent_contabilidad(self):
        """Diagnóstico del Agente de Contabilidad."""
        diag = AgentDiagnostic(agent_name="contabilidad")
        print("📒 Agente Contabilidad")
        print("-" * 40)
        
        # Test: Plan de cuentas (Odoo 19: sin 'deprecated', company_id en algunas instalaciones)
        await self._test_model_access(
            diag,
            "Plan de cuentas",
            "account.account",
            [],  # Sin filtro de company para compatibilidad
            ["code", "name", "account_type", "reconcile"],
            expected_fields=["code", "account_type"]
        )
        
        # Test: Asientos contables
        await self._test_model_access(
            diag,
            "Asientos contables",
            "account.move",
            [("state", "=", "posted"), ("company_id", "=", self.company_id)],
            ["name", "date", "amount_total_signed", "move_type", "journal_id"],
            expected_fields=["amount_total_signed"]
        )
        
        # Test: Diarios
        await self._test_model_access(
            diag,
            "Diarios contables",
            "account.journal",
            [("company_id", "=", self.company_id)],
            ["name", "type", "code", "default_account_id"],
            expected_fields=["type"]
        )
        
        # Test: Impuestos
        await self._test_model_access(
            diag,
            "Impuestos",
            "account.tax",
            [("active", "=", True), ("company_id", "=", self.company_id)],
            ["name", "amount", "type_tax_use", "amount_type"],
            expected_fields=["amount"]
        )
        
        # Test: Partidas sin conciliar
        await self._test_model_access(
            diag,
            "Partidas sin conciliar",
            "account.move.line",
            [("reconciled", "=", False),
             ("account_id.reconcile", "=", True),
             ("company_id", "=", self.company_id)],
            ["name", "account_id", "debit", "credit", "date"],
            expected_fields=["debit", "credit"]
        )
        
        self.results["contabilidad"] = diag
        self._print_agent_summary(diag)
    
    async def _test_data_quality_general(self):
        """Pruebas generales de calidad de datos."""
        diag = AgentDiagnostic(agent_name="calidad_datos")
        print("🔍 Calidad de Datos")
        print("-" * 40)
        
        # Productos sin categoría
        await self._test_data_quality(
            diag,
            "Productos sin categoría",
            self._check_products_without_category
        )
        
        # Clientes sin vendedor
        await self._test_data_quality(
            diag,
            "Clientes sin vendedor asignado",
            self._check_customers_without_salesperson
        )
        
        # Contactos sin email
        await self._test_data_quality(
            diag,
            "Contactos sin email",
            self._check_partners_without_email
        )
        
        # Productos costo >= precio
        await self._test_data_quality(
            diag,
            "Productos costo >= precio",
            self._check_cost_vs_price
        )
        
        self.results["calidad_datos"] = diag
        self._print_agent_summary(diag)
    
    # =========================================================================
    # HELPERS DE PRUEBAS
    # =========================================================================
    
    async def _test_model_access(
        self,
        diag: AgentDiagnostic,
        test_name: str,
        model: str,
        domain: list,
        fields: list,
        expected_fields: list = None
    ) -> Optional[list]:
        """Prueba acceso a un modelo de Odoo."""
        start = datetime.now()
        try:
            # Verificar que el modelo existe
            model_exists = self.odoo.search_count("ir.model", [("model", "=", model)])
            if not model_exists:
                diag.tests.append(TestResult(
                    name=test_name,
                    status=TestStatus.SKIP,
                    message=f"Modelo '{model}' no existe",
                    fix_suggestion=f"Verificar que el módulo que contiene '{model}' esté instalado"
                ))
                print(f"  ⏭️ {test_name}: Modelo no existe")
                return None
            
            # Ejecutar búsqueda
            records = self.odoo.search_read(model, domain, fields, limit=100)
            count = self.odoo.search_count(model, domain)
            duration = (datetime.now() - start).total_seconds() * 1000
            
            # Verificar campos esperados
            if records and expected_fields:
                missing_fields = []
                for field in expected_fields:
                    if field not in records[0]:
                        missing_fields.append(field)
                
                if missing_fields:
                    diag.tests.append(TestResult(
                        name=test_name,
                        status=TestStatus.WARN,
                        message=f"Campos faltantes: {missing_fields}",
                        details={"count": count, "model": model},
                        duration_ms=duration,
                        fix_suggestion=f"Verificar permisos de lectura en campos: {missing_fields}"
                    ))
                    print(f"  ⚠️ {test_name}: {count} registros, campos faltantes: {missing_fields}")
                    return records
            
            diag.tests.append(TestResult(
                name=test_name,
                status=TestStatus.PASS,
                message=f"{count} registros encontrados",
                details={"count": count, "model": model},
                duration_ms=duration
            ))
            
            if self.verbose:
                print(f"  ✅ {test_name}: {count} registros ({duration:.0f}ms)")
            else:
                print(f"  ✅ {test_name}: {count} registros")
            
            return records
            
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            diag.tests.append(TestResult(
                name=test_name,
                status=TestStatus.FAIL,
                message=str(e),
                details={"model": model, "domain": str(domain)},
                duration_ms=duration,
                fix_suggestion=f"Verificar permisos de acceso al modelo '{model}'"
            ))
            print(f"  ❌ {test_name}: {e}")
            return None
    
    async def _test_data_quality(
        self,
        diag: AgentDiagnostic,
        test_name: str,
        check_function
    ):
        """Ejecuta una prueba de calidad de datos."""
        start = datetime.now()
        try:
            result = check_function()
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if result["status"] == "ok":
                diag.tests.append(TestResult(
                    name=test_name,
                    status=TestStatus.PASS,
                    message=result["message"],
                    duration_ms=duration
                ))
                print(f"  ✅ {test_name}: {result['message']}")
            elif result["status"] == "warning":
                diag.tests.append(TestResult(
                    name=test_name,
                    status=TestStatus.WARN,
                    message=result["message"],
                    details=result.get("details"),
                    duration_ms=duration,
                    fix_suggestion=result.get("fix")
                ))
                print(f"  ⚠️ {test_name}: {result['message']}")
            else:
                diag.tests.append(TestResult(
                    name=test_name,
                    status=TestStatus.FAIL,
                    message=result["message"],
                    details=result.get("details"),
                    duration_ms=duration,
                    fix_suggestion=result.get("fix")
                ))
                print(f"  ❌ {test_name}: {result['message']}")
                
        except Exception as e:
            diag.tests.append(TestResult(
                name=test_name,
                status=TestStatus.FAIL,
                message=str(e)
            ))
            print(f"  ❌ {test_name}: {e}")
    
    async def _test_bank_balances(self, diag: AgentDiagnostic):
        """Prueba cálculo de saldos bancarios."""
        start = datetime.now()
        try:
            # Obtener cuentas de banco/efectivo
            journals = self.odoo.search_read(
                "account.journal",
                [("type", "in", ["bank", "cash"]),
                 ("company_id", "=", self.company_id)],
                ["name", "default_account_id"]
            )
            
            if not journals:
                diag.tests.append(TestResult(
                    name="Saldos bancarios",
                    status=TestStatus.WARN,
                    message="No hay diarios de banco/efectivo configurados"
                ))
                print(f"  ⚠️ Saldos bancarios: Sin diarios configurados")
                return
            
            total_balance = 0
            balances = []
            
            for journal in journals:
                if journal.get("default_account_id"):
                    account_id = journal["default_account_id"][0]
                    
                    # Obtener saldo de la cuenta
                    lines = self.odoo.search_read(
                        "account.move.line",
                        [("account_id", "=", account_id),
                         ("parent_state", "=", "posted"),
                         ("company_id", "=", self.company_id)],
                        ["balance"]
                    )
                    
                    balance = sum(l.get("balance", 0) for l in lines)
                    total_balance += balance
                    balances.append({"name": journal["name"], "balance": balance})
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            diag.tests.append(TestResult(
                name="Saldos bancarios",
                status=TestStatus.PASS,
                message=f"Total: ${total_balance:,.2f}",
                details={"balances": balances, "total": total_balance},
                duration_ms=duration
            ))
            
            print(f"  ✅ Saldos bancarios: Total ${total_balance:,.2f}")
            for b in balances:
                print(f"      • {b['name']}: ${b['balance']:,.2f}")
                
        except Exception as e:
            diag.tests.append(TestResult(
                name="Saldos bancarios",
                status=TestStatus.FAIL,
                message=str(e)
            ))
            print(f"  ❌ Saldos bancarios: {e}")
    
    async def _test_kpi_calculation(self, diag: AgentDiagnostic):
        """Prueba cálculo de KPIs del CEO."""
        start = datetime.now()
        try:
            # Ventas del mes
            month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
            sales = self.odoo.search_read(
                "sale.order",
                [("state", "in", ["sale", "done"]), 
                 ("date_order", ">=", month_start),
                 ("company_id", "=", self.company_id)],
                ["amount_total"]
            )
            total_sales = sum(s["amount_total"] for s in sales)
            
            # Facturas emitidas
            invoices = self.odoo.search_read(
                "account.move",
                [("move_type", "=", "out_invoice"), 
                 ("state", "=", "posted"),
                 ("invoice_date", ">=", month_start),
                 ("company_id", "=", self.company_id)],
                ["amount_total_signed"]
            )
            total_invoiced = sum(i["amount_total_signed"] for i in invoices)
            
            # Pagos recibidos
            payments = self.odoo.search_read(
                "account.payment",
                [("payment_type", "=", "inbound"), 
                 ("state", "=", "posted"),
                 ("date", ">=", month_start),
                 ("company_id", "=", self.company_id)],
                ["amount"]
            )
            total_collected = sum(p["amount"] for p in payments)
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            diag.tests.append(TestResult(
                name="Cálculo de KPIs",
                status=TestStatus.PASS,
                message=f"Ventas: ${total_sales:,.2f}, Facturado: ${total_invoiced:,.2f}, Cobrado: ${total_collected:,.2f}",
                details={
                    "ventas_mes": total_sales,
                    "facturado_mes": total_invoiced,
                    "cobrado_mes": total_collected
                },
                duration_ms=duration
            ))
            print(f"  ✅ KPIs: Ventas ${total_sales:,.0f} | Facturado ${total_invoiced:,.0f} | Cobrado ${total_collected:,.0f}")
            
        except Exception as e:
            diag.tests.append(TestResult(
                name="Cálculo de KPIs",
                status=TestStatus.FAIL,
                message=str(e)
            ))
            print(f"  ❌ KPIs: {e}")
    
    async def _test_aging_calculation(self, diag: AgentDiagnostic):
        """Prueba cálculo de antigüedad de cartera."""
        start = datetime.now()
        try:
            today = datetime.now()
            
            invoices = self.odoo.search_read(
                "account.move",
                [("move_type", "=", "out_invoice"),
                 ("state", "=", "posted"),
                 ("payment_state", "in", ["not_paid", "partial"]),
                 ("company_id", "=", self.company_id)],
                ["amount_residual", "invoice_date_due"]
            )
            
            aging = {"Not Due": 0, "0-30": 0, "31-60": 0, "61-90": 0, "91-120": 0, "120+": 0}
            
            for inv in invoices:
                due_date_str = inv.get("invoice_date_due")
                if due_date_str:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                else:
                    due_date = today
                
                days = (today - due_date).days
                amount = inv.get("amount_residual", 0)
                
                if days < 0:
                    aging["Not Due"] += amount
                elif days <= 30:
                    aging["0-30"] += amount
                elif days <= 60:
                    aging["31-60"] += amount
                elif days <= 90:
                    aging["61-90"] += amount
                elif days <= 120:
                    aging["91-120"] += amount
                else:
                    aging["120+"] += amount
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            total = sum(aging.values())
            overdue = total - aging["Not Due"]
            
            diag.tests.append(TestResult(
                name="Análisis de antigüedad",
                status=TestStatus.PASS,
                message=f"Total CxC: ${total:,.2f}, Vencido: ${overdue:,.2f}",
                details={"aging": aging, "total": total, "overdue": overdue},
                duration_ms=duration
            ))
            
            print(f"  ✅ Antigüedad: Total ${total:,.0f}")
            print(f"      Not Due: ${aging['Not Due']:,.0f} | 0-30: ${aging['0-30']:,.0f} | 31-60: ${aging['31-60']:,.0f}")
            print(f"      61-90: ${aging['61-90']:,.0f} | 91-120: ${aging['91-120']:,.0f} | 120+: ${aging['120+']:,.0f}")
            
        except Exception as e:
            diag.tests.append(TestResult(
                name="Análisis de antigüedad",
                status=TestStatus.FAIL,
                message=str(e)
            ))
            print(f"  ❌ Antigüedad: {e}")
    
    # =========================================================================
    # FUNCIONES DE VERIFICACIÓN DE DATOS
    # =========================================================================
    
    def _check_products_without_category(self) -> dict:
        """Verifica productos sin categoría."""
        count = self.odoo.search_count(
            "product.product",
            [("categ_id", "=", False), ("active", "=", True)]
        )
        if count == 0:
            return {"status": "ok", "message": "Todos los productos tienen categoría"}
        return {
            "status": "warning",
            "message": f"{count} productos sin categoría",
            "fix": "Asignar categoría a productos en Inventario > Productos"
        }
    
    def _check_cost_vs_price(self) -> dict:
        """Verifica productos donde el costo es mayor o igual al precio."""
        products = self.odoo.search_read(
            "product.product",
            [("sale_ok", "=", True), ("active", "=", True), ("list_price", ">", 0)],
            ["name", "default_code", "standard_price", "list_price"],
            limit=1000
        )
        
        issues = []
        for p in products:
            if p.get("standard_price", 0) >= p.get("list_price", 0):
                issues.append({
                    "name": p["name"],
                    "code": p.get("default_code"),
                    "cost": p["standard_price"],
                    "price": p["list_price"]
                })
        
        if not issues:
            return {"status": "ok", "message": "Todos los productos tienen margen positivo"}
        
        return {
            "status": "warning" if len(issues) < 10 else "fail",
            "message": f"{len(issues)} productos con costo >= precio",
            "details": {"products": issues[:10]},
            "fix": "Revisar costos o precios de estos productos"
        }
    
    def _check_customers_without_salesperson(self) -> dict:
        """Verifica clientes sin vendedor asignado."""
        count = self.odoo.search_count(
            "res.partner",
            [("customer_rank", ">", 0), ("user_id", "=", False), ("active", "=", True)]
        )
        if count == 0:
            return {"status": "ok", "message": "Todos los clientes tienen vendedor"}
        return {
            "status": "warning",
            "message": f"{count} clientes sin vendedor asignado",
            "fix": "Asignar vendedor en la ficha del cliente"
        }
    
    def _check_partners_without_email(self) -> dict:
        """Verifica contactos sin email."""
        count = self.odoo.search_count(
            "res.partner",
            ["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0),
             ("email", "=", False), ("active", "=", True)]
        )
        total = self.odoo.search_count(
            "res.partner",
            ["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0), ("active", "=", True)]
        )
        
        if count == 0:
            return {"status": "ok", "message": "Todos los contactos tienen email"}
        
        percentage = (count / total) * 100 if total else 0
        return {
            "status": "warning" if percentage < 30 else "fail",
            "message": f"{count} de {total} contactos ({percentage:.0f}%) sin email",
            "fix": "Completar emails de contactos principales"
        }
    
    async def _check_module_installed(self, module_name: str) -> bool:
        """Verifica si un módulo está instalado."""
        try:
            count = self.odoo.search_count(
                "ir.module.module",
                [("name", "=", module_name), ("state", "=", "installed")]
            )
            return count > 0
        except:
            return False
    
    # =========================================================================
    # REPORTES
    # =========================================================================
    
    def _print_agent_summary(self, diag: AgentDiagnostic):
        """Imprime resumen de un agente."""
        print(f"\n  Resumen: {diag.passed} ✅ | {diag.warnings} ⚠️ | {diag.failed} ❌")
        print()
    
    def _generate_report(self) -> dict:
        """Genera reporte final."""
        total_pass = sum(d.passed for d in self.results.values())
        total_warn = sum(d.warnings for d in self.results.values())
        total_fail = sum(d.failed for d in self.results.values())
        
        healthy_agents = [name for name, d in self.results.items() if d.is_healthy]
        unhealthy_agents = [name for name, d in self.results.items() if not d.is_healthy]
        
        duration = (datetime.now() - self.start_time).total_seconds()
        
        print("\n" + "=" * 70)
        print("📋 RESUMEN FINAL")
        print("=" * 70)
        print(f"\nDuración total: {duration:.1f} segundos")
        print(f"\nPruebas: {total_pass} ✅ | {total_warn} ⚠️ | {total_fail} ❌")
        print(f"\nAgentes saludables: {len(healthy_agents)}/{len(self.results)}")
        
        if unhealthy_agents:
            print(f"\n⚠️ Agentes con problemas: {', '.join(unhealthy_agents)}")
        
        # Mostrar sugerencias de corrección
        fixes = []
        for diag in self.results.values():
            for test in diag.tests:
                if test.fix_suggestion and test.status in [TestStatus.FAIL, TestStatus.WARN]:
                    fixes.append(f"  • {test.name}: {test.fix_suggestion}")
        
        if fixes:
            print("\n🔧 Sugerencias de corrección:")
            for fix in fixes[:10]:  # Máximo 10
                print(fix)
        
        print("\n" + "=" * 70)
        
        # Estado general
        if total_fail == 0:
            print("✅ SISTEMA SALUDABLE - Todos los agentes funcionan correctamente")
        elif total_fail < 5:
            print("⚠️ SISTEMA CON ALERTAS - Revisar problemas menores")
        else:
            print("❌ SISTEMA CON PROBLEMAS - Requiere atención inmediata")
        
        print("=" * 70 + "\n")
        
        return {
            "timestamp": self.start_time.isoformat(),
            "duration_seconds": duration,
            "company_id": self.company_id,
            "summary": {
                "total_tests": total_pass + total_warn + total_fail,
                "passed": total_pass,
                "warnings": total_warn,
                "failed": total_fail,
            },
            "agents": {
                name: {
                    "healthy": diag.is_healthy,
                    "passed": diag.passed,
                    "warnings": diag.warnings,
                    "failed": diag.failed,
                    "tests": [
                        {
                            "name": t.name,
                            "status": t.status.value,
                            "message": t.message,
                            "fix": t.fix_suggestion
                        }
                        for t in diag.tests
                    ]
                }
                for name, diag in self.results.items()
            }
        }


# =========================================================================
# CLI
# =========================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ARIA - Diagnóstico del Sistema")
    parser.add_argument("--agente", "-a", help="Diagnosticar solo un agente específico")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostrar más detalles")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    parser.add_argument("--output", "-o", help="Guardar reporte en archivo")
    
    args = parser.parse_args()
    
    diagnostic = ARIADiagnostic(verbose=args.verbose)
    
    if args.agente:
        result = await diagnostic.run_agent_diagnostic(args.agente)
    else:
        result = await diagnostic.run_full_diagnostic()
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n📄 Reporte guardado en: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
