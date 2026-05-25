function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function ema(values, period) {
  const smoothing = 2 / (period + 1);
  return values.reduce((series, value, index) => {
    if (index === 0) return [value];
    series.push(value * smoothing + series[index - 1] * (1 - smoothing));
    return series;
  }, []);
}

export function calculateRsi(candles, period = 14) {
  const changes = candles.slice(1).map((price, index) => price - candles[index]);
  const recent = changes.slice(-period);
  const gains = recent.filter((change) => change > 0);
  const losses = recent.filter((change) => change < 0).map(Math.abs);
  const avgGain = gains.length ? average(gains) : 0;
  const avgLoss = losses.length ? average(losses) : 0.01;
  const rs = avgGain / avgLoss;
  return Number((100 - 100 / (1 + rs)).toFixed(1));
}

export function calculateMacd(candles) {
  const fast = ema(candles, 12);
  const slow = ema(candles, 26);
  const macdLine = candles.map((_, index) => fast[index] - slow[index]);
  const signal = ema(macdLine, 9);
  const histogram = macdLine.at(-1) - signal.at(-1);
  return {
    line: Number(macdLine.at(-1).toFixed(2)),
    signal: Number(signal.at(-1).toFixed(2)),
    histogram: Number(histogram.toFixed(2))
  };
}

export function calculateVwap(candles, volume) {
  const totalVolume = volume.reduce((sum, value) => sum + value, 0);
  const weighted = candles.reduce((sum, price, index) => sum + price * volume[index], 0);
  return Number((weighted / totalVolume).toFixed(2));
}

export function analyzeTechnicals(candles, volume) {
  const last = candles.at(-1);
  const first = candles[0];
  const rsi = calculateRsi(candles);
  const macd = calculateMacd(candles);
  const vwap = calculateVwap(candles, volume);
  const trendReturn = (last - first) / first;
  const volumeTrend = volume.at(-1) / average(volume.slice(0, 8));
  const trendStrength = Math.tanh(trendReturn * 6 + macd.histogram / Math.max(1, last) * 7);

  return {
    lastPrice: last,
    rsi,
    macd,
    vwap,
    trendReturn: Number(trendReturn.toFixed(3)),
    trendStrength: Number(trendStrength.toFixed(3)),
    volumeTrend: Number(volumeTrend.toFixed(2)),
    bias: trendStrength > 0.18 ? "Bullish Momentum" : trendStrength < -0.18 ? "Bearish Momentum" : "Rangebound"
  };
}
