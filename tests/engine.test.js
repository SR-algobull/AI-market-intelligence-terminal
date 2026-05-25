import assert from "node:assert/strict";
import { analyzeTicker } from "../backend/decisionEngine.js";
import { scoreSentiment, classifyEvent, cleanAndDeduplicate } from "../backend/nlpEngine.js";

const bullish = scoreSentiment("Company beat revenue expectations and raised strong guidance");
assert.equal(bullish.label, "Bullish");
assert.ok(bullish.score > 0.3);

const bearish = scoreSentiment("Margins declined after price cuts pressured profitability");
assert.equal(bearish.label, "Bearish");
assert.ok(bearish.score < -0.2);

assert.equal(classifyEvent("The Fed rate outlook moved after inflation data"), "Macro/Fed");

const cleaned = cleanAndDeduplicate([
  { id: "1", text: "Strong growth strong growth", timestamp: "2026-05-25T10:00:00Z" },
  { id: "2", text: "Strong growth strong growth", timestamp: "2026-05-25T10:01:00Z" },
  { id: "3", text: "Click here for guaranteed 100x", timestamp: "2026-05-25T10:02:00Z" }
]);
assert.equal(cleaned.length, 1);

const nvda = analyzeTicker("NVDA");
assert.equal(nvda.symbol, "NVDA");
assert.ok(nvda.confidence >= 0 && nvda.confidence <= 1);
assert.ok(nvda.analyzedText.length > 0);

console.log("All engine tests passed.");
