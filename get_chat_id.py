"""Esegui UNA volta per ottenere il tuo TELEGRAM_CHAT_ID.

Prima:
  1. crea il bot con @BotFather su Telegram e copia il token
  2. apri una chat con il tuo bot, premi START e scrivigli un messaggio
Poi:
  TELEGRAM_TOKEN="il-tuo-token" python get_chat_id.py
"""
import os

import notify

notify.print_chat_ids(os.environ.get("TELEGRAM_TOKEN"))
