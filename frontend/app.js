import { analyzeTicker, getUniverseSymbols } from "../backend/decisionEngine.js";

const state = {
  selected: "NVDA",
  analysis: analyzeTicker("NVDA"),
  loading: false
};

const app = document.querySelector("#app");

function gaugeColor(value) {
  if (value >= 70) return "var(--green)";
  if (value >= 45) return "var(--amber)";
  return "var(--red)";
}

async function refreshAnalysis(symbol) {
  state.selected = symbol.toUpperCase();
  state.loading = true;
  render();

  try {
    const response = await fetch(`/api/analyze/${encodeURIComponent(state.selected)}`);
    if (!response.ok) throw new Error("Live API unavailable");
    state.analysis = await response.json();
  } catch {
    state.analysis = analyzeTicker(state.selected);
    state.analysis.dataMode = "demo";
  }

  state.loading = false;
  render();
}

function render() {
  const a = state.analysis;
  app.innerHTML = `
    <section class="topbar">
      <div>
        <p class="eyebrow">AI Market Intelligence Terminal</p>
        <h1>${a.symbol} <span>${a.company}</span></h1>
        <p class="data-mode">${state.loading ? "Updating..." : `${(a.dataMode ?? "demo").toUpperCase()} DATA${a.dataProvider ? ` (${a.dataProvider})` : ""} | ${(a.socialProvider ?? "demo").toUpperCase()} SOCIAL | ${(a.aiMode ?? "rules").toUpperCase()} AI`}</p>
      </div>
      <form class="search-form" id="searchForm">
        <input id="tickerInput" value="${a.symbol}" aria-label="Ticker search" />
        <button type="submit">Analyze</button>
      </form>
    </section>

    <section class="symbol-strip">
      ${getUniverseSymbols()
        .map(
          (item) => `
            <button class="symbol-chip ${item.symbol === a.symbol ? "active" : ""}" data-symbol="${item.symbol}">
              <strong>${item.symbol}</strong>
              <span>${item.sector}</span>
            </button>
          `
        )
        .join("")}
    </section>

    <section class="hero-grid">
      <article class="main-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">Decision Engine</p>
            <h2>${a.marketRegime}</h2>
          </div>
          <div class="confidence-ring" style="--score:${a.confidencePercent}; --ring:${gaugeColor(a.confidencePercent)}">
            <span>${a.confidencePercent}%</span>
          </div>
        </div>
        <p class="ai-summary">${a.explanation}</p>
        <div class="metric-grid">
          ${metric("Sentiment", a.sentiment.label, `${Math.round(a.sentiment.score * 100)} NLP score`)}
          ${metric("Risk", a.risk.level, `${Math.round(a.risk.score * 100)} risk index`)}
          ${metric("RSI", a.technicals.rsi, a.technicals.rsi > 70 ? "Overbought" : "Momentum")}
          ${metric("VWAP", `$${a.technicals.vwap}`, `Last $${a.technicals.lastPrice}`)}
        </div>
      </article>

      <article class="chart-panel">
        <div class="panel-head compact">
          <div>
            <p class="eyebrow">Live Price Simulation</p>
            <h2>OHLCV Trend</h2>
          </div>
          <span class="status-dot">Streaming</span>
        </div>
        <canvas id="priceChart" width="760" height="360" aria-label="Price trend chart"></canvas>
      </article>
    </section>

    <section class="dashboard-grid">
      <article>
        <p class="eyebrow">NLP Layer</p>
        <h2>News + Social Sentiment</h2>
        <div class="sentiment-row">
          <div class="bar-track"><span style="width:${Math.round((a.sentiment.score + 1) * 50)}%"></span></div>
          <strong>${a.sentiment.label}</strong>
        </div>
        <div class="event-tags">
          ${a.sentiment.topEvents.map((event) => `<span>${event.label}</span>`).join("")}
        </div>
        <div class="feed-list">
          ${a.analyzedText.map(renderFeedItem).join("")}
        </div>
      </article>

      <article>
        <p class="eyebrow">Risk AI</p>
        <h2>Volatility + Instability</h2>
        <div class="risk-meter">
          <span style="width:${Math.round(a.risk.score * 100)}%"></span>
        </div>
        <ul class="driver-list">
          ${a.risk.drivers.map((driver) => `<li>${driver}</li>`).join("")}
          <li>Options unusual activity: ${a.risk.unusualActivity}x</li>
          <li>Realized volatility: ${Math.round(a.risk.realizedVolatility * 100)}%</li>
        </ul>
      </article>

      <article>
        <p class="eyebrow">Technical AI</p>
        <h2>Momentum Model</h2>
        <div class="technical-stack">
          ${metric("MACD", a.technicals.macd.histogram, "Histogram")}
          ${metric("Trend", Math.round(a.technicals.trendStrength * 100), a.technicals.bias)}
          ${metric("Volume", `${a.technicals.volumeTrend}x`, "vs baseline")}
        </div>
      </article>

      <article>
        <p class="eyebrow">Alert Center</p>
        <h2>Actionable Watchlist</h2>
        <p class="alert-copy">${a.alert}</p>
        <div class="watchlist">
          ${getUniverseSymbols()
            .map((item) => {
              const score = analyzeTicker(item.symbol).confidencePercent;
              return `<button data-symbol="${item.symbol}"><span>${item.symbol}</span><strong>${score}%</strong></button>`;
            })
            .join("")}
        </div>
      </article>
    </section>
  `;

  bindEvents();
  drawChart(a.candles, a.volume);
}

