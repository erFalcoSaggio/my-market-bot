"""Recupero dati di mercato.

Fonte primaria: Yahoo Finance (yfinance) - copre ETF, azioni, indici, crypto,
forex e materie prime con un'unica interfaccia.
Fallback per le crypto: CoinGecko (gratis, senza chiave) quando Yahoo si auto-limita.

Tutte le funzioni ritornano un DataFrame con almeno la colonna 'Close' indicizzato
per data, oppure None se ogni fonte fallisce.
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import requests

log = logging.getLogger("trade-bot.data")

try:
    import yfinance as yf
except ImportError:  # la libreria viene installata da requirements.txt
    yf = None

# Mappa ticker Yahoo -> id CoinGecko, usata solo per il fallback crypto.
_COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
}

_PERIOD_TO_DAYS = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d",
                  retries: int = 3) -> pd.DataFrame | None:
    """Storico prezzi per un ticker. Prova Yahoo, poi (per le crypto) CoinGecko."""
    df = _fetch_yfinance(ticker, period, interval, retries)
    if df is not None and not df.empty:
        return df

    if ticker in _COINGECKO_IDS:
        log.warning("yfinance non disponibile per %s, provo CoinGecko", ticker)
        df = _fetch_coingecko(_COINGECKO_IDS[ticker], period)
        if df is not None and not df.empty:
            return df

    log.error("Impossibile recuperare i dati per %s da tutte le fonti", ticker)
    return None


def _fetch_yfinance(ticker, period, interval, retries):
    if yf is None:
        log.error("yfinance non installato")
        return None
    for attempt in range(1, retries + 1):
        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval)
            if df is not None and not df.empty and "Close" in df:
                out = df[["Close"]].dropna()
                if not out.empty:
                    return out
        except Exception as e:  # rate-limit (429), rete, cambi di Yahoo, ecc.
            log.warning("yfinance tentativo %d/%d per %s fallito: %s",
                        attempt, retries, ticker, e)
        time.sleep(2 * attempt)  # backoff crescente
    return None


def _fetch_coingecko(coin_id, period):
    days = _PERIOD_TO_DAYS.get(period, 365)
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    try:
        r = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=20)
        r.raise_for_status()
        prices = r.json().get("prices", [])
        if not prices:
            return None
        df = pd.DataFrame(prices, columns=["ts", "Close"])
        df["Date"] = pd.to_datetime(df["ts"], unit="ms")
        return df.set_index("Date")[["Close"]]
    except Exception as e:
        log.warning("CoinGecko fallito per %s: %s", coin_id, e)
        return None
