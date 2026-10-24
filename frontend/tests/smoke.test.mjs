import assert from "node:assert/strict";
import test from "node:test";

const baseUrl = process.env.SMOKE_BASE_URL || "http://localhost:3000";

test("la homepage se sirve y sus enlaces internos tienen destino", async () => {
  const response = await fetch(baseUrl, { signal: AbortSignal.timeout(15000) });
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /text\/html/);
  const html = await response.text();
  const ids = new Set(
    [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]),
  );
  const anchors = [...html.matchAll(/\bhref="#([^"]+)"/g)];
  assert.ok(anchors.length > 0, "La navegación debe tener destinos internos");
  for (const [, target] of anchors) {
    assert.ok(ids.has(target), `Falta el destino #${target}`);
  }
});
