"""
ARIA - Ejecutor de Acciones
============================

Ejecuta acciones aprobadas en Odoo.

Responsabilidades:
1. Recibir propuestas aprobadas
2. Ejecutar la acción en Odoo
3. Reportar resultado
4. Notificar al usuario
"""

from typing import Any, Optional

from aria.config import settings
from aria.models.proposal import Proposal, ProposalStatus, ProposalAction
from aria.utils.logger import get_logger

logger = get_logger("aria.action_executor")


class ActionExecutionError(Exception):
    """Error durante ejecución de acción."""
    pass


class ActionExecutor:
    """
    Ejecuta acciones aprobadas en Odoo.
    
    Se registra como callback en ApprovalEngine para
    ejecutar automáticamente cuando se aprueba una propuesta.
    
    Uso:
        from aria.action_executor import action_executor
        
        # Ejecutar manualmente
        result = await action_executor.execute(proposal)
        
        # O automáticamente al aprobar (configurar callback)
    """
    
    _instance: Optional["ActionExecutor"] = None
    
    def __new__(cls) -> "ActionExecutor":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._odoo = None
        self._initialized = True
        logger.info("ActionExecutor inicializado")
    
    @property
    def odoo(self):
        """Obtiene cliente Odoo (lazy loading)."""
        if self._odoo is None:
            from aria.odoo_client import OdooClient
            self._odoo = OdooClient.get_instance()
        return self._odoo
    
    async def execute(self, proposal: Proposal) -> dict[str, Any]:
        """
        Ejecuta una acción aprobada.
        
        Args:
            proposal: Propuesta aprobada a ejecutar
        
        Returns:
            Resultado de la ejecución
        
        Raises:
            ActionExecutionError: Si la ejecución falla
        """
        from aria.approval_engine import approval_engine
        from aria.notification_manager import notification_manager
        
        logger.info(f"Ejecutando acción: {proposal.short_id} - {proposal.title}")
        
        # Marcar como en ejecución
        proposal.mark_executing()
        
        try:
            result = await self._execute_action(proposal)
            
            # Marcar como completada
            await approval_engine.mark_executed(str(proposal.id), result)
            
            # Notificar éxito
            await notification_manager.send_execution_result(
                proposal,
                success=True,
                details=f"Resultado: {result}"
            )
            
            logger.info(f"Acción ejecutada exitosamente: {proposal.short_id}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error ejecutando acción {proposal.short_id}: {error_msg}")
            
            # Marcar como fallida
            await approval_engine.mark_failed(str(proposal.id), error_msg)
            
            # Notificar fallo
            await notification_manager.send_execution_result(
                proposal,
                success=False,
                details=f"Error: {error_msg}"
            )
            
            raise ActionExecutionError(error_msg) from e
    
    async def _execute_action(self, proposal: Proposal) -> dict[str, Any]:
        """
        Ejecuta la acción específica.
        
        Soporta:
        - Llamadas directas a métodos de Odoo
        - Acciones personalizadas por tipo
        """
        
        # Si tiene modelo y método de Odoo definidos
        if proposal.target_model and proposal.odoo_method:
            return self._execute_odoo_method(proposal)
        
        # Acciones por tipo
        action_handlers = {
            ProposalAction.SEND_REMINDER: self._handle_send_reminder,
            ProposalAction.SEND_PAYMENT_REQUEST: self._handle_send_payment,
            ProposalAction.BLOCK_CREDIT: self._handle_block_credit,
            ProposalAction.CREATE_PURCHASE_ORDER: self._handle_create_po,
            ProposalAction.CREATE_RECORD: self._handle_create_record,
            ProposalAction.UPDATE_RECORD: self._handle_update_record,
            ProposalAction.EXECUTE_ACTION: self._handle_execute_action,
        }
        
        handler = action_handlers.get(proposal.action)
        if handler:
            return await handler(proposal)
        
        # Si no hay acción específica, solo registrar
        return {
            "status": "acknowledged",
            "message": "Acción registrada (sin ejecución automática)",
            "proposal_id": str(proposal.id),
        }
    
    def _execute_odoo_method(self, proposal: Proposal) -> dict[str, Any]:
        """Ejecuta método directo en Odoo."""
        
        model = proposal.target_model
        method = proposal.odoo_method
        params = proposal.odoo_params
        
        args = params.get("args", [])
        kwargs = params.get("kwargs", {})
        
        logger.debug(f"Ejecutando {model}.{method} con args={args}, kwargs={kwargs}")
        
        result = self.odoo.execute(model, method, *args, **kwargs)
        
        return {
            "status": "success",
            "model": model,
            "method": method,
            "result": result,
        }
    
    # ==================== Handlers Específicos ====================
    
    async def _handle_send_reminder(self, proposal: Proposal) -> dict:
        """Envía recordatorio de cobranza."""
        payload = proposal.payload
        partner_id = payload.get("partner_id")
        template_id = payload.get("template_id")
        level = payload.get("escalation_level", 1)
        
        # Si hay template de email en Odoo, enviarlo
        if template_id and partner_id:
            try:
                # Buscar el partner
                partner = self.odoo.read("res.partner", [partner_id], ["email", "name"])
                if partner and partner[0].get("email"):
                    # Enviar usando template de Odoo
                    self.odoo.execute(
                        "mail.template",
                        "send_mail",
                        template_id,
                        partner_id,
                        force_send=True
                    )
                    
                    return {
                        "status": "success",
                        "action": "send_reminder",
                        "partner_id": partner_id,
                        "partner_name": partner[0].get("name"),
                        "level": level,
                        "method": "email_template"
                    }
            except Exception as e:
                logger.warning(f"No se pudo enviar email: {e}")
        
        # Registrar actividad de seguimiento
        logger.info(f"Recordatorio nivel {level} registrado para partner {partner_id}")
        
        return {
            "status": "success",
            "action": "send_reminder",
            "partner_id": partner_id,
            "level": level,
            "method": "logged"
        }
    
    async def _handle_send_payment(self, proposal: Proposal) -> dict:
        """Envía solicitud de pago."""
        payload = proposal.payload
        partner_id = payload.get("partner_id")
        invoice_ids = payload.get("invoice_ids", [])
        
        logger.info(f"Solicitud de pago enviada a partner {partner_id}")
        
        return {
            "status": "success",
            "action": "send_payment_request",
            "partner_id": partner_id,
            "invoice_ids": invoice_ids,
        }
    
    async def _handle_block_credit(self, proposal: Proposal) -> dict:
        """Bloquea crédito de un cliente."""
        payload = proposal.payload
        partner_id = payload.get("partner_id")
        
        if partner_id:
            # Poner límite de crédito en 0
            self.odoo.write("res.partner", [partner_id], {
                "credit_limit": 0,
            })
            
            # Agregar nota interna
            self.odoo.execute(
                "res.partner",
                "message_post",
                [partner_id],
                body=f"[ARIA] Crédito bloqueado automáticamente. Propuesta: {proposal.short_id}",
                message_type="comment",
            )
        
        return {
            "status": "success",
            "action": "block_credit",
            "partner_id": partner_id,
        }
    
    async def _handle_create_po(self, proposal: Proposal) -> dict:
        """Crea orden de compra."""
        payload = proposal.payload
        
        po_values = {
            "partner_id": payload.get("supplier_id"),
            "order_line": [
                (0, 0, line) for line in payload.get("lines", [])
            ],
        }
        
        # Agregar campos opcionales
        if payload.get("date_planned"):
            po_values["date_planned"] = payload["date_planned"]
        
        po_id = self.odoo.create("purchase.order", po_values)
        
        # Obtener nombre de la PO
        po = self.odoo.read("purchase.order", [po_id], ["name"])
        
        return {
            "status": "success",
            "action": "create_purchase_order",
            "purchase_order_id": po_id,
            "purchase_order_name": po[0]["name"] if po else None,
        }
    
    async def _handle_create_record(self, proposal: Proposal) -> dict:
        """Crea un registro genérico en Odoo."""
        model = proposal.target_model
        values = proposal.payload.get("values", {})
        
        if not model:
            raise ActionExecutionError("Modelo no especificado")
        
        record_id = self.odoo.create(model, values)
        
        return {
            "status": "success",
            "action": "create_record",
            "model": model,
            "record_id": record_id,
        }
    
    async def _handle_update_record(self, proposal: Proposal) -> dict:
        """Actualiza registros en Odoo."""
        model = proposal.target_model
        ids = proposal.target_ids
        values = proposal.payload.get("values", {})
        
        if not model or not ids:
            raise ActionExecutionError("Modelo o IDs no especificados")
        
        self.odoo.write(model, ids, values)
        
        return {
            "status": "success",
            "action": "update_record",
            "model": model,
            "record_ids": ids,
        }
    
    async def _handle_execute_action(self, proposal: Proposal) -> dict:
        """Ejecuta una acción genérica."""
        model = proposal.target_model
        method = proposal.odoo_method or proposal.payload.get("method")
        ids = proposal.target_ids
        
        if not model or not method:
            raise ActionExecutionError("Modelo o método no especificados")
        
        result = self.odoo.execute(model, method, ids)
        
        return {
            "status": "success",
            "action": "execute_action",
            "model": model,
            "method": method,
            "result": result,
        }
    
    # ==================== Registro de Callback ====================
    
    def register_with_approval_engine(self, agent_id: str) -> None:
        """
        Registra este executor como callback para un agente.
        
        Cuando se apruebe una propuesta del agente, se ejecutará automáticamente.
        """
        from aria.approval_engine import approval_engine
        
        approval_engine.register_callback(agent_id, self.execute)
        logger.debug(f"ActionExecutor registrado para agente: {agent_id}")


# Singleton global
action_executor = ActionExecutor()
