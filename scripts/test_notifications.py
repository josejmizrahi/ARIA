#!/usr/bin/env python3
"""
ARIA - Script de prueba del sistema de notificaciones.

Uso:
    python scripts/test_notifications.py
    
    # Solo probar Telegram
    python scripts/test_notifications.py --telegram
    
    # Solo probar propuestas
    python scripts/test_notifications.py --proposal
"""

import asyncio
import sys
from pathlib import Path

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from aria.config import settings
from aria.notification_manager import notification_manager
from aria.approval_engine import approval_engine
from aria.models.proposal import Proposal, ProposalType, ProposalAction, Priority
from aria.models.notification import NotificationPriority


async def test_console_notification():
    """Prueba notificación por consola."""
    print("\n" + "=" * 50)
    print("🧪 Probando notificación por consola...")
    print("=" * 50)
    
    notification = await notification_manager.notify(
        title="Prueba de Consola",
        message="Este es un mensaje de prueba del sistema ARIA.",
        priority=NotificationPriority.MEDIUM,
        agent_id="test_agent"
    )
    
    print(f"✅ Notificación enviada por: {notification.channel}")


async def test_telegram():
    """Prueba envío a Telegram."""
    print("\n" + "=" * 50)
    print("🧪 Probando Telegram...")
    print("=" * 50)
    
    if not settings.telegram_enabled:
        print("❌ Telegram no configurado")
        print("   Configura TELEGRAM_BOT_TOKEN y TELEGRAM_ADMIN_CHAT_ID en .env")
        return False
    
    telegram = notification_manager.telegram
    
    result = await telegram.send_message(
        "🧪 *Prueba de ARIA*\n\n"
        "Este es un mensaje de prueba del sistema.\n"
        "Si recibes esto, ¡la conexión funciona correctamente!"
    )
    
    if result.get("ok"):
        print("✅ Mensaje enviado a Telegram")
        return True
    else:
        print(f"❌ Error: {result}")
        return False


async def test_proposal():
    """Prueba envío de propuesta completa."""
    print("\n" + "=" * 50)
    print("🧪 Probando creación de propuesta...")
    print("=" * 50)
    
    proposal = Proposal(
        agent_id="cobranza",
        type=ProposalType.COBRANZA,
        action=ProposalAction.SEND_REMINDER,
        priority=Priority.HIGH,
        title="Cliente con cartera vencida",
        description="ACME Corporation tiene facturas vencidas que requieren atención.",
        situation_summary="""
Cliente: ACME Corporation
Total vencido: $150,000.00 MXN
Facturas vencidas: 3
Días máximo vencido: 45
Nivel de escalamiento: 3
        """.strip(),
        proposed_action_detail="Enviar carta formal de cobro nivel 3",
        supporting_data={
            "partner_id": 123,
            "partner_name": "ACME Corporation",
            "total_overdue": 150000,
            "invoices": [
                {"number": "FAC-001", "amount": 50000, "days_overdue": 45},
                {"number": "FAC-002", "amount": 60000, "days_overdue": 30},
                {"number": "FAC-003", "amount": 40000, "days_overdue": 15},
            ]
        },
        payload={
            "partner_id": 123,
            "escalation_level": 3,
            "contact_method": "email",
        },
        alternatives=[
            {"level": 2, "description": "Llamada de seguimiento"},
            {"level": 4, "description": "Suspender crédito"},
        ],
        risk_level=3,
        reversible=True,
    )
    
    # Registrar en ApprovalEngine
    await approval_engine.register(proposal)
    print(f"✅ Propuesta registrada: {proposal.short_id}")
    
    # Enviar notificación
    notification = await notification_manager.send_proposal(proposal)
    print(f"✅ Notificación enviada por: {notification.channel}")
    
    return proposal


async def test_approval_flow(proposal_id: str):
    """Prueba flujo de aprobación."""
    print("\n" + "=" * 50)
    print("🧪 Probando flujo de aprobación...")
    print("=" * 50)
    
    # Obtener propuesta
    proposal = await approval_engine.get(proposal_id)
    
    if not proposal:
        print("❌ Propuesta no encontrada")
        return
    
    print(f"📋 Propuesta: {proposal.title}")
    print(f"📊 Estado: {proposal.status.value}")
    
    # Aprobar
    proposal = await approval_engine.approve(proposal_id, approved_by="test_script")
    print(f"✅ Aprobada. Nuevo estado: {proposal.status.value}")
    
    # Ver stats
    stats = await approval_engine.get_stats()
    print(f"\n📊 Estadísticas: {stats}")


async def test_pending_list():
    """Prueba listar propuestas pendientes."""
    print("\n" + "=" * 50)
    print("🧪 Probando lista de pendientes...")
    print("=" * 50)
    
    pending = await approval_engine.get_pending()
    
    print(f"📋 Propuestas pendientes: {len(pending)}")
    
    for p in pending[:5]:
        print(f"   {p.priority_emoji} {p.short_id} - {p.title}")


async def main():
    """Ejecuta todas las pruebas."""
    print("=" * 60)
    print("🤖 ARIA - Prueba de Sistema de Notificaciones y Aprobaciones")
    print("=" * 60)
    
    # Verificar configuración
    print(f"\n📧 Telegram habilitado: {settings.telegram_enabled}")
    print(f"📨 Email habilitado: {settings.email_enabled}")
    print(f"🗄️ Redis URL: {settings.redis_url}")
    
    # Parsear argumentos
    args = sys.argv[1:]
    
    if "--telegram" in args:
        await test_telegram()
    elif "--proposal" in args:
        proposal = await test_proposal()
        if proposal:
            await test_pending_list()
    else:
        # Pruebas completas
        await test_console_notification()
        await test_telegram()
        
        proposal = await test_proposal()
        
        if proposal:
            print("\n⏳ Esperando 3 segundos...")
            await asyncio.sleep(3)
            
            await test_pending_list()
            
            # Preguntar si aprobar
            print("\n" + "-" * 60)
            response = input("¿Aprobar la propuesta de prueba? [s/N]: ").strip().lower()
            
            if response == "s":
                await test_approval_flow(str(proposal.id))
    
    # Cerrar conexiones
    await approval_engine.close()
    
    print("\n" + "=" * 60)
    print("✅ Pruebas completadas")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
