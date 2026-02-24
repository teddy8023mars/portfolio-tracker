#!/usr/bin/env python3
"""
CPF 投资组合每日报告 — 微信推送版
功能：
  1. 获取 DBS / CapitaLand / STI ETF 最新行情（昨开/昨收/今开/今收）
  2. 生成完整 HTML 格式报告（持仓汇总表 + 个股详情 + 真实盈亏分析）
  3. 上传 HTML 报告获取公开 CDN 链接
  4. 通过 Server酱（ServerChan）推送链接 + Markdown 摘要到微信
"""

import os
import sys
import json
import tempfile
import subprocess
import requests
import yfinance as yf
from datetime import datetime, date

# ──────────────────────────────────────────────
# 投资组合配置
# ──────────────────────────────────────────────
PORTFOLIO = [
    {"symbol": "D05.SI",  "name": "DBS",        "cost": 54.59, "shares": 100,  "buy_date": "2025-10-28"},
    {"symbol": "C38U.SI", "name": "CapitaLand", "cost": 2.45,  "shares": 1900, "buy_date": "2025-10-28"},
    {"symbol": "ES3.SI",  "name": "STI ETF",    "cost": 4.63,  "shares": 1238, "buy_date": "2025-10-28"},
]

# CPF 参数
CPF_OA_RATE = 0.035          # 3.5% p.a.
INVESTMENT_AMOUNT = 15935    # 投资总额

# DBS Vickers 费用参数
COMMISSION_RATE   = 0.0018   # 0.18%
MIN_COMMISSION    = 27.25
CLEARING_FEE_RATE = 0.000325 # 0.0325%
TRADING_FEE_RATE  = 0.000075 # 0.0075%
SETTLEMENT_FEE    = 0.35

# 已收股息
DIVIDENDS_RECEIVED = {"DBS": 75.0}

# Server酱 SendKey
SENDKEY = "SCT315967T2bf8axJU3yL5TQK8FXM0eKAv"

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def calc_tx_fee(amount):
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    return commission + amount * CLEARING_FEE_RATE + amount * TRADING_FEE_RATE + SETTLEMENT_FEE


def holding_days(buy_date_str):
    return (date.today() - datetime.strptime(buy_date_str, "%Y-%m-%d").date()).days


def cpf_opportunity_cost(investment, days):
    return investment * CPF_OA_RATE * (days / 365)


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
    """返回 dict: prev_open, prev_close, open, close, change, change_pct"""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    if hist.empty or len(hist) < 2:
        return None

    today_row = hist.iloc[-1]
    prev_row  = hist.iloc[-2]

    close      = float(today_row["Close"])
    open_price = float(today_row["Open"])
    prev_close = float(prev_row["Close"])
    prev_open  = float(prev_row["Open"])
    change     = close - prev_close
    change_pct = (change / prev_close) * 100

    return {
        "prev_open":  prev_open,
        "prev_close": prev_close,
        "open":       open_price,
        "close":      close,
        "change":     change,
        "change_pct": change_pct,
    }


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


# ──────────────────────────────────────────────
# HTML 报告生成
# ──────────────────────────────────────────────

