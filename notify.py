"""Formattazione messaggi (orientati all'azione) e invio su Telegram.

Filosofia: pochi messaggi, chiari. Quando il mercato e' in sconto il bot ti dice
in modo diretto COSA fare. Un calo viene presentato come OPPORTUNITA' (🟢 sconto),
non come perdita: cosi' e' utile e non genera ansia.
"""
from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger("trade-bot.notify")

DISCLAIMER = ("\n\n<i>ℹ️ Non e' una previsione ne' un consiglio finanziario: e' una regola "
              "di disciplina. Compra solo con liquidita' che non ti serve per anni. Decidi tu.</i>")

_TAG_RE = re.compile(r"<[^>]+>")


def fmt_price(v) -> str:
    if v is None:
        return "n/d"
    if abs(v) < 10:
        return f"{v:,.4f}"
    if abs(v) < 1000:
        return f"{v:,.2f}"
    return f"{v:,.0f}"


def fmt_pct(v, decimals: int = 1) -> str:
    if v is None:
        return "n/d"
    return f"{v:+.{decimals}f}%"


# --------------------------------------------------------- messaggi principali

def format_action(gauge_name: str, ind: dict, step: dict, buy_target: str) -> str:
    """Messaggio di ACQUISTO: il mercato e' in sconto, ecco cosa fare ora."""
    dd = -ind["drawdown_from_high_pct"]
    return (
        f"{step['level']}  →  <b>COMPRA EXTRA ORA</b>\n\n"
        f"Il {gauge_name} è <b>-{dd:.0f}% sotto i massimi</b>: è in sconto.\n\n"
        f"👉 <b>Azione:</b> compra circa <b>{step['suggest_eur']}€</b> di {buy_target}.\n"
        f"(Continua comunque il PAC automatico: questo è un acquisto in più.)"
        f"{DISCLAIMER}"
    )


def format_recovery(gauge_name: str, ind: dict) -> str:
    """Il mercato e' risalito sopra la soglia di sconto: nessuna azione."""
    return (
        f"✅ <b>Sconto finito</b>\n\n"
        f"Il {gauge_name} è risalito ({fmt_pct(ind['drawdown_from_high_pct'])} dai massimi). "
        f"Nessuna azione: continua tranquillo il PAC."
    )


def format_crypto_action(name: str, ind: dict, dip_pct: int, suggest_eur: int) -> str:
    dd = -ind["drawdown_from_high_pct"]
    return (
        f"₿ <b>{name} -{dd:.0f}% dai massimi</b> (soglia -{dip_pct}%)\n\n"
        f"Se tieni una piccola quota di crypto come \"soldi che posso perdere\", "
        f"questo è uno sconto: eventualmente ~{suggest_eur}€. La crypto è molto più "
        f"rischiosa di un ETF mondiale: non metterci soldi che ti servono."
        f"{DISCLAIMER}"
    )


def format_weekly_status(gauge_name: str, ind: dict, step: dict | None) -> str:
    dd = -ind["drawdown_from_high_pct"]
    head = f"📅 <b>Promemoria settimanale</b>\nIl {gauge_name} è a {fmt_pct(ind['drawdown_from_high_pct'])} dai massimi."
    if step:
        body = (f"\n\n{step['level']}: c'è uno sconto attivo. Se hai liquidità, valuta "
                f"~{step['suggest_eur']}€ extra. Continua comunque il PAC.")
    else:
        body = "\n\nNessuna occasione particolare: tutto regolare, continua il PAC e ignora il rumore. 👍"
    return head + body


def format_welcome(gauge_name: str, ind: dict, step: dict | None) -> str:
    intro = (
        "🤖 <b>Bot attivo — versione semplice!</b>\n\n"
        "Faccio una cosa sola, ma bene: controllo 24/7 quanto il mercato mondiale è "
        "<b>in sconto</b> rispetto ai suoi massimi. Ti scrivo <b>solo</b> quando c'è "
        "un'occasione concreta per comprare extra (oltre al tuo PAC), dicendoti "
        "quanto. Più un promemoria tranquillo una volta a settimana.\n"
    )
    return intro + "\n" + format_weekly_status(gauge_name, ind, step)


# ----------------------------------------------------------------------- invio

def send(token, chat_id, text, dry_run: bool = False) -> None:
    if dry_run or not token or not chat_id:
        print("\n----- MESSAGGIO (dry-run, non inviato) -----")
        print(_TAG_RE.sub("", text))
        print("--------------------------------------------")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=20)
        if r.status_code != 200:
            log.error("Telegram ha risposto %s: %s", r.status_code, r.text)
    except Exception as e:
        log.error("Invio Telegram fallito: %s", e)


def print_chat_ids(token) -> None:
    if not token:
        print("Manca la variabile TELEGRAM_TOKEN.")
        return
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
        result = r.json().get("result", [])
    except Exception as e:
        print(f"Errore nel contattare Telegram: {e}")
        return
    found = set()
    for upd in result:
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat", {})
        if chat:
            label = chat.get("username") or chat.get("title") or chat.get("first_name") or "?"
            found.add((chat.get("id"), chat.get("type"), label))
    if not found:
        print("Nessun chat_id trovato.\n1) Cerca il tuo bot su Telegram.\n"
              "2) Premi START e scrivigli un messaggio.\n3) Rilancia questo comando.")
        return
    print("Trovato! Usa questo come TELEGRAM_CHAT_ID:")
    for cid, ctype, label in found:
        print(f"  chat_id = {cid}   (tipo: {ctype}, nome: {label})")
