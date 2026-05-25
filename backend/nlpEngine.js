const bullishTerms = new Map([
  ["beat", 1.2],
  ["accelerated", 1.1],
  ["raised", 1.1],
  ["rallied", 1],
  ["improved", 0.8],
  ["strong", 0.9],
  ["resilient", 0.7],
  ["growth", 0.8],
  ["gained", 0.8],
  ["breakout", 0.9],
  ["stabilized", 0.5],
  ["upgrade", 0.7],
  ["leadership", 0.8],
  ["share", 0.45],
  ["gains", 0.75]
]);

const bearishTerms = new Map([
  ["declined", -1.1],
  ["cuts", -0.9],
  ["pressured", -0.9],
  ["scrutiny", -0.8],
  ["investigation", -1],
  ["fear", -0.9],
  ["weak", -0.9],
  ["risk", -0.65],
  ["stretched", -0.55],
  ["competition", -0.35],
  ["intense", -0.35],
  ["volatility", -0.45],
  ["exposure", -0.55],
  ["oversold", -0.25]
]);

const eventRules = [
  { label: "Earnings", terms: ["earnings", "revenue", "margins", "guidance", "estimates", "profitability"] },
  { label: "Macro/Fed", terms: ["fed", "rate", "yield", "dollar", "inflation"] },
  { label: "Regulatory", terms: ["regulatory", "scrutiny", "sec", "investigation", "safety"] },
  { label: "Sector Rotation", terms: ["sector", "semiconductor", "bank", "cloud", "capex"] },
  { label: "Options/Positioning", terms: ["options", "traders", "implied", "resistance", "breakout"] },
  { label: "Product/AI", terms: ["ai", "gpu", "iphone", "roadmap", "features"] }
];

export function normalizeText(text) {
  return text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[^a-z0-9$%\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function tokenize(text) {
  return normalizeText(text)
    .split(" ")
    .filter((token) => token.length > 2);
}

export function cleanAndDeduplicate(items) {
  const seen = new Set();
  return items
    .map((item) => ({ ...item, cleanText: normalizeText(item.text) }))
    .filter((item) => {
      const spammy = /(guaranteed|100x|free money|click here)/i.test(item.text);
      const fingerprint = item.cleanText.slice(0, 80);
      if (spammy || seen.has(fingerprint)) return false;
      seen.add(fingerprint);
      return true;
    })
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}

export function scoreSentiment(text) {
  const tokens = tokenize(text);
  let raw = 0;
  const evidence = [];

  for (const token of tokens) {
    if (bullishTerms.has(token)) {
      const weight = bullishTerms.get(token);
      raw += weight;
      evidence.push({ token, weight, polarity: "bullish" });
    }
    if (bearishTerms.has(token)) {
      const weight = bearishTerms.get(token);
      raw += weight;
      evidence.push({ token, weight, polarity: "bearish" });
    }
  }

  const normalized = Math.tanh(raw / 3);
  const confidence = Math.min(0.96, 0.42 + evidence.length * 0.09 + Math.abs(normalized) * 0.22);
  const label = normalized > 0.16 ? "Bullish" : normalized < -0.16 ? "Bearish" : "Neutral";

  return {
    label,
    score: Number(normalized.toFixed(3)),
    confidence: Number(confidence.toFixed(2)),
    evidence: evidence.slice(0, 5)
  };
}

export function classifyEvent(text) {
  const tokens = new Set(tokenize(text));
  const ranked = eventRules
    .map((rule) => ({
      label: rule.label,
      hits: rule.terms.filter((term) => tokens.has(term)).length
    }))
    .filter((rule) => rule.hits > 0)
    .sort((a, b) => b.hits - a.hits);

  return ranked[0]?.label ?? "General Market";
}

export function createKeywordEmbedding(text) {
  const vocabulary = [
    "earnings",
    "growth",
    "guidance",
    "margin",
    "risk",
    "regulatory",
    "ai",
    "demand",
    "volatility",
    "breakout"
  ];
  const tokens = tokenize(text);
  return vocabulary.map((term) => {
    const count = tokens.filter((token) => token.startsWith(term)).length;
    return Number((count / Math.max(1, tokens.length)).toFixed(3));
  });
}

export function analyzeTextStream(items) {
  return cleanAndDeduplicate(items).map((item) => {
    const sentiment = scoreSentiment(item.cleanText);
    return {
      ...item,
      sentiment,
      eventType: classifyEvent(item.cleanText),
      embedding: createKeywordEmbedding(item.cleanText)
    };
  });
}

export function aggregateSentiment(analyzedItems) {
  if (!analyzedItems.length) {
    return { label: "Neutral", score: 0, confidence: 0.4, topEvents: [] };
  }

  const weightedScore =
    analyzedItems.reduce((sum, item) => {
      const sourceWeight = item.source === "earnings" || item.source === "sec" ? 1.25 : 1;
      return sum + item.sentiment.score * item.sentiment.confidence * sourceWeight;
    }, 0) / analyzedItems.length;

  const score = Math.max(-1, Math.min(1, weightedScore));
  const label = score > 0.16 ? "Bullish" : score < -0.16 ? "Bearish" : "Neutral";
  const confidence =
    analyzedItems.reduce((sum, item) => sum + item.sentiment.confidence, 0) / analyzedItems.length;
  const eventCounts = analyzedItems.reduce((acc, item) => {
    acc[item.eventType] = (acc[item.eventType] ?? 0) + 1;
    return acc;
  }, {});

  return {
    label,
    score: Number(score.toFixed(3)),
    confidence: Number(confidence.toFixed(2)),
    topEvents: Object.entries(eventCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([label, count]) => ({ label, count }))
  };
}
