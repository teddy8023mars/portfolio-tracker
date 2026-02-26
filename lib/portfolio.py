from datetime import datetime, date
import yfinance as yf
from lib import config


def calc_tx_fee(amount):
    f = config.fees()
    commission = max(amount * f["commission_rate"], f["min_commission"])
    return commission + amount * f["clearing_fee_rate"] + amount * f["trading_fee_rate"] + f["settlement_fee"]


def holding_days(buy_date_str):
    return (date.today() - datetime.strptime(buy_date_str, "%Y-%m-%d").date()).days


def cpf_opportunity_cost(investment, days):
    return investment * config.get("cpf_oa_rate") * (days / 365)


def breakeven_price(cost, shares):
    buy_amount = cost * shares
    total_buy_cost = buy_amount + calc_tx_fee(buy_amount)
    target = cost
    for _ in range(20):
        sell_amt = target * shares
        net = sell_amt - calc_tx_fee(sell_amt)
        if net < total_buy_cost:
            target *= total_buy_cost / net
        else:
            break
    return target


def fetch_quotes(symbol):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    if hist.empty or len(hist) < 2:
        return None
    today_row = hist.iloc[-1]
    prev_row = hist.iloc[-2]
    return {
        "prev_open":  float(prev_row["Open"]),
        "prev_close": float(prev_row["Close"]),
        "open":       float(today_row["Open"]),
        "close":      float(today_row["Close"]),
        "high":       float(today_row["High"]),
        "low":        float(today_row["Low"]),
        "change":     float(today_row["Close"]) - float(prev_row["Close"]),
        "change_pct": (float(today_row["Close"]) - float(prev_row["Close"])) / float(prev_row["Close"]) * 100,
    }


def fetch_history(symbol, period="60d"):
    """Fetch longer history for technical analysis."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
    if hist.empty:
        return None
    return hist


def trading_suggestion(current, target, cost):
    if current >= target:
        d = (current - target) / target * 100
        return f"✅ 可卖出 (高于目标 {d:.2f}%)"
    elif current >= target * 0.995:
        d = (target - current) / target * 100
        return f"⚠️ 接近目标 (差 {d:.2f}%)"
    elif current >= cost:
        return "⏳ 持有 (高于成本但未达目标)"
    else:
        loss = (current - cost) / cost * 100
        if loss <= -5:
            return f"🔻 考虑止损 (亏损 {abs(loss):.2f}%)"
        return f"⏳ 持有 (亏损 {abs(loss):.2f}%)"
