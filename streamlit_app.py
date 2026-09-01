import base64
from email.message import EmailMessage
import json
import math
import os
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="AI Market Intelligence Terminal", layout="wide")


def load_local_env():
    if not os.path.exists(".env"):
        return
    with open(".env", "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_local_env()


BULLISH_TERMS = {
    "beat": 1.2,
    "accelerated": 1.1,
    "raised": 1.1,
    "rallied": 1.0,
    "improved": 0.8,
    "strong": 0.9,
    "resilient": 0.7,
    "growth": 0.8,
    "gained": 0.8,
    "breakout": 0.9,
    "upgrade": 0.7,
    "leadership": 0.8,
    "gains": 0.75,
}

BEARISH_TERMS = {
    "declined": -1.1,
    "cuts": -0.9,
    "pressured": -0.9,
    "scrutiny": -0.8,
    "investigation": -1.0,
    "fear": -0.9,
    "weak": -0.9,
    "risk": -0.65,
    "stretched": -0.55,
    "competition": -0.35,
    "volatility": -0.45,
    "exposure": -0.55,
}

EVENT_RULES = {
    "Earnings": ["earnings", "revenue", "margins", "guidance", "estimates", "profitability"],
    "Macro/Fed": ["fed", "rate", "yield", "dollar", "inflation"],
    "Regulatory": ["regulatory", "scrutiny", "sec", "investigation", "safety"],
    "Sector Rotation": ["sector", "semiconductor", "bank", "cloud", "capex"],
    "Options/Positioning": ["options", "traders", "implied", "resistance", "breakout"],
    "Product/AI": ["ai", "gpu", "iphone", "roadmap", "features"],
}

DEMO_MARKET = {
    "NVDA": {
        "candles": [
            906, 912, 918, 913, 927, 944, 951, 948, 959, 971, 964, 982,
            995, 1004, 1018, 1032, 1027, 1048, 1064, 1080, 1074, 1095, 1112, 1121,
        ],
        "volume": [
            44, 47, 48, 46, 52, 56, 58, 55, 60, 65, 62, 68,
            72, 73, 76, 82, 79, 86, 91, 94, 90, 98, 103, 108,
        ],
    },
    "TSLA": {
        "candles": [
            178, 181, 176, 174, 169, 171, 168, 165, 162, 164, 159, 156,
            158, 153, 150, 148, 151, 146, 144, 142, 145, 141, 139, 136,
        ],
        "volume": [
            75, 78, 81, 84, 88, 82, 90, 92, 95, 89, 101, 104,
            96, 108, 112, 118, 105, 121, 126, 129, 118, 132, 137, 140,
        ],
    },
}

DEMO_TEXT = [
    {
        "id": "demo-earnings",
        "source": "demo-news",
        "timestamp": "2026-05-25T13:00:00Z",
        "text": "NVIDIA beat revenue expectations as data center demand accelerated and management raised guidance.",
    },
    {
        "id": "demo-sector",
        "source": "demo-news",
        "timestamp": "2026-05-25T12:00:00Z",
        "text": "Semiconductor stocks rallied after cloud capex commentary improved across hyperscalers.",
    },
    {
        "id": "demo-social",
        "source": "demo-social",
        "timestamp": "2026-05-25T11:00:00Z",
        "text": "Traders warn that valuation is stretched, but momentum remains strong into the AI conference.",
    },
]

SP500_FALLBACK_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B", "LLY", "AVGO",
    "JPM", "TSLA", "XOM", "UNH", "V", "MA", "COST", "WMT", "PG", "JNJ",
    "HD", "ABBV", "BAC", "KO", "NFLX", "CRM", "AMD", "PEP", "TMO", "LIN",
    "CSCO", "ACN", "MCD", "ORCL", "WFC", "ABT", "GE", "INTU", "DIS", "IBM",
]

NASDAQ100_FALLBACK_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "AVGO", "GOOGL", "GOOG", "TSLA", "COST",
    "NFLX", "AMD", "PEP", "ADBE", "CSCO", "TMUS", "INTU", "QCOM", "AMAT", "TXN",
    "AMGN", "HON", "CMCSA", "ISRG", "BKNG", "LRCX", "SBUX", "GILD", "ADP", "MDLZ",
    "PANW", "MU", "ADI", "MELI", "KLAC", "SNPS", "CDNS", "MAR", "REGN", "CRWD",
]

def secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


