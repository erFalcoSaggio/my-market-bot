"""Formattazione messaggi (radar azioni) e invio su Telegram.

Quando un'azione crolla, il messaggio NON dice "compra" con sicurezza (sarebbe una
bugia per una singola azione): ti dice di andare a capire PERCHE' e' scesa, perche'
puo' essere un'occasione o una trappola di valore. Tu decidi dopo aver capito.
"""
from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger("trade-bot.notify")

DISCLAIMER = ("\n\n<i>ℹ️ Non e' una previsione ne' un consiglio finanziario. Le azioni singole "
              "sono rischiose: capisci l'azienda prima di comprare, e usa solo soldi che puoi "
              "permetterti di perdere. Decidi tu.</i>")

# Cosa fare quando un'azione e' crollata (vale per tutti i tipi di avviso).
_ACTION = ("\n👀 <b>Prima di comprare, scopri PERCHE' e' scesa</b> (una notizia? una trimestrale "
           "deludente? un problema vero dell'azienda?). È un'occasione o una trappola? "
           "Se l'azienda è solida e ci credi sul lungo periodo, può essere un buon punto "
           "d'ingresso — con importi piccoli. Altrimenti lascia perdere.")

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


def _header(stock: dict, ind: dict) -> str:
    return (f"<b>{stock['name']}</b> ({stock['ticker']})\n"
            f"Prezzo: {fmt_price(ind['last'])}  |  Oggi: {fmt_pct(ind['daily_change_pct'])}")


def format_stock_alert(stock: dict, alert: dict, ind: dict) -> str:
    t = alert["type"]
    d = alert.get("data", {})
    if t == "daily_drop":
        body = f"📉 <b>Crollo: {fmt_pct(d['change_pct'])} in giornata.</b>"
    elif t == "drawdown":
        body = f"🔻 <b>È a -{d['dd_pct']:.0f}% dai massimi a 52 settimane.</b>"
    elif t == "near_low":
        body = "🔽 <b>È sui minimi degli ultimi 12 mesi.</b>"
    else:
        body = "Aggiornamento."
    return f"{_header(stock, ind)}\n\n{body}{_ACTION}{DISCLAIMER}"


def format_weekly_status(snapshots) -> str:
    lines = ["📅 <b>Promemoria settimanale — la tua watchlist azioni</b>", ""]
    for stock, ind in snapshots:
        lines.append(
            f"• <b>{stock['name']}</b>: {fmt_price(ind['last'])} "
            f"({fmt_pct(ind['daily_change_pct'])} oggi · {fmt_pct(ind['drawdown_from_high_pct'])} dai max)"
        )
    lines.append("\nNessun crollo in corso = niente da fare. Ti avviso io se qualcosa si muove. 👍")
    return "\n".join(lines) + DISCLAIMER


def format_welcome(snapshots) -> str:
    intro = (
        "🤖 <b>Radar azioni attivo!</b>\n\n"
        "Tengo d'occhio 24/7 la tua watchlist di azioni e ti scrivo <b>solo quando una "
        "crolla</b> (calo forte in giornata, ai minimi dell'anno, o molto giù dai massimi). "
        "Non ti dico \"compra\": ti dico \"vai a vedere perché è scesa\". Decidi tu.\n"
        "Il tuo PAC resta separato e non lo tocco.\n\n"
        "Ecco la tua watchlist di partenza:"
    )
    snap = format_weekly_status(snapshots)
    # riusa il corpo del riepilogo settimanale senza la riga "promemoria settimanale"
    return intro + "\n\n" + "\n".join(snap.split("\n")[2:])


def format_crypto_action(name: str, ind: dict, dip_pct: int, suggest_eur: int) -> str:
    dd = -ind["drawdown_from_high_pct"]
    return (
        f"₿ <b>{name} -{dd:.0f}% dai massimi</b> (soglia -{dip_pct}%)\n\n"
        f"Se tieni una piccola quota di crypto come \"soldi che posso perdere\", "
        f"questo è uno sconto: eventualmente ~{suggest_eur}€. La crypto è molto più "
        f"rischiosa di un'azione: non metterci soldi che ti servono."
        f"{DISCLAIMER}"
    )


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
