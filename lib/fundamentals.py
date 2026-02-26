"""Fundamental data: PE, PB, ROE, dividend yield, 52-week high/low, valuation rating.
Uses local JSON cache — refreshes only when data is older than 7 days."""

import json
import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

_CACHE_PATH = Path(__file__).parent.parent / "output" / "fundamentals_cache.json"
_CACHE_MAX_AGE_DAYS = 7

SGX_BENCHMARKS = {
    "bank":  {"pe": 11.0, "pb": 1.4, "div_yield": 4.5, "roe": 12.0},
    "reit":  {"pe": 18.0, "pb": 0.9, "div_yield": 5.5, "roe": 8.0},
    "etf":   {"pe": 14.0, "pb": 1.2, "div_yield": 3.5, "roe": 10.0},
}

STOCK_SECTOR = {
    "D05.SI":  "bank",
    "C38U.SI": "reit",
    "ES3.SI":  "etf",
}


def _load_cache():
    if _CACHE_PATH.exists():
        try:
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            age = (datetime.now() - cached_at).days
            if age < _CACHE_MAX_AGE_DAYS:
                return data.get("stocks", {})
        except Exception:
            pass
    return None


def _save_cache(stocks):
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps({"cached_at": datetime.now().isoformat(), "stocks": stocks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _valuation_rating(metric, benchmark, higher_is_cheaper=False):
    if metric is None or benchmark is None:
        return "—", "var(--text-muted)"
    ratio = metric / benchmark if benchmark else 1
    if higher_is_cheaper:
        if ratio >= 1.3:
            return "低估", "var(--green)"
        if ratio >= 0.8:
            return "合理", "var(--text-muted)"
        return "高估", "var(--red)"
    else:
        if ratio <= 0.7:
            return "低估", "var(--green)"
        if ratio <= 1.3:
            return "合理", "var(--text-muted)"
        return "高估", "var(--red)"


def fetch_fundamentals(symbols):
    """
    Fetch fundamental data for a list of symbols.
    Returns dict: {symbol: {pe, pb, roe, div_yield, market_cap, week52_high, week52_low, ...}}
    Uses cache if fresh enough.
    """
    cached = _load_cache()
    if cached and all(s in cached for s in symbols):
        print("  📋 基本面数据来自缓存", file=sys.stderr)
        return cached

    result = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info
            sector = STOCK_SECTOR.get(sym, "etf")
            bench = SGX_BENCHMARKS.get(sector, {})

            pe = info.get("trailingPE") or info.get("forwardPE")
            pb = info.get("priceToBook")
            roe = (info.get("returnOnEquity") or 0) * 100 if info.get("returnOnEquity") else None
            div_yield = (info.get("dividendYield") or 0) * 100 if info.get("dividendYield") else None
            market_cap = info.get("marketCap")
            w52_high = info.get("fiftyTwoWeekHigh")
            w52_low = info.get("fiftyTwoWeekLow")
            current = info.get("currentPrice") or info.get("regularMarketPrice")

            pe_rating, pe_color = _valuation_rating(pe, bench.get("pe"))
            pb_rating, pb_color = _valuation_rating(pb, bench.get("pb"))
            div_rating, div_color = _valuation_rating(div_yield, bench.get("div_yield"), higher_is_cheaper=True)

            overall_scores = []
            if pe and bench.get("pe"):
                overall_scores.append(pe / bench["pe"])
            if pb and bench.get("pb"):
                overall_scores.append(pb / bench["pb"])

            if overall_scores:
                avg_ratio = sum(overall_scores) / len(overall_scores)
                if avg_ratio <= 0.7:
                    overall = "低估"
                    overall_color = "var(--green)"
                elif avg_ratio <= 1.3:
                    overall = "合理"
                    overall_color = "var(--text-muted)"
                else:
                    overall = "高估"
                    overall_color = "var(--red)"
            else:
                overall, overall_color = "—", "var(--text-muted)"

            w52_pos = None
            if w52_high and w52_low and current and w52_high != w52_low:
                w52_pos = (current - w52_low) / (w52_high - w52_low) * 100

            result[sym] = {
                "pe": pe, "pb": pb, "roe": roe, "div_yield": div_yield,
                "market_cap": market_cap,
                "week52_high": w52_high, "week52_low": w52_low, "week52_pos": w52_pos,
                "sector": sector,
                "bench_pe": bench.get("pe"), "bench_pb": bench.get("pb"),
                "bench_div": bench.get("div_yield"), "bench_roe": bench.get("roe"),
                "pe_rating": pe_rating, "pe_color": pe_color,
                "pb_rating": pb_rating, "pb_color": pb_color,
                "div_rating": div_rating, "div_color": div_color,
                "overall": overall, "overall_color": overall_color,
            }
        except Exception as e:
            print(f"  ⚠️ 基本面获取失败 {sym}: {e}", file=sys.stderr)
            result[sym] = None

    _save_cache(result)
    print("  📋 基本面数据已更新并缓存", file=sys.stderr)
    return result
