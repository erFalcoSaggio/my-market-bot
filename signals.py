"""Calcolo indicatori e generazione degli alert.

Tutto e' trasparente e basato su formule standard e documentate: nessuna "magia"
predittiva. Gli indicatori descrivono il PASSATO, non prevedono il futuro.

`generate_alerts` ritorna una lista di dizionari strutturati:
    {"key": <stringa stabile per l'anti-spam>, "type": <tipo>, "data": {...}}
La formattazione in testo umano avviene in notify.py.
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float | None:
    """RSI di Wilder (semplificato con media mobile). Ritorna l'ultimo valore."""
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi_series = 100 - (100 / (1 + rs))
    val = rsi_series.iloc[-1]
    return float(val) if pd.notna(val) else None


def compute_indicators(df: pd.DataFrame | None) -> dict | None:
    """Da uno storico prezzi a un dizionario di metriche correnti."""
    if df is None or df.empty or "Close" not in df:
        return None
    close = df["Close"].dropna()
    if len(close) < 2:
        return None

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    window_52w = close.tail(252)  # ~1 anno di sedute
    high_52w = float(window_52w.max())
    low_52w = float(window_52w.min())

    ind = {
        "last": last,
        "prev": prev,
        "daily_change_pct": (last / prev - 1) * 100 if prev else 0.0,
        "high_52w": high_52w,
        "low_52w": low_52w,
        # negativo = quanto siamo SOTTO il massimo a 52 settimane
        "drawdown_from_high_pct": (last / high_52w - 1) * 100 if high_52w else 0.0,
        "pct_from_52w_high": (last / high_52w - 1) * 100 if high_52w else 0.0,
        "pct_from_52w_low": (last / low_52w - 1) * 100 if low_52w else 0.0,
        "sma50": float(close.tail(50).mean()) if len(close) >= 50 else None,
        "sma200": float(close.tail(200).mean()) if len(close) >= 200 else None,
        "rsi14": rsi(close, 14),
    }

    # Incrocio medie mobili 50/200 (golden / death cross) tra ieri e oggi
    cross = None
    if len(close) >= 201:
        sma50_s = close.rolling(50).mean()
        sma200_s = close.rolling(200).mean()
        if pd.notna(sma50_s.iloc[-2]) and pd.notna(sma200_s.iloc[-2]):
            prev_diff = sma50_s.iloc[-2] - sma200_s.iloc[-2]
            last_diff = sma50_s.iloc[-1] - sma200_s.iloc[-1]
            if prev_diff <= 0 < last_diff:
                cross = "golden"
            elif prev_diff >= 0 > last_diff:
                cross = "death"
    ind["sma_cross"] = cross
    return ind


def generate_alerts(asset: dict, ind: dict, thresholds: dict) -> list[dict]:
    """Confronta gli indicatori con le soglie e produce gli alert (strutturati)."""
    ticker = asset["ticker"]
    alerts: list[dict] = []

    # 1) Movimento giornaliero forte
    dm = thresholds.get("daily_move_pct", 4.0)
    change = ind["daily_change_pct"]
    if abs(change) >= dm:
        direction = "up" if change > 0 else "down"
        alerts.append({
            "key": f"{ticker}:daily_move:{direction}",
            "type": "daily_move",
            "data": {"change_pct": change},
        })

    # 2) Drawdown dai massimi (solo il livello piu' profondo raggiunto)
    dd = -ind["drawdown_from_high_pct"]  # positivo = % sotto il massimo
    for level in sorted(thresholds.get("drawdown_levels", []), reverse=True):
        if dd >= level:
            alerts.append({
                "key": f"{ticker}:drawdown:{level}",
                "type": "drawdown",
                "data": {"dd_pct": dd, "level": level},
            })
            break

    # 3) RSI ipervenduto / ipercomprato
    rsi_v = ind.get("rsi14")
    if rsi_v is not None:
        if rsi_v <= thresholds.get("rsi_oversold", 30):
            alerts.append({"key": f"{ticker}:rsi_oversold", "type": "rsi_oversold",
                           "data": {"rsi": rsi_v}})
        elif rsi_v >= thresholds.get("rsi_overbought", 70):
            alerts.append({"key": f"{ticker}:rsi_overbought", "type": "rsi_overbought",
                           "data": {"rsi": rsi_v}})

    # 4) Vicinanza a massimo / minimo a 52 settimane
    nb = thresholds.get("near_52w_pct", 2.0)
    if abs(ind["pct_from_52w_high"]) <= nb:
        alerts.append({"key": f"{ticker}:near_52w_high", "type": "near_52w_high",
                       "data": {"pct": ind["pct_from_52w_high"]}})
    elif ind["pct_from_52w_low"] <= nb:
        alerts.append({"key": f"{ticker}:near_52w_low", "type": "near_52w_low",
                       "data": {"pct": ind["pct_from_52w_low"]}})

    # 5) Incrocio medie mobili
    if ind.get("sma_cross") == "golden":
        alerts.append({"key": f"{ticker}:golden_cross", "type": "golden_cross", "data": {}})
    elif ind.get("sma_cross") == "death":
        alerts.append({"key": f"{ticker}:death_cross", "type": "death_cross", "data": {}})

    return alerts
