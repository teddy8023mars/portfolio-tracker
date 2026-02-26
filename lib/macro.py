"""Macro environment: interest rates, STI benchmark, VIX fear index."""

import sys
import yfinance as yf


def _fetch_latest(symbol, period="5d"):
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty or len(hist) < 2:
            return None
        latest = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2])
        chg = latest - prev
        chg_pct = chg / prev * 100 if prev else 0
        return {"value": latest, "prev": prev, "change": chg, "change_pct": chg_pct}
    except Exception:
        return None


def _fetch_range(symbol, period="20d"):
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty or len(hist) < 5:
            return None
        closes = hist["Close"]
        latest = float(closes.iloc[-1])
        d5_ago = float(closes.iloc[-5]) if len(closes) >= 5 else latest
        d20_ago = float(closes.iloc[0])
        return {
            "value": latest,
            "change_5d": latest - d5_ago,
            "change_5d_pct": (latest - d5_ago) / d5_ago * 100 if d5_ago else 0,
            "change_20d": latest - d20_ago,
            "change_20d_pct": (latest - d20_ago) / d20_ago * 100 if d20_ago else 0,
        }
    except Exception:
        return None


def fetch_macro():
    """
    Fetch macro environment data.
    Returns dict with: sti, vix, us10y, and a summary string.
    """
    sti = _fetch_latest("^STI")
    vix = _fetch_range("^VIX", period="20d")
    us10y = _fetch_latest("^TNX")

    parts = []

    if sti:
        direction = "📈" if sti["change"] >= 0 else "📉"
        parts.append(f"STI {direction}{sti['change_pct']:+.2f}%")

    if vix:
        v = vix["value"]
        if v >= 30:
            vix_status = "恐慌"
            vix_icon = "🔴"
        elif v >= 20:
            vix_status = "警惕"
            vix_icon = "🟡"
        else:
            vix_status = "平稳"
            vix_icon = "🟢"

        vix_delta = ""
        if abs(vix.get("change_5d_pct", 0)) > 20:
            vix_delta = f" (5日变化 {vix['change_5d_pct']:+.1f}%!)"
        parts.append(f"VIX {v:.1f} {vix_icon}{vix_status}{vix_delta}")

    if us10y:
        parts.append(f"美10Y国债 {us10y['value']:.2f}%")

    summary = " | ".join(parts) if parts else "宏观数据获取失败"

    print(f"  🌍 宏观: {summary}", file=sys.stderr)

    return {
        "sti": sti,
        "vix": vix,
        "us10y": us10y,
        "summary": summary,
    }
