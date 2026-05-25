import { macroContext, marketUniverse } from "./data/marketData.js";
import { analyzeTextStream, aggregateSentiment } from "./nlpEngine.js";
import { analyzeTechnicals } from "./technicalEngine.js";
import { analyzeRisk } from "./riskEngine.js";
import { buildExplanation } from "./decisionEngine.js";
import {
  fetchAlpacaMarketSnapshot,
  fetchFinnhubSnapshot,
  fetchStockTwitsSocial,
  hasLiveKeys
} from "./liveProviders.js";
import { generateMarketExplanation } from "./aiExplanation.js";

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function toPercent(value) {
  return Math.round(value * 100);
}

function fallbackAsset(symbol) {
  return marketUniverse[symbol] ?? {
    name: symbol,
    sector: "General Market",
    macroBeta: 1.1,
    optionsFlow: { callPutRatio: 1, unusualVolume: 1 },
    candles: marketUniverse.NVDA.candles,
    volume: marketUniverse.NVDA.volume,
    news: marketUniverse.NVDA.news
  };
}

export async function analyzeTickerLive(symbol) {
  const ticker = symbol.toUpperCase();
  const base = fallbackAsset(ticker);
  let market = null;
  let live = null;
  let social = null;
  let providerError = null;

  try {
    market = await fetchAlpacaMarketSnapshot(ticker);
  } catch (error) {
    providerError = `Alpaca: ${error.message}`;
  }

  try {
    live = await fetchFinnhubSnapshot(ticker);
    if (live?.errors?.length) {
      providerError = providerError ? `${providerError}; Finnhub: ${live.errors.join("; ")}` : `Finnhub: ${live.errors.join("; ")}`;
    }
  } catch (error) {
    live = { error: error.message };
    providerError = providerError ? `${providerError}; Finnhub: ${error.message}` : `Finnhub: ${error.message}`;
  }

  try {
    social = await fetchStockTwitsSocial(ticker);
    if (social.errors.length) {
      providerError = providerError
        ? `${providerError}; StockTwits: ${social.errors.join("; ")}`
        : `StockTwits: ${social.errors.join("; ")}`;
    }
  } catch (error) {
    providerError = providerError ? `${providerError}; StockTwits: ${error.message}` : `StockTwits: ${error.message}`;
  }

  const textItems = [
    ...(live?.news?.length ? live.news : base.news),
    ...(social?.messages?.length ? social.messages : [])
  ];

  const asset = {
    ...base,
    candles: market?.candles?.length >= 15 ? market.candles : live?.candles?.length >= 15 ? live.candles : base.candles,
    volume: market?.volume?.length >= 15 ? market.volume : live?.volume?.length >= 15 ? live.volume : base.volume,
    news: textItems
  };

  if (!market?.candles?.length && live?.quote?.c) {
    asset.candles = [...asset.candles.slice(0, -1), live.quote.c];
  }

  const analyzedText = analyzeTextStream(asset.news);
  const sentiment = aggregateSentiment(analyzedText);
  const technicals = analyzeTechnicals(asset.candles, asset.volume);
  const risk = analyzeRisk({
    candles: asset.candles,
    volume: asset.volume,
    optionsFlow: asset.optionsFlow,
    sentiment,
    macroBeta: asset.macroBeta
  });
  const sectorMomentum = macroContext.sectorRotation[asset.sector] ?? 0;

  const technicalScore = (technicals.trendStrength + 1) / 2;
  const sentimentScore = (sentiment.score + 1) / 2;
  const optionsScore = clamp((asset.optionsFlow.callPutRatio - 0.55) / 1.7);
  const macroScore = clamp((sectorMomentum + 1) / 2);
  const riskPenalty = risk.score * 0.22;
  const confidence = clamp(
    technicalScore * 0.32 + sentimentScore * 0.3 + optionsScore * 0.15 + macroScore * 0.23 - riskPenalty
  );

  const marketRegime =
    confidence > 0.68 && technicals.trendStrength > 0
      ? "Bullish Momentum"
      : confidence < 0.42 && technicals.trendStrength < 0
        ? "Defensive / Bearish"
        : "Mixed Confirmation";

  let aiExplanation = null;
  let aiError = null;

  try {
    aiExplanation = await generateMarketExplanation({
      symbol: ticker,
      company: asset.name,
      technicals,
      sentiment,
      risk,
      confidence,
      news: asset.news
    });
  } catch (error) {
    aiError = error.message;
  }

  const fallbackExplanation = buildExplanation({
    asset,
    sentiment,
    technicals,
    risk,
    confidence,
    sectorMomentum
  });

  return {
    symbol: ticker,
    company: asset.name,
    sector: asset.sector,
    macro: macroContext,
    technicals,
    sentiment,
    risk,
    confidence: Number(confidence.toFixed(2)),
    confidencePercent: toPercent(confidence),
    marketRegime,
    alert:
      risk.level === "High"
        ? "Risk alert: position sizing should be reduced until volatility cools."
        : confidence > 0.72
          ? "Momentum alert: technical and NLP signals are aligned."
          : "Watchlist alert: wait for stronger confirmation before increasing exposure.",
    optionsFlow: asset.optionsFlow,
    analyzedText,
    candles: asset.candles,
    volume: asset.volume,
    dataMode: market?.candles?.length >= 15 ? "live" : live?.candles?.length >= 15 ? "live" : "demo",
    dataProvider: market?.candles?.length >= 15 ? `alpaca:${market.feed}` : live?.candles?.length >= 15 ? "finnhub" : "demo",
    socialProvider: social?.messages?.length ? "stocktwits" : "demo",
    stockTwitsSentiment: social?.sentiment,
    providerError,
    aiMode: aiExplanation ? "openai" : "rules",
    aiError,
    explanation: aiExplanation ?? fallbackExplanation
  };
}
