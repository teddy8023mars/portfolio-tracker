import subprocess
import sys
from datetime import date
from pathlib import Path

import requests
from lib import config


def push_github(repo_dir):
    """Git add, commit, push report.html to GitHub Pages. Returns pages URL."""
    pages_url = config.get("github_pages_url")
    try:
        subprocess.run(["git", "add", "output/report.html"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"daily report {date.today()}"],
            cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, check=True, capture_output=True, timeout=30)
        print(f"  ✅ 已推送 GitHub Pages → {pages_url}", file=sys.stderr)
    except Exception as e:
        print(f"  ⚠️ GitHub 推送失败 ({e})", file=sys.stderr)
    return pages_url


def push_wechat(title, desp):
    """Send message via Server酱 to WeChat."""
    sendkey = config.get("sendkey")
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    resp = requests.post(url, data={"title": title, "desp": desp}, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") == 0 or result.get("errno") == 0:
        print("  ✅ 微信推送成功", file=sys.stderr)
    else:
        print(f"  ⚠️ Server酱返回: {result}", file=sys.stderr)
