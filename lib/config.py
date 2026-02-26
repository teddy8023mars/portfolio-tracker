import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_cache = None


def load():
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def portfolio():
    return load()["portfolio"]


def fees():
    return load()["fees"]


def scoring_weights():
    return load()["scoring_weights"]


def get(key, default=None):
    return load().get(key, default)
