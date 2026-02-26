"""
Risk Analytics Module — Portfolio risk metrics and analysis.

Provides:
  - Historical volatility (daily & annualized)
  - Maximum drawdown
  - Value at Risk (VaR) at 95% and 99% confidence levels
  - Sharpe ratio
  - Correlation matrix across portfolio holdings
  - Portfolio-level risk aggregation
"""

import sys
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf


# ── Constants ────────────────────────────────────────────────────────────────

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.032  # Singapore 10Y govt bond ~3.2%


# ── Single-Stock Risk Metrics ────────────────────────────────────────────────

def calc_daily_returns(hist: pd.DataFrame) -> pd.Series:
    """Calculate daily log returns from a yfinance history DataFrame."""
    close = hist["Close"].dropna()
    if len(close) < 2:
        return pd.Series(dtype=float)
    return np.log(close / close.shift(1)).dropna()


def calc_volatility(returns: pd.Series) -> dict:
    """
    Calculate daily and annualized volatility.
    Returns dict with daily_vol, annual_vol (both as percentages).
    """
    if len(returns) < 5:
        return {"daily_vol": None, "annual_vol": None}
    daily_vol = float(returns.std())
    annual_vol = daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)
    return {
        "daily_vol": round(daily_vol * 100, 4),
        "annual_vol": round(annual_vol * 100, 2),
    }


def calc_max_drawdown(hist: pd.DataFrame) -> dict:
    """
    Calculate maximum drawdown from price history.
    Returns dict with max_drawdown (%), peak_date, trough_date.
    """
    close = hist["Close"].dropna()
    if len(close) < 2:
        return {"max_drawdown": None, "peak_date": None, "trough_date": None}

    cummax = close.cummax()
    drawdown = (close - cummax) / cummax

    trough_idx = drawdown.idxmin()
    peak_idx = close.loc[:trough_idx].idxmax()

    mdd = float(drawdown.min()) * 100  # negative percentage

    return {
        "max_drawdown": round(mdd, 2),
        "peak_date": peak_idx.strftime("%Y-%m-%d") if hasattr(peak_idx, "strftime") else str(peak_idx),
        "trough_date": trough_idx.strftime("%Y-%m-%d") if hasattr(trough_idx, "strftime") else str(trough_idx),
    }


def calc_var(returns: pd.Series, confidence_levels: list = None) -> dict:
    """
    Calculate historical Value at Risk (VaR).
    Returns dict with VaR at each confidence level (as negative percentages).
    """
    if confidence_levels is None:
        confidence_levels = [0.95, 0.99]

    if len(returns) < 10:
        return {f"var_{int(cl*100)}": None for cl in confidence_levels}

    result = {}
    for cl in confidence_levels:
        alpha = 1 - cl
        var_value = float(np.percentile(returns, alpha * 100))
        result[f"var_{int(cl*100)}"] = round(var_value * 100, 4)
    return result


def calc_sharpe_ratio(returns: pd.Series, risk_free_rate: float = None) -> Optional[float]:
    """
    Calculate annualized Sharpe ratio.
    Uses Singapore 10Y govt bond rate as risk-free rate by default.
    """
    if risk_free_rate is None:
        risk_free_rate = RISK_FREE_RATE

    if len(returns) < 20:
        return None

    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = returns - daily_rf
    mean_excess = float(excess_returns.mean())
    std_excess = float(excess_returns.std())

    if std_excess == 0:
        return None

    sharpe = (mean_excess / std_excess) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return round(sharpe, 3)


def calc_sortino_ratio(returns: pd.Series, risk_free_rate: float = None) -> Optional[float]:
    """
    Calculate annualized Sortino ratio (downside risk only).
    """
    if risk_free_rate is None:
        risk_free_rate = RISK_FREE_RATE

    if len(returns) < 20:
        return None

    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = returns - daily_rf
    mean_excess = float(excess_returns.mean())

    downside = returns[returns < daily_rf] - daily_rf
    if len(downside) < 2:
        return None
    downside_std = float(downside.std())

    if downside_std == 0:
        return None

    sortino = (mean_excess / downside_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return round(sortino, 3)


# ── Portfolio-Level Risk ─────────────────────────────────────────────────────

def calc_correlation_matrix(symbols: list, period: str = "120d") -> Optional[pd.DataFrame]:
    """
    Calculate correlation matrix of daily returns across symbols.
    Returns a DataFrame with symbol labels.
    """
    all_returns = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period=period)
            if hist is not None and len(hist) > 10:
                rets = calc_daily_returns(hist)
                all_returns[sym] = rets
        except Exception as e:
            print(f"  ⚠️ 相关性数据获取失败 {sym}: {e}", file=sys.stderr)

    if len(all_returns) < 2:
        return None

    df = pd.DataFrame(all_returns).dropna()
    if len(df) < 10:
        return None

    return df.corr().round(4)


