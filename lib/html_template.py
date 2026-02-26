"""HTML report template builder."""

from datetime import datetime, date
from lib import config

CPF_OA_RATE = config.get("cpf_oa_rate", 0.035)


def _color(val):
    return "var(--green)" if val >= 0 else "var(--red)"


def _advice_summary(rows):
    all_sell = all("可卖出" in r["suggestion"] for r in rows)
    any_stop = any("止损" in r["suggestion"] for r in rows)
    any_close = any("接近目标" in r["suggestion"] for r in rows)
    if all_sell:
        return "💡 全部标的已达目标价，可考虑部分落袋锁定利润"
    if any_stop:
        names = [r["name"] for r in rows if "止损" in r["suggestion"]]
        return f"⚠️ {', '.join(names)} 接近止损线，请密切关注"
    if any_close:
        return "📈 部分标的接近目标价，继续观察等待突破"
    return "📊 组合整体正常，继续持有观察"


def _score_color(score):
    if score >= 70:
        return "var(--green)"
    if score >= 50:
        return "#ffa726"
    return "var(--red)"


def _build_tech_section(tech):
    """Build the technical analysis HTML block for one stock card."""
    if tech is None:
        return '<div class="tech-note">技术指标数据不足</div>'

    sc = _score_color(tech["score"])
    rsi_c = "var(--red)" if tech["rsi14"] > 70 else ("var(--green)" if tech["rsi14"] < 30 else "var(--text-muted)")
    macd_c = "var(--green)" if "金叉" in tech["macd_status"] else ("var(--red)" if "死叉" in tech["macd_status"] else "var(--text-muted)")

    return f"""
      <div class="tech-header">
        <span class="tech-title">技术分析</span>
        <span class="tech-score" style="border-color:{sc}">
          <span class="score-num" style="color:{sc}">{tech['score']}</span>
          <span class="score-label">评分</span>
        </span>
      </div>
      <div class="tech-signal" style="color:{tech['signal_color']}">{tech['signal']}</div>
      <div class="tech-grid">
        <div class="tech-card">
          <div class="tech-card-title">均线</div>
          <div class="tech-card-main">{tech['ma_trend']}</div>
          <div class="ind-row"><span>MA5</span><span>${tech['ma5']:.4f}</span></div>
          <div class="ind-row"><span>MA10</span><span>${tech['ma10']:.4f}</span></div>
          <div class="ind-row"><span>MA20</span><span>${tech['ma20']:.4f}</span></div>
          <div class="ind-row"><span>MA20偏离</span><span style="color:{_color(tech['ma20_dev'])}">{tech['ma20_dev']:+.2f}%</span></div>
        </div>
        <div class="tech-card">
          <div class="tech-card-title">MACD</div>
          <div class="tech-card-main" style="color:{macd_c}">{tech['macd_status']}</div>
          <div class="ind-row"><span>DIF</span><span>{tech['dif']:.4f}</span></div>
          <div class="ind-row"><span>DEA</span><span>{tech['dea']:.4f}</span></div>
          <div class="ind-row"><span>柱状</span><span style="color:{_color(tech['macd_hist'])}">{tech['macd_hist']:.4f}</span></div>
        </div>
        <div class="tech-card">
          <div class="tech-card-title">RSI</div>
          <div class="tech-card-main" style="color:{rsi_c}">RSI14: {tech['rsi14']:.1f}</div>
          <div class="rsi-bar">
            <div class="rsi-zone rsi-oversold"></div>
            <div class="rsi-zone rsi-neutral"></div>
            <div class="rsi-zone rsi-overbought"></div>
            <div class="rsi-pointer" style="left:{min(max(tech['rsi14'],0),100):.1f}%"></div>
          </div>
          <div class="rsi-labels"><span>超卖30</span><span>中性</span><span>超买70</span></div>
          <div class="ind-row"><span>RSI6</span><span>{tech['rsi6']:.1f}</span></div>
        </div>
        <div class="tech-card">
          <div class="tech-card-title">布林带</div>
          <div class="tech-card-main">位置: {tech['bb_position']:.1f}%</div>
          <div class="ind-row"><span>上轨</span><span>${tech['bb_upper']:.4f}</span></div>
          <div class="ind-row"><span>中轨</span><span>${tech['bb_mid']:.4f}</span></div>
          <div class="ind-row"><span>下轨</span><span>${tech['bb_lower']:.4f}</span></div>
          <div class="ind-row"><span>量比</span><span>{tech['vol_ratio']:.2f}</span></div>
        </div>
      </div>"""


