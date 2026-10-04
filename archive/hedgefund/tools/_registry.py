"""The token registry, read from the one copy the repo tracks (data/rh_stock_tokens.json)."""
import json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_tokens():
    """symbol -> {"address": ...} for every stock token, plus USDG and WETH."""
    d = json.load(open(os.path.join(HERE, "data", "rh_stock_tokens.json")))
    out = {s: {"address": a} for s, a in d["stock_tokens"].items()}
    out["USDG"] = {"address": d["USDG"]}
    out["WETH"] = {"address": d["WETH"]}
    return out
