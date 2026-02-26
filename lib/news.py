"""News sentiment: Google News RSS scraping + keyword-based sentiment classification."""

import re
import sys
from html import unescape
from urllib.parse import quote
from datetime import datetime

import requests

POSITIVE_KEYWORDS = {
    "upgrade", "upgrades", "upgraded", "buy", "outperform", "overweight",
    "profit", "profits", "earnings beat", "record", "surge", "surges",
    "growth", "grows", "dividend", "dividends", "hike", "raises",
    "bullish", "rally", "rallies", "gain", "gains", "strong",
    "recovery", "recover", "optimistic", "positive", "boost",
    "expansion", "expand", "acquisition", "deal", "partnership",
}

NEGATIVE_KEYWORDS = {
    "downgrade", "downgrades", "downgraded", "sell", "underperform", "underweight",
    "loss", "losses", "earnings miss", "decline", "declines", "drop", "drops",
    "fall", "falls", "plunge", "plunges", "crash", "slump", "weak",
    "risk", "risks", "warning", "warns", "concern", "concerns",
    "bearish", "recession", "layoff", "layoffs", "cut", "cuts",
    "debt", "default", "fraud", "investigation", "lawsuit", "fine",
    "inflation", "headwind", "slowdown", "contraction",
}

SEARCH_TERMS = {
    "D05.SI":  "DBS Group Holdings SGX",
    "C38U.SI": "CapitaLand Integrated Commercial Trust",
    "ES3.SI":  "Straits Times Index ETF Singapore",
}


def _classify(title):
    lower = title.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in lower)
    if pos > neg:
        return "positive", "🟢"
    if neg > pos:
        return "negative", "🔴"
    return "neutral", "⚪"


def _parse_rss(xml_text):
    """Simple regex-based RSS parser — no lxml dependency needed."""
    items = []
    for match in re.finditer(r"<item>(.*?)</item>", xml_text, re.DOTALL):
        block = match.group(1)
        title_m = re.search(r"<title>(.*?)</title>", block)
        link_m = re.search(r"<link>(.*?)</link>", block)
        date_m = re.search(r"<pubDate>(.*?)</pubDate>", block)
        source_m = re.search(r"<source[^>]*>(.*?)</source>", block)
        if title_m:
            title = unescape(title_m.group(1).strip())
            link = link_m.group(1).strip() if link_m else ""
            pub_date = date_m.group(1).strip() if date_m else ""
            source = unescape(source_m.group(1).strip()) if source_m else ""
            items.append({"title": title, "link": link, "date": pub_date, "source": source})
    return items


def fetch_news(symbols, max_per_stock=3):
    """
    Fetch recent news for each symbol via Google News RSS.
    Returns dict: {symbol: [{"title", "link", "source", "sentiment", "icon"}, ...]}
    """
    result = {}
    for sym in symbols:
        query = SEARCH_TERMS.get(sym, sym)
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-SG&gl=SG&ceid=SG:en"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            items = _parse_rss(resp.text)[:max_per_stock]
            news_list = []
            for item in items:
                sentiment, icon = _classify(item["title"])
                news_list.append({
                    "title": item["title"],
                    "link": item["link"],
                    "source": item["source"],
                    "sentiment": sentiment,
                    "icon": icon,
                })
            result[sym] = news_list
            print(f"  📰 {sym}: {len(news_list)} 条新闻", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️ 新闻获取失败 {sym}: {e}", file=sys.stderr)
            result[sym] = []
    return result