def _build_fundamental_section(fund):
    """Build the fundamental data HTML block for one stock card."""
    if fund is None:
        return '<div class="tech-note">基本面数据暂无</div>'

    def _fmt(v, suffix="", decimals=2):
        if v is None:
            return "—"
        return f"{v:.{decimals}f}{suffix}"

    def _fmt_cap(v):
        if v is None:
            return "—"
        if v >= 1e9:
            return f"${v/1e9:.1f}B"
        return f"${v/1e6:.0f}M"

    w52_bar = ""
    if fund.get("week52_pos") is not None:
        w52_bar = f"""
          <div class="rsi-bar" style="margin:6px 0 2px">
            <div class="rsi-zone" style="width:100%;background:var(--border)"></div>
            <div class="rsi-pointer" style="left:{min(max(fund['week52_pos'],0),100):.1f}%"></div>
          </div>
          <div class="rsi-labels"><span>${_fmt(fund['week52_low'])}</span><span>52周</span><span>${_fmt(fund['week52_high'])}</span></div>"""

    return f"""
      <div class="tech-header">
        <span class="tech-title">基本面</span>
        <span class="tech-score" style="border-color:{fund['overall_color']}">
          <span class="score-num" style="color:{fund['overall_color']};font-size:12px">{fund['overall']}</span>
          <span class="score-label">估值</span>
        </span>
      </div>
      <div class="tech-grid">
        <div class="tech-card">
          <div class="tech-card-title">PE 市盈率</div>
          <div class="tech-card-main" style="color:{fund['pe_color']}">{_fmt(fund['pe'])} <small>({fund['pe_rating']})</small></div>
          <div class="ind-row"><span>行业均值</span><span>{_fmt(fund['bench_pe'])}</span></div>
        </div>
        <div class="tech-card">
          <div class="tech-card-title">PB 市净率</div>
          <div class="tech-card-main" style="color:{fund['pb_color']}">{_fmt(fund['pb'])} <small>({fund['pb_rating']})</small></div>
          <div class="ind-row"><span>行业均值</span><span>{_fmt(fund['bench_pb'])}</span></div>
        </div>
        <div class="tech-card">
          <div class="tech-card-title">股息率</div>
          <div class="tech-card-main" style="color:{fund['div_color']}">{_fmt(fund['div_yield'], '%')} <small>({fund['div_rating']})</small></div>
          <div class="ind-row"><span>行业均值</span><span>{_fmt(fund['bench_div'], '%')}</span></div>
        </div>
        <div class="tech-card">
          <div class="tech-card-title">其他</div>
          <div class="ind-row"><span>ROE</span><span>{_fmt(fund['roe'], '%')}</span></div>
          <div class="ind-row"><span>市值</span><span>{_fmt_cap(fund['market_cap'])}</span></div>
          {w52_bar}
        </div>
      </div>"""


def _build_news_section(news_list):
    """Build the news HTML block for one stock card."""
    if not news_list:
        return ""
    items = ""
    for n in news_list:
        items += f"""
          <div class="news-item">
            <span class="news-icon">{n['icon']}</span>
            <div class="news-content">
              <a class="news-title" href="{n['link']}" target="_blank">{n['title']}</a>
              <span class="news-source">{n['source']}</span>
            </div>
          </div>"""
    return f"""
      <div class="tech-header">
        <span class="tech-title">近期新闻</span>
      </div>
      {items}"""


def _build_macro_banner(macro):
    """Build the macro environment banner HTML."""
    if macro is None:
        return ""
    return f"""<div class="macro-banner">{macro['summary']}</div>"""


