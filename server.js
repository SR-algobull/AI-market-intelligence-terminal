import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { analyzeTickerLive } from "./backend/liveDecisionEngine.js";

const root = process.cwd();
const port = Number(process.env.PORT ?? 8080);

async function loadLocalEnv() {
  try {
    const file = await readFile(join(root, ".env"), "utf8");
    for (const line of file.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const index = trimmed.indexOf("=");
      if (index === -1) continue;
      const key = trimmed.slice(0, index).trim();
      const value = trimmed.slice(index + 1).trim();
      if (!process.env[key]) process.env[key] = value;
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8"
};

function sendJson(response, status, body) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(body));
}

await loadLocalEnv();

createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://${request.headers.host}`);

    if (url.pathname.startsWith("/api/analyze/")) {
      const symbol = decodeURIComponent(url.pathname.split("/").at(-1) || "NVDA");
      return sendJson(response, 200, await analyzeTickerLive(symbol));
    }

    const requested = url.pathname === "/" ? "/index.html" : url.pathname;
    const safePath = normalize(requested).replace(/^(\.\.[/\\])+/, "");
    const filePath = join(root, safePath);
    const file = await readFile(filePath);
    response.writeHead(200, { "content-type": mime[extname(filePath)] ?? "application/octet-stream" });
    response.end(file);
  } catch (error) {
    if (error.code === "ENOENT") {
      response.writeHead(404);
      response.end("Not found");
      return;
    }
    sendJson(response, 500, { error: error.message });
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`AI Market Intelligence Terminal running at http://127.0.0.1:${port}`);
});
