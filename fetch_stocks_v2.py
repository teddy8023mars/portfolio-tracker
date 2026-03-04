#!/usr/bin/env python3
"""
A股投资组合数据获取脚本 v2
功能：
  1. 获取11只A股最新行情（昨开/昨收/今开/今收）
  2. 获取1年历史数据计算技术指标（RSI/MACD/KDJ/BOLL/ATR/WR等）
  3. 输出结构化 JSON 到 /home/ubuntu/stock_data.json
"""

import json
import sys
import time
from datetime import datetime, date

import numpy as np
import pandas as pd
import yfinance as yf

# ──────────────────────────────────────────────
# A股投资组合配置
# ──────────────────────────────────────────────
PORTFOLIO = [
    {"symbol": "601965.SS", "name": "中国汽研", "cost": 11.735},
    {"symbol": "600050.SS", "name": "中国联通", "cost": 4.272},
    {"symbol": "600759.SS", "name": "洲际油气", "cost": 3.188},
    {"symbol": "601857.SS", "name": "中国石油", "cost": 10.091},
    {"symbol": "601952.SS", "name": "苏垦农发", "cost": 11.682},
    {"symbol": "688472.SS", "name": "阿特斯",   "cost": 15.957},
    {"symbol": "688553.SS", "name": "汇宇制药", "cost": 12.751},
    {"symbol": "000657.SZ", "name": "中钨高新", "cost": 44.923},
    {"symbol": "002625.SZ", "name": "光启技术", "cost": 40.623},
    {"symbol": "300059.SZ", "name": "东方财富", "cost": 7.614},
    {"symbol": "300918.SZ", "name": "南山智尚", "cost": 22.733},
]

OUTPUT_PATH = "/home/ubuntu/stock_data.json"


# ──────────────────────────────────────────────
# 技术指标计算
# ──────────────────────────────────────────────

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
    histogram = (dif - dea) * 2  # MACD柱 = (DIF-DEA)*2
    return dif, dea, histogram


