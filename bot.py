"""Entrypoint del bot — RADAR AZIONI.

Tiene d'occhio una watchlist di azioni e avvisa SOLO sui cali forti (crollo in
giornata, minimi a 52 settimane, forte calo dai massimi), come radar per andare a
investigare. Il PAC e' separato e non viene toccato. Pochi messaggi, con anti-spam.

Uso:
  python bot.py                # esecuzione normale (GitHub Actions)
  python bot.py --dry-run      # non invia nulla, stampa a video
  python bot.py --test         # messaggio di prova + watchlist + esempio di avviso
  python bot.py --status       # forza il promemoria settimanale
  python bot.py --get-chat-id  # stampa il chat_id Telegram

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


def collect_snapshots(stocks: list[dict]):
    snapshots = []
    for stock in stocks:
        ind = signals.compute_indicators(data.fetch_history(stock["ticker"], period="1y"))
        if ind is None:
            log.warning("Nessun dato per %s, salto", stock["ticker"])
            continue
        snapshots.append((stock, ind))
    return snapshots


def check_crypto(config, state, token, chat_id, dry_run):
    cfg = config.get("crypto", {})
    if not cfg.get("enabled"):
        return
    dip_pct = cfg.get("dip_pct", 25)
    crypto_state = state.setdefault("crypto", {})
    for ticker in cfg.get("tickers", []):
        ind = signals.compute_indicators(data.fetch_history(ticker, period="1y"))
        if not ind:
            continue
        in_dip = (-ind["drawdown_from_high_pct"]) >= dip_pct
        if in_dip and not crypto_state.get(ticker, False):
            notify.send(token, chat_id,
                        notify.format_crypto_action(ticker.replace("-USD", ""), ind,
                                                    dip_pct, cfg.get("suggest_eur", 25)), dry_run)
        crypto_state[ticker] = in_dip


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
    cooldown_h = config.get("alert_cooldown_hours", 48)
    now = datetime.now(timezone.utc)

    snapshots = collect_snapshots(config["stocks"])
    if not snapshots:
        log.error("Nessun dato recuperato per nessuna azione. Esco.")
        return 1

    # ---- Modalita' test ----
    if "--test" in args:
        notify.send(token, chat_id,
                    "✅ <b>Test riuscito</b>: il radar è configurato e i dati arrivano.", dry_run)
        notify.send(token, chat_id, notify.format_welcome(snapshots), dry_run)
        stock, ind = snapshots[0]
        demo_ind = dict(ind, daily_change_pct=-8.0)
        demo = {"type": "daily_drop", "data": {"change_pct": -8.0}}
        notify.send(token, chat_id,
                    "⤵️ <i>Esempio di come appare un avviso di crollo:</i>\n\n"
                    + notify.format_stock_alert(stock, demo, demo_ind), dry_run)
        return 0

    state = load_state()
    sent_keys: dict = state.setdefault("alerts", {})
    first_run = not state.get("initialized")

    # Tutti gli avvisi attualmente attivi (chiave con prefisso ticker)
    pending = []
    for stock, ind in snapshots:
        for alert in signals.stock_alerts(ind, thresholds):
            alert["key"] = f"{stock['ticker']}:{alert['key']}"
            pending.append((stock, alert, ind))

    if first_run:
        for _, alert, _ in pending:
            sent_keys[alert["key"]] = now.isoformat()
        state["initialized"] = True
        notify.send(token, chat_id, notify.format_welcome(snapshots), dry_run)
        log.info("Prima esecuzione: %d condizioni registrate come baseline.", len(pending))
    else:
        sent = 0
        for stock, alert, ind in pending:
            last = sent_keys.get(alert["key"])
            if last and _hours_since(last, now) < cooldown_h:
                continue
            notify.send(token, chat_id, notify.format_stock_alert(stock, alert, ind), dry_run)
            sent_keys[alert["key"]] = now.isoformat()
            sent += 1
        log.info("Inviati %d avvisi su %d condizioni attive.", sent, len(pending))

    # Le condizioni rientrate vengono dimenticate, cosi' potranno riallertare in futuro.
    active = {a["key"] for _, a, _ in pending}
    for k in list(sent_keys.keys()):
        if k not in active:
            del sent_keys[k]

    check_crypto(config, state, token, chat_id, dry_run)

    # ---- Promemoria settimanale ----
    ws = config.get("weekly_status", {})
    force = "--status" in args
    week_tag = now.strftime("%Y-W%U")
    due = now.weekday() == ws.get("weekday", 0) and now.hour == ws.get("hour_utc", 7)
    if force or (due and state.get("last_weekly") != week_tag):
        notify.send(token, chat_id, notify.format_weekly_status(snapshots), dry_run)
        if not force:
            state["last_weekly"] = week_tag

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
