"""Calcolo del calo dai massimi e della "scala degli sconti".

Tutto e' trasparente: misuriamo quanto il mercato e' sceso dal suo massimo a 52
settimane e lo confrontiamo con una scala di soglie. NON e' una previsione: e' una
regola di disciplina ("compra di piu' quando il mercato e' in sconto").
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float | None:
    """RSI (lasciato disponibile per usi futuri / report)."""
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
    """Da uno storico prezzi alle metriche correnti (prezzo, calo dai massimi, ...)."""
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
        "rsi14": rsi(close, 14),
    }


def dip_action_index(drawdown_from_high_pct: float, ladder: list[dict]):
    """Dato il calo dai massimi (negativo), trova il gradino piu' profondo raggiunto.

    Ritorna (idx, step, ladder_ordinata):
      - idx = -1 se non c'e' nessuno sconto rilevante (step = None)
      - idx >= 0 = posizione nella scala (0 = sconto piu' lieve)
    """
    dd = -drawdown_from_high_pct  # positivo = % sotto il massimo
    ordered = sorted(ladder, key=lambda s: s["drawdown"])
    idx = -1
    for i, step in enumerate(ordered):
        if dd >= step["drawdown"]:
            idx = i
    return idx, (ordered[idx] if idx >= 0 else None), ordered