def build_html(rows, totals, analyses):
    """rows: list of per-stock dicts, totals: dict, analyses: list of dicts"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 持仓汇总表行
    summary_rows = ""
    for r in rows:
        color = "#22c55e" if r["change"] >= 0 else "#ef4444"
        pnl_color = "#22c55e" if r["paper_profit"] >= 0 else "#ef4444"
        summary_rows += f"""
        <tr>
          <td>{r['name']}</td>
          <td>{r['shares']}</td>
          <td>${r['cost']:.2f}</td>
          <td>${r['close']:.4f}</td>
          <td>${r['target']:.4f}</td>
          <td style="color:{color}">{r['change']:+.4f} ({r['change_pct']:+.2f}%)</td>
          <td style="color:{pnl_color}">${r['paper_profit']:,.2f} ({r['paper_profit_pct']:+.2f}%)</td>
          <td>{r['suggestion']}</td>
        </tr>"""

    # 个股详情卡片
    detail_cards = ""
    for r in rows:
        q = r["quotes"]
        detail_cards += f"""
        <div class="card">
          <h3>{r['name']} ({r['symbol']})</h3>
          <table class="detail-table">
            <tr><td>昨日开盘</td><td>${q['prev_open']:.4f}</td><td>昨日收盘</td><td>${q['prev_close']:.4f}</td></tr>
            <tr><td>今日开盘</td><td>${q['open']:.4f}</td><td>今日收盘</td><td>${q['close']:.4f}</td></tr>
          </table>
        </div>"""

    # 盈亏分析行
    analysis_rows = ""
    for a in analyses:
        net_color = "#22c55e" if a["net_profit"] >= 0 else "#ef4444"
        div_received = DIVIDENDS_RECEIVED.get(a["name"], 0)
        div_row = f'<tr><td>已收股息</td><td style="color:#22c55e">+${div_received:.2f}</td></tr>' if div_received > 0 else ""
        analysis_rows += f"""
        <div class="card">
          <h3>{a['name']} — 如果今天卖出</h3>
          <table class="detail-table">
            <tr><td>投资金额</td><td>${a['investment']:,.2f}</td></tr>
            <tr><td>买入费用</td><td>${a['buy_fee']:.2f}</td></tr>
            <tr><td>当前市值</td><td>${a['current_value']:,.2f}</td></tr>
            <tr><td>账面收益</td><td>${a['paper_profit']:,.2f}</td></tr>
            <tr><td>卖出费用</td><td>-${a['sell_fee']:.2f}</td></tr>
            <tr><td>持有天数</td><td>{a['holding_days']} 天</td></tr>
            <tr><td>CPF机会成本 (3.5% p.a.)</td><td>-${a['cpf_cost']:.2f}</td></tr>
            {div_row}
            <tr style="font-weight:bold"><td>真实盈亏</td><td style="color:{net_color}">${a['net_profit']:,.2f} ({a['net_profit_pct']:+.2f}%)</td></tr>
          </table>
        </div>"""

    total_pnl_color = "#22c55e" if totals["net_profit"] >= 0 else "#ef4444"
    total_paper_color = "#22c55e" if totals["paper_profit"] >= 0 else "#ef4444"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CPF 投资组合报告 — {now_str}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background:#0f172a; color:#e2e8f0; padding:20px; }}
  h1 {{ text-align:center; margin-bottom:6px; font-size:1.5rem; }}
  .subtitle {{ text-align:center; color:#94a3b8; margin-bottom:20px; font-size:0.9rem; }}
  .section-title {{ font-size:1.15rem; margin:24px 0 12px; border-left:4px solid #3b82f6; padding-left:10px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:16px; font-size:0.85rem; }}
  th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid #1e293b; }}
  th {{ background:#1e293b; color:#94a3b8; font-weight:600; }}
  tr:hover {{ background:#1e293b55; }}
  .card {{ background:#1e293b; border-radius:10px; padding:16px; margin-bottom:14px; }}
  .card h3 {{ margin-bottom:10px; font-size:1rem; color:#60a5fa; }}
  .detail-table td {{ border-bottom:1px solid #334155; }}
  .totals {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px,1fr)); gap:12px; margin-bottom:20px; }}
  .total-card {{ background:#1e293b; border-radius:10px; padding:16px; text-align:center; }}
  .total-card .label {{ color:#94a3b8; font-size:0.8rem; }}
  .total-card .value {{ font-size:1.3rem; font-weight:700; margin-top:4px; }}
  .note {{ background:#1e293b; border-radius:10px; padding:16px; font-size:0.82rem; color:#94a3b8; line-height:1.7; }}
  .note strong {{ color:#e2e8f0; }}
</style>
</head>
<body>
<h1>📊 CPF 投资组合每日报告</h1>
<p class="subtitle">{now_str} (SGT)</p>

<!-- 总览 -->
<div class="totals">
  <div class="total-card"><div class="label">投资总额</div><div class="value">${totals['investment']:,.2f}</div></div>
  <div class="total-card"><div class="label">当前市值</div><div class="value">${totals['current_value']:,.2f}</div></div>
  <div class="total-card"><div class="label">账面收益</div><div class="value" style="color:{total_paper_color}">${totals['paper_profit']:,.2f} ({totals['paper_profit_pct']:+.2f}%)</div></div>
  <div class="total-card"><div class="label">真实盈亏（含费用+CPF成本）</div><div class="value" style="color:{total_pnl_color}">${totals['net_profit']:,.2f} ({totals['net_profit_pct']:+.2f}%)</div></div>
</div>

<!-- 持仓汇总表 -->
<h2 class="section-title">持仓汇总</h2>
<div style="overflow-x:auto;">
<table>
  <thead>
    <tr><th>产品</th><th>持仓</th><th>成本价</th><th>当前价</th><th>目标价</th><th>今日涨跌</th><th>账面收益</th><th>交易建议</th></tr>
  </thead>
  <tbody>{summary_rows}
  </tbody>
</table>
</div>

<!-- 个股行情详情 -->
<h2 class="section-title">个股行情详情</h2>
{detail_cards}

<!-- 真实盈亏分析 -->
<h2 class="section-title">真实盈亏分析（如果今天卖出）</h2>
{analysis_rows}

<!-- 总体真实盈亏 -->
<h2 class="section-title">总体真实盈亏</h2>
<div class="card">
  <table class="detail-table">
    <tr><td>账面收益</td><td>${totals['paper_profit']:,.2f}</td></tr>
    <tr><td>卖出费用合计</td><td>-${totals['sell_fee']:,.2f}</td></tr>
    <tr><td>CPF机会成本合计</td><td>-${totals['cpf_cost']:,.2f}</td></tr>
    <tr><td>已收股息合计</td><td style="color:#22c55e">+${totals['dividends']:,.2f}</td></tr>
    <tr style="font-weight:bold"><td>真实盈亏</td><td style="color:{total_pnl_color}">${totals['net_profit']:,.2f} ({totals['net_profit_pct']:+.2f}%)</td></tr>
  </table>
</div>

<!-- 说明 -->
<h2 class="section-title">说明</h2>
<div class="note">
  <strong>目标价格</strong>：卖出后不亏钱的最低价格（含所有交易费用）<br>
  <strong>真实盈亏</strong>：账面收益 − 卖出费用 − CPF机会成本 + 已收股息<br>
  <strong>CPF机会成本</strong>：使用 CPF OA 投资的机会成本 (3.5% p.a.)<br>
  <strong>交易费用</strong>：DBS Vickers 佣金 0.18% 或最低 $27.25 + 清算费 + 交易费 + 结算费<br>
  <strong>数据来源</strong>：Yahoo Finance（可能有 15 分钟延迟）
</div>
</body>
</html>"""
    return html


