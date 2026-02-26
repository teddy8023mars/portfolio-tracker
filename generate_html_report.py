#!/usr/bin/env python3
"""
CPF 投资组合日报 — HTML 报告 + 微信推送

用法:  python generate_html_report.py
输出:
  output/report.html   完整 HTML 报告（含技术指标）
  微信                 Server酱 Markdown 摘要 + GitHub Pages 链接
"""

import sys
from datetime import datetime, date
from pathlib import Path

from lib import config
from lib.portfolio import (
    calc_tx_fee, holding_days, cpf_opportunity_cost,
    breakeven_price, fetch_quotes, fetch_history, trading_suggestion,
)
from lib.technicals import analyze as calc_technicals
from lib.fundamentals import fetch_fundamentals
from lib.macro import fetch_macro
from lib.news import fetch_news
from lib.html_template import build_html, build_markdown
from lib.push import push_github, push_wechat

OUTPUT_DIR = Path(__file__).parent / "output"


def main():
    print(f"[{datetime.now()}] 开始生成 CPF 投资组合报告 ...", file=sys.stderr)

    cfg = config.load()
    portfolio = cfg["portfolio"]
    dividends = cfg.get("dividends_received", {})
    target_return = cfg.get("target_return", 0.10)

    symbols = [s["symbol"] for s in portfolio]
    fund_data = fetch_fundamentals(symbols)
    macro = fetch_macro()
    news_data = fetch_news(symbols)

    rows, analyses = [], []
    t_inv = t_val = t_pnl = t_sell = t_cpf = 0.0
    t_div = sum(dividends.values())
    common_days = 0

    for stock in portfolio:
        sym, name = stock["symbol"], stock["name"]
        cost, shares, buy_d = stock["cost"], stock["shares"], stock["buy_date"]

        quotes = fetch_quotes(sym)
        if quotes is None:
            print(f"  ⚠️ 无法获取 {name} ({sym}) 行情，跳过", file=sys.stderr)
            continue

        hist = fetch_history(sym, period="60d")
        tech = calc_technicals(hist)
        if tech:
            print(f"  📊 {name}: 评分 {tech['score']} ({tech['signal']})", file=sys.stderr)

        close = quotes["close"]
        target = breakeven_price(cost, shares)
        investment = cost * shares
        current_val = close * shares
        paper_profit = current_val - investment
        paper_pct = paper_profit / investment * 100
        buy_fee = calc_tx_fee(investment)
        sell_fee = calc_tx_fee(current_val)
        days = holding_days(buy_d)
        common_days = days
        cpf_cost = cpf_opportunity_cost(investment, days)
        div_recv = dividends.get(name, 0)
        net_profit = paper_profit - sell_fee - cpf_cost + div_recv
        net_pct = net_profit / investment * 100
        annualized = paper_pct * (365 / days) if days > 0 else 0
        target_10_price = cost * (1 + target_return)
        target_10_gap = (target_10_price - close) / close * 100

        rows.append({
            "symbol": sym, "name": name, "shares": shares,
            "cost": cost, "close": close, "target": target,
            "change": quotes["change"], "change_pct": quotes["change_pct"],
            "paper_profit": paper_profit, "paper_profit_pct": paper_pct,
            "suggestion": trading_suggestion(close, target, cost),
            "quotes": quotes, "tech": tech,
            "fund": fund_data.get(sym), "news": news_data.get(sym, []),
            "weight": 0,
            "annualized_pct": annualized,
            "target_10_price": target_10_price,
            "target_10_gap": target_10_gap,
        })
        analyses.append({
            "name": name, "investment": investment, "buy_fee": buy_fee,
            "current_value": current_val, "paper_profit": paper_profit,
            "paper_profit_pct": paper_pct,
            "sell_fee": sell_fee, "holding_days": days,
            "cpf_cost": cpf_cost, "net_profit": net_profit, "net_profit_pct": net_pct,
            "annualized_pct": annualized,
            "target_10_gap": target_10_gap,
        })
        t_inv += investment
        t_val += current_val
        t_pnl += paper_profit
        t_sell += sell_fee
        t_cpf += cpf_cost

    if not rows:
        print("❌ 未获取到任何行情数据，退出", file=sys.stderr)
        sys.exit(1)

    for r in rows:
        r["weight"] = (r["cost"] * r["shares"]) / t_inv * 100

    t_net = t_pnl - t_sell - t_cpf + t_div
    t_pnl_pct = t_pnl / t_inv * 100
    totals = {
        "investment": t_inv, "current_value": t_val,
        "paper_profit": t_pnl, "paper_profit_pct": t_pnl_pct,
        "sell_fee": t_sell, "cpf_cost": t_cpf, "dividends": t_div,
        "net_profit": t_net, "net_profit_pct": t_net / t_inv * 100,
        "annualized_pct": t_pnl_pct * (365 / common_days) if common_days > 0 else 0,
    }

    # 1) HTML report
    html = build_html(rows, totals, analyses, macro=macro)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = OUTPUT_DIR / "report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  ✅ HTML → {html_path}", file=sys.stderr)

    # 2) push to GitHub Pages
    repo_dir = Path(__file__).parent
    pages_url = push_github(repo_dir)

    # 3) Markdown + link → WeChat
    md = build_markdown(rows, totals, analyses, macro=macro)
    md += f"\n\n---\n[📄 点击查看详细报告]({pages_url})"

    title_date = datetime.now().strftime("%m/%d")
    pnl_sign = "📈" if t_pnl >= 0 else "📉"
    title = f"CPF组合 {title_date} {pnl_sign} ${t_pnl:+,.0f} ({t_pnl_pct:+.1f}%)"
    push_wechat(title, md)

    print(f"  标题: {title}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 报告生成失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