DEFAULT_HEADERS = {"User-Agent": "ai-market-intelligence-terminal/1.0"}
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def get_json(url, headers=None, params=None, timeout=20):
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    response = requests.get(url, headers=merged_headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def normalize_text(text):
    allowed = []
    for char in text.lower():
        allowed.append(char if char.isalnum() or char in "$%- " else " ")
    return " ".join("".join(allowed).split())


def tokenize(text):
    return [token for token in normalize_text(text).split() if len(token) > 2]


def score_sentiment(text):
    raw = 0
    evidence = []
    for token in tokenize(text):
        if token in BULLISH_TERMS:
            raw += BULLISH_TERMS[token]
            evidence.append(token)
        if token in BEARISH_TERMS:
            raw += BEARISH_TERMS[token]
            evidence.append(token)
    score = math.tanh(raw / 3)
    confidence = min(0.96, 0.42 + len(evidence) * 0.09 + abs(score) * 0.22)
    label = "Bullish" if score > 0.16 else "Bearish" if score < -0.16 else "Neutral"
    return {"label": label, "score": round(score, 3), "confidence": round(confidence, 2), "evidence": evidence[:5]}


def classify_event(text):
    tokens = set(tokenize(text))
    ranked = sorted(
        ((label, sum(term in tokens for term in terms)) for label, terms in EVENT_RULES.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    return ranked[0][0] if ranked and ranked[0][1] else "General Market"


def analyze_text(items):
    seen = set()
    analyzed = []
    for item in sorted(items, key=lambda row: row["timestamp"], reverse=True):
        clean = normalize_text(item["text"])
        fingerprint = clean[:80]
        if fingerprint in seen or any(spam in clean for spam in ["guaranteed", "100x", "free money", "click here"]):
            continue
        seen.add(fingerprint)
        sentiment = score_sentiment(clean)
        analyzed.append({**item, "cleanText": clean, "sentiment": sentiment, "eventType": classify_event(clean)})
    return analyzed


def aggregate_sentiment(items):
    if not items:
        return {"label": "Neutral", "score": 0, "confidence": 0.4, "topEvents": []}
    weighted = sum(item["sentiment"]["score"] * item["sentiment"]["confidence"] for item in items) / len(items)
    score = max(-1, min(1, weighted))
    label = "Bullish" if score > 0.16 else "Bearish" if score < -0.16 else "Neutral"
    event_counts = {}
    for item in items:
        event_counts[item["eventType"]] = event_counts.get(item["eventType"], 0) + 1
    return {
        "label": label,
        "score": round(score, 3),
        "confidence": round(sum(item["sentiment"]["confidence"] for item in items) / len(items), 2),
        "topEvents": sorted(event_counts, key=event_counts.get, reverse=True)[:3],
    }


def fetch_alpaca(symbol):
    key = secret("ALPACA_API_KEY")
    api_secret = secret("ALPACA_API_SECRET")
    feed = secret("ALPACA_DATA_FEED", "iex")
    if not key or not api_secret:
        return None, None, "missing-alpaca-secrets"
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": api_secret, "accept": "application/json"}
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=70)
    bars_url = "https://data.alpaca.markets/v2/stocks/bars"
    bar_params = {
        "symbols": symbol,
        "timeframe": "1Day",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "limit": 1000,
        "adjustment": "split",
        "feed": feed,
    }
    latest_url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest?feed={feed}"
    try:
        bars = get_json(bars_url, headers=headers, params=bar_params).get("bars", {}).get(symbol, [])
        latest = get_json(latest_url, headers=headers).get("quote", {})
    except Exception as error:
        return None, None, f"alpaca-error: {str(error)[:140]}"
    candles = [bar["c"] for bar in bars][-24:]
    volume = [(bar.get("v") or 0) / 1_000_000 for bar in bars][-24:]
    if candles and latest.get("ap") and latest.get("bp"):
        candles[-1] = round((latest["ap"] + latest["bp"]) / 2, 2)
    return candles, volume, f"alpaca:{feed}"


def fetch_finnhub_news(symbol):
    token = secret("FINNHUB_API_KEY")
    if not token:
        return []
    to_day = datetime.now().date()
    from_day = to_day - timedelta(days=7)
    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={from_day}&to={to_day}&token={token}"
    try:
        payload = get_json(url)
    except Exception:
        return []
    return [
        {
            "id": f"finnhub-{item.get('id', item.get('datetime'))}",
            "source": "news",
            "timestamp": datetime.fromtimestamp(item.get("datetime", 0), timezone.utc).isoformat(),
            "text": " ".join(part for part in [item.get("headline", ""), item.get("summary", "")] if part),
        }
        for item in payload[:12]
    ]


def fetch_stocktwits(symbol):
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    headers = {}
    username = secret("STOCKTWITS_USERNAME")
    password = secret("STOCKTWITS_PASSWORD")
    if username and password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["authorization"] = f"Basic {token}"
    try:
        payload = get_json(url, headers=headers)
    except Exception:
        return []
    return [
        {
            "id": f"stocktwits-{message['id']}",
            "source": "stocktwits",
            "timestamp": message["created_at"],
            "text": message["body"],
        }
        for message in payload.get("messages", [])[:12]
    ]


def fetch_yahoo_chart(symbol, range_name, interval):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": range_name, "interval": interval, "includePrePost": "false", "events": "div,splits"}
    try:
        result = get_json(url, headers=YAHOO_HEADERS, params=params, timeout=25)["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quote.get("close", [])
        highs = quote.get("high", [])
        volumes = quote.get("volume", [])
    except Exception:
        return []

    rows = []
    for index, timestamp in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue
        rows.append(
            {
                "time": datetime.fromtimestamp(timestamp, timezone.utc),
                "close": round(float(close), 4),
                "high": round(float(highs[index]), 4) if index < len(highs) and highs[index] is not None else round(float(close), 4),
                "volume": (volumes[index] or 0) / 1_000_000 if index < len(volumes) else 0,
            }
        )
    return rows


def fetch_chart_ranges(symbol, fallback_candles, fallback_volume):
    ranges = {
        "1D": fetch_yahoo_chart(symbol, "1d", "5m"),
        "1M": fetch_yahoo_chart(symbol, "1mo", "1d"),
        "1Y": fetch_yahoo_chart(symbol, "1y", "1d"),
        "3Y": fetch_yahoo_chart(symbol, "3y", "1wk"),
        "5Y": fetch_yahoo_chart(symbol, "5y", "1mo"),
    }
    if not ranges["1M"]:
        now = datetime.now(timezone.utc)
        ranges["1M"] = [
            {"time": now - timedelta(days=len(fallback_candles) - index), "close": price, "high": price, "volume": fallback_volume[index]}
            for index, price in enumerate(fallback_candles)
        ]
    return ranges


def fetch_yahoo_market_snapshot(symbol):
    rows = fetch_yahoo_chart(symbol, "1mo", "1d")
    if not rows:
        return None, None, "missing-yahoo-market-data"
    recent = rows[-24:]
    candles = [row["close"] for row in recent]
    volume = [row["volume"] for row in recent]
    return candles, volume, "yahoo"


def yahoo_symbol(symbol):
    return symbol.replace(".", "-")


@st.cache_data(ttl=24 * 60 * 60)
def fetch_sp500_symbols():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        html = requests.get(url, headers=YAHOO_HEADERS, timeout=20).text
        tables = pd.read_html(html)
        symbols = tables[0]["Symbol"].astype(str).tolist()
        return [symbol.strip() for symbol in symbols if symbol.strip()]
    except Exception:
        return SP500_FALLBACK_SYMBOLS


@st.cache_data(ttl=24 * 60 * 60)
def fetch_nasdaq100_symbols():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        html = requests.get(url, headers=YAHOO_HEADERS, timeout=20).text
        tables = pd.read_html(html)
        for table in tables:
            for column in table.columns:
                if str(column).lower() in {"ticker", "symbol"}:
                    symbols = table[column].astype(str).tolist()
                    return [symbol.strip() for symbol in symbols if symbol.strip() and symbol.strip().lower() != "nan"]
    except Exception:
        return NASDAQ100_FALLBACK_SYMBOLS
    return NASDAQ100_FALLBACK_SYMBOLS


def screen_52w_drawdowns(symbols, threshold_pct=15, max_symbols=None):
    selected_symbols = symbols[:max_symbols] if max_symbols else symbols
    results = []
    progress = st.progress(0, text="Scanning 52-week highs...")

    for index, symbol in enumerate(selected_symbols):
        rows = fetch_yahoo_chart(yahoo_symbol(symbol), "1y", "1d")
        if rows:
            current = rows[-1]["close"]
            high_52 = max(row["high"] for row in rows if row.get("high"))
            low_52 = min(row["close"] for row in rows if row.get("close"))
            distance_pct = ((current - high_52) / high_52) * 100 if high_52 else 0
            if distance_pct <= -threshold_pct:
                results.append(
                    {
                        "Symbol": symbol,
                        "Current": round(current, 2),
                        "52W High": round(high_52, 2),
                        "52W Low": round(low_52, 2),
                        "% From 52W High": round(distance_pct, 2),
                        "Drawdown %": round(abs(distance_pct), 2),
                    }
                )
        progress.progress((index + 1) / max(1, len(selected_symbols)), text=f"Scanned {index + 1}/{len(selected_symbols)}")

    progress.empty()
    return sorted(results, key=lambda row: row["Drawdown %"], reverse=True)


def consolidation_metrics(symbol):
    rows = fetch_yahoo_chart(yahoo_symbol(symbol), "3mo", "1d")
    if len(rows) < 25:
        return None

    recent = rows[-20:]
    closes = [row["close"] for row in recent if row.get("close")]
    highs = [row["high"] for row in recent if row.get("high")]
    volumes = [row["volume"] for row in recent if row.get("volume") is not None]
    if len(closes) < 15:
        return None

    current = closes[-1]
    range_high = max(highs or closes)
    range_low = min(closes)
    range_pct = ((range_high - range_low) / current) * 100 if current else 0
    drift_pct = ((current - closes[0]) / closes[0]) * 100 if closes[0] else 0
    returns = [(closes[index] - closes[index - 1]) / closes[index - 1] for index in range(1, len(closes)) if closes[index - 1]]
    avg_return = sum(returns) / len(returns) if returns else 0
    volatility = math.sqrt(sum((value - avg_return) ** 2 for value in returns) / max(1, len(returns))) * math.sqrt(252) * 100
    range_position = ((current - range_low) / (range_high - range_low)) if range_high != range_low else 0.5
    avg_volume = sum(volumes) / max(1, len(volumes))
    latest_volume_ratio = volumes[-1] / avg_volume if avg_volume else 1

    tight_range_score = max(0, min(1, (12 - range_pct) / 12))
    low_drift_score = max(0, min(1, (6 - abs(drift_pct)) / 6))
    low_vol_score = max(0, min(1, (45 - volatility) / 45))
    midpoint_score = max(0, 1 - abs(range_position - 0.5) * 2)
    score = tight_range_score * 0.38 + low_drift_score * 0.26 + low_vol_score * 0.22 + midpoint_score * 0.14

    if score >= 0.72:
        phase = "Strong consolidation"
    elif score >= 0.55:
        phase = "Possible consolidation"
    else:
        phase = "Not consolidating"

    return {
        "Symbol": symbol,
        "Current": round(current, 2),
        "Phase": phase,
        "Consolidation Score": round(score * 100, 1),
        "20D Range %": round(range_pct, 2),
        "20D Drift %": round(drift_pct, 2),
        "Annualized Vol %": round(volatility, 2),
        "Range Position %": round(range_position * 100, 2),
        "Volume Ratio": round(latest_volume_ratio, 2),
        "Support": round(range_low, 2),
        "Resistance": round(range_high, 2),
    }


def screen_consolidation(symbols, min_score=55, max_symbols=None):
    selected_symbols = symbols[:max_symbols] if max_symbols else symbols
    results = []
    progress = st.progress(0, text="Scanning consolidation setups...")

    for index, symbol in enumerate(selected_symbols):
        metrics = consolidation_metrics(symbol)
        if metrics and metrics["Consolidation Score"] >= min_score:
            results.append(metrics)
        progress.progress((index + 1) / max(1, len(selected_symbols)), text=f"Scanned {index + 1}/{len(selected_symbols)}")

    progress.empty()
    return sorted(results, key=lambda row: row["Consolidation Score"], reverse=True)


def neutral_sentiment():
    return {"label": "Neutral", "score": 0, "confidence": 0.4, "topEvents": []}


def suggested_trade_metrics(symbol, include_nlp=False):
    rows = fetch_yahoo_chart(yahoo_symbol(symbol), "1y", "1d")
    if len(rows) < 30:
        return None

    recent = rows[-24:]
    candles = [row["close"] for row in recent]
    volume = [row["volume"] for row in recent]
    if len(candles) < 20 or not all(candles):
        return None

    analyzed = []
    sentiment = neutral_sentiment()
    if include_nlp:
        text_items = fetch_finnhub_news(symbol) + fetch_stocktwits(symbol)
        analyzed = analyze_text(text_items)
        sentiment = aggregate_sentiment(analyzed)

    tech = technicals(candles, volume)
    tech["macdSignificance"] = macd_significance(tech["macdHistogram"], tech["bias"])
    levels = key_levels(candles, tech)
    charts = {"1Y": rows}
    week_52 = week_52_position(charts, tech["lastPrice"])
    volume_view = volume_analysis(candles, volume)
    overbought = overbought_indicator(tech, volume_view)
    risk = risk_score(candles, sentiment)
    irrationality = irrationality_gauge(analyzed, sentiment, tech, risk, volume_view) if include_nlp else {
        "score": 0,
        "level": "Low",
        "label": "Not evaluated",
        "explanation": "NLP was not included in this scan.",
        "drivers": [],
    }

    trend_points = ((tech["trendStrength"] + 1) / 2) * 25
    sentiment_points = ((sentiment["score"] + 1) / 2) * 18 if include_nlp else 9
    volume_points = 9 if volume_view["label"] in {"Bullish accumulation", "Participation increasing"} else -8 if volume_view["label"] == "Distribution pressure" else 1
    level_points = {
        "Breakout": 13,
        "Near support": 7,
        "Between levels": 2,
        "Near resistance": -7,
        "Breakdown": -13,
    }.get(levels["status"], 0)
    week_52_points = 5 if week_52["drawdownPct"] <= 10 else 2 if week_52["drawdownPct"] <= 25 else -4
    overbought_penalty = overbought["score"] * 10
    risk_penalty = risk["score"] * 15
    irrationality_penalty = irrationality["score"] * 8
    score = max(0, min(100, trend_points + sentiment_points + volume_points + level_points + week_52_points - overbought_penalty - risk_penalty - irrationality_penalty + 35))

    if levels["status"] == "Breakout" and volume_view["label"] in {"Bullish accumulation", "Participation increasing"} and overbought["level"] != "High":
        side = "Bullish"
        trade_type = "Breakout long watch"
    elif levels["status"] == "Near support" and risk["level"] != "High":
        side = "Bullish"
        trade_type = "Support bounce watch"
    elif tech["bias"] == "Bullish Momentum" and levels["status"] != "Near resistance" and overbought["level"] != "High":
        side = "Bullish"
        trade_type = "Momentum continuation watch"
    elif levels["status"] == "Breakdown" or risk["level"] == "High":
        side = "Bearish"
        trade_type = "Downside risk / avoid long"
    else:
        side = "Neutral"
        trade_type = "Wait for confirmation"

    if score >= 72 and side == "Bullish":
        recommendation = "Bullish - Strong Watch"
    elif score >= 58 and side == "Bullish":
        recommendation = "Bullish - Watch"
    elif side == "Bearish":
        recommendation = "Bearish - Avoid Long"
    else:
        recommendation = "Neutral - Wait"

    rr = risk_reward_profile(side, tech["lastPrice"], levels)
    rationale = (
        f"{side} bias. {trade_type}: {tech['bias']}; key levels are {levels['status'].lower()}; "
        f"volume is {volume_view['label'].lower()}; overbought risk is {overbought['level'].lower()}; "
        f"risk is {risk['level'].lower()}; risk/reward is {rr['ratioLabel']}."
    )

    return {
        "Symbol": symbol,
        "Side": side,
        "Recommendation": recommendation,
        "Trade Type": trade_type,
        "Score": round(score, 1),
        "Current": round(tech["lastPrice"], 2),
        "Support": levels["nearestSupport"],
        "Resistance": levels["nearestResistance"],
        "Risk/Reward": rr["ratioLabel"],
        "Reward %": rr["rewardPct"],
        "Risk %": rr["riskPct"],
        "Stop Context": rr["stop"],
        "Target Context": rr["target"],
        "Trend": tech["bias"],
        "MACD Hist": tech["macdHistogram"],
        "Volume": volume_view["label"],
        "Overbought": overbought["level"],
        "Risk": risk["level"],
        "52W Drawdown %": week_52["drawdownPct"],
        "Irrationality": irrationality["level"],
        "Sentiment": sentiment["label"],
        "Rationale": rationale,
    }


def screen_suggested_trades(symbols, min_score=58, max_symbols=None, include_nlp=False):
    selected_symbols = symbols[:max_symbols] if max_symbols else symbols
    results = []
    progress = st.progress(0, text="Scoring trade candidates...")

    for index, symbol in enumerate(selected_symbols):
        metrics = suggested_trade_metrics(symbol, include_nlp=include_nlp)
        if metrics and metrics["Score"] >= min_score:
            results.append(metrics)
        progress.progress((index + 1) / max(1, len(selected_symbols)), text=f"Scored {index + 1}/{len(selected_symbols)}")

    progress.empty()
    return sorted(results, key=lambda row: row["Score"], reverse=True)


def risk_reward_profile(side, current_price, levels):
    support = levels["nearestSupport"]
    resistance = levels["nearestResistance"]
    recent_range = max(0.01, levels["recentHigh"] - levels["recentLow"])

    if side == "Bearish":
        stop = resistance if resistance > current_price else current_price + recent_range * 0.5
        target = support if support < current_price else current_price - recent_range
    else:
        stop = support if support < current_price else current_price - recent_range * 0.5
        target = resistance if resistance > current_price else current_price + recent_range

    risk = abs(current_price - stop)
    reward = abs(target - current_price)
    ratio = reward / risk if risk else 0

    if ratio >= 2:
        label = f"{ratio:.2f}:1 favorable"
    elif ratio >= 1:
        label = f"{ratio:.2f}:1 balanced"
    elif ratio > 0:
        label = f"{ratio:.2f}:1 weak"
    else:
        label = "N/A"

    return {
        "ratio": round(ratio, 2),
        "ratioLabel": label,
        "riskPct": round((risk / current_price) * 100, 2) if current_price else 0,
        "rewardPct": round((reward / current_price) * 100, 2) if current_price else 0,
        "stop": round(stop, 2),
        "target": round(target, 2),
    }


def average_true_range(rows, period=14):
    recent = rows[-period:]
    ranges = [
        max(
            row.get("high") or row.get("close") or 0,
            row.get("close") or 0,
        )
        - min(
            row.get("low") or row.get("close") or 0,
            row.get("close") or 0,
        )
        for row in recent
        if row.get("close")
    ]
    return sum(ranges) / len(ranges) if ranges else 0


def chart_take_profit(side, entry, levels, atr):
    recent_range = max(0.01, levels["recentHigh"] - levels["recentLow"])
    midpoint = (levels["recentHigh"] + levels["recentLow"]) / 2
    min_move = max(atr * 0.35, entry * 0.004)

    if side == "Long / Buy":
        candidates = [
            ("nearest resistance", levels["nearestResistance"], 4),
            ("recent 20-day high", levels["recentHigh"], 3),
            ("range midpoint retrace", midpoint, 2),
            ("measured range extension", entry + recent_range * 0.75, 1),
        ]
        valid = [(name, price, weight) for name, price, weight in candidates if price > entry + min_move]
    else:
        candidates = [
            ("nearest support", levels["nearestSupport"], 4),
            ("recent 20-day low", levels["recentLow"], 3),
            ("range midpoint retrace", midpoint, 2),
            ("measured range extension", entry - recent_range * 0.75, 1),
        ]
        valid = [(name, price, weight) for name, price, weight in candidates if price < entry - min_move]

    if not valid:
        fallback = entry + recent_range if side == "Long / Buy" else entry - recent_range
        return {
            "price": fallback,
            "basis": "measured recent range",
            "explanation": "No nearby chart level was far enough from entry, so the planner used the recent trading range as a fallback target.",
        }

    def target_score(candidate):
        _, price, weight = candidate
        distance = abs(price - entry)
        distance_score = 1 / max(distance / max(atr, entry * 0.01), 0.25)
        return weight + distance_score

    basis, price, _ = max(valid, key=target_score)
    return {
        "price": price,
        "basis": basis,
        "explanation": f"The take-profit is based on the {basis}, which is the nearest high-probability chart reaction area for this direction.",
    }


def trade_plan(symbol, side, position_status, manual_entry=None):
    rows = fetch_yahoo_chart(yahoo_symbol(symbol), "1y", "1d")
    if len(rows) < 30:
        return None

    recent = rows[-24:]
    candles = [row["close"] for row in recent if row.get("close")]
    volume = [row["volume"] for row in recent if row.get("close")]
    if len(candles) < 20:
        return None

    tech = technicals(candles, volume)
    levels = key_levels(candles, tech)
    volume_view = volume_analysis(candles, volume)
    risk = risk_score(candles, neutral_sentiment())
    overbought = overbought_indicator(tech, volume_view)
    current = tech["lastPrice"]
    entry = manual_entry if position_status == "Already entered" and manual_entry else current
    planning_price = current
    atr = average_true_range(rows)
    recent_range = max(0.01, levels["recentHigh"] - levels["recentLow"])
    buffer = max(atr * 0.25, planning_price * 0.003)

    if side == "Long / Buy":
        stop = levels["nearestSupport"] - buffer
        if stop >= planning_price:
            stop = planning_price - max(atr, recent_range * 0.5, planning_price * 0.01)
        directional_note = "Long plan: protect below nearby support and look for upside into the most relevant chart-based reaction area."
    else:
        stop = levels["nearestResistance"] + buffer
        if stop <= planning_price:
            stop = planning_price + max(atr, recent_range * 0.5, planning_price * 0.01)
        directional_note = "Short plan: protect above nearby resistance and look for downside into the most relevant chart-based reaction area."

    target = chart_take_profit(side, planning_price, levels, atr)
    displayed_current = round(current, 2)
    displayed_entry = round(entry, 2)
    displayed_stop = round(stop, 2)
    displayed_target = round(target["price"], 2)
    risk_amount = abs(displayed_current - displayed_stop)
    reward = abs(displayed_target - displayed_current)
    ratio = reward / risk_amount if risk_amount else 0
    entry_pnl = (
        ((displayed_current - displayed_entry) / displayed_entry) * 100
        if side == "Long / Buy"
        else ((displayed_entry - displayed_current) / displayed_entry) * 100
    ) if displayed_entry else 0

    if ratio >= 2:
        ratio_label = f"{ratio:.2f}:1 favorable"
    elif ratio >= 1:
        ratio_label = f"{ratio:.2f}:1 balanced"
    elif ratio > 0:
        ratio_label = f"{ratio:.2f}:1 weak"
    else:
        ratio_label = "N/A"

    return {
        "symbol": symbol,
        "side": side,
        "positionStatus": position_status,
        "current": displayed_current,
        "entry": displayed_entry,
        "stop": displayed_stop,
        "takeProfit": displayed_target,
        "takeProfitBasis": target["basis"],
        "takeProfitExplanation": target["explanation"],
        "entryPnlPct": round(entry_pnl, 2),
        "riskPct": round((risk_amount / displayed_current) * 100, 2) if displayed_current else 0,
        "rewardPct": round((reward / displayed_current) * 100, 2) if displayed_current else 0,
        "riskReward": round(ratio, 2),
        "riskRewardLabel": ratio_label,
        "riskAmount": round(risk_amount, 2),
        "rewardAmount": round(reward, 2),
        "levels": levels,
        "tech": tech,
        "risk": risk,
        "volume": volume_view,
        "overbought": overbought,
        "atr": round(atr, 2),
        "note": directional_note,
    }


def tradier_headers():
    token = secret("TRADIER_API_TOKEN")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def tradier_get(path, params=None):
    headers = tradier_headers()
    if not headers:
        raise RuntimeError("Missing Tradier API token")
    base_url = secret("TRADIER_BASE_URL", "https://api.tradier.com/v1").rstrip("/")
    response = requests.get(f"{base_url}{path}", headers=headers, params=params or {}, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_tradier_quote(symbol):
    data = tradier_get("/markets/quotes", {"symbols": symbol})
    quote = data.get("quotes", {}).get("quote")
    if isinstance(quote, list):
        quote = quote[0] if quote else {}
    return quote or {}


def fetch_tradier_expirations(symbol):
    data = tradier_get("/markets/options/expirations", {"symbol": symbol, "includeAllRoots": "true"})
    dates = data.get("expirations", {}).get("date", [])
    if isinstance(dates, str):
        dates = [dates]
    return dates


def fetch_tradier_chain(symbol, expiration):
    data = tradier_get(
        "/markets/options/chains",
        {"symbol": symbol, "expiration": expiration, "greeks": "true"},
    )
    options = data.get("options", {}).get("option", [])
    if isinstance(options, dict):
        options = [options]
    return options or []


def option_mid(option):
    bid = float(option.get("bid") or 0)
    ask = float(option.get("ask") or 0)
    last = float(option.get("last") or 0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    return round(last, 2) if last > 0 else 0


def option_delta(option):
    greeks = option.get("greeks") or {}
    try:
        return round(float(greeks.get("delta", 0)), 3)
    except (TypeError, ValueError):
        return 0


def liquid_options(options, option_type):
    filtered = []
    for option in options:
        if option.get("option_type") != option_type:
            continue
        mid = option_mid(option)
        if mid <= 0:
            continue
        filtered.append({**option, "mid": mid, "deltaValue": option_delta(option)})
    return sorted(filtered, key=lambda row: float(row.get("strike") or 0))


def nearest_by_strike(options, target, below=None):
    candidates = []
    for option in options:
        strike = float(option.get("strike") or 0)
        if below is True and strike > target:
            continue
        if below is False and strike < target:
            continue
        candidates.append(option)
    if not candidates:
        candidates = options
    return min(candidates, key=lambda row: abs(float(row.get("strike") or 0) - target)) if candidates else None


def spread_short_leg(options, long_leg, boundary_price, bias):
    if not long_leg:
        return None
    long_strike = float(long_leg.get("strike") or 0)
    if bias == "Bullish":
        candidates = [option for option in options if float(option.get("strike") or 0) > long_strike]
    else:
        candidates = [option for option in options if float(option.get("strike") or 0) < long_strike]
    if not candidates:
        return None
    return min(candidates, key=lambda row: abs(float(row.get("strike") or 0) - boundary_price))


def option_contract_summary(option):
    if not option:
        return {}
    return {
        "Symbol": option.get("symbol"),
        "Strike": float(option.get("strike") or 0),
        "Type": option.get("option_type", "").upper(),
        "Bid": float(option.get("bid") or 0),
        "Ask": float(option.get("ask") or 0),
        "Mid": option.get("mid", option_mid(option)),
        "Delta": option.get("deltaValue", option_delta(option)),
        "Volume": int(option.get("volume") or 0),
        "Open Interest": int(option.get("open_interest") or 0),
    }


def build_options_idea(symbol, bias, boundary_price, expiration):
    quote = fetch_tradier_quote(symbol)
    current = float(quote.get("last") or quote.get("close") or quote.get("bid") or quote.get("ask") or 0)
    chain = fetch_tradier_chain(symbol, expiration)
    if not current or not chain:
        return None

    if bias == "Bullish":
        calls = liquid_options(chain, "call")
        long_leg = nearest_by_strike(calls, current, below=True)
        short_leg = spread_short_leg(calls, long_leg, boundary_price, bias)
        strategy = "Bull Call Debit Spread"
        thesis = "Bullish but capped: buy a call near the current price and sell a call near the price you do not expect it to exceed."
    else:
        puts = liquid_options(chain, "put")
        long_leg = nearest_by_strike(puts, current, below=False)
        short_leg = spread_short_leg(puts, long_leg, boundary_price, bias)
        strategy = "Bear Put Debit Spread"
        thesis = "Bearish but bounded: buy a put near the current price and sell a put near the price you do not expect it to fall below."

    if not long_leg or not short_leg:
        return None

    long_strike = float(long_leg.get("strike") or 0)
    short_strike = float(short_leg.get("strike") or 0)
    width = abs(short_strike - long_strike)
    debit = max(0, round(float(long_leg["mid"]) - float(short_leg["mid"]), 2))
    max_profit = max(0, round(width - debit, 2))
    breakeven = round(long_strike + debit, 2) if bias == "Bullish" else round(long_strike - debit, 2)
    rr = round(max_profit / debit, 2) if debit else 0

    single_option = long_leg
    return {
        "symbol": symbol,
        "bias": bias,
        "current": round(current, 2),
        "expiration": expiration,
        "boundary": boundary_price,
        "strategy": strategy,
        "thesis": thesis,
        "longLeg": option_contract_summary(long_leg),
        "shortLeg": option_contract_summary(short_leg),
        "singleOption": option_contract_summary(single_option),
        "debit": debit,
        "width": round(width, 2),
        "maxProfit": max_profit,
        "breakeven": breakeven,
        "riskReward": f"{rr}:1" if rr else "N/A",
        "explanation": (
            f"The spread uses the long leg near current price ${round(current, 2)} and the short leg near your "
            f"{'upside ceiling' if bias == 'Bullish' else 'downside floor'} of ${boundary_price}. "
            "This keeps the idea aligned with your view instead of choosing a random strike."
        ),
    }


AI_TRADES_DB = "ai_trades.sqlite3"


def ai_trade_db():
    connection = sqlite3.connect(AI_TRADES_DB)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry REAL NOT NULL,
            stop_loss REAL NOT NULL,
            target_1 REAL NOT NULL,
            target_2 REAL NOT NULL,
            score REAL NOT NULL,
            risk_reward REAL NOT NULL,
            status TEXT NOT NULL,
            last_price REAL,
            rationale TEXT NOT NULL,
            instructions TEXT NOT NULL,
            data_json TEXT NOT NULL,
            alert_email TEXT,
            alerted_at TEXT,
            closed_at TEXT
        )
        """
    )
    connection.commit()
    return connection


def current_stock_price(symbol):
    candles, _, _ = fetch_yahoo_market_snapshot(yahoo_symbol(symbol))
    if candles:
        return round(candles[-1], 2)
    rows = fetch_yahoo_chart(yahoo_symbol(symbol), "5d", "1d")
    closes = [row["close"] for row in rows if row.get("close")]
    return round(closes[-1], 2) if closes else None


def parse_ratio(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).split(":")[0].split()[0])
    except (TypeError, ValueError, IndexError):
        return 0


def ai_trade_instructions(symbol, side, entry, stop, target_1, target_2, metrics, plan):
    direction = "long" if side == "Bullish" else "short"
    trigger = (
        f"Look for price to hold above ${entry} with improving volume before considering the {direction} idea."
        if side == "Bullish"
        else f"Look for price to stay below ${entry} with weak bounces before considering the {direction} idea."
    )
    return (
        f"{symbol} {side.lower()} watch. Trigger: {trigger} "
        f"Stop/invalidation: ${stop}. Target 1: ${target_1}. Target 2: ${target_2}. "
        f"Manage risk first: if price hits the stop, the setup is considered failed; if price reaches Target 1, "
        "consider whether to reduce risk or trail based on volume and trend confirmation. "
        f"Core reason: {metrics['Rationale']} Trade planner context: {plan['takeProfitExplanation']}"
    )


def openai_ai_trade_rationale(trade):
    api_key = secret("OPENAI_API_KEY")
    if not api_key:
        return trade["instructions"]
    model = secret("OPENAI_MODEL", "gpt-5.2")
    payload = {
        "model": model,
        "instructions": "You are an institutional equity trade research assistant. Be concise. Do not give personalized financial advice.",
        "input": (
            f"Create a concise educational trade-plan explanation for this AI-generated stock setup.\n"
            f"Symbol: {trade['symbol']}\nSide: {trade['side']}\nEntry area: {trade['entry']}\n"
            f"Stop: {trade['stop_loss']}\nTarget 1: {trade['target_1']}\nTarget 2: {trade['target_2']}\n"
            f"Score: {trade['score']}\nRisk/reward: {trade['risk_reward']}:1\n"
            f"Rationale: {trade['rationale']}\nInstructions: {trade['instructions']}\n"
            "Return five compact lines: setup, trigger, stop/invalidation, targets, why it is attractive."
        ),
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("output_text") or trade["instructions"]


def build_ai_trade(symbol, include_nlp=False):
    metrics = suggested_trade_metrics(symbol, include_nlp=include_nlp)
    if not metrics or metrics["Side"] not in {"Bullish", "Bearish"}:
        return None

    planner_side = "Long / Buy" if metrics["Side"] == "Bullish" else "Short / Sell"
    plan = trade_plan(symbol, planner_side, "Entering now")
    if not plan:
        return None

    entry = plan["current"]
    stop = plan["stop"]
    target_1 = plan["takeProfit"]
    reward = abs(target_1 - entry)
    target_2 = round(entry + reward * 1.5, 2) if metrics["Side"] == "Bullish" else max(0.01, round(entry - reward * 1.5, 2))
    rr = parse_ratio(plan["riskReward"])

    trade = {
        "symbol": symbol,
        "side": metrics["Side"],
        "entry": entry,
        "stop_loss": stop,
        "target_1": target_1,
        "target_2": target_2,
        "score": metrics["Score"],
        "risk_reward": rr,
        "status": "OPEN",
        "last_price": entry,
        "rationale": metrics["Rationale"],
        "instructions": ai_trade_instructions(symbol, metrics["Side"], entry, stop, target_1, target_2, metrics, plan),
        "data": {"metrics": metrics, "plan": plan},
    }
    try:
        trade["ai_explanation"] = openai_ai_trade_rationale(trade)
    except Exception:
        trade["ai_explanation"] = trade["instructions"]
    return trade


def scan_ai_trades(symbols, max_symbols=50, include_nlp=False, min_score=58, min_rr=1.0):
    selected_symbols = symbols[:max_symbols]
    results = []
    progress = st.progress(0, text="Scanning AI trade setups...")
    for index, symbol in enumerate(selected_symbols):
        trade = build_ai_trade(symbol, include_nlp=include_nlp)
        if trade and trade["score"] >= min_score and trade["risk_reward"] >= min_rr:
            results.append(trade)
        progress.progress((index + 1) / max(1, len(selected_symbols)), text=f"Scanned {index + 1}/{len(selected_symbols)}")
    progress.empty()
    return sorted(results, key=lambda row: (row["score"], row["risk_reward"]), reverse=True)


def save_ai_trade(trade, alert_email=None):
    connection = ai_trade_db()
    cursor = connection.execute(
        """
        INSERT INTO ai_trades (
            created_at, symbol, side, entry, stop_loss, target_1, target_2, score, risk_reward,
            status, last_price, rationale, instructions, data_json, alert_email
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            trade["symbol"],
            trade["side"],
            trade["entry"],
            trade["stop_loss"],
            trade["target_1"],
            trade["target_2"],
            trade["score"],
            trade["risk_reward"],
            trade["status"],
            trade["last_price"],
            trade["rationale"],
            trade.get("ai_explanation", trade["instructions"]),
            json.dumps(trade["data"]),
            alert_email,
        ),
    )
    connection.commit()
    connection.close()
    return cursor.lastrowid


def load_ai_trades():
    connection = ai_trade_db()
    rows = pd.read_sql_query("SELECT * FROM ai_trades ORDER BY created_at DESC", connection)
    connection.close()
    return rows


def ai_trade_status(row, last_price):
    side = row["side"]
    if side == "Bullish":
        if last_price <= row["stop_loss"]:
            return "LOST"
        if last_price >= row["target_2"]:
            return "WON_T2"
        if last_price >= row["target_1"]:
            return "WON_T1"
    else:
        if last_price >= row["stop_loss"]:
            return "LOST"
        if last_price <= row["target_2"]:
            return "WON_T2"
        if last_price <= row["target_1"]:
            return "WON_T1"
    return "OPEN"


def smtp_ready():
    return all(secret(name) for name in ["SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM"])


def send_trade_alert(to_email, row, last_price, new_status):
    if not to_email or not smtp_ready():
        return False
    message = EmailMessage()
    message["Subject"] = f"AI Trade Alert: {row['symbol']} {new_status}"
    message["From"] = secret("EMAIL_FROM")
    message["To"] = to_email
    message.set_content(
        f"{row['symbol']} {row['side']} trade level triggered.\n\n"
        f"Status: {new_status}\nLast price: ${last_price}\nEntry: ${row['entry']}\n"
        f"Stop: ${row['stop_loss']}\nTarget 1: ${row['target_1']}\nTarget 2: ${row['target_2']}\n\n"
        f"Original plan:\n{row['instructions']}"
    )
    port = int(secret("SMTP_PORT", "587"))
    with smtplib.SMTP(secret("SMTP_HOST"), port, timeout=20) as server:
        server.starttls()
        server.login(secret("SMTP_USERNAME"), secret("SMTP_PASSWORD"))
        server.send_message(message)
    return True


def monitor_ai_trades():
    rows = load_ai_trades()
    if rows.empty:
        return rows
    connection = ai_trade_db()
    updated = []
    for _, row in rows.iterrows():
        if row["status"] not in {"OPEN", "WON_T1"}:
            updated.append(row.to_dict())
            continue
        last_price = current_stock_price(row["symbol"])
        if not last_price:
            updated.append(row.to_dict())
            continue
        new_status = ai_trade_status(row, last_price)
        alerted_at = row.get("alerted_at")
        closed_at = row.get("closed_at")
        if new_status != row["status"]:
            closed_at = datetime.now(timezone.utc).isoformat() if new_status in {"LOST", "WON_T2"} else closed_at
            if not alerted_at and row.get("alert_email"):
                try:
                    if send_trade_alert(row["alert_email"], row, last_price, new_status):
                        alerted_at = datetime.now(timezone.utc).isoformat()
                except Exception:
                    alerted_at = alerted_at
        connection.execute(
            "UPDATE ai_trades SET status = ?, last_price = ?, alerted_at = ?, closed_at = ? WHERE id = ?",
            (new_status, last_price, alerted_at, closed_at, int(row["id"])),
        )
        updated_row = row.to_dict()
        updated_row.update({"status": new_status, "last_price": last_price, "alerted_at": alerted_at, "closed_at": closed_at})
        updated.append(updated_row)
    connection.commit()
    connection.close()
    return pd.DataFrame(updated)


def demo_market(symbol):
    market = DEMO_MARKET.get(symbol, DEMO_MARKET["NVDA"])
    return market["candles"], market["volume"], "demo"


def rsi(candles, period=14):
    changes = [candles[index] - candles[index - 1] for index in range(1, len(candles))]
    recent = changes[-period:]
    gains = [change for change in recent if change > 0]
    losses = [abs(change) for change in recent if change < 0]
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0.01
    return round(100 - 100 / (1 + avg_gain / avg_loss), 1)


def ema(values, period):
    result = [values[0]]
    smoothing = 2 / (period + 1)
    for value in values[1:]:
        result.append(value * smoothing + result[-1] * (1 - smoothing))
    return result


def technicals(candles, volume):
    fast = ema(candles, 12)
    slow = ema(candles, 26)
    macd_line = [fast[index] - slow[index] for index in range(len(candles))]
    signal = ema(macd_line, 9)
    histogram = macd_line[-1] - signal[-1]
    vwap = sum(price * volume[index] for index, price in enumerate(candles)) / max(1, sum(volume))
    trend_return = (candles[-1] - candles[0]) / candles[0]
    trend_strength = math.tanh(trend_return * 6 + histogram / max(1, candles[-1]) * 7)
    return {
        "lastPrice": candles[-1],
        "rsi": rsi(candles),
        "vwap": round(vwap, 2),
        "macdHistogram": round(histogram, 2),
        "trendStrength": round(trend_strength, 3),
        "bias": "Bullish Momentum" if trend_strength > 0.18 else "Bearish Momentum" if trend_strength < -0.18 else "Rangebound",
    }


def macd_significance(histogram, trend_bias):
    if histogram > 0.25 and trend_bias == "Bullish Momentum":
        return "MACD confirms bullish momentum because the fast trend is above the slower trend and expansion is positive."
    if histogram > 0:
        return "MACD is mildly constructive, but the signal is not strong enough by itself; confirmation from price and volume matters."
    if histogram < -0.25 and trend_bias == "Bearish Momentum":
        return "MACD confirms bearish pressure because downside momentum is expanding below the signal line."
    if histogram < 0:
        return "MACD is a caution flag: momentum is cooling even if price trend has not fully broken down."
    return "MACD is neutral, so the model leans more heavily on price trend, volume, sentiment, and risk."


def volume_analysis(candles, volume):
    recent_volume = volume[-1]
    baseline = sum(volume[:-1]) / max(1, len(volume) - 1)
    volume_ratio = recent_volume / baseline if baseline else 1
    price_change = (candles[-1] - candles[-2]) / candles[-2] if len(candles) > 1 else 0
    volume_trend = (sum(volume[-5:]) / 5) / max(0.001, sum(volume[:5]) / 5)

    if volume_ratio >= 1.5 and price_change > 0:
        label = "Bullish accumulation"
        explanation = "Price is rising on above-normal volume, which suggests buyers are participating rather than price drifting up on thin liquidity."
    elif volume_ratio >= 1.5 and price_change < 0:
        label = "Distribution pressure"
        explanation = "Price is falling on above-normal volume, which can signal heavier selling pressure or institutional distribution."
    elif volume_ratio <= 0.75 and abs(price_change) < 0.01:
        label = "Low-conviction consolidation"
        explanation = "Volume is below normal and price movement is muted, so the setup has less confirmation."
    elif volume_trend > 1.25:
        label = "Participation increasing"
        explanation = "Recent volume is trending above the early-period baseline, which means market participation is expanding."
    else:
        label = "Normal participation"
        explanation = "Volume is close to baseline, so the model treats price and sentiment signals as more important than volume."

    return {
        "label": label,
        "latest": round(recent_volume, 2),
        "baseline": round(baseline, 2),
        "ratio": round(volume_ratio, 2),
        "trend": round(volume_trend, 2),
        "priceChangePct": round(price_change * 100, 2),
        "explanation": explanation,
    }


def overbought_indicator(tech, volume_view):
    price = tech["lastPrice"]
    vwap = tech["vwap"]
    rsi_value = tech["rsi"]
    vwap_extension = ((price - vwap) / vwap) if vwap else 0

    rsi_pressure = max(0, (rsi_value - 60) / 25)
    vwap_pressure = max(0, vwap_extension / 0.08)
    volume_pressure = max(0, min(1, (volume_view["ratio"] - 1) / 1.2))
    score = max(0, min(1, rsi_pressure * 0.55 + vwap_pressure * 0.3 + volume_pressure * 0.15))

    if rsi_value >= 75 or score >= 0.72:
        level = "High"
        label = "Overbought risk"
        explanation = "Price is extended relative to momentum and/or VWAP, so chasing strength carries elevated pullback risk."
    elif rsi_value >= 65 or score >= 0.45:
        level = "Moderate"
        label = "Getting extended"
        explanation = "Momentum is firm, but the setup is becoming stretched; confirmation matters before adding exposure."
    elif rsi_value <= 35:
        level = "Low"
        label = "Oversold / not overbought"
        explanation = "RSI is low enough that the stock is not overbought; downside exhaustion or mean reversion may matter more."
    else:
        level = "Low"
        label = "Not overbought"
        explanation = "RSI and VWAP extension do not show a major overbought condition."

    return {
        "score": round(score, 2),
        "level": level,
        "label": label,
        "rsi": rsi_value,
        "vwapExtensionPct": round(vwap_extension * 100, 2),
        "explanation": explanation,
    }


def key_levels(candles, tech):
    current = candles[-1]
    recent_high = max(candles[-20:])
    recent_low = min(candles[-20:])
    prior_high = max(candles[-21:-1]) if len(candles) > 21 else max(candles[:-1])
    prior_low = min(candles[-21:-1]) if len(candles) > 21 else min(candles[:-1])
    vwap = tech["vwap"]
    midpoint = (recent_high + recent_low) / 2

    supports = sorted({round(recent_low, 2), round(prior_low, 2), round(vwap, 2), round(midpoint, 2)})
    resistances = sorted({round(recent_high, 2), round(prior_high, 2), round(vwap, 2), round(midpoint, 2)})
    support_below = [level for level in supports if level <= current]
    resistance_above = [level for level in resistances if level >= current]
    nearest_support = max(support_below) if support_below else min(supports)
    nearest_resistance = min(resistance_above) if resistance_above else max(resistances)
    support_distance = ((current - nearest_support) / current) if current else 0
    resistance_distance = ((nearest_resistance - current) / current) if current else 0

    if current > prior_high * 1.01:
        status = "Breakout"
        explanation = "Price is trading above recent resistance, so the setup has a breakout component."
    elif current < prior_low * 0.99:
        status = "Breakdown"
        explanation = "Price is trading below recent support, so downside technical risk is elevated."
    elif resistance_distance <= 0.015:
        status = "Near resistance"
        explanation = "Price is close to overhead resistance, so upside may need stronger volume confirmation."
    elif support_distance <= 0.015:
        status = "Near support"
        explanation = "Price is close to support, so risk/reward may depend on whether that level holds."
    else:
        status = "Between levels"
        explanation = "Price is between major support and resistance, so confirmation from momentum and sentiment matters more."

    return {
        "status": status,
        "current": round(current, 2),
        "nearestSupport": round(nearest_support, 2),
        "nearestResistance": round(nearest_resistance, 2),
        "supportDistancePct": round(support_distance * 100, 2),
        "resistanceDistancePct": round(resistance_distance * 100, 2),
        "recentHigh": round(recent_high, 2),
        "recentLow": round(recent_low, 2),
        "vwap": round(vwap, 2),
        "explanation": explanation,
    }


def week_52_position(charts, current_price):
    one_year = charts.get("1Y", [])
    highs = [row["high"] for row in one_year if row.get("high")]
    closes = [row["close"] for row in one_year if row.get("close")]
    if not highs:
        highs = closes or [current_price]
    high_52 = max(highs)
    low_52 = min(closes or highs)
    distance_from_high = ((current_price - high_52) / high_52) if high_52 else 0
    drawdown_pct = abs(min(0, distance_from_high)) * 100
    range_position = ((current_price - low_52) / (high_52 - low_52)) if high_52 != low_52 else 1

    if drawdown_pct <= 3:
        label = "Near 52-week high"
        explanation = "The stock is trading close to its 52-week high, so breakout continuation and overbought risk both matter."
    elif drawdown_pct <= 10:
        label = "Within striking distance"
        explanation = "The stock is below its 52-week high but still close enough that resistance and prior highs may influence behavior."
    elif drawdown_pct <= 25:
        label = "Moderate discount"
        explanation = "The stock is meaningfully below its 52-week high, which can reduce overbought pressure but may also reflect weaker momentum."
    else:
        label = "Deep drawdown"
        explanation = "The stock is far below its 52-week high, so recovery potential must be weighed against possible structural weakness."

    return {
        "high": round(high_52, 2),
        "low": round(low_52, 2),
        "current": round(current_price, 2),
        "distancePct": round(distance_from_high * 100, 2),
        "drawdownPct": round(drawdown_pct, 2),
        "rangePositionPct": round(max(0, min(1, range_position)) * 100, 2),
        "label": label,
        "explanation": explanation,
    }


def irrationality_gauge(analyzed_items, sentiment, tech, risk, volume_view):
    if not analyzed_items:
        return {
            "score": 0,
            "level": "Low",
            "label": "No signal",
            "explanation": "There is not enough live text data to evaluate market overreaction.",
            "drivers": [],
        }

    severe_events = {"Earnings", "Regulatory", "Macro/Fed"}
    high_signal_items = [
        item for item in analyzed_items if abs(item["sentiment"]["score"]) >= 0.45 or item["sentiment"]["confidence"] >= 0.7
    ]
    low_severity_share = sum(item["eventType"] not in severe_events for item in high_signal_items) / max(1, len(high_signal_items))
    source_mix = {item["source"] for item in analyzed_items[:10]}
    social_heavy = sum(item["source"] == "stocktwits" for item in analyzed_items[:10]) / max(1, min(10, len(analyzed_items)))
    sentiment_intensity = min(1, abs(sentiment["score"]) * 1.6)
    price_confirmation = min(1, abs(tech["trendStrength"]))
    volume_confirmation = min(1.4, volume_view["ratio"]) / 1.4
    risk_confirmation = risk["score"]

    hype_without_confirmation = max(0, sentiment_intensity - (price_confirmation * 0.35 + volume_confirmation * 0.25 + risk_confirmation * 0.2))
    social_amplifier = 0.16 if social_heavy >= 0.55 else 0
    weak_event_amplifier = 0.18 * low_severity_share
    single_source_penalty = 0.08 if len(source_mix) == 1 else 0
    score = max(0, min(1, hype_without_confirmation + social_amplifier + weak_event_amplifier + single_source_penalty))

    if score >= 0.68:
        level = "High"
        label = "Likely overreaction"
    elif score >= 0.42:
        level = "Moderate"
        label = "Possible overreaction"
    else:
        level = "Low"
        label = "Reaction looks supported"

    drivers = [
        f"Sentiment intensity: {round(sentiment_intensity, 2)}",
        f"Price confirmation: {round(price_confirmation, 2)}",
        f"Volume confirmation: {round(volume_confirmation, 2)}",
        f"Low-severity high-emotion share: {round(low_severity_share, 2)}",
    ]

    if score >= 0.42:
        explanation = (
            "The market may be overreacting because sentiment is stronger than the confirmation from price, volume, risk, "
            "or event severity. This is a cue to investigate the actual catalyst before trusting the crowd reaction."
        )
    else:
        explanation = (
            "The reaction appears reasonably supported by price, volume, risk, or event context, so the model is not flagging "
            "a major irrationality gap."
        )

    return {
        "score": round(score, 2),
        "level": level,
        "label": label,
        "explanation": explanation,
        "drivers": drivers,
    }


def risk_score(candles, sentiment):
    returns = [(candles[index] - candles[index - 1]) / candles[index - 1] for index in range(1, len(candles))]
    mean = sum(returns) / len(returns)
    realized_vol = math.sqrt(sum((value - mean) ** 2 for value in returns) / len(returns)) * math.sqrt(252)
    score = min(1, (realized_vol * 0.9 + abs(sentiment["score"]) * 0.4 + 0.2) / 1.4)
    return {"score": round(score, 2), "level": "High" if score > 0.68 else "Moderate" if score > 0.42 else "Low"}


def openai_explanation(symbol, tech, sentiment, risk, volume, irrationality, overbought, levels, week_52, confidence, items):
    api_key = secret("OPENAI_API_KEY")
    if not api_key:
        return None
    model = secret("OPENAI_MODEL", "gpt-5.2")
    headlines = "\n".join(f"- {item['source']}: {item['text'][:220]}" for item in items[:6])
    payload = {
        "model": model,
        "instructions": "You are an institutional market intelligence analyst. Be concise. Do not give personalized financial advice.",
        "input": (
            f"Ticker: {symbol}\nConfidence: {round(confidence * 100)}%\n"
            f"Regime: {tech['bias']}\nSentiment: {sentiment['label']} {sentiment['score']}\n"
            f"Risk: {risk['level']} {risk['score']}\nRSI: {tech['rsi']}\n"
            f"MACD histogram: {tech['macdHistogram']}\nMACD significance: {tech['macdSignificance']}\n"
            f"Volume: {volume['label']} | ratio {volume['ratio']}x | {volume['explanation']}\n"
            f"Market irrationality gauge: {irrationality['level']} ({irrationality['score']}) | {irrationality['label']} | {irrationality['explanation']}\n"
            f"Overbought indicator: {overbought['level']} ({overbought['score']}) | {overbought['label']} | RSI {overbought['rsi']} | VWAP extension {overbought['vwapExtensionPct']}% | {overbought['explanation']}\n"
            f"Key levels: {levels['status']} | current {levels['current']} | support {levels['nearestSupport']} ({levels['supportDistancePct']}% away) | resistance {levels['nearestResistance']} ({levels['resistanceDistancePct']}% away) | {levels['explanation']}\n"
            f"52-week position: current {week_52['current']} | high {week_52['high']} | distance from high {week_52['distancePct']}% | range position {week_52['rangePositionPct']}% | {week_52['explanation']}\n"
            f"Recent text:\n{headlines}\n"
            "Return exactly seven sentences: setup, 52-week context, key levels, MACD significance, overbought read, irrationality/overreaction read, then main risk."
        ),
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("output_text") or "".join(
        content.get("text", "") for item in data.get("output", []) for content in item.get("content", [])
    )


def analyze(symbol):
    candles, volume, provider = fetch_alpaca(symbol)
    if not candles or not volume:
        provider_status = provider
        candles, volume, provider = fetch_yahoo_market_snapshot(symbol)
        if not candles or not volume:
            candles, volume, provider = demo_market(symbol)
    else:
        provider_status = None

    charts = fetch_chart_ranges(symbol, candles, volume)
    text_items = fetch_finnhub_news(symbol) + fetch_stocktwits(symbol)
    if not text_items:
        text_items = DEMO_TEXT
    analyzed = analyze_text(text_items)
    sentiment = aggregate_sentiment(analyzed)
    tech = technicals(candles, volume)
    tech["macdSignificance"] = macd_significance(tech["macdHistogram"], tech["bias"])
    levels = key_levels(candles, tech)
    week_52 = week_52_position(charts, tech["lastPrice"])
    volume_view = volume_analysis(candles, volume)
    overbought = overbought_indicator(tech, volume_view)
    risk = risk_score(candles, sentiment)
    irrationality = irrationality_gauge(analyzed, sentiment, tech, risk, volume_view)
    volume_boost = max(-0.08, min(0.08, (volume_view["ratio"] - 1) * 0.06))
    irrationality_penalty = irrationality["score"] * 0.08
    overbought_penalty = overbought["score"] * 0.06
    level_adjustment = 0.04 if levels["status"] == "Breakout" else -0.05 if levels["status"] in {"Breakdown", "Near resistance"} else 0
    confidence = max(0, min(1, ((tech["trendStrength"] + 1) / 2) * 0.38 + ((sentiment["score"] + 1) / 2) * 0.34 + volume_boost + level_adjustment - risk["score"] * 0.2 - irrationality_penalty - overbought_penalty + 0.16))
    try:
        explanation = openai_explanation(symbol, tech, sentiment, risk, volume_view, irrationality, overbought, levels, week_52, confidence, analyzed)
        ai_mode = "OpenAI"
    except Exception as error:
        explanation = (
            f"{symbol} has a {round(confidence * 100)}% trade confidence score because {tech['bias'].lower()} "
            f"and {sentiment['label'].lower()} NLP sentiment are being weighed against {risk['level'].lower()} risk. "
            f"It is {week_52['distancePct']}% from its 52-week high. "
            f"Key levels status: {levels['status'].lower()}. "
            f"{tech['macdSignificance']} Volume is classified as {volume_view['label'].lower()}: {volume_view['explanation']} "
            f"Overbought indicator: {overbought['label'].lower()}. Irrationality gauge: {irrationality['label'].lower()}."
        )
        ai_mode = f"Rules ({str(error)[:80]})"
    return {
        "symbol": symbol,
        "candles": candles,
        "volume": volume,
        "charts": charts,
        "provider": provider,
        "sentiment": sentiment,
        "technicals": tech,
        "keyLevels": levels,
        "week52": week_52,
        "volumeAnalysis": volume_view,
        "overbought": overbought,
        "irrationality": irrationality,
        "risk": risk,
        "confidence": confidence,
        "explanation": explanation,
        "aiMode": ai_mode,
        "analyzed": analyzed,
        "providerStatus": provider_status,
    }


page = st.sidebar.radio(
    "Page",
    [
        "Market Intelligence Terminal",
        "52-Week Drawdown Screener",
        "Consolidation Screener",
        "Suggested Trades",
        "AI Trades",
        "Trade Planner",
        "Options Strategy Builder",
    ],
)

if page == "52-Week Drawdown Screener":
    st.title("52-Week Drawdown Screener")
    st.caption("Find S&P 500 and Nasdaq-100 stocks trading at least 15% below their 52-week high.")

    universe = st.selectbox("Universe", ["S&P 500", "Nasdaq-100", "S&P 500 + Nasdaq-100"])
    threshold = st.slider("Minimum drawdown from 52-week high", 5, 60, 15, 1)
    max_symbols = st.number_input(
        "Max symbols to scan",
        min_value=25,
        max_value=650,
        value=150,
        step=25,
        help="Higher values scan more names but can take longer on Streamlit Cloud.",
    )

    if universe == "S&P 500":
        symbols = fetch_sp500_symbols()
    elif universe == "Nasdaq-100":
        symbols = fetch_nasdaq100_symbols()
    else:
        symbols = sorted(set(fetch_sp500_symbols() + fetch_nasdaq100_symbols()))

    st.write(f"Universe size: {len(symbols)} symbols")
    st.info("The scan uses Yahoo public chart data and may take a minute for larger universes.")

    if st.button("Run Screener", type="primary"):
        results = screen_52w_drawdowns(symbols, threshold_pct=threshold, max_symbols=int(max_symbols))
        st.subheader(f"Stocks at least {threshold}% below 52-week high")
        if results:
            result_df = pd.DataFrame(results)
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV",
                result_df.to_csv(index=False),
                file_name=f"drawdown_screener_{threshold}pct.csv",
                mime="text/csv",
            )
        else:
            st.success("No stocks matched the selected threshold in the scanned set.")

    st.stop()


if page == "Consolidation Screener":
    st.title("Consolidation Screener")
    st.caption("Find S&P 500 and Nasdaq-100 stocks trading in compressed, sideways ranges.")

    universe = st.selectbox("Universe", ["S&P 500", "Nasdaq-100", "S&P 500 + Nasdaq-100"], key="consolidation_universe")
    min_score = st.slider("Minimum consolidation score", 40, 90, 55, 1)
    max_symbols = st.number_input(
        "Max symbols to scan",
        min_value=25,
        max_value=650,
        value=150,
        step=25,
        key="consolidation_max_symbols",
        help="Higher values scan more names but can take longer on Streamlit Cloud.",
    )

    if universe == "S&P 500":
        symbols = fetch_sp500_symbols()
    elif universe == "Nasdaq-100":
        symbols = fetch_nasdaq100_symbols()
    else:
        symbols = sorted(set(fetch_sp500_symbols() + fetch_nasdaq100_symbols()))

    st.write(f"Universe size: {len(symbols)} symbols")
    st.info(
        "Consolidation score blends 20-day range compression, low directional drift, lower volatility, "
        "and price position near the middle of the range."
    )

    if st.button("Run Consolidation Scan", type="primary"):
        results = screen_consolidation(symbols, min_score=min_score, max_symbols=int(max_symbols))
        st.subheader(f"Stocks with consolidation score >= {min_score}")
        if results:
            result_df = pd.DataFrame(results)
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV",
                result_df.to_csv(index=False),
                file_name=f"consolidation_screener_{min_score}.csv",
                mime="text/csv",
            )
        else:
            st.success("No stocks matched the selected consolidation threshold in the scanned set.")

    st.stop()


if page == "Suggested Trades":
    st.title("Suggested Trades")
    st.caption("Rank trade candidates using trend, key levels, volume, 52-week context, overbought risk, risk scoring, and optional NLP.")
    st.warning("Educational research only. These are watchlist ideas, not financial advice or executable trade instructions.")

    universe = st.selectbox("Universe", ["S&P 500", "Nasdaq-100", "S&P 500 + Nasdaq-100"], key="suggested_universe")
    min_score = st.slider("Minimum trade score", 40, 95, 58, 1)
    max_symbols = st.number_input(
        "Max symbols to score",
        min_value=25,
        max_value=650,
        value=100,
        step=25,
        key="suggested_max_symbols",
        help="Higher values scan more names but can take longer. Optional NLP is slower.",
    )
    include_nlp = st.checkbox("Include live NLP sentiment in scan", value=False, help="Slower because it pulls news/social text per symbol.")

    if universe == "S&P 500":
        symbols = fetch_sp500_symbols()
    elif universe == "Nasdaq-100":
        symbols = fetch_nasdaq100_symbols()
    else:
        symbols = sorted(set(fetch_sp500_symbols() + fetch_nasdaq100_symbols()))

    st.write(f"Universe size: {len(symbols)} symbols")
    st.info(
        "Trade score blends trend, support/resistance, 52-week position, volume participation, overbought risk, "
        "market irrationality, risk, and risk/reward context. Enable NLP for richer but slower scans."
    )
    st.caption("Side meanings: Bullish = long/watchlist bias, Bearish = avoid long or downside-risk bias, Neutral = wait for confirmation.")
    st.caption("Risk/reward is a metric only: it estimates reward to target versus risk to stop using nearby key levels.")

    if st.button("Generate Suggested Trades", type="primary"):
        results = screen_suggested_trades(
            symbols,
            min_score=min_score,
            max_symbols=int(max_symbols),
            include_nlp=include_nlp,
        )
        st.subheader(f"Suggested trades with score >= {min_score}")
        if results:
            result_df = pd.DataFrame(results)
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download CSV",
                result_df.to_csv(index=False),
                file_name=f"suggested_trades_{min_score}.csv",
                mime="text/csv",
            )
        else:
            st.success("No trade candidates matched the selected score threshold.")

    st.stop()


if page == "AI Trades":
    st.title("AI Trades")
    st.caption("Generate concise AI trade setups, save them to a tracker, and monitor whether targets or stops are hit.")
    st.warning("Educational research only. These are AI-generated watchlist plans, not personalized financial advice or executable orders.")

    universe = st.selectbox("Universe", ["S&P 500", "Nasdaq-100", "S&P 500 + Nasdaq-100"], key="ai_trades_universe")
    max_symbols = st.number_input(
        "Max symbols to scan",
        min_value=10,
        max_value=300,
        value=50,
        step=10,
        key="ai_trades_max_symbols",
        help="Higher values scan more names but take longer.",
    )
    min_score = st.slider("Minimum AI trade score", 40, 95, 62, 1, key="ai_trades_min_score")
    min_rr = st.slider("Minimum chart-based R/R", 0.5, 5.0, 1.2, 0.1, key="ai_trades_min_rr")
    include_nlp = st.checkbox("Include live NLP sentiment", value=False, key="ai_trades_nlp", help="Slower because it pulls news/social text per symbol.")
    alert_email = st.text_input("Email for level alerts", "", key="ai_trades_email", help="Optional. Requires SMTP secrets to be configured.")

    if universe == "S&P 500":
        symbols = fetch_sp500_symbols()
    elif universe == "Nasdaq-100":
        symbols = fetch_nasdaq100_symbols()
    else:
        symbols = sorted(set(fetch_sp500_symbols() + fetch_nasdaq100_symbols()))

    st.write(f"Universe size: {len(symbols)} symbols")
    st.info(
        "AI Trades ranks setups by the existing technical, volume, key-level, risk, 52-week, sentiment, and chart-based R/R signals. "
        "The AI explanation turns those signals into a concise playbook."
    )

    if alert_email and not smtp_ready():
        st.warning("Email is entered, but SMTP secrets are not configured yet. The trade can still be tracked, but alerts will not send.")

    if st.button("Find AI Trades", type="primary"):
        with st.spinner("Scanning for AI trade setups..."):
            ideas = scan_ai_trades(
                symbols,
                max_symbols=int(max_symbols),
                include_nlp=include_nlp,
                min_score=min_score,
                min_rr=min_rr,
            )
        st.session_state.ai_trade_ideas = ideas[:10]

    ideas = st.session_state.get("ai_trade_ideas", [])
    if ideas:
        st.subheader("Top AI Trade Ideas")
        for index, idea in enumerate(ideas, start=1):
            with st.expander(f"{index}. {idea['symbol']} {idea['side']} | Score {idea['score']} | R/R {idea['risk_reward']}:1", expanded=index == 1):
                cols = st.columns(5)
                cols[0].metric("Entry Area", f"${idea['entry']}")
                cols[1].metric("Stop", f"${idea['stop_loss']}")
                cols[2].metric("Target 1", f"${idea['target_1']}")
                cols[3].metric("Target 2", f"${idea['target_2']}")
                cols[4].metric("Score", idea["score"])
                st.write(idea.get("ai_explanation", idea["instructions"]))
                st.caption("Saved trades are monitored against Target 1, Target 2, and Stop. Target/stop checks use the latest available Yahoo quote snapshot.")
                if st.button(f"Save {idea['symbol']} To AI Trade Tracker", key=f"save_ai_trade_{index}"):
                    trade_id = save_ai_trade(idea, alert_email=alert_email.strip() or None)
                    st.success(f"Saved {idea['symbol']} as AI trade #{trade_id}.")

        ideas_df = pd.DataFrame([
            {
                "Symbol": idea["symbol"],
                "Side": idea["side"],
                "Entry": idea["entry"],
                "Stop": idea["stop_loss"],
                "Target 1": idea["target_1"],
                "Target 2": idea["target_2"],
                "Score": idea["score"],
                "R/R": idea["risk_reward"],
                "Rationale": idea["rationale"],
            }
            for idea in ideas
        ])
        st.download_button(
            "Download AI Ideas CSV",
            ideas_df.to_csv(index=False),
            file_name="ai_trade_ideas.csv",
            mime="text/csv",
        )

    st.subheader("AI Trade Tracker")
    tracker_cols = st.columns(2)
    monitor_clicked = tracker_cols[0].button("Refresh Monitor")
    clear_closed = tracker_cols[1].checkbox("Show closed trades", value=True)
    st.caption("Saved trades are checked whenever this page loads or refreshes. Email alerts send once when a saved trade hits Target 1, Target 2, or Stop, if SMTP secrets are configured.")

    tracked = monitor_ai_trades()
    if monitor_clicked:
        st.success("Saved AI trades refreshed.")
    if tracked.empty:
        st.info("No AI trades saved yet.")
    else:
        display = tracked.copy()
        if not clear_closed:
            display = display[display["status"].isin(["OPEN", "WON_T1"])]
        if display.empty:
            st.info("No trades match the current tracker filter.")
        else:
            st.dataframe(
                display[
                    [
                        "id",
                        "created_at",
                        "symbol",
                        "side",
                        "status",
                        "entry",
                        "last_price",
                        "stop_loss",
                        "target_1",
                        "target_2",
                        "score",
                        "risk_reward",
                        "alert_email",
                        "alerted_at",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            with st.expander("Saved Trade Details", expanded=False):
                selected_id = st.number_input("Trade ID", min_value=1, value=int(display["id"].iloc[0]), step=1)
                selected = tracked[tracked["id"] == selected_id]
                if not selected.empty:
                    row = selected.iloc[0]
                    st.write(row["instructions"])
                    st.json(json.loads(row["data_json"]))

    st.stop()


if page == "Trade Planner":
    st.title("Trade Planner")
    st.caption("Plan stop-loss and take-profit levels for a new or existing long/short position using market structure.")
    st.warning("Educational research only. These levels are planning references, not personalized financial advice.")

    planner_symbol = st.text_input("Ticker", "NVDA", key="planner_symbol").upper().strip() or "NVDA"
    side = st.radio("Trade direction", ["Long / Buy", "Short / Sell"], horizontal=True)
    position_status = st.radio("Position status", ["Entering now", "Already entered"], horizontal=True)

    manual_entry = None
    if position_status == "Already entered":
        manual_entry = st.number_input(
            "Your entry price",
            min_value=0.01,
            value=100.0,
            step=0.01,
            help="Use the price where you already bought or sold short.",
        )

    if st.button("Build Trade Plan", type="primary"):
        with st.spinner("Calculating stop-loss and take-profit levels..."):
            plan = trade_plan(
                planner_symbol,
                side=side,
                position_status=position_status,
                manual_entry=manual_entry,
            )

        if not plan:
            st.error("Could not build a plan for this ticker right now. Try another symbol or rerun the planner.")
        else:
            st.subheader(f"{plan['symbol']} {plan['side']} Plan")
            st.info(plan["note"])

            metric_cols = st.columns(4)
            metric_cols[0].metric("Current Price", f"${plan['current']}")
            metric_cols[1].metric("Entry Price", f"${plan['entry']}", f"{plan['entryPnlPct']}% from entry")
            metric_cols[2].metric("Stop Loss", f"${plan['stop']}", f"-{plan['riskPct']}% current risk")
            metric_cols[3].metric("Take Profit", f"${plan['takeProfit']}", f"{plan['rewardPct']}% current reward")

            target_cols = st.columns(3)
            target_cols[0].metric("TP Basis", plan["takeProfitBasis"].title())
            target_cols[1].metric("Chart-Based R/R", plan["riskRewardLabel"])
            target_cols[2].metric("ATR Buffer", f"${plan['atr']}")

            with st.expander("Why These Levels?", expanded=True):
                st.write(
                    f"The stop uses the nearest {'support' if side == 'Long / Buy' else 'resistance'} level with a volatility buffer. "
                    "The take-profit is chart-driven, meaning it is selected from the most relevant support/resistance, range, "
                    "or retracement area instead of being created from the stop-loss distance."
                )
                st.write(plan["takeProfitExplanation"])
                st.write(
                    f"Risk/reward math from current price: reward ${plan['rewardAmount']} divided by risk ${plan['riskAmount']} "
                    f"= {plan['riskReward']}:1. For existing trades, this evaluates the hold/exit decision now; it does not use the old entry to create the TP."
                )
                st.write(
                    f"Market structure: {plan['levels']['status']}. Support is ${plan['levels']['nearestSupport']} "
                    f"and resistance is ${plan['levels']['nearestResistance']}."
                )
                st.write(
                    f"Trend is {plan['tech']['bias']}, volume is {plan['volume']['label']}, "
                    f"overbought risk is {plan['overbought']['level']}, and overall risk is {plan['risk']['level']}."
                )

            plan_df = pd.DataFrame([
                {
                    "Symbol": plan["symbol"],
                    "Side": plan["side"],
                    "Position Status": plan["positionStatus"],
                    "Current": plan["current"],
                    "Entry": plan["entry"],
                    "P/L From Entry %": plan["entryPnlPct"],
                    "Stop Loss": plan["stop"],
                    "Current Risk %": plan["riskPct"],
                    "Take Profit": plan["takeProfit"],
                    "TP Basis": plan["takeProfitBasis"],
                    "Current Reward %": plan["rewardPct"],
                    "Chart-Based R/R": plan["riskRewardLabel"],
                    "Risk $": plan["riskAmount"],
                    "Reward $": plan["rewardAmount"],
                    "Support": plan["levels"]["nearestSupport"],
                    "Resistance": plan["levels"]["nearestResistance"],
                    "Trend": plan["tech"]["bias"],
                    "Risk": plan["risk"]["level"],
                }
            ])
            st.dataframe(plan_df, use_container_width=True, hide_index=True)

    st.stop()


if page == "Options Strategy Builder":
    st.title("Options Strategy Builder")
    st.caption("Use Tradier option-chain data to match a bullish or bearish view with a single option or defined-risk vertical spread.")
    st.warning("Educational research only. This does not place trades and is not personalized financial advice.")

    if not secret("TRADIER_API_TOKEN"):
        st.error("Missing Tradier setup. Add TRADIER_API_TOKEN to Streamlit secrets or your local .env file.")
        st.stop()

    option_symbol = st.text_input("Ticker", "NVDA", key="options_symbol").upper().strip() or "NVDA"
    bias = st.radio("Directional view", ["Bullish", "Bearish"], horizontal=True)

    try:
        quote = fetch_tradier_quote(option_symbol)
        current_price = float(quote.get("last") or quote.get("close") or quote.get("bid") or quote.get("ask") or 0)
        expirations = fetch_tradier_expirations(option_symbol)
    except Exception as error:
        st.error(f"Tradier data could not be loaded: {str(error)[:160]}")
        st.stop()

    if not current_price:
        st.error("Tradier did not return a usable stock price for this ticker.")
        st.stop()
    if not expirations:
        st.error("Tradier did not return option expirations for this ticker.")
        st.stop()

    default_boundary = current_price * 1.05 if bias == "Bullish" else current_price * 0.95
    boundary_label = (
        "Price level you think it will not go over"
        if bias == "Bullish"
        else "Price level you think it will not go below"
    )

    st.metric("Current Stock Price", f"${round(current_price, 2)}")
    expiration = st.selectbox("Expiration", expirations[:12], index=min(2, len(expirations[:12]) - 1))
    boundary = st.number_input(
        boundary_label,
        min_value=0.01,
        value=round(default_boundary, 2),
        step=0.5,
        help="This level is used to choose the short strike in the spread.",
    )

    if bias == "Bullish" and boundary <= current_price:
        st.warning("For a bullish capped spread, choose a level above the current stock price.")
    if bias == "Bearish" and boundary >= current_price:
        st.warning("For a bearish bounded spread, choose a level below the current stock price.")

    if st.button("Find Option Idea", type="primary"):
        if (bias == "Bullish" and boundary <= current_price) or (bias == "Bearish" and boundary >= current_price):
            st.error("Adjust the boundary level first so it matches your directional view.")
            st.stop()
        with st.spinner("Pulling Tradier option chain and building strategy..."):
            try:
                idea = build_options_idea(option_symbol, bias, boundary, expiration)
            except Exception as error:
                st.error(f"Could not build an option idea from Tradier data: {str(error)[:180]}")
                st.stop()

        if not idea:
            st.error("Could not find a liquid enough option setup for that ticker, expiration, and level.")
        else:
            st.subheader(f"{idea['symbol']} {idea['strategy']}")
            st.info(idea["thesis"])

            summary_cols = st.columns(5)
            summary_cols[0].metric("Stock", f"${idea['current']}")
            summary_cols[1].metric("Boundary", f"${idea['boundary']}")
            summary_cols[2].metric("Net Debit", f"${idea['debit']}")
            summary_cols[3].metric("Max Profit", f"${idea['maxProfit']}")
            summary_cols[4].metric("Spread R/R", idea["riskReward"])

            st.metric("Breakeven", f"${idea['breakeven']}")

            legs = pd.DataFrame([
                {"Leg": "Buy", **idea["longLeg"]},
                {"Leg": "Sell", **idea["shortLeg"]},
            ])
            st.dataframe(legs, use_container_width=True, hide_index=True)

            with st.expander("Why This Strategy?", expanded=True):
                st.write(idea["explanation"])
                st.write(
                    "The spread is defined risk: the debit is the estimated max loss before commissions/fees, "
                    "and the max profit is the strike width minus that debit."
                )
                st.write(
                    "The single-option alternative is shown below, but the spread is usually more aligned with a capped view "
                    "because selling the boundary strike helps finance the long option."
                )

            st.subheader("Single Option Alternative")
            st.dataframe(pd.DataFrame([idea["singleOption"]]), use_container_width=True, hide_index=True)

    st.stop()


st.title("AI Market Intelligence Terminal")
symbol = st.text_input("Ticker", "NVDA").upper().strip() or "NVDA"

if st.button("Analyze", type="primary") or "analysis" not in st.session_state:
    with st.spinner("Pulling market, news, social, and AI signals..."):
        try:
            st.session_state.analysis = analyze(symbol)
        except Exception as error:
            st.session_state.analysis = {
                "symbol": symbol,
                "candles": [],
                "volume": [],
                "charts": {"1D": [], "1M": [], "1Y": [], "3Y": [], "5Y": []},
                "provider": "setup-error",
                "sentiment": {"label": "Setup Required", "score": 0, "confidence": 0, "topEvents": []},
                "technicals": {
                    "lastPrice": 0,
                    "rsi": 0,
                    "vwap": 0,
                    "macdHistogram": 0,
                    "trendStrength": 0,
                    "bias": "Setup Required",
                    "macdSignificance": "Setup required.",
                },
                "keyLevels": {
                    "status": "Setup Required",
                    "current": 0,
                    "nearestSupport": 0,
                    "nearestResistance": 0,
                    "supportDistancePct": 0,
                    "resistanceDistancePct": 0,
                    "recentHigh": 0,
                    "recentLow": 0,
                    "vwap": 0,
                    "explanation": "Setup required.",
                },
                "week52": {
                    "high": 0,
                    "low": 0,
                    "current": 0,
                    "distancePct": 0,
                    "drawdownPct": 0,
                    "rangePositionPct": 0,
                    "label": "Setup Required",
                    "explanation": "Setup required.",
                },
                "volumeAnalysis": {
                    "label": "Setup Required",
                    "latest": 0,
                    "baseline": 0,
                    "ratio": 0,
                    "trend": 0,
                    "priceChangePct": 0,
                    "explanation": "Setup required.",
                },
                "overbought": {
                    "score": 0,
                    "level": "Setup Required",
                    "label": "Setup Required",
                    "rsi": 0,
                    "vwapExtensionPct": 0,
                    "explanation": "Setup required.",
                },
                "irrationality": {
                    "score": 0,
                    "level": "Setup Required",
                    "label": "Setup Required",
                    "explanation": "Setup required.",
                    "drivers": [],
                },
                "risk": {"score": 0, "level": "Setup Required"},
                "confidence": 0,
                "explanation": f"Startup failed before analysis completed: {str(error)[:180]}",
                "aiMode": "Setup Required",
                "analyzed": [],
                "setupError": True,
            }

analysis = st.session_state.analysis
st.caption(f"LIVE DATA ({analysis['provider']}) | STOCKTWITS SOCIAL | {analysis['aiMode'].upper()} AI")

if analysis.get("setupError"):
    st.error(analysis["explanation"])
    st.info("Configure deployment secrets in Streamlit Cloud settings, then reboot the app.")
    st.stop()

if analysis.get("providerStatus"):
    st.warning(
        "Live Alpaca data is not active, so this session is using demo market data. "
        f"Provider status: {analysis['providerStatus']}. Add Streamlit Secrets to enable live mode."
    )

with st.expander("Decision Overview", expanded=True):
    overview = st.columns(3)
    overview[0].metric("Trade Confidence", f"{round(analysis['confidence'] * 100)}%")
    overview[1].metric("Sentiment", analysis["sentiment"]["label"], f"{analysis['sentiment']['score']} NLP score")
    overview[2].metric("Risk", analysis["risk"]["level"], f"{analysis['risk']['score']} risk index")
    st.write(analysis["explanation"])

with st.expander("Price + Volume Chart", expanded=True):
    st.caption("Chart ranges use Yahoo public chart data when available. Core live analysis uses Alpaca first, then Yahoo fallback, then demo fallback.")
    chart_tabs = st.tabs(["1D", "1M", "1Y", "3Y", "5Y"])
    for tab, range_name in zip(chart_tabs, ["1D", "1M", "1Y", "3Y", "5Y"]):
        with tab:
            rows = analysis["charts"].get(range_name, [])
            if rows:
                chart_df = pd.DataFrame(rows)
                line = alt.Chart(chart_df).mark_line(point=True).encode(
                    x=alt.X("time:T", title="Time"),
                    y=alt.Y("close:Q", title="Price", scale=alt.Scale(zero=False)),
                    tooltip=["time:T", "close:Q", "volume:Q"],
                )
                bars = alt.Chart(chart_df).mark_bar(opacity=0.25).encode(
                    x=alt.X("time:T", title="Time"),
                    y=alt.Y("volume:Q", title="Volume (M)"),
                )
                st.altair_chart(line | bars, use_container_width=True)
            else:
                st.info(f"{range_name} chart data is temporarily unavailable.")

with st.expander("Technical Indicators", expanded=False):
    metrics = st.columns(4)
    metrics[0].metric("RSI", analysis["technicals"]["rsi"])
    metrics[1].metric("VWAP", f"${analysis['technicals']['vwap']}")
    metrics[2].metric("MACD Hist", analysis["technicals"]["macdHistogram"])
    metrics[3].metric("Trend", analysis["technicals"]["bias"])
    st.markdown(f"**MACD significance:** {analysis['technicals']['macdSignificance']}")

with st.expander("Key Levels", expanded=True):
    levels = analysis["keyLevels"]
    level_cols = st.columns(4)
    level_cols[0].metric("Level Status", levels["status"])
    level_cols[1].metric("Nearest Support", f"${levels['nearestSupport']}", f"{levels['supportDistancePct']}% below")
    level_cols[2].metric("Nearest Resistance", f"${levels['nearestResistance']}", f"{levels['resistanceDistancePct']}% above")
    level_cols[3].metric("VWAP", f"${levels['vwap']}")
    st.write(levels["explanation"])
    st.write(f"Recent high: ${levels['recentHigh']} | Recent low: ${levels['recentLow']} | Current: ${levels['current']}")

with st.expander("52-Week High Distance", expanded=True):
    week_52 = analysis["week52"]
    week_cols = st.columns(4)
    week_cols[0].metric("52W High", f"${week_52['high']}")
    week_cols[1].metric("Distance From High", f"{week_52['distancePct']}%")
    week_cols[2].metric("52W Low", f"${week_52['low']}")
    week_cols[3].metric("Range Position", f"{week_52['rangePositionPct']}%")
    st.markdown(f"**{week_52['label']}**")
    st.write(week_52["explanation"])

with st.expander("Volume Analysis", expanded=True):
    volume_view = analysis["volumeAnalysis"]
    volume_cols = st.columns(4)
    volume_cols[0].metric("Volume Signal", volume_view["label"])
    volume_cols[1].metric("Latest Volume", f"{volume_view['latest']}M")
    volume_cols[2].metric("Vs Baseline", f"{volume_view['ratio']}x")
    volume_cols[3].metric("Price Change", f"{volume_view['priceChangePct']}%")
    st.write(volume_view["explanation"])

with st.expander("Overbought Indicator", expanded=True):
    overbought = analysis["overbought"]
    over_cols = st.columns(4)
    over_cols[0].metric("Overbought", overbought["level"])
    over_cols[1].metric("Gauge Score", f"{round(overbought['score'] * 100)}%")
    over_cols[2].metric("RSI", overbought["rsi"])
    over_cols[3].metric("VWAP Extension", f"{overbought['vwapExtensionPct']}%")
    st.write(overbought["explanation"])

with st.expander("Market Irrationality Gauge", expanded=True):
    irrationality = analysis["irrationality"]
    irr_cols = st.columns(3)
    irr_cols[0].metric("Irrationality", irrationality["level"])
    irr_cols[1].metric("Gauge Score", f"{round(irrationality['score'] * 100)}%")
    irr_cols[2].metric("Read", irrationality["label"])
    st.write(irrationality["explanation"])
    if irrationality["drivers"]:
        st.markdown("**Drivers**")
        for driver in irrationality["drivers"]:
            st.write(f"- {driver}")

with st.expander("Risk Engine", expanded=False):
    st.metric("Risk Level", analysis["risk"]["level"], f"{analysis['risk']['score']} risk index")
    st.write("Risk combines realized price volatility with the strength and uncertainty of NLP sentiment.")

with st.expander("News + StockTwits NLP Feed", expanded=False):
    for item in analysis["analyzed"][:20]:
        sent = item["sentiment"]
        st.markdown(
            f"**{item['source']} | {item['eventType']} | {sent['label']} {round(sent['confidence'] * 100)}%**  \n"
            f"{item['text']}"
        )