def build_html(rows, totals, analyses, macro=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    advice = _advice_summary(rows)
    dividends = config.get("dividends_received", {})

    table_rows = ""
    for r in rows:
        chg_c = _color(r["change"])
        pnl_c = _color(r["paper_profit"])
        sc = _score_color(r.get("tech", {}).get("score", 50)) if r.get("tech") else "var(--text-muted)"
        score_val = r["tech"]["score"] if r.get("tech") else "—"
        table_rows += f"""
            <tr>
              <td>{r['name']}</td><td>{r['shares']}</td><td>{r['weight']:.1f}%</td><td>${r['cost']:.2f}</td>
              <td>${r['close']:.4f}</td><td>${r['target']:.4f}</td>
              <td style="color:{chg_c}">{r['change']:+.4f} ({r['change_pct']:+.2f}%)</td>
              <td style="color:{pnl_c}">${r['paper_profit']:,.2f} ({r['paper_profit_pct']:+.2f}%)</td>
              <td style="color:{sc};font-weight:700">{score_val}</td>
              <td>{r['suggestion']}</td>
            </tr>"""

    mobile_cards = ""
    for r in rows:
        chg_c = _color(r["change"])
        pnl_c = _color(r["paper_profit"])
        t10_c = "var(--green)" if r["target_10_gap"] <= 0 else "var(--text-muted)"
        t10_txt = "已达成 ✓" if r["target_10_gap"] <= 0 else f"还差 {r['target_10_gap']:.2f}%"
        tech = r.get("tech")
        sc = _score_color(tech["score"]) if tech else "var(--text-muted)"
        score_val = tech["score"] if tech else "—"
        signal_txt = tech["signal"] if tech else "—"
        mobile_cards += f"""
        <div class="stock-card">
          <div class="stock-card-header">
            <span class="stock-name">{r['name']}</span>
            <span class="stock-suggestion">{r['suggestion']}</span>
          </div>
          <div class="stock-card-grid">
            <div class="metric"><span class="metric-label">持仓</span><span class="metric-value">{r['shares']} 股</span></div>
            <div class="metric"><span class="metric-label">占比</span><span class="metric-value">{r['weight']:.1f}%</span></div>
            <div class="metric"><span class="metric-label">成本价</span><span class="metric-value">${r['cost']:.2f}</span></div>
            <div class="metric"><span class="metric-label">当前价</span><span class="metric-value">${r['close']:.4f}</span></div>
            <div class="metric"><span class="metric-label">今日涨跌</span><span class="metric-value" style="color:{chg_c}">{r['change']:+.4f} ({r['change_pct']:+.2f}%)</span></div>
            <div class="metric"><span class="metric-label">账面收益</span><span class="metric-value" style="color:{pnl_c}">${r['paper_profit']:,.2f} ({r['paper_profit_pct']:+.2f}%)</span></div>
            <div class="metric"><span class="metric-label">年化收益</span><span class="metric-value" style="color:{pnl_c}">{r['annualized_pct']:+.1f}%</span></div>
            <div class="metric"><span class="metric-label">技术评分</span><span class="metric-value" style="color:{sc}">{score_val} {signal_txt}</span></div>
          </div>
        </div>"""

    stock_detail_cards = ""
    for r, a in zip(rows, analyses):
        chg_c = _color(r["change"])
        net_c = _color(a["net_profit"])
        ann_c = _color(a["annualized_pct"])
        q = r["quotes"]
        tech = r.get("tech")
        tech_html = _build_tech_section(tech)
        div_recv = dividends.get(r["name"], 0)
        div_row = f'<tr><td>已收股息</td><td style="color:var(--green)">+${div_recv:.2f}</td></tr>' if div_recv > 0 else ""
        t10_c = "var(--green)" if a["target_10_gap"] <= 0 else "var(--red)"
        t10_txt = f"已达成 ✓ (当前 {a['paper_profit_pct']:+.2f}%)" if a["target_10_gap"] <= 0 else f"还差 {a['target_10_gap']:.2f}%"

        stock_detail_cards += f"""
        <div class="card">
          <h3>{r['name']} ({r['symbol']})</h3>
          <div class="quote-grid">
            <div class="metric"><span class="metric-label">昨日开盘</span><span class="metric-value">${q['prev_open']:.4f}</span></div>
            <div class="metric"><span class="metric-label">昨日收盘</span><span class="metric-value">${q['prev_close']:.4f}</span></div>
            <div class="metric"><span class="metric-label">今日开盘</span><span class="metric-value">${q['open']:.4f}</span></div>
            <div class="metric"><span class="metric-label">今日收盘</span><span class="metric-value">${q['close']:.4f}</span></div>
            <div class="metric"><span class="metric-label">今日最高</span><span class="metric-value" style="color:var(--green)">${q['high']:.4f}</span></div>
            <div class="metric"><span class="metric-label">今日最低</span><span class="metric-value" style="color:var(--red)">${q['low']:.4f}</span></div>
          </div>

          {tech_html}
          {_build_fundamental_section(r.get("fund"))}
          {_build_news_section(r.get("news", []))}

          <h4 class="detail-subtitle">盈亏分析（如果今天卖出）</h4>
          <table class="kv-table">
            <tr><td>投资金额</td><td>${a['investment']:,.2f}</td></tr>
            <tr><td>买入费用</td><td>${a['buy_fee']:.2f}</td></tr>
            <tr><td>当前市值</td><td>${a['current_value']:,.2f}</td></tr>
            <tr><td>账面收益</td><td style="color:{_color(a['paper_profit'])}">${a['paper_profit']:+,.2f} ({a['paper_profit_pct']:+.2f}%)</td></tr>
            <tr><td>卖出费用</td><td>-${a['sell_fee']:.2f}</td></tr>
            <tr><td>持有天数</td><td>{a['holding_days']} 天</td></tr>
            <tr><td>CPF 机会成本 (3.5%)</td><td>-${a['cpf_cost']:.2f}</td></tr>
            {div_row}
            <tr class="row-highlight"><td>真实盈亏</td><td style="color:{net_c}">${a['net_profit']:+,.2f} ({a['net_profit_pct']:+.2f}%)</td></tr>
            <tr><td>年化收益率</td><td style="color:{ann_c}">{a['annualized_pct']:+.1f}%</td></tr>
            <tr><td>距 10% 目标收益</td><td style="color:{t10_c}">{t10_txt}</td></tr>
          </table>
        </div>"""

    advice_items = ""
    for r in rows:
        if "可卖出" in r["suggestion"]:
            icon, action = "✅", f"已超目标价，收益率 {r['paper_profit_pct']:+.2f}%，可考虑部分落袋"
        elif "接近目标" in r["suggestion"]:
            icon, action = "⚠️", "接近目标价，密切关注，准备操作"
        elif "止损" in r["suggestion"]:
            icon, action = "🔻", f"亏损 {abs(r['paper_profit_pct']):.2f}%，考虑止损或设定观察期"
        else:
            icon, action = "⏳", f"继续持有，距目标收益 10% 还差 {r['target_10_gap']:.2f}%" if r['target_10_gap'] > 0 else "已达 10% 目标但未达保本目标价"
        tech = r.get("tech")
        tech_note = f" | 技术评分 {tech['score']} ({tech['signal']})" if tech else ""
        advice_items += f"""
          <div class="advice-item">
            <span class="advice-icon">{icon}</span>
            <div>
              <div class="advice-stock">{r['name']}</div>
              <div class="advice-action">{action}{tech_note}</div>
            </div>
          </div>"""

    tp_c = _color(totals["paper_profit"])
    tn_c = _color(totals["net_profit"])
    ann_c = _color(totals["annualized_pct"])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>CPF 投资组合报告 — {now_str}</title>
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
  .totals{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px}}
  .total-card{{background:var(--card-bg);border-radius:10px;padding:14px 12px;text-align:center}}
  .total-card .label{{color:var(--text-muted);font-size:0.75rem;margin-bottom:4px}}
  .total-card .value{{font-size:1.15rem;font-weight:700;word-break:break-all}}
  .advice-banner{{background:var(--card-bg);border-radius:10px;padding:14px 16px;margin-bottom:20px;border-left:4px solid var(--accent);font-size:0.95rem;font-weight:600}}
  .macro-banner{{background:var(--card-bg);border-radius:10px;padding:10px 16px;margin-bottom:12px;font-size:0.82rem;color:var(--text-muted);text-align:center;border:1px solid var(--border)}}
  .card{{background:var(--card-bg);border-radius:10px;padding:16px;margin-bottom:12px}}
  .card h3{{margin-bottom:10px;font-size:0.95rem;color:#60a5fa}}
  .detail-subtitle{{font-size:0.85rem;color:var(--text-muted);margin:18px 0 8px;padding-top:12px;border-top:1px solid var(--border)}}
  .quote-grid,.stock-card-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
  .metric{{display:flex;flex-direction:column}}.metric-label{{font-size:0.72rem;color:var(--text-muted)}}.metric-value{{font-size:0.9rem;font-weight:600}}
  .stock-card{{background:var(--card-bg);border-radius:10px;padding:14px;margin-bottom:10px}}
  .stock-card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px}}
  .stock-name{{font-size:1rem;font-weight:700;color:#60a5fa}}.stock-suggestion{{font-size:0.75rem;color:var(--text-muted)}}
  .desktop-table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}
  .desktop-table table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
  .desktop-table th,.desktop-table td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}}
  .desktop-table th{{background:var(--card-bg);color:var(--text-muted);font-weight:600}}
  .desktop-table tr:hover{{background:rgba(30,41,59,0.5)}}
  .kv-table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
  .kv-table td{{padding:7px 4px;border-bottom:1px solid var(--border)}}
  .kv-table td:first-child{{color:var(--text-muted);width:55%}}.kv-table td:last-child{{text-align:right;font-weight:500}}
  .row-highlight td{{font-weight:700!important;border-top:2px solid var(--border);padding-top:10px}}
  .advice-item{{display:flex;gap:10px;align-items:flex-start;padding:12px 0;border-bottom:1px solid var(--border)}}
  .advice-item:last-child{{border-bottom:none}}.advice-icon{{font-size:1.2rem;flex-shrink:0;margin-top:2px}}
  .advice-stock{{font-weight:700;color:#60a5fa;font-size:0.9rem}}.advice-action{{font-size:0.82rem;color:var(--text-muted);margin-top:2px}}
  .note{{background:var(--card-bg);border-radius:10px;padding:16px;font-size:0.78rem;color:var(--text-muted);line-height:1.8}}
  .note strong{{color:var(--text)}}
  .mobile-cards{{display:block}}
  .tech-header{{display:flex;justify-content:space-between;align-items:center;margin:18px 0 8px;padding-top:12px;border-top:1px solid var(--border)}}
  .tech-title{{font-size:0.85rem;color:var(--text-muted);font-weight:600}}
  .tech-score{{width:48px;height:48px;border:2px solid;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center}}
  .score-num{{font-size:18px;font-weight:800;line-height:1}}.score-label{{font-size:9px;color:var(--text-muted)}}
  .tech-signal{{font-size:0.82rem;font-weight:600;margin-bottom:10px}}
  .tech-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
  .tech-card{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px}}
  .tech-card-title{{font-size:0.7rem;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}}
  .tech-card-main{{font-size:0.85rem;font-weight:700;color:var(--text);margin-bottom:6px}}
  .ind-row{{display:flex;justify-content:space-between;padding:2px 0;font-size:0.75rem;color:var(--text-muted)}}
  .ind-row span:last-child{{color:var(--text);font-weight:500}}
  .tech-note{{font-size:0.8rem;color:var(--text-muted);padding:12px 0;border-top:1px solid var(--border);margin-top:12px}}
  .rsi-bar{{height:6px;border-radius:3px;display:flex;overflow:hidden;position:relative;margin:6px 0 2px}}
  .rsi-zone{{height:100%}}.rsi-oversold{{width:30%;background:#1b5e20}}.rsi-neutral{{width:40%;background:#37474f}}.rsi-overbought{{width:30%;background:#b71c1c}}
  .rsi-pointer{{position:absolute;top:-2px;width:2px;height:10px;background:#fff;border-radius:1px;transform:translateX(-50%)}}
  .rsi-labels{{display:flex;justify-content:space-between;font-size:0.6rem;color:var(--text-muted)}}
  .news-item{{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--border)}}
  .news-item:last-child{{border-bottom:none}}.news-icon{{flex-shrink:0;margin-top:2px}}
  .news-content{{min-width:0}}.news-title{{font-size:0.8rem;color:var(--text);text-decoration:none;display:block;overflow:hidden;text-overflow:ellipsis}}
  .news-title:hover{{color:var(--accent)}}.news-source{{font-size:0.65rem;color:var(--text-muted)}}
  @media(min-width:768px){{
    body{{padding:32px}}h1{{font-size:1.6rem}}.totals{{grid-template-columns:repeat(4,1fr)}}.total-card .value{{font-size:1.3rem}}
    .quote-grid{{grid-template-columns:repeat(3,1fr)}}.stock-card-grid{{grid-template-columns:repeat(3,1fr)}}
    .mobile-cards{{display:none}}.kv-table{{font-size:0.88rem}}.kv-table td:first-child{{width:50%}}
    .tech-grid{{grid-template-columns:repeat(4,1fr)}}
  }}
  @media(max-width:374px){{
    body{{padding:10px;font-size:14px}}.total-card .value{{font-size:1rem}}.stock-card-grid{{grid-template-columns:1fr 1fr}}
    .quote-grid{{grid-template-columns:1fr 1fr}}.tech-grid{{grid-template-columns:1fr 1fr}}
  }}
</style>
</head>
<body>
<h1>📊 CPF 投资组合每日报告</h1>
<p class="subtitle">{now_str} (SGT)</p>
{_build_macro_banner(macro)}

<div class="desktop-table">
  <table>
    <thead><tr><th>产品</th><th>持仓</th><th>占比</th><th>成本价</th><th>当前价</th><th>目标价</th><th>今日涨跌</th><th>账面收益</th><th>评分</th><th>交易建议</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>
<div class="mobile-cards">{mobile_cards}</div>

<div class="totals">
  <div class="total-card"><div class="label">投资总额</div><div class="value">${totals['investment']:,.2f}</div></div>
  <div class="total-card"><div class="label">当前市值</div><div class="value">${totals['current_value']:,.2f}</div></div>
  <div class="total-card"><div class="label">账面收益</div><div class="value" style="color:{tp_c}">${totals['paper_profit']:+,.2f}<br><small>({totals['paper_profit_pct']:+.2f}%)</small></div></div>
  <div class="total-card"><div class="label">真实盈亏</div><div class="value" style="color:{tn_c}">${totals['net_profit']:+,.2f}<br><small>({totals['net_profit_pct']:+.2f}%)</small></div></div>
</div>
<div class="advice-banner">{advice}</div>

<h2 class="section-title">个股详情 & 技术分析</h2>
{stock_detail_cards}

<h2 class="section-title">总体真实盈亏</h2>
<div class="card">
  <table class="kv-table">
    <tr><td>投资总额</td><td>${totals['investment']:,.2f}</td></tr>
    <tr><td>当前市值</td><td>${totals['current_value']:,.2f}</td></tr>
    <tr><td>账面收益</td><td style="color:{tp_c}">${totals['paper_profit']:+,.2f}</td></tr>
    <tr><td>卖出费用合计</td><td>-${totals['sell_fee']:,.2f}</td></tr>
    <tr><td>CPF 机会成本合计</td><td>-${totals['cpf_cost']:,.2f}</td></tr>
    <tr><td>已收股息合计</td><td style="color:var(--green)">+${totals['dividends']:,.2f}</td></tr>
    <tr class="row-highlight"><td>真实盈亏</td><td style="color:{tn_c}">${totals['net_profit']:+,.2f} ({totals['net_profit_pct']:+.2f}%)</td></tr>
    <tr><td>组合年化收益率</td><td style="color:{ann_c}">{totals['annualized_pct']:+.1f}%</td></tr>
    <tr><td>若全部留在 CPF OA</td><td>${totals['cpf_cost']:,.2f} ({CPF_OA_RATE*100:.1f}% p.a.)</td></tr>
    <tr><td>跑赢 CPF OA</td><td style="color:{_color(totals['net_profit'])}">${totals['net_profit'] + totals['cpf_cost']:+,.2f}</td></tr>
  </table>
</div>

<h2 class="section-title">交易建议</h2>
<div class="card">{advice_items}</div>

<h2 class="section-title">说明</h2>
<div class="note">
  <strong>目标价格</strong>：卖出后不亏钱的最低价格（含所有交易费用）<br>
  <strong>真实盈亏</strong>：账面收益 - 卖出费用 - CPF机会成本 + 已收股息<br>
  <strong>技术评分</strong>：综合 RSI/MACD/均线/布林带，满分100。>70偏多 | 50-70中性 | <50偏空<br>
  <strong>年化收益率</strong>：收益率 x (365 / 持有天数)<br>
  <strong>CPF 机会成本</strong>：CPF OA 利率 3.5% p.a.<br>
  <strong>交易费用</strong>：DBS Vickers 佣金 0.18% 或最低 $27.25 + 清算费 + 交易费 + 结算费<br>
  <strong>数据来源</strong>：Yahoo Finance（可能有 15 分钟延迟）
</div>
</body>
</html>"""


def build_markdown(rows, totals, analyses, macro=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    advice = _advice_summary(rows)
    dividends = config.get("dividends_received", {})
    lines = [f"## CPF 投资组合报告 {now_str}\n"]
    if macro:
        lines.append(f"> 🌍 {macro['summary']}\n")
    lines.append(f"> {advice}\n")

    lines.append("### 持仓汇总\n")
    lines.append("| 产品 | 当前价 | 涨跌 | 盈亏 | 评分 | 信号 |")
    lines.append("|------|--------|------|------|------|------|")
    for r in rows:
        sign = "📈" if r["change"] >= 0 else "📉"
        tech = r.get("tech")
        score = str(tech["score"]) if tech else "—"
        signal = tech["signal"] if tech else "—"
        lines.append(
            f"| {r['name']} | ${r['close']:.2f} "
            f"| {sign} {r['change_pct']:+.2f}% "
            f"| ${r['paper_profit']:+,.2f} ({r['paper_profit_pct']:+.2f}%) "
            f"| {score} | {signal} |"
        )

    lines.append("")
    pp, np_ = totals["paper_profit"], totals["net_profit"]
    pe = "📈" if pp >= 0 else "📉"
    ne = "✅" if np_ >= 0 else "❌"
    lines.append(f"**投资**: ${totals['investment']:,.2f} → **市值**: ${totals['current_value']:,.2f}")
    lines.append(f"**账面**: {pe} ${pp:+,.2f} ({totals['paper_profit_pct']:+.2f}%) | **真实**: {ne} ${np_:+,.2f} ({totals['net_profit_pct']:+.2f}%)")
    lines.append(f"**年化**: {totals['annualized_pct']:+.1f}%\n")

    lines.append("### 交易建议\n")
    for r in rows:
        tech = r.get("tech")
        tech_note = f"(评分{tech['score']})" if tech else ""
        if "可卖出" in r["suggestion"]:
            lines.append(f"- ✅ **{r['name']}** {tech_note}: 已超目标，收益 {r['paper_profit_pct']:+.2f}%，可考虑落袋")
        elif "接近目标" in r["suggestion"]:
            lines.append(f"- ⚠️ **{r['name']}** {tech_note}: 接近目标价")
        elif "止损" in r["suggestion"]:
            lines.append(f"- 🔻 **{r['name']}** {tech_note}: 亏损 {abs(r['paper_profit_pct']):.2f}%")
        else:
            lines.append(f"- ⏳ **{r['name']}** {tech_note}: 持有观察")

    return "\n".join(lines)
