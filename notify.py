"""Formattazione dei messaggi e invio su Telegram.

Ogni messaggio e' pensato per INFORMARE e dare contesto, non per dare ordini di
trading. Per il tuo PAC (MSCI World) il tono rinforza la strategia corretta:
continuare ad accumulare, comprare nei cali, non vendere nel panico.
"""
from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger("trade-bot.notify")

DISCLAIMER = ("\n\n<i>ℹ️ Informazione, non un consiglio finanziario. Gli indicatori sono "
              "euristiche su dati storici, non previsioni. Decidi sempre tu.</i>")

_TAG_RE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------- formattazione

def fmt_price(v) -> str:
    if v is None:
        return "n/d"
    if abs(v) < 10:
        return f"{v:,.4f}"
    if abs(v) < 1000:
        return f"{v:,.2f}"
    return f"{v:,.0f}"


def fmt_pct(v, decimals: int = 2) -> str:
    if v is None:
        return "n/d"
    return f"{v:+.{decimals}f}%"


def _header(asset: dict, ind: dict) -> str:
    return (f"<b>{asset['name']}</b> ({asset['ticker']})\n"
            f"Prezzo: {fmt_price(ind['last'])}  |  Oggi: {fmt_pct(ind['daily_change_pct'])}")


def format_alert(asset: dict, alert: dict, ind: dict) -> str:
    """Trasforma un alert strutturato in un messaggio Telegram (HTML)."""
    t = alert["type"]
    d = alert.get("data", {})
    is_pac = asset.get("is_pac", False)
    body = ""

    if t == "daily_move":
        ch = d["change_pct"]
        arrow = "📈" if ch > 0 else "📉"
        body = f"{arrow} Movimento forte: <b>{fmt_pct(ch)}</b> in giornata."
        if is_pac and ch < 0:
            body += ("\nÈ il tuo PAC. La strategia su un calo è continuare a comprare a "
                     "prezzi più bassi, non vendere. Se hai liquidità extra, un crollo è "
                     "storicamente stato un buon momento per accumulare.")

    elif t == "drawdown":
        dd = d["dd_pct"]
        lvl = d.get("level", 0)
        soglia = f" (soglia -{lvl}%)" if lvl else ""
        body = f"🔻 È sceso del <b>-{dd:.1f}%</b> dal massimo a 52 settimane{soglia}."
        if is_pac:
            body += ("\nQuesto è il tuo PAC. I cali fanno parte del gioco: chi continua ad "
                     "accumulare compra le stesse quote a sconto. Storicamente vendere nel "
                     "panico è l'errore più costoso. Valuta semmai un acconto extra, non una vendita.")
        else:
            body += "\nNessuna azione richiesta: è solo un'informazione di contesto."

    elif t == "rsi_oversold":
        body = (f"🟢 RSI a <b>{d['rsi']:.0f}</b> (≤30): tecnicamente \"ipervenduto\". "
                "Spesso (non sempre) è seguito da un rimbalzo. È un segnale statistico, non una certezza.")

    elif t == "rsi_overbought":
        body = (f"🔴 RSI a <b>{d['rsi']:.0f}</b> (≥70): tecnicamente \"ipercomprato\". "
                "Può indicare che la corsa è tirata. Non è un invito a vendere: è solo contesto.")

    elif t == "near_52w_high":
        body = "🔼 È a un soffio dal <b>massimo a 52 settimane</b>."

    elif t == "near_52w_low":
        body = "🔽 È vicino al <b>minimo a 52 settimane</b>."

    elif t == "golden_cross":
        body = ("✨ <b>Golden cross</b>: la media a 50 giorni ha superato quella a 200. "
                "Nell'analisi tecnica è letto come segnale di trend rialzista di lungo periodo "
                "(indicatore in ritardo, non profetico).")

    elif t == "death_cross":
        body = ("⚠️ <b>Death cross</b>: la media a 50 giorni è scesa sotto quella a 200. "
                "Letto come segnale di trend ribassista di lungo periodo (indicatore in ritardo).")

    else:
        body = "Aggiornamento."

    return f"{_header(asset, ind)}\n\n{body}{DISCLAIMER}"


def format_digest(snapshots, now, title: str = "📊 Riepilogo mercati") -> str:
    lines = [f"<b>{title}</b>  <i>({now:%d/%m %H:%M} UTC)</i>", ""]
    for asset, ind in snapshots:
        rsi_v = ind.get("rsi14")
        rsi_str = f"RSI {rsi_v:.0f}" if rsi_v is not None else "RSI n/d"
        lines.append(
            f"• <b>{asset['name']}</b>: {fmt_price(ind['last'])} "
            f"({fmt_pct(ind['daily_change_pct'])} oggi · {fmt_pct(ind['drawdown_from_high_pct'])} dai max · {rsi_str})"
        )
    return "\n".join(lines) + DISCLAIMER


def format_welcome(snapshots, now) -> str:
    intro = ("🤖 <b>Bot attivo!</b>\n"
             "Da ora controllo i mercati 24/7 e ti scrivo solo quando succede qualcosa di "
             "rilevante (cali importanti, movimenti forti, indicatori tecnici). "
             "Ti do contesto: <b>decidi sempre tu</b>.\n")
    return intro + "\n" + format_digest(snapshots, now, title="📷 Situazione di partenza")


# ----------------------------------------------------------------------- invio

def send(token, chat_id, text, dry_run: bool = False) -> None:
    """Invia un messaggio Telegram. In dry-run (o senza credenziali) stampa a video."""
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
    """Stampa i chat_id che hanno scritto al bot (usa get_chat_id.py)."""
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
        print("Nessun chat_id trovato.\n"
              "1) Apri Telegram e cerca il tuo bot per nome utente.\n"
              "2) Premi START e scrivigli un messaggio qualsiasi.\n"
              "3) Rilancia questo comando.")
        return
    print("Trovato! Usa questo valore come TELEGRAM_CHAT_ID:")
    for cid, ctype, label in found:
        print(f"  chat_id = {cid}   (tipo: {ctype}, nome: {label})")
