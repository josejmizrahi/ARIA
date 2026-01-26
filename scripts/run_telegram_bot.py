#!/usr/bin/env python3
"""
ARIA - Script para ejecutar el bot de Telegram.

Uso:
    python scripts/run_telegram_bot.py
"""

import asyncio
import sys
from pathlib import Path

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from aria.config import settings
from aria.telegram_bot import get_telegram_bot
from aria.utils.logger import setup_logging, print_banner


async def main():
    """Inicia el bot de Telegram."""
    setup_logging(settings.log_level.value)
    print_banner()
    
    print("\n🤖 Iniciando bot de Telegram...")
    
    if not settings.telegram_enabled:
        print("\n❌ Telegram no configurado.")
        print("   Configura las siguientes variables en tu archivo .env:")
        print("   - TELEGRAM_BOT_TOKEN")
        print("   - TELEGRAM_ADMIN_CHAT_ID")
        print("\n   Para obtener estas credenciales:")
        print("   1. Habla con @BotFather en Telegram")
        print("   2. Crea un nuevo bot con /newbot")
        print("   3. Copia el token al .env")
        print("   4. Envía un mensaje a tu bot")
        print("   5. Visita: https://api.telegram.org/bot<TOKEN>/getUpdates")
        print("   6. Copia el chat_id al .env")
        sys.exit(1)
    
    print(f"📱 Chat ID: {settings.telegram_admin_chat_id}")
    print("\n✅ Bot listo. Presiona Ctrl+C para detener.\n")
    
    bot = get_telegram_bot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo bot...")
    finally:
        await bot.stop()
        print("👋 Bot detenido.")


if __name__ == "__main__":
    asyncio.run(main())
