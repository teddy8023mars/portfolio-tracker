"""Technical indicators: MA, RSI, MACD, Bollinger Bands, and composite scoring."""

import pandas as pd
from lib import config


def calc_ma(series, window):
    return series.rolling(window=window).mean()


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    histogram = dif - dea
    return dif, dea, histogram


def calc_bollinger(series, window=20, num_std=2):
    mid = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def _find_cross(fast_series, slow_series, lookback=5):
    """Return (cross_type, days_ago). cross_type: 'golden', 'death', or None."""
    for i in range(1, min(lookback + 1, len(fast_series))):
        idx = -i
        prev = -(i + 1)
        if prev < -len(fast_series):
            break
        f_now, f_prev = fast_series.iloc[idx], fast_series.iloc[prev]
        s_now, s_prev = slow_series.iloc[idx], slow_series.iloc[prev]
        if f_prev <= s_prev and f_now > s_now:
            return "golden", i - 1
        if f_prev >= s_prev and f_now < s_now:
            return "death", i - 1
    return None, None


def analyze(hist):
    """
    Given a DataFrame from yfinance (60d history), compute all technical indicators.
    Returns a dict with indicator values and composite score.
    """
    if hist is None or len(hist) < 26:
        return None

    close = hist["Close"]
    volume = hist["Volume"]
    latest = float(close.iloc[-1])

    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)

    ma5_val = float(ma5.iloc[-1])
    ma10_val = float(ma10.iloc[-1])
    ma20_val = float(ma20.iloc[-1])
    ma20_dev = (latest - ma20_val) / ma20_val * 100 if ma20_val else 0

    if ma5_val > ma10_val > ma20_val:
        ma_trend = "多头排列（强势）"
    elif ma5_val < ma10_val < ma20_val:
        ma_trend = "空头排列（弱势）"
    else:
        ma_trend = "均线交织（震荡）"

    rsi6 = calc_rsi(close, 6)
    rsi14 = calc_rsi(close, 14)
    rsi14_val = float(rsi14.iloc[-1])
    rsi6_val = float(rsi6.iloc[-1])

    dif, dea, histogram = calc_macd(close)
    dif_val = float(dif.iloc[-1])
    dea_val = float(dea.iloc[-1])
    hist_val = float(histogram.iloc[-1])
    macd_cross, macd_cross_days = _find_cross(dif, dea)

    if macd_cross == "golden":
        macd_status = f"金叉（{macd_cross_days}日前）"
    elif macd_cross == "death":
        macd_status = f"死叉（{macd_cross_days}日前）"
    elif hist_val > 0:
        macd_status = "多头运行"
    else:
        macd_status = "空头运行"

    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    bb_upper_val = float(bb_upper.iloc[-1])
    bb_mid_val = float(bb_mid.iloc[-1])
    bb_lower_val = float(bb_lower.iloc[-1])
    bb_width = bb_upper_val - bb_lower_val
    bb_position = (latest - bb_lower_val) / bb_width * 100 if bb_width > 0 else 50

    vol_today = float(volume.iloc[-1])
    vol_5d = float(volume.iloc[-5:].mean())
    vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1.0

    # ── composite score (base 50) ──
    w = config.scoring_weights()
    score = 50

    if rsi14_val > 60:
        score += w.get("rsi_strong", 5)
    elif rsi14_val < 40:
        score += w.get("rsi_weak", -5)

    if macd_cross == "golden":
        score += w.get("macd_golden", 15)
    elif macd_cross == "death":
        score += w.get("macd_death", -15)
    elif hist_val > 0:
        score += 5
    else:
        score -= 5

    if "多头" in ma_trend:
        score += w.get("ma_bull", 15)
    elif "空头" in ma_trend:
        score += w.get("ma_bear", -15)

    if bb_position > 95:
        score += w.get("bb_upper", -5)
    elif bb_position < 5:
        score += w.get("bb_lower", 5)

    if vol_ratio > 1.5 and float(close.iloc[-1]) > float(close.iloc[-2]):
        score += w.get("volume_up", 10)

    score = max(0, min(100, score))

    if score >= 70:
        signal = "偏多，持股待涨"
        signal_color = "var(--green)"
    elif score >= 50:
        signal = "中性，观望为主"
        signal_color = "var(--text-muted)"
    else:
        signal = "偏空，注意风险"
        signal_color = "var(--red)"

    return {
        "ma5": ma5_val, "ma10": ma10_val, "ma20": ma20_val,
        "ma20_dev": ma20_dev, "ma_trend": ma_trend,
        "rsi6": rsi6_val, "rsi14": rsi14_val,
        "dif": dif_val, "dea": dea_val, "macd_hist": hist_val,
        "macd_status": macd_status, "macd_cross": macd_cross,
        "bb_upper": bb_upper_val, "bb_mid": bb_mid_val, "bb_lower": bb_lower_val,
        "bb_position": bb_position,
        "vol_today": vol_today, "vol_5d": vol_5d, "vol_ratio": vol_ratio,
        "score": score, "signal": signal, "signal_color": signal_color,
    }
