import math
import pandas as pd
from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        f_val = float(value)
        if not math.isfinite(f_val):
            return default
        return f_val
    except (TypeError, ValueError):
        return default


def round_value(value, decimals: int = 6):
    if value is None:
        return None
    try:
        f_val = float(value)
        if not math.isfinite(f_val):
            return None
        return round(f_val, decimals)
    except (TypeError, ValueError):
        return None


def format_price(value, decimals: int = None) -> str:
    if value is None:
        return "N/A"
    try:
        f_val = float(value)
    except (TypeError, ValueError):
        return str(value)

    if decimals is not None:
        return f"{f_val:.{decimals}f}"

    abs_value = abs(f_val)
    if abs_value == 0:
        return "0"
    if abs_value >= 100:
        return f"{f_val:.2f}"
    if abs_value >= 1:
        return f"{f_val:.4f}"
    if abs_value >= 0.01:
        return f"{f_val:.5f}"
    if abs_value >= 0.0001:
        return f"{f_val:.8f}"
    return f"{f_val:.12f}"


def unique_items(items) -> list:
    if not items:
        return []
    if isinstance(items, str):
        items = [items]

    seen = set()
    cleaned = []
    # Etiquetas de sección que no deben ser tratadas como items
    section_labels = {"razones", "condiciones faltantes", "advertencias"}
    
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        # Evitar duplicar etiquetas de sección si vienen en la lista
        if text.rstrip(":").strip().lower() in section_labels:
            continue
        if text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def clean_optional(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def volume_confirmation_text(vol_ratio, min_vol=1.2, low_vol=0.8) -> str:
    vol_text = f"{vol_ratio:.2f}x" if pd.notna(vol_ratio) else "N/A"
    min_text = f"{min_vol:.2f}x"
    if pd.isna(vol_ratio):
        return f"Volumen insuficiente para confirmar: {vol_text} / {min_text}"
    if vol_ratio < low_vol:
        return f"Volumen muy bajo: {vol_text} / {min_text}"
    if vol_ratio < min_vol:
        return f"Volumen insuficiente para confirmar: {vol_text} / {min_text}"
    return f"Volumen confirma: {vol_text} / {min_text}"


def display_timeframe(timeframe: str) -> str:
    if not timeframe:
        return "?"
    if timeframe.endswith(("h", "d")):
        return timeframe.upper()
    return timeframe


def entry_now_display(entry_now_text: str) -> str:
    text = entry_now_text or "Entrada ahora: no recomendable"
    prefix = "Entrada ahora:"
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix):].strip()
    if not text:
        return "No recomendable"
    return text[:1].upper() + text[1:]
