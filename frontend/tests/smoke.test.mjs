import assert from "node:assert/strict";
import test from "node:test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://localhost:3000";

test("la página inicial responde y muestra el instituto", async () => {
  const response = await fetch(baseUrl, { signal: AbortSignal.timeout(15000) });
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /text\/html/);
  const html = await response.text();
  assert.match(html, /<html[^>]*lang="es"/);
  assert.match(html, /<h1[^>]*>Cianci Platform<\/h1>/);
  assert.match(html, /Instituto de danza/);
});
