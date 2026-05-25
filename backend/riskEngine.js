function stdev(values) {
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

export function analyzeRisk({ candles, volume, optionsFlow, sentiment, macroBeta }) {
  const returns = candles.slice(1).map((price, index) => (price - candles[index]) / candles[index]);
  const realizedVol = stdev(returns) * Math.sqrt(252);
  const latestVolumeSpike = volume.at(-1) / (volume.reduce((sum, value) => sum + value, 0) / volume.length);
  const sentimentShock = Math.abs(sentiment.score) * (1 - sentiment.confidence * 0.35);
  const optionsRisk = Math.max(0, optionsFlow.unusualVolume - 1) * 0.16;
  const betaRisk = Math.max(0, macroBeta - 1) * 0.18;

  const rawRisk = realizedVol * 0.9 + latestVolumeSpike * 0.16 + sentimentShock + optionsRisk + betaRisk;
  const score = Math.min(1, rawRisk / 1.4);
  const level = score > 0.68 ? "High" : score > 0.42 ? "Moderate" : "Low";

  return {
    level,
    score: Number(score.toFixed(2)),
    realizedVolatility: Number(realizedVol.toFixed(2)),
    unusualActivity: Number(Math.max(latestVolumeSpike, optionsFlow.unusualVolume).toFixed(2)),
    drivers: [
      realizedVol > 0.38 ? "Elevated realized volatility" : "Contained realized volatility",
      optionsFlow.unusualVolume > 1.4 ? "Unusual options activity" : "Normal options activity",
      sentiment.confidence < 0.62 ? "Lower NLP confidence" : "Consistent NLP signal"
    ]
  };
}
