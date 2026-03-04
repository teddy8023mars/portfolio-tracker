#!/usr/bin/env python3
"""
A股投资组合HTML报告生成器 v3
功能：
  读取 /home/ubuntu/stock_data.json，生成完整HTML报告到 /home/ubuntu/daily_stock_report.html
  报告包含：持仓总览明细表（最前面）、个股详细技术分析卡片
"""

import json
import sys
from datetime import datetime

INPUT_PATH = "/home/ubuntu/stock_data.json"
OUTPUT_PATH = "/home/ubuntu/daily_stock_report.html"


def _color(val):
    return "var(--green)" if val >= 0 else "var(--red)"


def _score_color(score):
    if score >= 70:
        return "var(--green)"
    if score >= 50:
        return "#ffa726"
    return "var(--red)"


def _rsi_color(val):
    if val > 70:
        return "var(--red)"
    if val < 30:
        return "var(--green)"
    return "var(--text-muted)"


def build_html(data):
    now_str = data["generated_at"][:19].replace("T", " ")
    stocks = data["stocks"]
    today = data["today"]

    # ── 持仓总览表格行 ──
    table_rows = ""
    mobile_cards = ""
    for s in stocks:
        q = s["quotes"]
        tech = s.get("technicals")
        chg_c = _color(q["change"])
        pnl_c = _color(s["profit_pct"])
        score_val = tech["score"] if tech else "—"
        sc = _score_color(tech["score"]) if tech else "var(--text-muted)"
        signal = tech["signal"] if tech else "—"
        advice = tech["advice"] if tech else "—"
        delayed = " ⏰" if s.get("is_delayed") else ""

        table_rows += f"""
            <tr>
              <td>{s['name']}{delayed}</td>
              <td>¥{s['cost']:.3f}</td>
              <td>¥{q['current_price']:.3f}</td>
              <td style="color:{chg_c}">{q['change']:+.3f} ({q['change_pct']:+.2f}%)</td>
              <td style="color:{pnl_c}">{s['profit_pct']:+.2f}%</td>
              <td style="color:{sc};font-weight:700">{score_val}</td>
              <td>{advice}</td>
            </tr>"""

        mobile_cards += f"""
        <div class="stock-card">
          <div class="stock-card-header">
            <span class="stock-name">{s['name']}{delayed}</span>
            <span class="stock-score" style="color:{sc}">{score_val}分</span>
          </div>
          <div class="stock-card-grid">
            <div class="metric"><span class="metric-label">成本价</span><span class="metric-value">¥{s['cost']:.3f}</span></div>
            <div class="metric"><span class="metric-label">现价</span><span class="metric-value">¥{q['current_price']:.3f}</span></div>
            <div class="metric"><span class="metric-label">涨跌</span><span class="metric-value" style="color:{chg_c}">{q['change']:+.3f} ({q['change_pct']:+.2f}%)</span></div>
            <div class="metric"><span class="metric-label">盈亏</span><span class="metric-value" style="color:{pnl_c}">{s['profit_pct']:+.2f}%</span></div>
            <div class="metric" style="grid-column:1/-1"><span class="metric-label">建议</span><span class="metric-value">{advice}</span></div>
          </div>
        </div>"""

    # ── 个股详细技术分析卡片 ──
    detail_cards = ""
    for s in stocks:
        q = s["quotes"]
        tech = s.get("technicals")
        chg_c = _color(q["change"])
        delayed_note = f'<span class="delayed-badge">数据日期: {s["trade_date"]}</span>' if s.get("is_delayed") else ""

        # 行情信息
        quote_html = f"""
          <div class="quote-grid">
            <div class="metric"><span class="metric-label">昨日开盘</span><span class="metric-value">¥{q['prev_open']:.3f}</span></div>
            <div class="metric"><span class="metric-label">昨日收盘</span><span class="metric-value">¥{q['prev_close']:.3f}</span></div>
            <div class="metric"><span class="metric-label">今日开盘</span><span class="metric-value">¥{q['today_open']:.3f}</span></div>
            <div class="metric"><span class="metric-label">今日收盘</span><span class="metric-value" style="color:{chg_c}">¥{q['current_price']:.3f}</span></div>
            <div class="metric"><span class="metric-label">今日最高</span><span class="metric-value" style="color:var(--green)">¥{q['today_high']:.3f}</span></div>
            <div class="metric"><span class="metric-label">今日最低</span><span class="metric-value" style="color:var(--red)">¥{q['today_low']:.3f}</span></div>
          </div>"""

        # 技术分析
        if tech is None:
            tech_html = '<div class="tech-note">技术指标数据不足</div>'
        else:
            sc = _score_color(tech["score"])
            rsi_c = _rsi_color(tech["rsi14"])
            macd_c = "var(--green)" if "金叉" in tech["macd_status"] else ("var(--red)" if "死叉" in tech["macd_status"] else "var(--text-muted)")
            kdj_c = "var(--green)" if "金叉" in tech["kdj_status"] else ("var(--red)" if "死叉" in tech["kdj_status"] else "var(--text-muted)")

            tech_html = f"""
          <div class="tech-header">
            <div>
              <span class="tech-title">技术分析</span>
              <span class="tech-signal" style="color:{tech['signal_color']}">{tech['signal']}</span>
            </div>
            <span class="tech-score" style="border-color:{sc}">
              <span class="score-num" style="color:{sc}">{tech['score']}</span>
              <span class="score-label">评分</span>
            </span>
          </div>
          <div class="advice-box">{tech['advice']}</div>
          <div class="tech-grid">
            <div class="tech-card">
              <div class="tech-card-title">均线系统</div>
              <div class="tech-card-main">{tech['ma_trend']}</div>
              <div class="ind-row"><span>MA5</span><span>¥{tech['ma5']:.3f}</span></div>
              <div class="ind-row"><span>MA10</span><span>¥{tech['ma10']:.3f}</span></div>
              <div class="ind-row"><span>MA20</span><span>¥{tech['ma20']:.3f}</span></div>
              <div class="ind-row"><span>MA60</span><span>{'¥'+format(tech['ma60'],'.3f') if tech['ma60'] else '—'}</span></div>
              <div class="ind-row"><span>MA20偏离</span><span style="color:{_color(tech['ma20_dev'])}">{tech['ma20_dev']:+.2f}%</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">MACD</div>
              <div class="tech-card-main" style="color:{macd_c}">{tech['macd_status']}</div>
              <div class="ind-row"><span>DIF</span><span>{tech['dif']:.4f}</span></div>
              <div class="ind-row"><span>DEA</span><span>{tech['dea']:.4f}</span></div>
              <div class="ind-row"><span>MACD柱</span><span style="color:{_color(tech['macd_hist'])}">{tech['macd_hist']:.4f}</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">KDJ</div>
              <div class="tech-card-main" style="color:{kdj_c}">{tech['kdj_status']}</div>
              <div class="ind-row"><span>K</span><span>{tech['k']:.2f}</span></div>
              <div class="ind-row"><span>D</span><span>{tech['d']:.2f}</span></div>
              <div class="ind-row"><span>J</span><span style="color:{_color(tech['j']-50)}">{tech['j']:.2f}</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">RSI</div>
              <div class="tech-card-main" style="color:{rsi_c}">{tech['rsi_status']} ({tech['rsi14']:.1f})</div>
              <div class="rsi-bar">
                <div class="rsi-zone rsi-oversold"></div>
                <div class="rsi-zone rsi-neutral"></div>
                <div class="rsi-zone rsi-overbought"></div>
                <div class="rsi-pointer" style="left:{min(max(tech['rsi14'],0),100):.1f}%"></div>
              </div>
              <div class="rsi-labels"><span>超卖30</span><span>中性</span><span>超买70</span></div>
              <div class="ind-row"><span>RSI6</span><span>{tech['rsi6']:.1f}</span></div>
              <div class="ind-row"><span>RSI14</span><span>{tech['rsi14']:.1f}</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">布林带</div>
              <div class="tech-card-main">位置: {tech['bb_position']:.1f}%</div>
              <div class="bb-bar">
                <div class="bb-fill" style="width:{min(max(tech['bb_position'],0),100):.1f}%"></div>
              </div>
              <div class="ind-row"><span>上轨</span><span>¥{tech['bb_upper']:.3f}</span></div>
              <div class="ind-row"><span>中轨</span><span>¥{tech['bb_mid']:.3f}</span></div>
              <div class="ind-row"><span>下轨</span><span>¥{tech['bb_lower']:.3f}</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">ATR 波动率</div>
              <div class="tech-card-main">ATR: {tech['atr']:.3f}</div>
              <div class="ind-row"><span>ATR%</span><span>{tech['atr_pct']:.2f}%</span></div>
              <div class="ind-row"><span>日波动</span><span>±¥{tech['atr']:.3f}</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">威廉指标 WR</div>
              <div class="tech-card-main">{tech['wr_status']}</div>
              <div class="ind-row"><span>WR6</span><span>{tech['wr6']:.2f}</span></div>
              <div class="ind-row"><span>WR14</span><span>{tech['wr14']:.2f}</span></div>
            </div>
            <div class="tech-card">
              <div class="tech-card-title">成交量</div>
              <div class="tech-card-main">{tech['vol_status']}</div>
              <div class="ind-row"><span>今日量</span><span>{tech['vol_today']/10000:.0f}万</span></div>
              <div class="ind-row"><span>5日均量</span><span>{tech['vol_5d']/10000:.0f}万</span></div>
              <div class="ind-row"><span>量比(5日)</span><span>{tech['vol_ratio']:.2f}</span></div>
              <div class="ind-row"><span>量比(10日)</span><span>{tech['vol_ratio_10d']:.2f}</span></div>
            </div>
          </div>
          <div class="sr-section">
            <div class="sr-title">支撑位与压力位</div>
            <div class="sr-grid">
              <div class="sr-item sr-resistance"><span>压力位1</span><span>¥{tech['resistance_1']:.3f}</span></div>
              <div class="sr-item sr-resistance"><span>压力位2</span><span>¥{tech['resistance_2']:.3f}</span></div>
              <div class="sr-item sr-support"><span>支撑位1</span><span>¥{tech['support_1']:.3f}</span></div>
              <div class="sr-item sr-support"><span>支撑位2</span><span>¥{tech['support_2']:.3f}</span></div>
            </div>
          </div>"""

        detail_cards += f"""
        <div class="card">
          <h3>{s['name']} ({s['symbol']}) {delayed_note}</h3>
          {quote_html}
          {tech_html}
        </div>"""

    # ── 组装完整 HTML ──
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>A股投资组合报告 — {now_str}</title>
<style>
  :root {{
    --bg: #0f172a; --card-bg: #1e293b; --border: #334155;
    --text: #e2e8f0; --text-muted: #94a3b8; --accent: #3b82f6;
    --green: #22c55e; --red: #ef4444;
  }}
  *{{margin:0;padding:0;box-sizing:border-box}}
  html{{font-size:16px;-webkit-text-size-adjust:100%}}
  body{{
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
    background:var(--bg);color:var(--text);padding:16px;line-height:1.6;max-width:960px;margin:0 auto;
  }}
  h1{{text-align:center;font-size:1.35rem;margin-bottom:4px}}
  .subtitle{{text-align:center;color:var(--text-muted);font-size:0.85rem;margin-bottom:20px}}
  .section-title{{font-size:1.05rem;margin:28px 0 14px;border-left:4px solid var(--accent);padding-left:10px}}
  .card{{background:var(--card-bg);border-radius:10px;padding:16px;margin-bottom:12px}}
  .card h3{{margin-bottom:10px;font-size:0.95rem;color:#60a5fa}}
  .delayed-badge{{font-size:0.7rem;color:#ffa726;background:rgba(255,167,38,0.15);padding:2px 8px;border-radius:4px;margin-left:8px}}

  /* 桌面表格 */
  .desktop-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}
  .desktop-table table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
  .desktop-table th,.desktop-table td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}}
  .desktop-table th{{background:var(--card-bg);color:var(--text-muted);font-weight:600;position:sticky;top:0}}
  .desktop-table tr:hover{{background:rgba(30,41,59,0.5)}}

  /* 移动端卡片 */
  .mobile-cards{{display:block}}
  .stock-card{{background:var(--card-bg);border-radius:10px;padding:14px;margin-bottom:10px}}
  .stock-card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px}}
  .stock-name{{font-size:1rem;font-weight:700;color:#60a5fa}}
  .stock-score{{font-size:0.85rem;font-weight:700}}

  /* 指标网格 */
  .quote-grid,.stock-card-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
  .metric{{display:flex;flex-direction:column}}.metric-label{{font-size:0.72rem;color:var(--text-muted)}}.metric-value{{font-size:0.9rem;font-weight:600}}

  /* 技术分析 */
  .tech-header{{display:flex;justify-content:space-between;align-items:center;margin:18px 0 8px;padding-top:12px;border-top:1px solid var(--border)}}
  .tech-title{{font-size:0.85rem;color:var(--text-muted);font-weight:600}}
  .tech-signal{{font-size:0.82rem;font-weight:600;margin-left:10px}}
  .tech-score{{width:48px;height:48px;border:2px solid;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0}}
  .score-num{{font-size:18px;font-weight:800;line-height:1}}.score-label{{font-size:9px;color:var(--text-muted)}}
  .advice-box{{font-size:0.82rem;color:var(--accent);background:rgba(59,130,246,0.1);padding:8px 12px;border-radius:6px;margin-bottom:10px;font-weight:600}}
  .tech-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
  .tech-card{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px}}
  .tech-card-title{{font-size:0.7rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}}
  .tech-card-main{{font-size:0.85rem;font-weight:700;color:var(--text);margin-bottom:6px}}
  .ind-row{{display:flex;justify-content:space-between;padding:2px 0;font-size:0.75rem;color:var(--text-muted)}}
  .ind-row span:last-child{{color:var(--text);font-weight:500}}
  .tech-note{{font-size:0.8rem;color:var(--text-muted);padding:12px 0;border-top:1px solid var(--border);margin-top:12px}}

  /* RSI条 */
  .rsi-bar{{height:6px;border-radius:3px;display:flex;overflow:hidden;position:relative;margin:6px 0 2px}}
  .rsi-zone{{height:100%}}.rsi-oversold{{width:30%;background:#1b5e20}}.rsi-neutral{{width:40%;background:#37474f}}.rsi-overbought{{width:30%;background:#b71c1c}}
  .rsi-pointer{{position:absolute;top:-2px;width:2px;height:10px;background:#fff;border-radius:1px;transform:translateX(-50%)}}
  .rsi-labels{{display:flex;justify-content:space-between;font-size:0.6rem;color:var(--text-muted)}}

  /* 布林带条 */
  .bb-bar{{height:6px;border-radius:3px;background:var(--border);overflow:hidden;margin:6px 0 2px}}
  .bb-fill{{height:100%;background:var(--accent);border-radius:3px}}

  /* 支撑压力 */
  .sr-section{{margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}}
  .sr-title{{font-size:0.78rem;color:var(--text-muted);font-weight:600;margin-bottom:8px}}
  .sr-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}}
  .sr-item{{display:flex;justify-content:space-between;padding:6px 10px;border-radius:6px;font-size:0.78rem}}
  .sr-resistance{{background:rgba(239,68,68,0.1);color:var(--red)}}
  .sr-support{{background:rgba(34,197,94,0.1);color:var(--green)}}

  .note{{background:var(--card-bg);border-radius:10px;padding:16px;font-size:0.78rem;color:var(--text-muted);line-height:1.8}}
  .note strong{{color:var(--text)}}

  @media(min-width:768px){{
    body{{padding:32px}}h1{{font-size:1.6rem}}
    .quote-grid{{grid-template-columns:repeat(3,1fr)}}
    .stock-card-grid{{grid-template-columns:repeat(3,1fr)}}
    .mobile-cards{{display:none}}
    .tech-grid{{grid-template-columns:repeat(4,1fr)}}
    .sr-grid{{grid-template-columns:repeat(4,1fr)}}
  }}
  @media(max-width:767px){{
    .desktop-table{{display:none}}
  }}
  @media(max-width:374px){{
    body{{padding:10px;font-size:14px}}
    .stock-card-grid{{grid-template-columns:1fr 1fr}}
    .quote-grid{{grid-template-columns:1fr 1fr}}
    .tech-grid{{grid-template-columns:1fr 1fr}}
  }}
</style>
</head>
<body>

<h1>📊 A股投资组合每日报告</h1>
<p class="subtitle">{now_str} (北京时间)</p>

<!-- ── 持仓总览明细表 ── -->
<h2 class="section-title">持仓总览</h2>

<div class="desktop-table">
  <table>
    <thead><tr><th>股票</th><th>成本价</th><th>现价</th><th>今日涨跌</th><th>盈亏</th><th>评分</th><th>操作建议</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>
<div class="mobile-cards">{mobile_cards}</div>

<!-- ── 个股详细技术分析 ── -->
<h2 class="section-title">个股详细技术分析</h2>
{detail_cards}

<!-- ── 说明 ── -->
<h2 class="section-title">说明</h2>
<div class="note">
  <strong>综合评分</strong>：基于 RSI/MACD/KDJ/均线/布林带/ATR/WR 等多指标加权计算，满分100。≥70偏多 | 50-70中性 | &lt;50偏空<br>
  <strong>RSI</strong>：相对强弱指标，&gt;70超买，&lt;30超卖<br>
  <strong>MACD</strong>：DIF上穿DEA为金叉（买入信号），下穿为死叉（卖出信号）<br>
  <strong>KDJ</strong>：随机指标，K上穿D为金叉，J&gt;80超买，J&lt;20超卖<br>
  <strong>布林带</strong>：位置接近上轨为超买，接近下轨为超卖<br>
  <strong>ATR</strong>：平均真实波幅，衡量股票波动性<br>
  <strong>威廉指标</strong>：WR&lt;20超买，WR&gt;80超卖<br>
  <strong>数据来源</strong>：Yahoo Finance（可能有延迟）<br>
  <strong>免责声明</strong>：本报告仅供参考，不构成投资建议
</div>

</body>
</html>"""

    return html


def main():
    print(f"[{datetime.now()}] 开始生成HTML报告 ...", file=sys.stderr)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = build_html(data)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[{datetime.now()}] ✅ HTML报告已生成: {OUTPUT_PATH}", file=sys.stderr)
    print(f"  共 {data['stock_count']} 只股票", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 报告生成失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