def calc_portfolio_volatility(
    symbols: list,
    weights: list,
    period: str = "120d",
) -> Optional[dict]:
    """
    Calculate portfolio-level volatility using covariance matrix.
    weights: list of floats summing to 1.0 (proportion of each stock).
    Returns dict with portfolio annual volatility and diversification benefit.
    """
    all_returns = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period=period)
            if hist is not None and len(hist) > 10:
                rets = calc_daily_returns(hist)
                all_returns[sym] = rets
        except Exception:
            pass

    if len(all_returns) != len(symbols):
        return None

    df = pd.DataFrame(all_returns).dropna()
    if len(df) < 10:
        return None

    w = np.array(weights)
    cov_matrix = df.cov() * TRADING_DAYS_PER_YEAR
    port_variance = float(w @ cov_matrix.values @ w)
    port_vol = np.sqrt(port_variance)

    # Weighted average of individual volatilities (no diversification)
    individual_vols = df.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    undiversified_vol = float(np.sum(w * individual_vols.values))
    diversification_benefit = undiversified_vol - port_vol

    return {
        "portfolio_annual_vol": round(port_vol * 100, 2),
        "undiversified_vol": round(undiversified_vol * 100, 2),
        "diversification_benefit": round(diversification_benefit * 100, 2),
    }


# ── Main Analysis Entry Point ────────────────────────────────────────────────

def analyze_stock_risk(symbol: str, period: str = "120d") -> Optional[dict]:
    """
    Run full risk analysis for a single stock.
    Returns dict with all risk metrics.
    """
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist is None or len(hist) < 20:
            print(f"  ⚠️ 风险分析数据不足 {symbol}", file=sys.stderr)
            return None

        returns = calc_daily_returns(hist)
        vol = calc_volatility(returns)
        mdd = calc_max_drawdown(hist)
        var = calc_var(returns)
        sharpe = calc_sharpe_ratio(returns)
        sortino = calc_sortino_ratio(returns)

        return {
            **vol,
            **mdd,
            **var,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "data_points": len(returns),
            "period": period,
        }
    except Exception as e:
        print(f"  ⚠️ 风险分析失败 {symbol}: {e}", file=sys.stderr)
        return None


def analyze_portfolio_risk(portfolio: list, period: str = "120d") -> dict:
    """
    Run full risk analysis for the entire portfolio.

    Args:
        portfolio: list of dicts with keys: symbol, name, cost, shares
        period: yfinance period string

    Returns:
        dict with per-stock risk, correlation matrix, and portfolio-level metrics.
    """
    symbols = [s["symbol"] for s in portfolio]
    names = {s["symbol"]: s["name"] for s in portfolio}

    # Calculate portfolio weights by current investment value
    investments = {}
    for s in portfolio:
        investments[s["symbol"]] = s["cost"] * s["shares"]
    total_inv = sum(investments.values())
    weights = [investments[sym] / total_inv for sym in symbols]

    # Per-stock risk
    stock_risks = {}
    for sym in symbols:
        print(f"  📊 风险分析: {names[sym]} ({sym})", file=sys.stderr)
        risk = analyze_stock_risk(sym, period)
        if risk:
            risk["name"] = names[sym]
            risk["weight"] = round(investments[sym] / total_inv * 100, 2)
        stock_risks[sym] = risk

    # Correlation matrix
    print("  📊 计算相关性矩阵 ...", file=sys.stderr)
    corr = calc_correlation_matrix(symbols, period)

    # Portfolio-level volatility
    print("  📊 计算组合波动率 ...", file=sys.stderr)
    port_vol = calc_portfolio_volatility(symbols, weights, period)

    # Risk rating
    risk_level = "—"
    risk_color = "var(--text-muted)"
    if port_vol:
        pv = port_vol["portfolio_annual_vol"]
        if pv < 10:
            risk_level = "低风险"
            risk_color = "var(--green)"
        elif pv < 20:
            risk_level = "中等风险"
            risk_color = "var(--text-muted)"
        elif pv < 30:
            risk_level = "较高风险"
            risk_color = "var(--red)"
        else:
            risk_level = "高风险"
            risk_color = "var(--red)"

    return {
        "stock_risks": stock_risks,
        "correlation": corr,
        "portfolio_vol": port_vol,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "weights": {sym: round(w * 100, 2) for sym, w in zip(symbols, weights)},
    }