# ──────────────────────────────────────────────
# Markdown 摘要（用于 Server酱 正文）
# ──────────────────────────────────────────────

def build_markdown_summary(rows, totals):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## CPF 投资组合报告 {now_str}\n"]

    lines.append("| 产品 | 当前价 | 涨跌 | 账面收益 |")
    lines.append("|------|--------|------|----------|")
    for r in rows:
        sign = "📈" if r["change"] >= 0 else "📉"
        lines.append(
            f"| {r['name']} | ${r['close']:.2f} | {sign} {r['change']:+.2f} ({r['change_pct']:+.2f}%) | ${r['paper_profit']:,.2f} ({r['paper_profit_pct']:+.2f}%) |"
        )

    lines.append("")
    lines.append(f"**投资总额**: ${totals['investment']:,.2f}")
    lines.append(f"**当前市值**: ${totals['current_value']:,.2f}")
    pnl_emoji = "📈" if totals['paper_profit'] >= 0 else "📉"
    lines.append(f"**账面收益**: {pnl_emoji} ${totals['paper_profit']:,.2f} ({totals['paper_profit_pct']:+.2f}%)")
    net_emoji = "✅" if totals['net_profit'] >= 0 else "❌"
    lines.append(f"**真实盈亏**: {net_emoji} ${totals['net_profit']:,.2f} ({totals['net_profit_pct']:+.2f}%)")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 上传 HTML → 公开链接
# ──────────────────────────────────────────────

def upload_html(html_content):
    """将 HTML 写入临时文件，用 manus-upload-file 上传并返回 URL"""
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8")
    tmp.write(html_content)
    tmp.close()
    try:
        result = subprocess.run(
            ["manus-upload-file", tmp.name],
            capture_output=True, text=True, timeout=120
        )
        # manus-upload-file 输出多行，需要从中提取 CDN URL
        url = None
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if line.startswith("http"):
                url = line
            elif "CDN URL:" in line:
                url = line.split("CDN URL:", 1)[1].strip()
        if not url or not url.startswith("http"):
            raise RuntimeError(f"上传失败: stdout={result.stdout}, stderr={result.stderr}")
        return url
    finally:
        os.unlink(tmp.name)


