function getOutputText(payload) {
  if (payload.output_text) return payload.output_text.trim();

  return (payload.output ?? [])
    .flatMap((item) => item.content ?? [])
    .map((content) => content.text ?? "")
    .join("")
    .trim();
}

export async function generateMarketExplanation({ symbol, company, technicals, sentiment, risk, confidence, news }) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return null;

  const model = process.env.OPENAI_MODEL || "gpt-5.2";
  const newsBullets = news
    .slice(0, 5)
    .map((item) => `- ${item.source}: ${item.text}`)
    .join("\n");

  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      authorization: `Bearer ${apiKey}`,
      "content-type": "application/json"
    },
    body: JSON.stringify({
      model,
      instructions:
        "You are an institutional market intelligence analyst. Write concise, educational analysis. Do not give personalized financial advice. Mention the main drivers and risk in plain English.",
      input: `Ticker: ${symbol}
Company: ${company}
Trade confidence: ${Math.round(confidence * 100)}%
Market regime: ${technicals.bias}
NLP sentiment: ${sentiment.label} (${sentiment.score})
Sentiment confidence: ${sentiment.confidence}
Risk: ${risk.level} (${risk.score})
RSI: ${technicals.rsi}
MACD histogram: ${technicals.macd.histogram}
VWAP: ${technicals.vwap}
Recent news/social:
${newsBullets}

Return exactly two sentences: one sentence explaining the market setup and one sentence explaining the main risk.`
    })
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`OpenAI ${response.status}: ${body.slice(0, 240)}`);
  }

  return getOutputText(await response.json());
}
