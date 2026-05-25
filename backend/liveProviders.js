const DAY = 24 * 60 * 60;

function env(name) {
  return process.env[name] ?? "";
}

function unixDaysAgo(days) {
  return Math.floor(Date.now() / 1000) - days * DAY;
}

async function getJson(url, headers = {}) {
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function hasLiveKeys() {
  return Boolean(env("ALPACA_API_KEY") && env("ALPACA_API_SECRET")) || Boolean(env("FINNHUB_API_KEY"));
}

function alpacaHeaders() {
  return {
    accept: "application/json",
    "APCA-API-KEY-ID": env("ALPACA_API_KEY"),
    "APCA-API-SECRET-KEY": env("ALPACA_API_SECRET")
  };
}

function toAlpacaIso(daysAgo) {
  return new Date(Date.now() - daysAgo * DAY * 1000).toISOString();
}

export async function fetchAlpacaMarketSnapshot(symbol) {
  const key = env("ALPACA_API_KEY");
  const secret = env("ALPACA_API_SECRET");
  if (!key || !secret) return null;

  const ticker = encodeURIComponent(symbol.toUpperCase());
  const feed = env("ALPACA_DATA_FEED") || "iex";
  const start = encodeURIComponent(toAlpacaIso(70));
  const end = encodeURIComponent(new Date().toISOString());

  const [barsPayload, latestQuotePayload, latestBarPayload] = await Promise.all([
    getJson(
      `https://data.alpaca.markets/v2/stocks/bars?symbols=${ticker}&timeframe=1Day&start=${start}&end=${end}&limit=1000&adjustment=split&feed=${feed}`,
      alpacaHeaders()
    ),
    getJson(`https://data.alpaca.markets/v2/stocks/${ticker}/quotes/latest?feed=${feed}`, alpacaHeaders()),
    getJson(`https://data.alpaca.markets/v2/stocks/${ticker}/bars/latest?feed=${feed}`, alpacaHeaders())
  ]);

  const bars = barsPayload?.bars?.[symbol.toUpperCase()] ?? [];
  const latestQuote = latestQuotePayload?.quote;
  const latestBar = latestBarPayload?.bar;
  const closes = bars.map((bar) => bar.c).filter(Number.isFinite).slice(-24);
  const volumes = bars.map((bar) => (bar.v ?? 0) / 1_000_000).slice(-24);

  if (latestBar?.c && closes.length) {
    closes[closes.length - 1] = latestBar.c;
  }

  const midpoint =
    latestQuote?.ap && latestQuote?.bp ? Number(((latestQuote.ap + latestQuote.bp) / 2).toFixed(2)) : null;
  if (midpoint && closes.length) {
    closes[closes.length - 1] = midpoint;
  }

  return {
    provider: "alpaca",
    feed,
    quote: latestQuote,
    latestBar,
    candles: closes,
    volume: volumes
  };
}

export async function fetchFinnhubSnapshot(symbol) {
  const token = env("FINNHUB_API_KEY");
  if (!token) return null;

  const ticker = encodeURIComponent(symbol.toUpperCase());
  const to = Math.floor(Date.now() / 1000);
  const from = unixDaysAgo(45);
  const newsFrom = new Date(Date.now() - 7 * DAY * 1000).toISOString().slice(0, 10);
  const newsTo = new Date().toISOString().slice(0, 10);

  const errors = [];
  const quote = await getJson(`https://finnhub.io/api/v1/quote?symbol=${ticker}&token=${token}`).catch((error) => {
    errors.push(`quote: ${error.message}`);
    return null;
  });
  const candles = await getJson(
    `https://finnhub.io/api/v1/stock/candle?symbol=${ticker}&resolution=D&from=${from}&to=${to}&token=${token}`
  ).catch((error) => {
    errors.push(`candles: ${error.message}`);
    return null;
  });
  const news = await getJson(
    `https://finnhub.io/api/v1/company-news?symbol=${ticker}&from=${newsFrom}&to=${newsTo}&token=${token}`
  ).catch((error) => {
    errors.push(`news: ${error.message}`);
    return [];
  });

  const liveCandles = candles?.s === "ok" && Array.isArray(candles.c) ? candles.c.slice(-24) : [];
  const liveVolume = candles?.s === "ok" && Array.isArray(candles.v) ? candles.v.slice(-24).map((v) => v / 1_000_000) : [];

  return {
    provider: "finnhub",
    errors,
    quote,
    candles: liveCandles,
    volume: liveVolume,
    news: Array.isArray(news)
      ? news.slice(0, 12).map((item) => ({
          id: String(item.id ?? item.datetime),
          source: "news",
          timestamp: new Date((item.datetime ?? Date.now() / 1000) * 1000).toISOString(),
          text: [item.headline, item.summary].filter(Boolean).join(" ")
        }))
      : []
  };
}

function stockTwitsAuthHeader() {
  const username = env("STOCKTWITS_USERNAME");
  const password = env("STOCKTWITS_PASSWORD");
  if (!username || !password) return {};

  return {
    authorization: `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`
  };
}

function stripHtml(text = "") {
  return text
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

export async function fetchStockTwitsSocial(symbol) {
  const ticker = encodeURIComponent(symbol.toUpperCase());
  const social = {
    provider: "stocktwits",
    sentiment: null,
    messages: [],
    errors: []
  };

  try {
    social.sentiment = await getJson(
      `https://firestream.stocktwits.com/external/sentiment/v2/${ticker}/detail`,
      stockTwitsAuthHeader()
    );
  } catch (error) {
    social.errors.push(`Firestream sentiment: ${error.message}`);
  }

  try {
    const stream = await getJson(`https://api.stocktwits.com/api/2/streams/symbol/${ticker}.json`);
    social.messages = (stream.messages ?? []).slice(0, 12).map((message) => ({
      id: `stocktwits-${message.id}`,
      source: "stocktwits",
      timestamp: message.created_at,
      text: stripHtml(message.body)
    }));
  } catch (error) {
    social.errors.push(`Public stream: ${error.message}`);
  }

  return social;
}
