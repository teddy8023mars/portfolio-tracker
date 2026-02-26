#!/usr/bin/env python3
"""
Portfolio Risk Analytics Report
================================
Standalone script that generates a comprehensive risk analysis report
for the CPF investment portfolio.

Usage:
    python risk_report.py

Output:
    - Console: formatted risk analysis summary
    - output/risk_report.html: full HTML risk report
"""

import sys
from datetime import datetime
from pathlib import Path

from lib import config
from lib.risk import (
    analyze_portfolio_risk,
    RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
)

OUTPUT_DIR = Path(__file__).parent / "output"


def _fmt(val, suffix="%", decimals=2, na="N/A"):
    """Format a numeric value with suffix, or return N/A."""
    if val is None:
        return na
    return f"{val:+.{decimals}f}{suffix}" if val < 0 else f"{val:.{decimals}f}{suffix}"


def _rating_emoji(sharpe):
    """Return emoji based on Sharpe ratio quality."""
    if sharpe is None:
        return "—"
    if sharpe >= 1.0:
        return "🟢 优秀"
    if sharpe >= 0.5:
        return "🟡 良好"
    if sharpe >= 0:
        return "🟠 一般"
    return "🔴 较差"


def _corr_emoji(val):
    """Return description for correlation value."""
    if val is None:
        return "—"
    abs_val = abs(val)
    if abs_val >= 0.8:
        return "强相关"
    if abs_val >= 0.5:
        return "中等相关"
    if abs_val >= 0.3:
        return "弱相关"
    return "几乎无关"


