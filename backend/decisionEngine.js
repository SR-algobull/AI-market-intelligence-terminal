import { macroContext, marketUniverse } from "./data/marketData.js";
import { analyzeTextStream, aggregateSentiment } from "./nlpEngine.js";
import { analyzeTechnicals } from "./technicalEngine.js";
import { analyzeRisk } from "./riskEngine.js";

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function toPercent(value) {
  return Math.round(value * 100);
}

export function analyzeTicker(symbol) {
  const ticker = symbol.toUpperCase();
  const asset = marketUniverse[ticker] ?? marketUniverse.NVDA;
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

  const alert =
    risk.level === "High"
      ? "Risk alert: position sizing should be reduced until volatility cools."
      : confidence > 0.72
        ? "Momentum alert: technical and NLP signals are aligned."
        : "Watchlist alert: wait for stronger confirmation before increasing exposure.";

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
    alert,
    optionsFlow: asset.optionsFlow,
    analyzedText,
    candles: asset.candles,
    volume: asset.volume,
    explanation: buildExplanation({
      asset,
      sentiment,
      technicals,
      risk,
      confidence,
      sectorMomentum
    })
  };
}

export function buildExplanation({ asset, sentiment, technicals, risk, confidence, sectorMomentum }) {
  const sentimentPhrase =
    sentiment.label === "Bullish"
      ? "positive news and social sentiment"
      : sentiment.label === "Bearish"
        ? "negative NLP sentiment"
        : "mixed sentiment";
  const trendPhrase =
    technicals.bias === "Bullish Momentum"
      ? "price trend and MACD momentum are supportive"
      : technicals.bias === "Bearish Momentum"
        ? "trend indicators remain weak"
        : "technicals are still rangebound";
  const sectorPhrase =
    sectorMomentum > 0.35
      ? `${asset.sector} sector rotation is favorable`
      : sectorMomentum < -0.2
        ? `${asset.sector} sector rotation is a headwind`
        : `${asset.sector} sector rotation is neutral`;

  return `${asset.name} receives a ${Math.round(confidence * 100)}% trade confidence score because ${sentimentPhrase}, ${trendPhrase}, and ${sectorPhrase}. Risk is ${risk.level.toLowerCase()} due to ${risk.drivers[0].toLowerCase()} and ${risk.drivers[1].toLowerCase()}.`;
}

export function getUniverseSymbols() {
  return Object.entries(marketUniverse).map(([symbol, asset]) => ({
    symbol,
    name: asset.name,
    sector: asset.sector
  }));
}
