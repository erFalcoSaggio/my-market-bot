"""Entrypoint del bot — versione semplice e orientata all'azione.

Idea: misura quanto il mercato mondiale e' in sconto rispetto ai massimi e, quando
lo sconto supera una soglia, ti dice in modo netto COSA comprare e quanto.
Pochi messaggi: solo quando lo sconto si APPROFONDISCE, piu' un promemoria settimanale.

Uso:
  python bot.py                # esecuzione normale (GitHub Actions)
  python bot.py --dry-run      # non invia nulla, stampa a video
  python bot.py --test         # invia un messaggio di prova + esempio di segnale d'acquisto
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


def gauge_indicators(config: dict):
    g = config["market_gauge"]
    ind = signals.compute_indicators(data.fetch_history(g["ticker"], period="1y"))
    return g, ind


def check_crypto(config, state, token, chat_id, dry_run, now):
    """Avvisi crypto opzionali (default: spenti). Solo sui forti cali."""
    cfg = config.get("crypto", {})
    if not cfg.get("enabled"):
        return
    dip_pct = cfg.get("dip_pct", 25)
    crypto_state = state.setdefault("crypto", {})
    for ticker in cfg.get("tickers", []):
        ind = signals.compute_indicators(data.fetch_history(ticker, period="1y"))
        if not ind:
            continue
        dd = -ind["drawdown_from_high_pct"]
        in_dip = dd >= dip_pct
        was_in_dip = crypto_state.get(ticker, False)
        if in_dip and not was_in_dip:
            name = ticker.replace("-USD", "")
            notify.send(token, chat_id,
                        notify.format_crypto_action(name, ind, dip_pct, cfg.get("suggest_eur", 25)),
                        dry_run)
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
    ladder = config["dip_ladder"]
    buy_target = config.get("buy_target", "il tuo ETF MSCI World")
    now = datetime.now(timezone.utc)

    g, ind = gauge_indicators(config)
    if ind is None:
        log.error("Nessun dato per il termometro %s. Esco.", g["ticker"])
        return 1

    idx, step, _ = signals.dip_action_index(ind["drawdown_from_high_pct"], ladder)
    log.info("%s: %s dai massimi -> gradino sconto %d (%s)",
             g["ticker"], f"{ind['drawdown_from_high_pct']:+.1f}%", idx,
             step["level"] if step else "nessuno")

    # ---- Modalita' test: mostra benvenuto + un esempio di segnale d'acquisto ----
    if "--test" in args:
        notify.send(token, chat_id,
                    "✅ <b>Test riuscito</b>: il bot è configurato e i dati arrivano.", dry_run)
        notify.send(token, chat_id, notify.format_welcome(g["name"], ind, step), dry_run)
        demo_step = ladder[min(1, len(ladder) - 1)]  # es. "buon sconto"
        demo_ind = dict(ind, drawdown_from_high_pct=-float(demo_step["drawdown"]))
        notify.send(token, chat_id,
                    "⤵️ <i>Esempio di come appare un SEGNALE D'ACQUISTO:</i>\n\n"
                    + notify.format_action(g["name"], demo_ind, demo_step, buy_target), dry_run)
        return 0

    state = load_state()
    first_run = not state.get("initialized")

    if first_run:
        notify.send(token, chat_id, notify.format_welcome(g["name"], ind, step), dry_run)
        state["initialized"] = True
        state["dip_idx"] = idx
        log.info("Prima esecuzione: benvenuto inviato, baseline registrata.")
    else:
        old_idx = state.get("dip_idx", -1)
        if idx > old_idx and step is not None:
            # Lo sconto si e' approfondito: e' il momento di comprare extra.
            notify.send(token, chat_id, notify.format_action(g["name"], ind, step, buy_target), dry_run)
            log.info("Segnale d'acquisto inviato (gradino %d).", idx)
        elif idx < old_idx and idx == -1:
            # Tornati sopra la soglia di sconto: nessuna azione.
            notify.send(token, chat_id, notify.format_recovery(g["name"], ind), dry_run)
        state["dip_idx"] = idx

    # Avvisi crypto opzionali
    check_crypto(config, state, token, chat_id, dry_run, now)

    # ---- Promemoria settimanale ----
    ws = config.get("weekly_status", {})
    force = "--status" in args
    week_tag = now.strftime("%Y-W%U")
    due = now.weekday() == ws.get("weekday", 0) and now.hour == ws.get("hour_utc", 7)
    if force or (due and state.get("last_weekly") != week_tag):
        notify.send(token, chat_id, notify.format_weekly_status(g["name"], ind, step), dry_run)
        if not force:
            state["last_weekly"] = week_tag

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