# ──────────────────────────────────────────────
# Server酱推送
# ──────────────────────────────────────────────

def send_to_wechat(title, desp):
    url = f"https://sctapi.ftqq.com/{SENDKEY}.send"
    resp = requests.post(url, data={"title": title, "desp": desp}, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0 and result.get("errno") != 0:
        print(f"Server酱返回: {json.dumps(result, ensure_ascii=False)}")
    return result


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main():
    print(f"[{datetime.now()}] 开始生成 CPF 投资组合报告 ...")

    rows = []
    analyses = []
    total_investment = 0
    total_current_value = 0
    total_paper_profit = 0
    total_sell_fee = 0
    total_cpf_cost = 0
    total_dividends = sum(DIVIDENDS_RECEIVED.values())

    for stock in PORTFOLIO:
        sym   = stock["symbol"]
        name  = stock["name"]
        cost  = stock["cost"]
        shares = stock["shares"]
        buy_d = stock["buy_date"]

        quotes = fetch_quotes(sym)
        if quotes is None:
            print(f"  ⚠️ 无法获取 {name} ({sym}) 行情，跳过")
            continue

        close  = quotes["close"]
        target = breakeven_price(cost, shares)

        investment   = cost * shares
        current_val  = close * shares
        paper_profit = current_val - investment
        paper_pct    = paper_profit / investment * 100

        buy_fee  = calc_tx_fee(investment)
        sell_fee = calc_tx_fee(current_val)
        days     = holding_days(buy_d)
        cpf_cost = cpf_opportunity_cost(investment, days)
        div_recv = DIVIDENDS_RECEIVED.get(name, 0)
        net_profit = paper_profit - sell_fee - cpf_cost + div_recv
        net_pct    = net_profit / investment * 100

        rows.append({
            "symbol": sym, "name": name, "shares": shares,
            "cost": cost, "close": close, "target": target,
            "change": quotes["change"], "change_pct": quotes["change_pct"],
            "paper_profit": paper_profit, "paper_profit_pct": paper_pct,
            "suggestion": trading_suggestion(close, target, cost),
            "quotes": quotes,
        })

        analyses.append({
            "name": name, "investment": investment, "buy_fee": buy_fee,
            "current_value": current_val, "paper_profit": paper_profit,
            "sell_fee": sell_fee, "holding_days": days,
            "cpf_cost": cpf_cost, "net_profit": net_profit, "net_profit_pct": net_pct,
        })

        total_investment   += investment
        total_current_value += current_val
        total_paper_profit += paper_profit
        total_sell_fee     += sell_fee
        total_cpf_cost     += cpf_cost

    if not rows:
        print("❌ 未获取到任何行情数据，退出")
        sys.exit(1)

    total_paper_pct = total_paper_profit / total_investment * 100
    total_net_profit = total_paper_profit - total_sell_fee - total_cpf_cost + total_dividends
    total_net_pct    = total_net_profit / total_investment * 100

    totals = {
        "investment": total_investment,
        "current_value": total_current_value,
        "paper_profit": total_paper_profit,
        "paper_profit_pct": total_paper_pct,
        "sell_fee": total_sell_fee,
        "cpf_cost": total_cpf_cost,
        "dividends": total_dividends,
        "net_profit": total_net_profit,
        "net_profit_pct": total_net_pct,
    }

    # 1) 生成 HTML
    html = build_html(rows, totals, analyses)
    print("  ✅ HTML 报告已生成")

    # 2) 上传 HTML
    cdn_url = upload_html(html)
    print(f"  ✅ 已上传至 CDN: {cdn_url}")

    # 3) 构建 Markdown 摘要
    md = build_markdown_summary(rows, totals)
    md += f"\n\n---\n[📄 查看完整 HTML 报告]({cdn_url})"

    # 4) 推送到微信
    title_date = datetime.now().strftime("%m/%d")
    pnl_sign = "📈" if total_paper_profit >= 0 else "📉"
    title = f"CPF组合 {title_date} {pnl_sign} ${total_paper_profit:+,.0f} ({total_paper_pct:+.1f}%)"
    result = send_to_wechat(title, md)
    print(f"  ✅ 已推送到微信 (Server酱返回: {json.dumps(result, ensure_ascii=False)})")
    print(f"[{datetime.now()}] 完成！")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 报告生成/推送失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
