import base64
import math
import os
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


def secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


DEFAULT_HEADERS = {"User-Agent": "ai-market-intelligence-terminal/1.0"}


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
        raise RuntimeError("Missing Alpaca secrets")
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
    bars = get_json(bars_url, headers=headers, params=bar_params).get("bars", {}).get(symbol, [])
    latest = get_json(latest_url, headers=headers).get("quote", {})
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
    try:
        payload = get_json(url)
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


def risk_score(candles, sentiment):
    returns = [(candles[index] - candles[index - 1]) / candles[index - 1] for index in range(1, len(candles))]
    mean = sum(returns) / len(returns)
    realized_vol = math.sqrt(sum((value - mean) ** 2 for value in returns) / len(returns)) * math.sqrt(252)
    score = min(1, (realized_vol * 0.9 + abs(sentiment["score"]) * 0.4 + 0.2) / 1.4)
    return {"score": round(score, 2), "level": "High" if score > 0.68 else "Moderate" if score > 0.42 else "Low"}


def openai_explanation(symbol, tech, sentiment, risk, confidence, items):
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
            f"MACD histogram: {tech['macdHistogram']}\nRecent text:\n{headlines}\n"
            "Return exactly two sentences: setup then risk."
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
    text_items = fetch_finnhub_news(symbol) + fetch_stocktwits(symbol)
    analyzed = analyze_text(text_items)
    sentiment = aggregate_sentiment(analyzed)
    tech = technicals(candles, volume)
    risk = risk_score(candles, sentiment)
    confidence = max(0, min(1, ((tech["trendStrength"] + 1) / 2) * 0.42 + ((sentiment["score"] + 1) / 2) * 0.36 - risk["score"] * 0.2 + 0.14))
    try:
        explanation = openai_explanation(symbol, tech, sentiment, risk, confidence, analyzed)
        ai_mode = "OpenAI"
    except Exception as error:
        explanation = (
            f"{symbol} has a {round(confidence * 100)}% trade confidence score because {tech['bias'].lower()} "
            f"and {sentiment['label'].lower()} NLP sentiment are being weighed against {risk['level'].lower()} risk."
        )
        ai_mode = f"Rules ({str(error)[:80]})"
    return {
        "symbol": symbol,
        "candles": candles,
        "volume": volume,
        "provider": provider,
        "sentiment": sentiment,
        "technicals": tech,
        "risk": risk,
        "confidence": confidence,
        "explanation": explanation,
        "aiMode": ai_mode,
        "analyzed": analyzed,
    }


st.title("AI Market Intelligence Terminal")
symbol = st.text_input("Ticker", "NVDA").upper().strip() or "NVDA"

if st.button("Analyze", type="primary") or "analysis" not in st.session_state:
    with st.spinner("Pulling market, news, social, and AI signals..."):
        st.session_state.analysis = analyze(symbol)

analysis = st.session_state.analysis
st.caption(f"LIVE DATA ({analysis['provider']}) | STOCKTWITS SOCIAL | {analysis['aiMode'].upper()} AI")

left, right = st.columns([0.9, 1.3])
with left:
    st.metric("Trade Confidence", f"{round(analysis['confidence'] * 100)}%")
    st.metric("Sentiment", analysis["sentiment"]["label"], f"{analysis['sentiment']['score']} NLP score")
    st.metric("Risk", analysis["risk"]["level"], f"{analysis['risk']['score']} risk index")
    st.write(analysis["explanation"])

with right:
    chart_df = pd.DataFrame({"day": range(len(analysis["candles"])), "price": analysis["candles"], "volume": analysis["volume"]})
    line = alt.Chart(chart_df).mark_line(point=True).encode(x="day", y=alt.Y("price", scale=alt.Scale(zero=False)))
    bars = alt.Chart(chart_df).mark_bar(opacity=0.25).encode(x="day", y="volume")
    st.altair_chart(line | bars, use_container_width=True)

metrics = st.columns(4)
metrics[0].metric("RSI", analysis["technicals"]["rsi"])
metrics[1].metric("VWAP", f"${analysis['technicals']['vwap']}")
metrics[2].metric("MACD Hist", analysis["technicals"]["macdHistogram"])
metrics[3].metric("Trend", analysis["technicals"]["bias"])

st.subheader("News + StockTwits NLP Feed")
for item in analysis["analyzed"][:20]:
    sent = item["sentiment"]
    st.markdown(
        f"**{item['source']} | {item['eventType']} | {sent['label']} {round(sent['confidence'] * 100)}%**  \n"
        f"{item['text']}"
    )
