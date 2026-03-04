#!/usr/bin/env python3
"""
A股投资组合微信推送脚本 v2
功能：
  1. 读取 /home/ubuntu/stock_data.json 生成摘要
  2. 将报告推送到 GitHub Pages 获取公开链接（国内可访问）
  3. 通过Server酱推送链接+持仓摘要到微信
  4. 如果 GitHub Pages 推送失败，回退到 CDN 上传
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, date
from pathlib import Path

import requests

# Server酱 SendKey
SENDKEY = "SCT316237TB991Emt4QDffzexJQcebE1eP"

DATA_PATH = "/home/ubuntu/stock_data.json"
REPORT_PATH = "/home/ubuntu/daily_stock_report.html"

# GitHub Pages 配置
REPO_DIR = "/home/ubuntu/portfolio-tracker"
GITHUB_PAGES_URL = "https://teddy8023mars.github.io/portfolio-tracker/output/a_stock_report.html"


def push_to_github_pages(report_path):
    """将报告推送到 GitHub Pages，返回公开 URL"""
    try:
        repo = Path(REPO_DIR)
        if not repo.exists():
            # 克隆仓库
            subprocess.run(
                ["gh", "repo", "clone", "teddy8023mars/portfolio-tracker", REPO_DIR],
                check=True, capture_output=True, text=True, timeout=30
            )

        # 复制报告到仓库
        dest = repo / "output" / "a_stock_report.html"
        dest.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy2(report_path, str(dest))

        # Git add, commit, push
        subprocess.run(["git", "add", "output/a_stock_report.html"], cwd=REPO_DIR, check=True, capture_output=True)

        # 尝试 commit（如果没有变化会失败，忽略）
        commit_result = subprocess.run(
            ["git", "commit", "-m", f"A股日报 {date.today()}"],
            cwd=REPO_DIR, capture_output=True, text=True
        )

        # Pull rebase 再 push
        subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            cwd=REPO_DIR, check=True, capture_output=True, text=True, timeout=30
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=REPO_DIR, check=True, capture_output=True, text=True, timeout=30
        )

        print(f"  ✅ 已推送 GitHub Pages → {GITHUB_PAGES_URL}", file=sys.stderr)
        return GITHUB_PAGES_URL
    except Exception as e:
        print(f"  ⚠️ GitHub Pages 推送失败: {e}", file=sys.stderr)
        return None


def upload_html_cdn(html_path):
    """备选方案：上传HTML报告到CDN，返回公开URL"""
    try:
        result = subprocess.run(
            ["manus-upload-file", html_path],
            capture_output=True, text=True, timeout=120
        )
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
    except Exception as e:
        print(f"  ⚠️ CDN上传失败: {e}", file=sys.stderr)
        return None


def build_markdown_summary(data, report_url=None):
    """构建Markdown摘要"""
    stocks = data["stocks"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [f"## A股投资组合报告 {now_str}\n"]

    profit_count = sum(1 for s in stocks if s["profit_pct"] >= 0)
    loss_count = len(stocks) - profit_count
    lines.append(f"> 共 {len(stocks)} 只股票 | 📈盈利 {profit_count} | 📉亏损 {loss_count}\n")

    lines.append("| 股票 | 现价 | 涨跌 | 盈亏 | 评分 |")
    lines.append("|------|------|------|------|------|")
    for s in stocks:
        q = s["quotes"]
        tech = s.get("technicals")
        sign = "📈" if q["change"] >= 0 else "📉"
        score = str(tech["score"]) if tech else "—"
        delayed = " ⏰" if s.get("is_delayed") else ""
        lines.append(
            f"| {s['name']}{delayed} | ¥{q['current_price']:.3f} "
            f"| {sign} {q['change_pct']:+.2f}% "
            f"| {s['profit_pct']:+.2f}% "
            f"| {score} |"
        )

    lines.append("")
    lines.append("### 操作建议\n")
    for s in stocks:
        tech = s.get("technicals")
        if tech:
            score = tech["score"]
            advice = tech["advice"]
            if score >= 70:
                icon = "✅"
            elif score >= 50:
                icon = "⏳"
            elif score >= 35:
                icon = "⚠️"
            else:
                icon = "🔻"
            lines.append(f"- {icon} **{s['name']}** (评分{score}): {advice}")
        else:
            lines.append(f"- ⚪ **{s['name']}**: 数据不足")

    md = "\n".join(lines)
    if report_url:
        md += f"\n\n---\n[📄 查看完整HTML报告]({report_url})"

    return md


def send_to_wechat(title, desp):
    """通过Server酱推送到微信"""
    url = f"https://sctapi.ftqq.com/{SENDKEY}.send"
    resp = requests.post(url, data={"title": title, "desp": desp}, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result


def main():
    print(f"[{datetime.now()}] 开始推送A股投资组合报告到微信 ...", file=sys.stderr)

    # 读取数据
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    stocks = data["stocks"]

    # 1) 优先推送到 GitHub Pages
    report_url = None
    if os.path.exists(REPORT_PATH):
        print("  📤 正在推送报告到 GitHub Pages ...", file=sys.stderr)
        report_url = push_to_github_pages(REPORT_PATH)

        # 如果 GitHub Pages 失败，回退到 CDN
        if not report_url:
            print("  📤 回退到 CDN 上传 ...", file=sys.stderr)
            report_url = upload_html_cdn(REPORT_PATH)
            if report_url:
                print(f"  ✅ CDN链接: {report_url}", file=sys.stderr)
    else:
        print(f"  ⚠️ HTML报告不存在: {REPORT_PATH}，将仅推送摘要文字", file=sys.stderr)

    # 2) 构建Markdown摘要
    md = build_markdown_summary(data, report_url)

    # 3) 推送到微信
    up_count = sum(1 for s in stocks if s["quotes"]["change"] >= 0)
    down_count = len(stocks) - up_count

    title_date = datetime.now().strftime("%m/%d")
    title = f"A股组合 {title_date} 📈{up_count}涨 📉{down_count}跌"

    print(f"  📱 推送标题: {title}", file=sys.stderr)
    result = send_to_wechat(title, md)

    if result.get("code") == 0 or result.get("errno") == 0:
        print(f"  ✅ 微信推送成功！", file=sys.stderr)
    else:
        print(f"  ⚠️ Server酱返回: {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)

    print(f"[{datetime.now()}] 完成！", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 推送失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