function metric(label, value, hint) {
  return `
    <div class="metric">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${hint}</small>
    </div>
  `;
}

function renderFeedItem(item) {
  const polarityClass = item.sentiment.label.toLowerCase();
  const evidence = item.sentiment.evidence.map((hit) => hit.token).join(", ") || "low signal";
  return `
    <div class="feed-item">
      <div>
        <span class="source">${item.source}</span>
        <strong>${item.eventType}</strong>
      </div>
      <p>${item.text}</p>
      <footer>
        <span class="${polarityClass}">${item.sentiment.label} ${Math.round(item.sentiment.confidence * 100)}%</span>
        <span>Evidence: ${evidence}</span>
      </footer>
    </div>
  `;
}

function bindEvents() {
  document.querySelector("#searchForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = document.querySelector("#tickerInput").value.trim().toUpperCase();
    refreshAnalysis(value || "NVDA");
  });

  document.querySelectorAll("[data-symbol]").forEach((button) => {
    button.addEventListener("click", () => {
      refreshAnalysis(button.dataset.symbol);
    });
  });
}

function drawChart(candles, volume) {
  const canvas = document.querySelector("#priceChart");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = 38;
  const min = Math.min(...candles);
  const max = Math.max(...candles);
  const maxVol = Math.max(...volume);

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#10151f";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#263245";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i += 1) {
    const y = padding + i * ((height - padding * 2) / 4);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  volume.forEach((bar, index) => {
    const x = padding + index * ((width - padding * 2) / (volume.length - 1));
    const barHeight = (bar / maxVol) * 74;
    ctx.fillStyle = "rgba(74, 163, 255, 0.24)";
    ctx.fillRect(x - 5, height - padding - barHeight, 8, barHeight);
  });

  ctx.beginPath();
  candles.forEach((price, index) => {
    const x = padding + index * ((width - padding * 2) / (candles.length - 1));
    const y = height - padding - ((price - min) / (max - min || 1)) * (height - padding * 2);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = candles.at(-1) >= candles[0] ? "#3ddc97" : "#ff6b6b";
  ctx.lineWidth = 4;
  ctx.stroke();

  ctx.fillStyle = "#c9d6e5";
  ctx.font = "16px Inter, Arial";
  ctx.fillText(`$${candles.at(-1)}`, width - 108, padding + 8);
}

render();
refreshAnalysis(state.selected);