def print_console_report(result: dict, portfolio: list):
    """Print formatted risk report to console."""
    print()
    print("=" * 80)
    print(f"📊 投资组合风险分析报告 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # ── Per-stock risk ──
    print("【个股风险指标】")
    print("-" * 80)
    for sym, risk in result["stock_risks"].items():
        if risk is None:
            print(f"  ⚠️ {sym}: 数据不足，无法分析")
            continue

        name = risk.get("name", sym)
        weight = risk.get("weight", 0)
        print(f"\n  📈 {name} ({sym}) — 仓位占比 {weight:.1f}%")
        print(f"     年化波动率:    {_fmt(risk['annual_vol'])}")
        print(f"     最大回撤:      {_fmt(risk['max_drawdown'])}")
        print(f"       峰值日期:    {risk.get('peak_date', 'N/A')}")
        print(f"       谷底日期:    {risk.get('trough_date', 'N/A')}")
        print(f"     VaR (95%):     {_fmt(risk.get('var_95'), decimals=4)}")
        print(f"     VaR (99%):     {_fmt(risk.get('var_99'), decimals=4)}")
        print(f"     夏普比率:      {risk.get('sharpe_ratio', 'N/A')}  {_rating_emoji(risk.get('sharpe_ratio'))}")
        print(f"     索提诺比率:    {risk.get('sortino_ratio', 'N/A')}")
        print(f"     数据点数:      {risk.get('data_points', 'N/A')} 个交易日")

    # ── Correlation matrix ──
    print()
    print("-" * 80)
    print("【相关性矩阵】")
    corr = result.get("correlation")
    if corr is not None:
        print()
        # Header
        names = {s["symbol"]: s["name"] for s in portfolio}
        header = "          " + "  ".join(f"{names.get(c, c):>10}" for c in corr.columns)
        print(header)
        for idx in corr.index:
            row = f"  {names.get(idx, idx):>8}"
            for col in corr.columns:
                val = corr.loc[idx, col]
                row += f"  {val:>10.4f}"
            print(row)
        print()
        # Interpretation
        print("  解读:")
        symbols = list(corr.columns)
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                val = corr.iloc[i, j]
                n1 = names.get(symbols[i], symbols[i])
                n2 = names.get(symbols[j], symbols[j])
                desc = _corr_emoji(val)
                print(f"    {n1} ↔ {n2}: {val:.4f} ({desc})")
    else:
        print("  ⚠️ 数据不足，无法计算相关性矩阵")

    # ── Portfolio-level ──
    print()
    print("-" * 80)
    print("【组合整体风险】")
    port_vol = result.get("portfolio_vol")
    if port_vol:
        print(f"  组合年化波动率:      {port_vol['portfolio_annual_vol']:.2f}%")
        print(f"  未分散化波动率:      {port_vol['undiversified_vol']:.2f}%")
        print(f"  分散化收益:          {port_vol['diversification_benefit']:.2f}%")
        print(f"  风险等级:            {result['risk_level']}")
    else:
        print("  ⚠️ 数据不足，无法计算组合风险")

    print()
    print("=" * 80)
    print("📝 指标说明")
    print("=" * 80)
    print("• 年化波动率: 价格波动的年化标准差，越高表示风险越大")
    print("• 最大回撤: 从峰值到谷底的最大跌幅，衡量最坏情况下的损失")
    print(f"• VaR (95%): 在95%置信度下，单日最大可能损失")
    print(f"• VaR (99%): 在99%置信度下，单日最大可能损失")
    print(f"• 夏普比率: 风险调整后收益率（无风险利率: {RISK_FREE_RATE*100:.1f}%），>1优秀, >0.5良好")
    print("• 索提诺比率: 仅考虑下行风险的夏普比率变体，更关注亏损风险")
    print("• 分散化收益: 通过持有多只股票降低的波动率，越高越好")
    print("=" * 80)


def build_risk_html(result: dict, portfolio: list) -> str:
    """Build a standalone HTML risk report."""
    names = {s["symbol"]: s["name"] for s in portfolio}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build per-stock rows
    stock_rows = ""
    for sym, risk in result["stock_risks"].items():
        if risk is None:
            continue
        name = risk.get("name", sym)
        weight = risk.get("weight", 0)

        sharpe = risk.get("sharpe_ratio")
        sharpe_class = ""
        if sharpe is not None:
            if sharpe >= 1.0:
                sharpe_class = "green"
            elif sharpe >= 0.5:
                sharpe_class = ""
            elif sharpe >= 0:
                sharpe_class = "orange"
            else:
                sharpe_class = "red"

        mdd = risk.get("max_drawdown")
        mdd_class = ""
        if mdd is not None:
            if mdd > -5:
                mdd_class = "green"
            elif mdd > -10:
                mdd_class = "orange"
            else:
                mdd_class = "red"

        stock_rows += f"""
        <tr>
            <td><strong>{name}</strong><br><small>{sym}</small></td>
            <td>{weight:.1f}%</td>
            <td>{_fmt(risk.get('annual_vol'))}</td>
            <td class="{mdd_class}">{_fmt(mdd)}</td>
            <td>{_fmt(risk.get('var_95'), decimals=4)}</td>
            <td>{_fmt(risk.get('var_99'), decimals=4)}</td>
            <td class="{sharpe_class}">{sharpe if sharpe is not None else 'N/A'}</td>
            <td>{risk.get('sortino_ratio', 'N/A')}</td>
        </tr>"""

    # Build correlation table
    corr_html = ""
    corr = result.get("correlation")
    if corr is not None:
        corr_header = "<th></th>" + "".join(f"<th>{names.get(c, c)}</th>" for c in corr.columns)
        corr_body = ""
        for idx in corr.index:
            cells = f"<td><strong>{names.get(idx, idx)}</strong></td>"
            for col in corr.columns:
                val = corr.loc[idx, col]
                if idx == col:
                    cls = "neutral"
                elif abs(val) >= 0.7:
                    cls = "high-corr"
                elif abs(val) >= 0.4:
                    cls = "mid-corr"
                else:
                    cls = "low-corr"
                cells += f'<td class="{cls}">{val:.4f}</td>'
            corr_body += f"<tr>{cells}</tr>\n"

        corr_html = f"""
        <table class="corr-table">
            <thead><tr>{corr_header}</tr></thead>
            <tbody>{corr_body}</tbody>
        </table>"""
    else:
        corr_html = "<p>数据不足，无法计算相关性矩阵</p>"

    # Portfolio-level
    port_vol = result.get("portfolio_vol")
    if port_vol:
        port_html = f"""
        <div class="metric-cards">
            <div class="metric-card">
                <div class="metric-label">组合年化波动率</div>
                <div class="metric-value">{port_vol['portfolio_annual_vol']:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">未分散化波动率</div>
                <div class="metric-value">{port_vol['undiversified_vol']:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">分散化收益</div>
                <div class="metric-value highlight">{port_vol['diversification_benefit']:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">风险等级</div>
                <div class="metric-value" style="color: {result['risk_color']}">{result['risk_level']}</div>
            </div>
        </div>"""
    else:
        port_html = "<p>数据不足，无法计算组合风险</p>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投资组合风险分析报告 — {now}</title>
<style>
:root {{
    --bg: #0d1117;
    --card-bg: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --blue: #58a6ff;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
}}
h1 {{
    text-align: center;
    margin-bottom: 8px;
    font-size: 1.6em;
}}
.subtitle {{
    text-align: center;
    color: var(--text-muted);
    margin-bottom: 30px;
    font-size: 0.9em;
}}
h2 {{
    color: var(--blue);
    margin: 30px 0 15px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    font-size: 1.2em;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    font-size: 0.9em;
}}
th, td {{
    padding: 10px 12px;
    text-align: center;
    border-bottom: 1px solid var(--border);
}}
th {{
    background: var(--card-bg);
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.85em;
    text-transform: uppercase;
}}
td:first-child {{ text-align: left; }}
tr:hover {{ background: rgba(88, 166, 255, 0.05); }}
.green {{ color: var(--green); font-weight: 600; }}
.red {{ color: var(--red); font-weight: 600; }}
.orange {{ color: var(--orange); font-weight: 600; }}
.corr-table td {{ font-family: monospace; font-size: 0.85em; }}
.high-corr {{ background: rgba(248, 81, 73, 0.15); }}
.mid-corr {{ background: rgba(210, 153, 34, 0.1); }}
.low-corr {{ background: rgba(63, 185, 80, 0.1); }}
.neutral {{ background: rgba(88, 166, 255, 0.1); }}
.metric-cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin: 20px 0;
}}
.metric-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    text-align: center;
}}
.metric-label {{
    color: var(--text-muted);
    font-size: 0.85em;
    margin-bottom: 8px;
}}
.metric-value {{
    font-size: 1.5em;
    font-weight: 700;
}}
.metric-value.highlight {{ color: var(--green); }}
.notes {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    margin-top: 30px;
    font-size: 0.85em;
    color: var(--text-muted);
    line-height: 1.8;
}}
.notes strong {{ color: var(--text); }}
@media (max-width: 768px) {{
    body {{ padding: 12px; }}
    table {{ font-size: 0.8em; }}
    th, td {{ padding: 6px 8px; }}
    .metric-cards {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<h1>📊 投资组合风险分析报告</h1>
<p class="subtitle">生成时间: {now} | 无风险利率: {RISK_FREE_RATE*100:.1f}% (新加坡10年期国债)</p>

<h2>📈 个股风险指标</h2>
<table>
<thead>
<tr>
    <th>产品</th>
    <th>仓位</th>
    <th>年化波动率</th>
    <th>最大回撤</th>
    <th>VaR (95%)</th>
    <th>VaR (99%)</th>
    <th>夏普比率</th>
    <th>索提诺比率</th>
</tr>
</thead>
<tbody>
{stock_rows}
</tbody>
</table>

<h2>🔗 相关性矩阵</h2>
{corr_html}

<h2>🏦 组合整体风险</h2>
{port_html}

<div class="notes">
<strong>📝 指标说明</strong><br>
• <strong>年化波动率</strong>: 价格波动的年化标准差，越高表示风险越大<br>
• <strong>最大回撤</strong>: 从峰值到谷底的最大跌幅，衡量最坏情况下的损失<br>
• <strong>VaR (95%/99%)</strong>: 在对应置信度下，单日最大可能损失百分比<br>
• <strong>夏普比率</strong>: 风险调整后收益率，&gt;1 优秀, &gt;0.5 良好, &lt;0 较差<br>
• <strong>索提诺比率</strong>: 仅考虑下行风险的夏普比率变体，更关注亏损风险<br>
• <strong>分散化收益</strong>: 通过持有多只股票降低的波动率，越高说明分散化效果越好
</div>
</body>
</html>"""
    return html


def main():
    """Main entry point for risk report generation."""
    cfg = config.load()
    portfolio = cfg["portfolio"]

    print(f"[{datetime.now()}] 开始生成风险分析报告 ...", file=sys.stderr)

    result = analyze_portfolio_risk(portfolio, period="120d")

    # Console report
    print_console_report(result, portfolio)

    # HTML report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_risk_html(result, portfolio)
    html_path = OUTPUT_DIR / "risk_report.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"\n✅ HTML 风险报告已保存: {html_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 风险报告生成失败: {e}")
        import traceback
        traceback.print_exc()
