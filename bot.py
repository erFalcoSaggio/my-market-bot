"""Entrypoint del bot di analisi mercati + alert.

Flusso a ogni esecuzione:
  1. carica config.yaml e state.json
  2. scarica i dati di ogni asset e calcola gli indicatori
  3. genera gli alert, filtra quelli gia' inviati di recente (anti-spam)
  4. invia su Telegram cio' che resta + eventuale digest giornaliero
  5. salva lo stato

Uso:
  python bot.py                # esecuzione normale (usata da GitHub Actions)
  python bot.py --dry-run      # non invia nulla, stampa i messaggi a video
  python bot.py --test         # invia un messaggio di prova + snapshot + esempio di alert
  python bot.py --digest       # forza l'invio del riepilogo
  python bot.py --get-chat-id  # stampa il chat_id Telegram (config iniziale)

Variabili d'ambiente: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

import yaml

import data
import notify
import signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("trade-bot")

CONFIG_FILE = "config.yaml"
STATE_FILE = "state.json"


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _hours_since(iso_ts: str, now: datetime) -> float:
    try:
        then = datetime.fromisoformat(iso_ts)
    except ValueError:
        return 1e9
    return (now - then).total_seconds() / 3600.0


def collect_snapshots(config: dict):
    """Scarica i dati e calcola gli indicatori per ogni asset."""
    snapshots = []
    for asset in config["assets"]:
        df = data.fetch_history(asset["ticker"], period="1y")
        ind = signals.compute_indicators(df)
        if ind is None:
            log.warning("Nessun dato utilizzabile per %s, salto", asset["ticker"])
            continue
        snapshots.append((asset, ind))
    return snapshots


def main() -> int:
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if "--get-chat-id" in args:
        notify.print_chat_ids(token)
        return 0

    config = load_config()
    thresholds = config.get("thresholds", {})
    cooldown_h = config.get("alert_cooldown_hours", 24)
    now = datetime.now(timezone.utc)

    snapshots = collect_snapshots(config)
    if not snapshots:
        log.error("Nessun dato recuperato per nessun asset. Esco.")
        return 1

    # ---- Modalita' di test: mostra come appaiono i messaggi, niente stato ----
    if "--test" in args:
        notify.send(token, chat_id,
                    "✅ <b>Test riuscito</b>: il bot è configurato e i dati di mercato arrivano.",
                    dry_run)
        notify.send(token, chat_id, notify.format_digest(snapshots, now, title="📊 Snapshot di test"), dry_run)
        asset, ind = snapshots[0]
        demo = {"key": "demo", "type": "drawdown",
                "data": {"dd_pct": abs(ind["drawdown_from_high_pct"]), "level": 0}}
        notify.send(token, chat_id,
                    "⤵️ <i>Esempio di come appariranno gli alert:</i>\n\n"
                    + notify.format_alert(asset, demo, ind), dry_run)
        return 0

    state = load_state()
    sent_keys: dict = state.setdefault("alerts", {})
    first_run = not state.get("initialized")

    # Tutti gli alert attualmente attivi
    pending = []
    for asset, ind in snapshots:
        for alert in signals.generate_alerts(asset, ind, thresholds):
            pending.append((asset, alert, ind))

    if first_run:
        # Prima esecuzione: registriamo le condizioni attuali come "gia' viste"
        # per non sommergere di alert, e mandiamo solo un messaggio di benvenuto.
        for asset, alert, ind in pending:
            sent_keys[alert["key"]] = now.isoformat()
        state["initialized"] = True
        notify.send(token, chat_id, notify.format_welcome(snapshots, now), dry_run)
        log.info("Prima esecuzione: %d condizioni registrate come baseline.", len(pending))
    else:
        sent = 0
        for asset, alert, ind in pending:
            last = sent_keys.get(alert["key"])
            if last and _hours_since(last, now) < cooldown_h:
                continue  # gia' avvisato di recente
            notify.send(token, chat_id, notify.format_alert(asset, alert, ind), dry_run)
            sent_keys[alert["key"]] = now.isoformat()
            sent += 1
        log.info("Inviati %d alert su %d condizioni attive.", sent, len(pending))

    # Le condizioni rientrate vengono dimenticate, cosi' potranno riallertare in futuro.
    active = {a["key"] for _, a, _ in pending}
    for k in list(sent_keys.keys()):
        if k not in active:
            del sent_keys[k]

    # ---- Digest giornaliero ----
    digest_hour = config.get("daily_digest_hour_utc", 7)
    today = now.date().isoformat()
    force_digest = "--digest" in args
    if force_digest or (now.hour == digest_hour and state.get("last_digest") != today):
        notify.send(token, chat_id, notify.format_digest(snapshots, now), dry_run)
        if not force_digest:
            state["last_digest"] = today

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
