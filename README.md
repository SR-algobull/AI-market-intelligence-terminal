# AI Market Intelligence Terminal

A portfolio-grade AI finance platform that combines market technicals, NLP sentiment, risk scoring, alerts, and an explainable trade confidence engine.

## What It Does

- Search a stock ticker and generate an AI market readout.
- Analyze news, earnings, SEC-style events, macro notes, and social chatter.
- Score bullish/bearish sentiment with confidence and token-level evidence.
- Calculate RSI, VWAP, MACD, trend strength, volatility, and unusual activity.
- Combine technicals, NLP, options flow, sector rotation, and risk into a trade confidence score.
- Explain why the model is bullish, bearish, or mixed.

## Architecture

```text
frontend/
  app.js              Interactive terminal UI, charts, search, alerts
  styles.css          Responsive Bloomberg-style interface
backend/
  data/marketData.js  Mock market, options, news, social, and macro feeds
  nlpEngine.js        Text cleaning, dedupe, sentiment, event classification, embeddings
  technicalEngine.js  RSI, VWAP, MACD, trend model
  riskEngine.js       Volatility, unusual activity, instability scoring
  decisionEngine.js   Multi-signal confidence score and explanations
tests/
  engine.test.js      Basic NLP and decision-engine tests
```

## Run Locally

```bash
npm install
npm run dev
```

Then open the Vite URL shown in the terminal.

## Run With Live API Proxy

Create `.env` from `.env.example`, add `ALPACA_API_KEY`, `ALPACA_API_SECRET`, and optionally `FINNHUB_API_KEY`, then run:

```bash
npm run start:live
```

Open `http://127.0.0.1:8080`. The backend endpoint `/api/analyze/:symbol` pulls live/delayed candles and quotes through Alpaca, plus company news through Finnhub when a key is present. Without usable keys, the app falls back to demo data so the interface still works.

StockTwits social data is pulled from the ticker message stream and merged into the same NLP pipeline as news. Firestream sentiment is attempted when the account is authorized for it.

## Test

```bash
npm test
```

## How To Talk About The NLP Layer

The NLP engine mirrors the production flow you would use with FinBERT or another financial transformer:

1. **Normalize text**: lowercase, remove URLs/punctuation, collapse whitespace.
2. **Filter noise**: remove spam-like posts and duplicate headlines.
3. **Tokenize**: split cleaned text into meaningful tokens.
4. **Sentiment scoring**: detect finance-specific bullish and bearish language, then squash the raw score into `-1..1`.
5. **Confidence scoring**: increase confidence when more evidence terms appear and the sentiment magnitude is stronger.
6. **Event classification**: classify text into earnings, macro/Fed, regulatory, options, sector rotation, or product/AI events.
7. **Embedding stub**: convert each text into a small keyword vector, representing where a vector database or transformer embedding would fit.

In a production version, `scoreSentiment` would call FinBERT, and `createKeywordEmbedding` would call a real embedding model before storing vectors in Pinecone, pgvector, Weaviate, or MongoDB Atlas Vector Search.