def calc_kdj(high, low, close, n=9, m1=3, m2=3):
    """计算KDJ指标"""
    lowest_low = low.rolling(window=n).min()
    highest_high = high.rolling(window=n).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low).replace(0, 1e-10) * 100
    k = rsv.ewm(alpha=1/m1, adjust=False).mean()
    d = k.ewm(alpha=1/m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def calc_bollinger(series, window=20, num_std=2):
    mid = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def calc_atr(high, low, close, period=14):
    """计算ATR（平均真实波幅）"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calc_wr(high, low, close, period=14):
    """计算威廉指标 WR"""
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    wr = (highest_high - close) / (highest_high - lowest_low).replace(0, 1e-10) * 100
    return wr


def find_cross(fast_series, slow_series, lookback=5):
    """检测金叉/死叉"""
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


def find_support_resistance(close, high, low, window=20):
    """计算支撑位和压力位"""
    recent_close = close.iloc[-window:]
    recent_high = high.iloc[-window:]
    recent_low = low.iloc[-window:]

    # 简单方法：用近期高低点
    resistance_1 = float(recent_high.max())
    resistance_2 = float(recent_high.nlargest(3).iloc[-1]) if len(recent_high) >= 3 else resistance_1
    support_1 = float(recent_low.min())
    support_2 = float(recent_low.nsmallest(3).iloc[-1]) if len(recent_low) >= 3 else support_1

    return {
        "resistance_1": resistance_1,
        "resistance_2": resistance_2,
        "support_1": support_1,
        "support_2": support_2,
    }


def analyze_technicals(hist):
    """计算所有技术指标，返回字典"""
    if hist is None or len(hist) < 30:
        return None

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    latest = float(close.iloc[-1])

    # 均线
    ma5 = calc_ma(close, 5)
    ma10 = calc_ma(close, 10)
    ma20 = calc_ma(close, 20)
    ma60 = calc_ma(close, 60)

    ma5_val = float(ma5.iloc[-1])
    ma10_val = float(ma10.iloc[-1])
    ma20_val = float(ma20.iloc[-1])
    ma60_val = float(ma60.iloc[-1]) if not np.isnan(ma60.iloc[-1]) else None
    ma20_dev = (latest - ma20_val) / ma20_val * 100 if ma20_val else 0

    if ma5_val > ma10_val > ma20_val:
        ma_trend = "多头排列（强势）"
    elif ma5_val < ma10_val < ma20_val:
        ma_trend = "空头排列（弱势）"
    else:
        ma_trend = "均线交织（震荡）"

    # RSI
    rsi6 = calc_rsi(close, 6)
    rsi14 = calc_rsi(close, 14)
    rsi6_val = float(rsi6.iloc[-1])
    rsi14_val = float(rsi14.iloc[-1])

    if rsi14_val > 80:
        rsi_status = "严重超买"
    elif rsi14_val > 70:
        rsi_status = "超买"
    elif rsi14_val < 20:
        rsi_status = "严重超卖"
    elif rsi14_val < 30:
        rsi_status = "超卖"
    else:
        rsi_status = "中性"

    # MACD
    dif, dea, macd_hist = calc_macd(close)
    dif_val = float(dif.iloc[-1])
    dea_val = float(dea.iloc[-1])
    macd_hist_val = float(macd_hist.iloc[-1])
    macd_cross, macd_cross_days = find_cross(dif, dea)

    if macd_cross == "golden":
        macd_status = f"金叉（{macd_cross_days}日前）"
    elif macd_cross == "death":
        macd_status = f"死叉（{macd_cross_days}日前）"
    elif macd_hist_val > 0:
        macd_status = "多头运行"
    else:
        macd_status = "空头运行"

    # KDJ
    k, d, j = calc_kdj(high, low, close)
    k_val = float(k.iloc[-1])
    d_val = float(d.iloc[-1])
    j_val = float(j.iloc[-1])
    kdj_cross, kdj_cross_days = find_cross(k, d)

    if kdj_cross == "golden":
        kdj_status = f"金叉（{kdj_cross_days}日前）"
    elif kdj_cross == "death":
        kdj_status = f"死叉（{kdj_cross_days}日前）"
    elif j_val > 80:
        kdj_status = "超买区域"
    elif j_val < 20:
        kdj_status = "超卖区域"
    else:
        kdj_status = "中性区域"

    # 布林带
    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    bb_upper_val = float(bb_upper.iloc[-1])
    bb_mid_val = float(bb_mid.iloc[-1])
    bb_lower_val = float(bb_lower.iloc[-1])
    bb_width = bb_upper_val - bb_lower_val
    bb_position = (latest - bb_lower_val) / bb_width * 100 if bb_width > 0 else 50

    # ATR
    atr = calc_atr(high, low, close)
    atr_val = float(atr.iloc[-1])
    atr_pct = atr_val / latest * 100  # ATR占价格百分比

    # 威廉指标
    wr6 = calc_wr(high, low, close, 6)
    wr14 = calc_wr(high, low, close, 14)
    wr6_val = float(wr6.iloc[-1])
    wr14_val = float(wr14.iloc[-1])

    if wr14_val < 20:
        wr_status = "超买"
    elif wr14_val > 80:
        wr_status = "超卖"
    else:
        wr_status = "中性"

    # 成交量分析
    vol_today = float(volume.iloc[-1])
    vol_5d = float(volume.iloc[-5:].mean())
    vol_10d = float(volume.iloc[-10:].mean())
    vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1.0
    vol_ratio_10d = vol_today / vol_10d if vol_10d > 0 else 1.0

    if vol_ratio > 2.0:
        vol_status = "显著放量"
    elif vol_ratio > 1.5:
        vol_status = "温和放量"
    elif vol_ratio < 0.5:
        vol_status = "显著缩量"
    elif vol_ratio < 0.7:
        vol_status = "温和缩量"
    else:
        vol_status = "量能平稳"

    # 支撑位和压力位
    sr = find_support_resistance(close, high, low)

    # ── 综合评分 (基准50分) ──
    score = 50

    # RSI 评分
    if rsi14_val > 60:
        score += 5
    elif rsi14_val < 40:
        score -= 5
    if rsi14_val > 80:
        score -= 5  # 超买风险
    elif rsi14_val < 20:
        score += 5  # 超卖反弹机会

    # MACD 评分
    if macd_cross == "golden":
        score += 15
    elif macd_cross == "death":
        score -= 15
    elif macd_hist_val > 0:
        score += 5
    else:
        score -= 5

    # KDJ 评分
    if kdj_cross == "golden":
        score += 10
    elif kdj_cross == "death":
        score -= 10

    # 均线评分
    if "多头" in ma_trend:
        score += 15
    elif "空头" in ma_trend:
        score -= 15

    # 布林带评分
    if bb_position > 95:
        score -= 5
    elif bb_position < 5:
        score += 5

    # 量价配合
    if vol_ratio > 1.5 and float(close.iloc[-1]) > float(close.iloc[-2]):
        score += 10
    elif vol_ratio > 1.5 and float(close.iloc[-1]) < float(close.iloc[-2]):
        score -= 5

    # WR 评分
    if wr14_val > 80:
        score += 5  # 超卖
    elif wr14_val < 20:
        score -= 5  # 超买

    score = max(0, min(100, score))

    if score >= 70:
        signal = "偏多，可持股待涨"
        signal_color = "#22c55e"
    elif score >= 50:
        signal = "中性，观望为主"
        signal_color = "#94a3b8"
    elif score >= 35:
        signal = "偏空，注意风险"
        signal_color = "#ffa726"
    else:
        signal = "强烈偏空，建议减仓"
        signal_color = "#ef4444"

    # 操作建议
    if score >= 70:
        if vol_ratio > 1.5:
            advice = "量价齐升，可适当加仓"
        else:
            advice = "趋势向好，持股待涨"
    elif score >= 50:
        if "金叉" in macd_status:
            advice = "MACD金叉，可关注买入机会"
        elif "金叉" in kdj_status:
            advice = "KDJ金叉，短线可关注"
        else:
            advice = "震荡整理，观望为主"
    elif score >= 35:
        advice = "趋势偏弱，谨慎操作"
    else:
        advice = "多指标偏空，建议减仓或止损"

    return {
        "ma5": ma5_val, "ma10": ma10_val, "ma20": ma20_val, "ma60": ma60_val,
        "ma20_dev": round(ma20_dev, 2), "ma_trend": ma_trend,
        "rsi6": round(rsi6_val, 2), "rsi14": round(rsi14_val, 2), "rsi_status": rsi_status,
        "dif": round(dif_val, 4), "dea": round(dea_val, 4),
        "macd_hist": round(macd_hist_val, 4), "macd_status": macd_status, "macd_cross": macd_cross,
        "k": round(k_val, 2), "d": round(d_val, 2), "j": round(j_val, 2),
        "kdj_status": kdj_status, "kdj_cross": kdj_cross,
        "bb_upper": round(bb_upper_val, 3), "bb_mid": round(bb_mid_val, 3),
        "bb_lower": round(bb_lower_val, 3), "bb_position": round(bb_position, 1),
        "atr": round(atr_val, 3), "atr_pct": round(atr_pct, 2),
        "wr6": round(wr6_val, 2), "wr14": round(wr14_val, 2), "wr_status": wr_status,
        "vol_today": vol_today, "vol_5d": round(vol_5d, 0), "vol_10d": round(vol_10d, 0),
        "vol_ratio": round(vol_ratio, 2), "vol_ratio_10d": round(vol_ratio_10d, 2),
        "vol_status": vol_status,
        "support_1": round(sr["support_1"], 3), "support_2": round(sr["support_2"], 3),
        "resistance_1": round(sr["resistance_1"], 3), "resistance_2": round(sr["resistance_2"], 3),
        "score": score, "signal": signal, "signal_color": signal_color,
        "advice": advice,
    }


def fetch_quotes(symbol, retries=3):
    """获取最近行情数据"""
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if hist.empty or len(hist) < 2:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return None

            today_row = hist.iloc[-1]
            prev_row = hist.iloc[-2]

            trade_date = str(hist.index[-1].date())

            return {
                "prev_open": round(float(prev_row["Open"]), 3),
                "prev_close": round(float(prev_row["Close"]), 3),
                "today_open": round(float(today_row["Open"]), 3),
                "current_price": round(float(today_row["Close"]), 3),
                "today_high": round(float(today_row["High"]), 3),
                "today_low": round(float(today_row["Low"]), 3),
                "volume": float(today_row["Volume"]),
                "change": round(float(today_row["Close"]) - float(prev_row["Close"]), 3),
                "change_pct": round((float(today_row["Close"]) - float(prev_row["Close"])) / float(prev_row["Close"]) * 100, 2),
                "trade_date": trade_date,
            }
        except Exception as e:
            print(f"  ⚠️ 获取 {symbol} 行情失败 (第{attempt+1}次): {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(3)
    return None


def fetch_history(symbol, period="1y", retries=3):
    """获取历史数据用于技术分析"""
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            if hist.empty:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return None
            return hist
        except Exception as e:
            print(f"  ⚠️ 获取 {symbol} 历史数据失败 (第{attempt+1}次): {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(3)
    return None


def main():
    print(f"[{datetime.now()}] 开始获取A股投资组合数据 ...", file=sys.stderr)
    today_str = str(date.today())

    results = []
    for stock in PORTFOLIO:
        sym = stock["symbol"]
        name = stock["name"]
        cost = stock["cost"]

        print(f"  📊 正在获取 {name} ({sym}) ...", file=sys.stderr)

        # 获取行情
        quotes = fetch_quotes(sym)
        if quotes is None:
            print(f"  ❌ 无法获取 {name} ({sym}) 行情数据，跳过", file=sys.stderr)
            continue

        # 检查日期
        is_delayed = quotes["trade_date"] != today_str
        if is_delayed:
            print(f"  ⚠️ {name} 数据日期为 {quotes['trade_date']}，非当日数据（可能为非交易日或延迟）", file=sys.stderr)

        # 获取历史数据并计算技术指标
        hist = fetch_history(sym, period="1y")
        tech = analyze_technicals(hist)
        if tech:
            print(f"  ✅ {name}: 评分 {tech['score']} ({tech['signal']})", file=sys.stderr)
        else:
            print(f"  ⚠️ {name}: 技术指标数据不足", file=sys.stderr)

        # 盈亏计算
        current_price = quotes["current_price"]
        profit_pct = (current_price - cost) / cost * 100

        result = {
            "symbol": sym,
            "name": name,
            "cost": cost,
            "current_price": current_price,
            "profit_pct": round(profit_pct, 2),
            "quotes": quotes,
            "technicals": tech,
            "is_delayed": is_delayed,
            "trade_date": quotes["trade_date"],
        }
        results.append(result)

        # 避免请求过快被限流
        time.sleep(1)

    if not results:
        print("❌ 未获取到任何数据，退出", file=sys.stderr)
        sys.exit(1)

    output = {
        "generated_at": datetime.now().isoformat(),
        "today": today_str,
        "stock_count": len(results),
        "stocks": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[{datetime.now()}] ✅ 数据已保存到 {OUTPUT_PATH}（共 {len(results)} 只股票）", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 数据获取失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
