"""Calcolo metriche e generazione degli avvisi sulle azioni.

Filosofia: il bot e' un RADAR, non un oracolo. Segnala solo i cali forti, perche'
un'azione crollata va INVESTIGATA (puo' essere un'occasione o una trappola di valore).
Niente previsioni.
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float | None:
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
    if df is None or df.empty or "Close" not in df:
        return None
    close = df["Close"].dropna()
    if len(close) < 2:
        return None

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    window_52w = close.tail(252)
    high_52w = float(window_52w.max())
    low_52w = float(window_52w.min())

    return {
        "last": last,
        "prev": prev,
        "daily_change_pct": (last / prev - 1) * 100 if prev else 0.0,
        "high_52w": high_52w,
        "low_52w": low_52w,
        # negativo = quanto siamo SOTTO il massimo a 52 settimane
        "drawdown_from_high_pct": (last / high_52w - 1) * 100 if high_52w else 0.0,
        "pct_from_52w_low": (last / low_52w - 1) * 100 if low_52w else 0.0,
        "rsi14": rsi(close, 14),
    }


def stock_alerts(ind: dict, thresholds: dict) -> list[dict]:
    """Genera gli avvisi 'calo forte' per una singola azione."""
    alerts: list[dict] = []

    dchg = ind["daily_change_pct"]
    if dchg <= -abs(thresholds.get("daily_drop_pct", 7)):
        alerts.append({"key": "daily_drop", "type": "daily_drop", "data": {"change_pct": dchg}})

    dd = -ind["drawdown_from_high_pct"]  # positivo = % sotto il massimo
    if dd >= thresholds.get("drawdown_pct", 30):
        alerts.append({"key": "drawdown", "type": "drawdown", "data": {"dd_pct": dd}})

    if ind.get("pct_from_52w_low") is not None and ind["pct_from_52w_low"] <= thresholds.get("near_low_pct", 3):
        alerts.append({"key": "near_low", "type": "near_low", "data": {"pct": ind["pct_from_52w_low"]}})

    return alerts
