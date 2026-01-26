"""
ARIA - Agente de Cobranza
==========================

Agente de Cobranza - Gestión de Cuentas por Cobrar

Responsabilidades:
- Monitorear facturas vencidas
- Calcular antigüedad de saldos (aging)
- Detectar patrones de pago deteriorados
- Proponer acciones de cobro escalonadas
- Recomendar suspensión de crédito
- Proyectar cobranza esperada
"""

from datetime import datetime, timedelta
from typing import Any

from aria.agents.base import BaseAgent
from aria.models.proposal import Priority, ProposalAction
from aria.models.task import TaskDefinition, TaskResult


class ReceivablesAgent(BaseAgent):
    """
    Agente autónomo para gestión de cobranza.
    
    Monitorea la cartera de clientes y propone acciones
    de cobro según niveles de escalamiento configurados.
    
    IMPORTANTE: Este agente filtra por company_id para coincidir
    con los reportes nativos de Odoo que son por compañía.
    """
    
    def __init__(self, company_id: int | None = None) -> None:
        super().__init__(
            name="cobranza",
            description="Gestión de cuentas por cobrar y recuperación de cartera"
        )
        
        # Compañía a monitorear (default desde settings)
        from aria.config import settings
        self.company_id = company_id or settings.odoo.company_id
        
        # Configuración de escalamiento
        self.escalation_levels = {
            1: {
                "days_overdue": 1,
                "action": "Enviar recordatorio amigable por email",
                "contact_method": "email",
            },
            2: {
                "days_overdue": 7,
                "action": "Segundo recordatorio + llamada de seguimiento",
                "contact_method": "phone",
            },
            3: {
                "days_overdue": 15,
                "action": "Enviar carta formal de cobro",
                "contact_method": "formal_letter",
            },
            4: {
                "days_overdue": 30,
                "action": "Notificar suspensión de crédito",
                "contact_method": "phone",
            },
            5: {
                "days_overdue": 45,
                "action": "Suspender crédito + preparar acción legal",
                "contact_method": "legal",
            },
        }
        
        # Umbrales
        self.min_amount_to_alert = 10000  # $10,000 MXN mínimo
        self.critical_amount = 500000  # $500,000 MXN para prioridad crítica
    
    def _register_tasks(self) -> None:
        """Registra tareas del agente de cobranza."""
        
        # Revisión diaria de vencidos
        self.register_task(TaskDefinition(
            name="check_overdue",
            method="check_overdue_invoices",
            schedule="0 8 * * *",  # 8:00 AM diario
            description="Revisa facturas vencidas y propone acciones de cobro"
        ))
        
        # Análisis de antigüedad semanal
        self.register_task(TaskDefinition(
            name="aging_analysis",
            method="aging_analysis",
            schedule="0 9 * * 1",  # Lunes 9:00 AM
            description="Genera análisis de antigüedad de cartera"
        ))
        
        # Detección de patrones
        self.register_task(TaskDefinition(
            name="payment_patterns",
            method="check_payment_patterns",
            schedule="0 10 * * 1",  # Lunes 10:00 AM
            description="Detecta deterioro en patrones de pago"
        ))
        
        # Verificación de límites de crédito
        self.register_task(TaskDefinition(
            name="credit_limits",
            method="check_credit_limits",
            schedule="0 */4 * * *",  # Cada 4 horas
            description="Verifica clientes cerca del límite de crédito"
        ))
        
        # Proyección de cobranza
        self.register_task(TaskDefinition(
            name="project_collections",
            method="project_collections",
            schedule="0 8 * * 5",  # Viernes 8:00 AM
            description="Proyecta cobranza de la próxima semana"
        ))
        
        # Análisis de pagos parciales
        self.register_task(TaskDefinition(
            name="partial_payments",
            method="analyze_partial_payments",
            schedule="0 11 * * 1",  # Lunes 11:00 AM
            description="Analiza facturas con pago parcial pendiente"
        ))
    
    async def get_status_summary(self) -> dict[str, Any]:
        """Retorna resumen del estado de cobranza."""
        
        overdue = self._get_overdue_invoices()
        total_overdue = sum(inv.get("amount_residual", 0) for inv in overdue)
        
        aging = self._calculate_aging_buckets(overdue)
        
        # Determinar estado general
        if aging.get("90+", 0) > self.critical_amount:
            status = "critical"
        elif aging.get("61-90", 0) + aging.get("90+", 0) > self.critical_amount:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": status,
            "company_id": self.company_id,
            "company_filter": "Todas" if not self.company_id else f"ID {self.company_id}",
            "total_overdue": total_overdue,
            "overdue_count": len(overdue),
            "aging": aging,
            "last_updated": datetime.now().isoformat(),
        }
    
    # ==================== Tareas ====================
    
    async def check_overdue_invoices(self) -> TaskResult:
        """
        Revisa facturas vencidas y propone acciones de cobro.
        También procesa mensajes pendientes de otros agentes.
        """
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Revisando facturas vencidas...")
        
        # Procesar mensajes pendientes de otros agentes
        await self._process_pending_messages()
        
        overdue = self._get_overdue_invoices()
        
        if not overdue:
            self.logger.info("No hay facturas vencidas")
            return TaskResult(
                task_name="check_overdue",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
                records_processed=0,
            )
        
        # Agrupar por cliente
        by_customer = self._group_by_customer(overdue)
        
        # Procesar cada cliente
        for partner_id, data in by_customer.items():
            # Ignorar montos pequeños
            if data["total"] < self.min_amount_to_alert:
                continue
            
            # Determinar nivel de escalamiento
            level = self._get_escalation_level(data["max_days_overdue"])
            level_config = self.escalation_levels[level]
            
            # Determinar prioridad
            if data["total"] > self.critical_amount or level >= 4:
                priority = Priority.CRITICAL
            elif data["total"] > self.critical_amount / 2 or level >= 3:
                priority = Priority.HIGH
            elif level >= 2:
                priority = Priority.MEDIUM
            else:
                priority = Priority.LOW
            
            # Crear propuesta
            await self.propose(
                title=f"Cobro a {data['name']}",
                description=f"Cliente con {self.format_currency(data['total'])} vencidos",
                action=ProposalAction.SEND_REMINDER,
                priority=priority,
                situation_summary=f"""
Cliente: {data['name']}
Total vencido: {self.format_currency(data['total'])}
Facturas vencidas: {len(data['invoices'])}
Días máximo vencido: {data['max_days_overdue']}
Nivel de escalamiento: {level}

Facturas:
{self._format_invoice_list(data['invoices'][:5])}
                """.strip(),
                proposed_action_detail=level_config["action"],
                supporting_data={
                    "partner_id": partner_id,
                    "partner_name": data["name"],
                    "total_overdue": data["total"],
                    "invoice_count": len(data["invoices"]),
                    "max_days_overdue": data["max_days_overdue"],
                    "escalation_level": level,
                    "invoices": data["invoices"][:10],
                },
                payload={
                    "partner_id": partner_id,
                    "escalation_level": level,
                    "contact_method": level_config["contact_method"],
                },
                alternatives=[
                    {"level": l, "description": cfg["action"]}
                    for l, cfg in self.escalation_levels.items()
                    if l != level
                ],
                risk_level=min(level, 5),
            )
            
            proposals_created += 1
        
        return TaskResult(
            task_name="check_overdue",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            records_processed=len(overdue),
        )
    
    async def aging_analysis(self) -> TaskResult:
        """
        Genera análisis de antigüedad de cartera.
        
        Usa buckets estándar de Odoo para coincidir con
        el reporte "Aged Receivable" nativo.
        """
        started_at = datetime.now()
        
        company_info = f" (Company ID: {self.company_id})" if self.company_id else " (Todas)"
        self.logger.info(f"Generando análisis de antigüedad...{company_info}")
        
        # Obtener TODAS las cuentas por cobrar (vencidas y por vencer)
        all_receivables = self._get_all_receivables()
        
        if not all_receivables:
            return TaskResult(
                task_name="aging_analysis",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Usar buckets estándar de Odoo
        aging = self._calculate_aging_buckets(all_receivables, odoo_standard=True)
        total = sum(aging.values())
        
        # Total vencido = Total - No vencido
        total_due = total - aging.get("Not Due", 0)
        
        # Calcular porcentajes
        pct = {k: (v / total * 100) if total > 0 else 0 for k, v in aging.items()}
        
        # Alertar si hay mucho en buckets críticos (61+ días)
        critical_amount = aging.get("61-90", 0) + aging.get("91-120", 0) + aging.get("120+", 0)
        
        message = f"""
*📊 Aging de Cartera (Estándar Odoo)*{company_info}

| Bucket | Monto | % |
|--------|-------|---|
| No vencido | {self.format_currency(aging.get('Not Due', 0))} | {pct.get('Not Due', 0):.1f}% |
| 0-30 días | {self.format_currency(aging.get('0-30', 0))} | {pct.get('0-30', 0):.1f}% |
| 31-60 días | {self.format_currency(aging.get('31-60', 0))} | {pct.get('31-60', 0):.1f}% |
| 61-90 días | {self.format_currency(aging.get('61-90', 0))} | {pct.get('61-90', 0):.1f}% |
| 91-120 días | {self.format_currency(aging.get('91-120', 0))} | {pct.get('91-120', 0):.1f}% |
| 120+ días | {self.format_currency(aging.get('120+', 0))} | {pct.get('120+', 0):.1f}% |

*Total CxC:* {self.format_currency(total)}
*Total vencido:* {self.format_currency(total_due)}
*Cartera crítica (60+ días):* {self.format_currency(critical_amount)}
        """.strip()
        
        priority = Priority.HIGH if critical_amount > self.critical_amount else Priority.MEDIUM
        
        await self.notify(
            title="📊 Aging de Cartera",
            message=message,
            priority=priority,
            data={
                "aging": aging, 
                "total": total,
                "total_due": total_due,
                "critical_amount": critical_amount,
                "company_id": self.company_id,
            }
        )
        
        return TaskResult(
            task_name="aging_analysis",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"aging": aging, "total_due": total_due}
        )
    
    async def check_payment_patterns(self) -> TaskResult:
        """Detecta clientes con deterioro en patrón de pago."""
        started_at = datetime.now()
        
        self.logger.info("Analizando patrones de pago...")
        
        # Clientes con facturas
        customers = self.search_read(
            "res.partner",
            [("customer_rank", ">", 0)],
            ["name", "total_invoiced", "total_due", "credit_limit"],
            limit=500
        )
        
        alerts = []
        
        for customer in customers:
            total_invoiced = customer.get("total_invoiced", 0)
            total_due = customer.get("total_due", 0)
            
            if total_due <= 0 or total_invoiced <= 0:
                continue
            
            # Ratio de cartera vencida
            ratio = total_due / total_invoiced
            
            # Alertar si más del 30% está vencido
            if ratio > 0.3 and total_due > 50000:
                alerts.append({
                    "id": customer["id"],
                    "name": customer["name"],
                    "total_due": total_due,
                    "ratio": ratio,
                })
        
        if alerts:
            alerts.sort(key=lambda x: x["total_due"], reverse=True)
            
            message = "*Clientes con patrón de pago deteriorado:*\n\n"
            
            for a in alerts[:10]:
                message += f"• {a['name']}: {self.format_currency(a['total_due'])} ({a['ratio']*100:.0f}% vencido)\n"
            
            if len(alerts) > 10:
                message += f"\n... y {len(alerts) - 10} más"
            
            await self.notify(
                title=f"⚠️ {len(alerts)} clientes con pago deteriorado",
                message=message,
                priority=Priority.MEDIUM,
                data={"alerts": alerts}
            )
        
        return TaskResult(
            task_name="payment_patterns",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"alerts_count": len(alerts)}
        )
    
    async def check_credit_limits(self) -> TaskResult:
        """Verifica clientes cerca o sobre su límite de crédito."""
        started_at = datetime.now()
        proposals_created = 0
        
        self.logger.info("Verificando límites de crédito...")
        
        customers = self.search_read(
            "res.partner",
            [("customer_rank", ">", 0), ("credit_limit", ">", 0)],
            ["name", "credit_limit", "total_due"],
            limit=500
        )
        
        exceeded = []
        near_limit = []
        
        for customer in customers:
            credit_limit = customer.get("credit_limit", 0)
            total_due = customer.get("total_due", 0)
            
            if credit_limit <= 0:
                continue
            
            utilization = total_due / credit_limit
            
            if utilization >= 1.0:
                exceeded.append({
                    "id": customer["id"],
                    "name": customer["name"],
                    "limit": credit_limit,
                    "used": total_due,
                    "utilization": utilization,
                })
            elif utilization >= 0.8:
                near_limit.append({
                    "id": customer["id"],
                    "name": customer["name"],
                    "limit": credit_limit,
                    "used": total_due,
                    "utilization": utilization,
                })
        
        # Proponer suspensión para los que excedieron
        for customer in exceeded:
            await self.propose(
                title=f"Suspender crédito: {customer['name']}",
                description=f"Cliente ha excedido su límite de crédito",
                action=ProposalAction.BLOCK_CREDIT,
                priority=Priority.HIGH,
                situation_summary=f"""
Cliente: {customer['name']}
Límite de crédito: {self.format_currency(customer['limit'])}
Saldo actual: {self.format_currency(customer['used'])}
Utilización: {customer['utilization']*100:.0f}%

⚠️ El cliente ha excedido su límite de crédito.
                """.strip(),
                proposed_action_detail="Suspender ventas a crédito hasta regularización",
                supporting_data=customer,
                payload={
                    "partner_id": customer["id"],
                },
                risk_level=3,
            )
            proposals_created += 1
        
        # Notificar los que están cerca del límite
        if near_limit:
            message = "*Clientes cerca del límite de crédito:*\n\n"
            
            for c in near_limit[:10]:
                message += f"• {c['name']}: {c['utilization']*100:.0f}% usado\n"
            
            await self.notify(
                title=f"⚠️ {len(near_limit)} clientes cerca del límite",
                message=message,
                priority=Priority.MEDIUM,
            )
        
        return TaskResult(
            task_name="credit_limits",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            proposals_created=proposals_created,
            data={"exceeded": len(exceeded), "near_limit": len(near_limit)}
        )
    
    async def project_collections(self) -> TaskResult:
        """
        Proyecta cobranza esperada para la próxima semana.
        
        Usa account.move.line para obtener saldos reales pendientes
        con vencimiento en los próximos 7 días.
        """
        started_at = datetime.now()
        
        self.logger.info("Proyectando cobranza...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Partidas por cobrar que vencen esta semana (usando account.move.line)
        domain = [
            ("account_type", "=", "asset_receivable"),
            ("reconciled", "=", False),
            ("parent_state", "=", "posted"),
            ("amount_residual", ">", 0),  # Solo saldos positivos
            ("date_maturity", ">=", today),
            ("date_maturity", "<=", next_week),
        ]
        
        if self.company_id:
            domain.append(("company_id", "=", self.company_id))
        
        due_this_week = self.search_read(
            "account.move.line",
            domain,
            ["move_name", "partner_id", "amount_residual", "date_maturity", "ref"],
            limit=500,
            order="date_maturity asc"
        )
        
        total_expected = sum(line.get("amount_residual", 0) for line in due_this_week)
        
        message = f"""
*Proyección de Cobranza - Próximos 7 días*

Total esperado: {self.format_currency(total_expected)}
Documentos: {len(due_this_week)}

*Principales:*
        """.strip()
        
        for line in due_this_week[:10]:
            partner = line.get("partner_id")
            partner_name = partner[1] if partner else "Desconocido"
            amount = line.get("amount_residual", 0)
            due_date = line.get("date_maturity", "")
            doc_name = line.get("move_name", "") or line.get("ref", "")
            message += f"\n• {partner_name}: {self.format_currency(amount)} (vence {self.format_date(due_date)})"
        
        await self.notify(
            title=f"💰 Cobranza esperada: {self.format_currency(total_expected)}",
            message=message,
            priority=Priority.LOW,
            data={"total": total_expected, "count": len(due_this_week)}
        )
        
        return TaskResult(
            task_name="project_collections",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={"total_expected": total_expected}
        )
    
    # ==================== Helpers ====================
    
    def _get_overdue_receivables(self) -> list[dict]:
        """
        Obtiene partidas de cuentas por cobrar vencidas.
        
        IMPORTANTE: Usa account.move.line (no account.move) porque:
        - Refleja pagos parciales aplicados
        - Considera notas de crédito cruzadas
        - Maneja anticipos conciliados
        - Es la misma fuente que los reportes nativos de Odoo
        
        FILTROS CRÍTICOS:
        - amount_residual > 0: Solo deudas, excluye anticipos/notas de crédito
        - company_id: Filtra por compañía para coincidir con reportes de Odoo
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Dominio base
        domain = [
            ("account_type", "=", "asset_receivable"),  # Cuentas por cobrar
            ("reconciled", "=", False),                  # No conciliadas
            ("parent_state", "=", "posted"),            # Asientos publicados
            ("amount_residual", ">", 0),                # Solo saldos positivos (deudas)
            ("date_maturity", "<", today),              # Vencidas
        ]
        
        # Agregar filtro de compañía si está configurado
        if self.company_id:
            domain.append(("company_id", "=", self.company_id))
        
        return self.search_read(
            "account.move.line",
            domain,
            [
                "id", "move_id", "move_name", "partner_id",
                "date", "date_maturity", "amount_residual",
                "amount_residual_currency", "currency_id", "ref",
                "company_id"
            ],
            limit=5000,
            order="date_maturity asc"
        )
    
    def _get_overdue_invoices(self) -> list[dict]:
        """
        Wrapper para compatibilidad - retorna datos en formato legacy.
        Internamente usa _get_overdue_receivables (account.move.line).
        """
        receivables = self._get_overdue_receivables()
        
        # Convertir a formato compatible con el código existente
        result = []
        for line in receivables:
            result.append({
                "id": line.get("move_id", [0, ""])[0] if line.get("move_id") else 0,
                "name": line.get("move_name", "") or line.get("ref", ""),
                "partner_id": line.get("partner_id"),
                "invoice_date": line.get("date", ""),
                "invoice_date_due": line.get("date_maturity", ""),
                "amount_residual": line.get("amount_residual", 0),
                "currency_id": line.get("currency_id"),
                # Campos adicionales de move.line
                "line_id": line.get("id"),
            })
        
        return result
    
    def _get_all_receivables(self, company_id: int | None = None) -> list[dict]:
        """
        Obtiene TODAS las partidas de cuentas por cobrar pendientes (vencidas y por vencer).
        Útil para el análisis completo de cartera.
        """
        domain = [
            ("account_type", "=", "asset_receivable"),
            ("reconciled", "=", False),
            ("parent_state", "=", "posted"),
            ("amount_residual", ">", 0),  # Solo saldos positivos
        ]
        
        if self.company_id:
            domain.append(("company_id", "=", self.company_id))
        
        return self.search_read(
            "account.move.line",
            domain,
            [
                "id", "move_id", "move_name", "partner_id",
                "date", "date_maturity", "amount_residual",
                "amount_residual_currency", "currency_id", "ref",
                "company_id"
            ],
            limit=5000,
            order="date_maturity asc"
        )
    
    async def _process_pending_messages(self) -> None:
        """Procesa mensajes pendientes de otros agentes."""
        try:
            messages = self.check_messages(unread_only=True)
            
            for msg_data in messages:
                try:
                    from uuid import UUID
                    msg_id = UUID(msg_data.get("id"))
                    msg_type = msg_data.get("message_type")
                    from_agent = msg_data.get("from_agent")
                    content = msg_data.get("content", "")
                    data = msg_data.get("data", {})
                    
                    # Responder a consultas sobre proyección de cobranza
                    if msg_type == "alert" and ("cobranza" in content.lower() or "proyección" in content.lower()):
                        weeks = data.get("weeks", 4)
                        company_id = data.get("company_id", self.company_id)
                        
                        # Calcular proyección de cobranza
                        total_expected = 0
                        receivables = self._get_all_receivables()
                        
                        for week in range(1, weeks + 1):
                            days_start = (week - 1) * 7
                            days_end = week * 7
                            week_collections = sum(
                                r.get("amount_residual", 0) for r in receivables
                                if self._days_until_due(r.get("date_maturity", "")) <= days_end
                                and self._days_until_due(r.get("date_maturity", "")) > days_start
                            )
                            total_expected += week_collections
                        
                        # Responder
                        await self.respond_to_agent(
                            message_id=str(msg_id),
                            response=f"Proyección de cobranza para {weeks} semanas: {self.format_currency(total_expected)}",
                            data={
                                "weeks": weeks,
                                "total_expected": total_expected,
                                "company_id": company_id,
                            }
                        )
                        
                        self.logger.info(f"Respondido a {from_agent} sobre proyección de cobranza")
                    
                    # Marcar como leído
                    self.messaging.mark_read(msg_id, self.name)
                    
                except Exception as msg_error:
                    self.logger.warning(f"Error procesando mensaje individual: {msg_error}")
                    continue
                
        except Exception as e:
            self.logger.warning(f"Error procesando mensajes pendientes: {e}")
    
    def _days_until_due(self, due_date: str) -> int:
        """Calcula días hasta vencimiento."""
        if not due_date:
            return 999
        
        try:
            from datetime import datetime
            due = datetime.strptime(str(due_date)[:10], "%Y-%m-%d")
            today = datetime.now()
            return (due - today).days
        except Exception:
            return 999
    
    def _group_by_customer(self, receivables: list[dict]) -> dict[int, dict]:
        """Agrupa partidas por cobrar por cliente."""
        by_customer: dict[int, dict] = {}
        
        for line in receivables:
            partner = line.get("partner_id")
            partner_id = partner[0] if partner else 0
            partner_name = partner[1] if partner else "Desconocido"
            
            if partner_id not in by_customer:
                by_customer[partner_id] = {
                    "name": partner_name,
                    "invoices": [],
                    "total": 0,
                    "max_days_overdue": 0,
                }
            
            due_date = line.get("invoice_date_due") or line.get("date_maturity", "")
            # days_between retorna días desde la fecha (positivo si es pasado)
            # Para calcular días hasta vencimiento, usar negativo si es futuro
            days_diff = self.days_between(due_date) if due_date else 0
            days_overdue = max(0, days_diff)  # Solo positivo = vencido
            amount = line.get("amount_residual", 0)
            
            by_customer[partner_id]["invoices"].append({
                "number": line.get("name", "") or line.get("move_name", ""),
                "amount": amount,
                "due_date": due_date,
                "days_overdue": days_overdue,
            })
            by_customer[partner_id]["total"] += amount
            by_customer[partner_id]["max_days_overdue"] = max(
                by_customer[partner_id]["max_days_overdue"],
                days_overdue
            )
        
        return by_customer
    
    def _calculate_aging_buckets(
        self, 
        receivables: list[dict], 
        odoo_standard: bool = True
    ) -> dict[str, float]:
        """
        Calcula buckets de antigüedad desde account.move.line.
        
        Usa date_maturity (fecha de vencimiento de la línea) que es
        la fecha correcta para calcular días vencidos.
        
        Args:
            receivables: Lista de líneas de cuenta por cobrar
            odoo_standard: Si True, usa buckets estándar de Odoo:
                           Not Due, 0-30, 31-60, 61-90, 91-120, 120+
                           Si False, usa buckets personalizados.
        """
        if odoo_standard:
            # Buckets estándar de Odoo (Aged Receivable Report)
            aging: dict[str, float] = {
                "Not Due": 0,   # No vencido
                "0-30": 0,      # 0-30 días vencido
                "31-60": 0,     # 31-60 días vencido
                "61-90": 0,     # 61-90 días vencido
                "91-120": 0,    # 91-120 días vencido
                "120+": 0,      # Más de 120 días vencido
            }
        else:
            # Buckets personalizados más granulares
            aging = {
                "1-7": 0,
                "8-15": 0,
                "16-30": 0,
                "31-60": 0,
                "61-90": 0,
                "90+": 0,
            }
        
        for line in receivables:
            # Usar date_maturity de move.line o invoice_date_due si viene del wrapper
            due_date = line.get("date_maturity") or line.get("invoice_date_due", "")
            days = self.days_between(due_date) if due_date else 0
            amount = line.get("amount_residual", 0)
            
            if odoo_standard:
                # Buckets estándar de Odoo
                if days <= 0:
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
            else:
                # Solo contar si está vencido (days > 0)
                if days <= 0:
                    continue
                
                if days <= 7:
                    aging["1-7"] += amount
                elif days <= 15:
                    aging["8-15"] += amount
                elif days <= 30:
                    aging["16-30"] += amount
                elif days <= 60:
                    aging["31-60"] += amount
                elif days <= 90:
                    aging["61-90"] += amount
                else:
                    aging["90+"] += amount
        
        return aging
    
    async def analyze_partial_payments(self) -> TaskResult:
        """Analiza facturas con pagos parciales pendientes."""
        started_at = datetime.now()
        
        self.logger.info("Analizando facturas con pago parcial...")
        
        # Dominio para facturas con pago parcial
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "=", "partial"),  # Pago parcial
        ]
        
        if self.company_id:
            domain.append(("company_id", "=", self.company_id))
        
        partial_invoices = self.search_read(
            "account.move",
            domain,
            [
                "name", "partner_id", "invoice_date", "invoice_date_due",
                "amount_total", "amount_residual", "payment_state",
                "invoice_user_id"
            ],
            limit=500,
            order="amount_residual desc"
        )
        
        if not partial_invoices:
            return TaskResult(
                task_name="partial_payments",
                agent_name=self.name,
                started_at=started_at,
                completed_at=datetime.now(),
                success=True,
            )
        
        # Calcular totales
        total_original = sum(inv.get("amount_total", 0) for inv in partial_invoices)
        total_pending = sum(inv.get("amount_residual", 0) for inv in partial_invoices)
        total_paid = total_original - total_pending
        
        # Agrupar por cliente
        by_customer = {}
        for inv in partial_invoices:
            partner = inv.get("partner_id")
            partner_name = partner[1] if partner else "Desconocido"
            
            if partner_name not in by_customer:
                by_customer[partner_name] = {"count": 0, "pending": 0, "invoices": []}
            
            by_customer[partner_name]["count"] += 1
            by_customer[partner_name]["pending"] += inv.get("amount_residual", 0)
            by_customer[partner_name]["invoices"].append(inv)
        
        # Ordenar por monto pendiente
        sorted_customers = sorted(
            by_customer.items(),
            key=lambda x: x[1]["pending"],
            reverse=True
        )
        
        message = f"""
*💳 Facturas con Pago Parcial*

*Resumen:*
• Facturas: {len(partial_invoices)}
• Total original: {self.format_currency(total_original)}
• Ya cobrado: {self.format_currency(total_paid)}
• Pendiente: {self.format_currency(total_pending)}

*Por cliente (Top 10):*
"""
        
        for name, data in sorted_customers[:10]:
            pct_pending = (data["pending"] / total_pending * 100) if total_pending > 0 else 0
            message += f"• {name[:25]}: {data['count']} fact. - {self.format_currency(data['pending'])} ({pct_pending:.0f}%)\n"
        
        # Facturas con más de 30 días de pago parcial
        today = datetime.now()
        old_partial = [
            inv for inv in partial_invoices
            if inv.get("invoice_date") and self.days_between(inv["invoice_date"]) > 30
        ]
        
        if old_partial:
            message += f"\n*⚠️ {len(old_partial)} facturas con pago parcial >30 días*"
        
        await self.notify(
            title=f"💳 {len(partial_invoices)} facturas con pago parcial: {self.format_currency(total_pending)}",
            message=message,
            priority=Priority.MEDIUM if len(old_partial) > 5 else Priority.LOW,
        )
        
        return TaskResult(
            task_name="partial_payments",
            agent_name=self.name,
            started_at=started_at,
            completed_at=datetime.now(),
            success=True,
            data={
                "count": len(partial_invoices),
                "total_pending": total_pending,
                "old_partial_count": len(old_partial),
            }
        )
    
    def _get_escalation_level(self, days_overdue: int) -> int:
        """Determina nivel de escalamiento."""
        for level in sorted(self.escalation_levels.keys(), reverse=True):
            if days_overdue >= self.escalation_levels[level]["days_overdue"]:
                return level
        return 1
    
    def _format_invoice_list(self, invoices: list[dict]) -> str:
        """Formatea lista de facturas para mostrar."""
        lines = []
        for inv in invoices:
            lines.append(
                f"• {inv['number']}: {self.format_currency(inv['amount'])} "
                f"(vencida hace {inv['days_overdue']} días)"
            )
        return "\n".join(lines)


def create_receivables_agent(company_id: int | None = None) -> ReceivablesAgent:
    """
    Crea y retorna el agente de cobranza.
    
    Args:
        company_id: ID de la compañía a monitorear.
                   Si es None, monitorea todas las compañías.
                   Para coincidir con reportes de Odoo, especifica una compañía.
    
    Compañías disponibles (ejemplo Quimibond):
        1: PRODUCTORA DE NO TEJIDOS QUIMIBOND
        2: JACOBO MIZRAHI PENHOS
        3: Jose Mizrahi Daniel
        4: BDC BOSQUES
    """
    return ReceivablesAgent(company_id=company_id)
