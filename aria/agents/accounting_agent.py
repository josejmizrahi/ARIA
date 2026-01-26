"""
Agente de Contabilidad - Cierre y cumplimiento fiscal.

Monitorea facturas pendientes de timbrar, conciliaciones,
cierre mensual y vencimientos fiscales.
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.models.task import TaskDefinition, TaskResult
from aria.models.proposal import Priority


class AccountingAgent(BaseAgent):
    """
    Agente autónomo para gestión contable y fiscal.
    
    Monitorea:
    - Facturas sin timbrar (México: CFDI)
    - Conciliaciones bancarias pendientes
    - Checklist de cierre mensual
    - Vencimientos fiscales
    """
    
    def __init__(self) -> None:
        super().__init__(
            name="contabilidad",
            description="Cierre contable, cumplimiento fiscal y conciliaciones"
        )
        
        # Configuración (México)
        self.tax_deadline_day = 17  # Día límite declaraciones mensuales
        self.annual_deadline_month = 3  # Marzo para declaración anual
        self.warning_days_before = 3  # Días de anticipación para alertar
    
    def _register_tasks(self) -> None:
        """Registra las tareas del agente de contabilidad."""
        
        # Facturas sin timbrar
        self.register_task(TaskDefinition(
            name="pending_invoices",
            method="check_pending_invoices",
            schedule="0 9 * * *",  # Diario 9:00 AM
            description="Revisa facturas sin timbrar/publicar"
        ))
        
        # Conciliaciones
        self.register_task(TaskDefinition(
            name="reconciliation",
            method="check_reconciliation",
            schedule="0 10 * * *",  # Diario 10:00 AM
            description="Verifica estado de conciliaciones bancarias"
        ))
        
        # Cierre mensual
        self.register_task(TaskDefinition(
            name="monthly_close",
            method="check_monthly_close",
            schedule="0 9 1 * *",  # Día 1 de cada mes
            description="Checklist de cierre del mes anterior"
        ))
        
        # Vencimientos fiscales
        self.register_task(TaskDefinition(
            name="tax_deadlines",
            method="check_tax_deadlines",
            schedule="0 8 * * 1",  # Lunes 8:00 AM
            description="Alerta vencimientos fiscales próximos"
        ))
        
        # Asientos pendientes
        self.register_task(TaskDefinition(
            name="pending_entries",
            method="check_pending_entries",
            schedule="0 11 * * *",  # Diario 11:00 AM
            description="Revisa asientos contables en borrador"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado contable."""
        
        # Facturas sin publicar
        pending_invoices = self.search_count(
            "account.move",
            [
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "=", "draft"),
            ]
        )
        
        # Asientos en borrador
        draft_entries = self.search_count(
            "account.move",
            [
                ("move_type", "=", "entry"),
                ("state", "=", "draft"),
            ]
        )
        
        # Días para vencimiento fiscal
        today = datetime.now()
        if today.day <= self.tax_deadline_day:
            days_to_deadline = self.tax_deadline_day - today.day
        else:
            # Ya pasó, calcular para próximo mes
            days_to_deadline = (30 - today.day) + self.tax_deadline_day
        
        # Determinar estado
        if pending_invoices > 20 or days_to_deadline <= 2:
            status = "critical"
        elif pending_invoices > 10 or days_to_deadline <= 5:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "pending_invoices": pending_invoices,
            "draft_entries": draft_entries,
            "days_to_tax_deadline": days_to_deadline,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_pending_invoices(self) -> TaskResult:
        """Revisa facturas sin timbrar/publicar."""
        started_at = datetime.now()
        
        self.logger.info("Verificando facturas pendientes...")
        
        # Facturas de cliente en borrador
        customer_invoices = self.search_read(
            "account.move",
            [
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "=", "draft"),
            ],
            ["name", "partner_id", "amount_total", "invoice_date", "create_date"],
            limit=100,
            order="create_date asc"
        )
        
        # Facturas de proveedor en borrador
        vendor_bills = self.search_read(
            "account.move",
            [
                ("move_type", "in", ["in_invoice", "in_refund"]),
                ("state", "=", "draft"),
            ],
            ["name", "partner_id", "amount_total", "invoice_date", "create_date"],
            limit=100,
            order="create_date asc"
        )
        
        total_pending = len(customer_invoices) + len(vendor_bills)
        
        if total_pending == 0:
            return TaskResult(
                task_name="pending_invoices",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Clasificar por antigüedad
        old_customer = []
        old_vendor = []
        
        for inv in customer_invoices:
            create_date = inv.get("create_date", "")
            if create_date:
                days = self.days_between(create_date)
                if days >= 3:
                    old_customer.append({
                        "name": inv.get("name", "Nuevo"),
                        "partner": inv.get("partner_id", [0, ""])[1] if inv.get("partner_id") else "",
                        "amount": inv.get("amount_total", 0),
                        "days": days,
                    })
        
        for bill in vendor_bills:
            create_date = bill.get("create_date", "")
            if create_date:
                days = self.days_between(create_date)
                if days >= 3:
                    old_vendor.append({
                        "name": bill.get("name", "Nuevo"),
                        "partner": bill.get("partner_id", [0, ""])[1] if bill.get("partner_id") else "",
                        "amount": bill.get("amount_total", 0),
                        "days": days,
                    })
        
        message = f"""
*📄 Facturas Pendientes de Publicar*

*Facturas de cliente:* {len(customer_invoices)}
*Facturas de proveedor:* {len(vendor_bills)}
        """.strip()
        
        if old_customer:
            message += f"\n\n*⚠️ Clientes antiguas (>3 días):*"
            for inv in old_customer[:5]:
                message += f"\n• {inv['partner'][:20]}: {self.format_currency(inv['amount'])} ({inv['days']}d)"
        
        if old_vendor:
            message += f"\n\n*⚠️ Proveedores antiguas (>3 días):*"
            for bill in old_vendor[:5]:
                message += f"\n• {bill['partner'][:20]}: {self.format_currency(bill['amount'])} ({bill['days']}d)"
        
        # Determinar prioridad
        if len(customer_invoices) > 20 or len(old_customer) > 5:
            priority = Priority.HIGH
        elif len(customer_invoices) > 10:
            priority = Priority.MEDIUM
        else:
            priority = Priority.LOW
        
        await self.notify(
            title=f"📄 {total_pending} facturas sin publicar",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="pending_invoices",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"customer": len(customer_invoices), "vendor": len(vendor_bills)}
        )
    
    async def check_reconciliation(self) -> TaskResult:
        """Verifica estado de conciliaciones bancarias."""
        started_at = datetime.now()
        
        self.logger.info("Verificando conciliaciones bancarias...")
        
        # Obtener diarios bancarios
        bank_journals = self.search_read(
            "account.journal",
            [("type", "=", "bank")],
            ["name", "last_statement_id"],
            limit=20
        )
        
        if not bank_journals:
            return TaskResult(
                task_name="reconciliation",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Verificar última conciliación de cada banco
        reconciliation_status = []
        needs_attention = []
        
        for journal in bank_journals:
            last_stmt = journal.get("last_statement_id")
            
            if last_stmt:
                # Obtener fecha del último estado de cuenta
                stmt = self.search_read(
                    "account.bank.statement",
                    [("id", "=", last_stmt[0])],
                    ["date"],
                    limit=1
                )
                
                if stmt:
                    last_date = stmt[0].get("date", "")
                    days_since = self.days_between(last_date) if last_date else 999
                    
                    status = {
                        "journal": journal["name"],
                        "last_reconciliation": last_date,
                        "days_since": days_since,
                    }
                    reconciliation_status.append(status)
                    
                    if days_since > 7:
                        needs_attention.append(status)
            else:
                # Sin conciliación registrada
                reconciliation_status.append({
                    "journal": journal["name"],
                    "last_reconciliation": None,
                    "days_since": 999,
                })
                needs_attention.append({
                    "journal": journal["name"],
                    "last_reconciliation": "Nunca",
                    "days_since": 999,
                })
        
        if needs_attention:
            message = f"*🏦 Conciliaciones Pendientes*\n\n"
            message += f"*{len(needs_attention)} de {len(bank_journals)} bancos requieren atención:*\n"
            
            for acc in needs_attention:
                last = acc["last_reconciliation"] or "Nunca"
                if last != "Nunca":
                    last = self.format_date(last)
                message += f"\n• {acc['journal']}: última {last}"
            
            await self.notify(
                title=f"🏦 {len(needs_attention)} conciliaciones pendientes",
                message=message,
                priority=Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="reconciliation",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"status": reconciliation_status}
        )
    
    async def check_monthly_close(self) -> TaskResult:
        """Checklist de cierre del mes anterior."""
        started_at = datetime.now()
        
        self.logger.info("Generando checklist de cierre mensual...")
        
        # Mes anterior
        today = datetime.now()
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        
        month_name = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ][prev_month - 1]
        
        # Verificar pendientes del mes anterior
        date_from = f"{prev_year}-{prev_month:02d}-01"
        if prev_month == 12:
            date_to = f"{prev_year + 1}-01-01"
        else:
            date_to = f"{prev_year}-{prev_month + 1:02d}-01"
        
        # 1. Facturas de cliente en borrador del mes anterior
        draft_invoices = self.search_count(
            "account.move",
            [
                ("move_type", "in", ["out_invoice", "out_refund"]),
                ("state", "=", "draft"),
                ("create_date", ">=", date_from),
                ("create_date", "<", date_to),
            ]
        )
        
        # 2. Facturas de proveedor en borrador
        draft_bills = self.search_count(
            "account.move",
            [
                ("move_type", "in", ["in_invoice", "in_refund"]),
                ("state", "=", "draft"),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<", date_to),
            ]
        )
        
        # 3. Asientos en borrador del mes
        draft_entries = self.search_count(
            "account.move",
            [
                ("move_type", "=", "entry"),
                ("state", "=", "draft"),
                ("date", ">=", date_from),
                ("date", "<", date_to),
            ]
        )
        
        # Construir checklist
        checklist = [
            {"item": "Facturas de cliente publicadas", "pending": draft_invoices, "ok": draft_invoices == 0},
            {"item": "Facturas de proveedor registradas", "pending": draft_bills, "ok": draft_bills == 0},
            {"item": "Asientos contables publicados", "pending": draft_entries, "ok": draft_entries == 0},
        ]
        
        total_pending = draft_invoices + draft_bills + draft_entries
        
        message = f"""
*📋 Checklist de Cierre - {month_name} {prev_year}*

        """.strip()
        
        for item in checklist:
            emoji = "✅" if item["ok"] else "❌"
            pending_txt = f" ({item['pending']} pendientes)" if not item["ok"] else ""
            message += f"\n{emoji} {item['item']}{pending_txt}"
        
        if total_pending > 0:
            message += f"\n\n⚠️ *{total_pending} documentos pendientes de revisar*"
            priority = Priority.HIGH
        else:
            message += "\n\n✅ *Mes listo para cerrar*"
            priority = Priority.LOW
        
        await self.notify(
            title=f"📋 Cierre {month_name}: {total_pending} pendientes",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="monthly_close",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"checklist": checklist, "total_pending": total_pending}
        )
    
    async def check_tax_deadlines(self) -> TaskResult:
        """Alerta vencimientos fiscales próximos."""
        started_at = datetime.now()
        
        self.logger.info("Verificando vencimientos fiscales...")
        
        today = datetime.now()
        day = today.day
        
        # Calcular días hasta vencimiento mensual (día 17 en México)
        if day <= self.tax_deadline_day:
            days_to_deadline = self.tax_deadline_day - day
            deadline_month = today.month
        else:
            # Calcular para próximo mes
            if today.month == 12:
                next_month_days = 31  # Enero
            else:
                # Aproximación
                next_month_days = 30
            days_to_deadline = (next_month_days - day) + self.tax_deadline_day
            deadline_month = today.month + 1 if today.month < 12 else 1
        
        # Obtener nombre del mes
        months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        
        message = f"""
*📅 Vencimientos Fiscales*

*Declaraciones mensuales:*
• Vencimiento: Día {self.tax_deadline_day}
• Faltan: {days_to_deadline} días
• Periodo: {months[deadline_month - 2] if deadline_month > 1 else months[11]}
        """.strip()
        
        # Verificar si es inicio de año (declaración anual)
        if today.month <= self.annual_deadline_month:
            days_to_annual = (
                datetime(today.year, self.annual_deadline_month, 31) - today
            ).days
            message += f"\n\n*Declaración anual:*\n• Vencimiento: 31 de Marzo\n• Faltan: {days_to_annual} días"
        
        # Determinar prioridad
        if days_to_deadline <= self.warning_days_before:
            priority = Priority.HIGH
            message += f"\n\n🔴 *ATENCIÓN: Vencimiento en {days_to_deadline} días*"
        elif days_to_deadline <= 7:
            priority = Priority.MEDIUM
            message += f"\n\n⚠️ *Preparar declaraciones*"
        else:
            priority = Priority.LOW
        
        await self.notify(
            title=f"📅 Vencimiento fiscal en {days_to_deadline} días",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="tax_deadlines",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"days_to_deadline": days_to_deadline}
        )
    
    async def check_pending_entries(self) -> TaskResult:
        """Revisa asientos contables en borrador."""
        started_at = datetime.now()
        
        self.logger.info("Verificando asientos pendientes...")
        
        # Asientos en borrador (no facturas)
        entries = self.search_read(
            "account.move",
            [
                ("move_type", "=", "entry"),
                ("state", "=", "draft"),
            ],
            ["name", "ref", "date", "amount_total", "journal_id"],
            limit=50,
            order="date asc"
        )
        
        if not entries:
            return TaskResult(
                task_name="pending_entries",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Clasificar por antigüedad
        old_entries = []
        for entry in entries:
            date = entry.get("date", "")
            if date:
                days = self.days_between(date)
                if days >= 7:
                    old_entries.append({
                        "name": entry.get("name", ""),
                        "ref": entry.get("ref", ""),
                        "date": date,
                        "amount": entry.get("amount_total", 0),
                        "journal": entry.get("journal_id", [0, ""])[1] if entry.get("journal_id") else "",
                        "days": days,
                    })
        
        message = f"*📝 {len(entries)} asientos en borrador*\n"
        
        if old_entries:
            message += f"\n*⚠️ {len(old_entries)} con más de 7 días:*\n"
            for e in old_entries[:5]:
                ref = f" - {e['ref'][:20]}" if e['ref'] else ""
                message += f"• {e['name']}{ref}: {self.format_currency(e['amount'])} ({e['days']}d)\n"
        
        priority = Priority.MEDIUM if old_entries else Priority.LOW
        
        await self.notify(
            title=f"📝 {len(entries)} asientos pendientes",
            message=message,
            priority=priority,
        )
        
        return TaskResult(
            task_name="pending_entries",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"total": len(entries), "old": len(old_entries)}
        )


def create_accounting_agent() -> AccountingAgent:
    """Crea y retorna el agente de contabilidad."""
    return AccountingAgent()
