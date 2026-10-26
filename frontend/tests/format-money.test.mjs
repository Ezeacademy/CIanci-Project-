import assert from "node:assert/strict";
import test from "node:test";

import { formatArsAmount } from "../lib/format-money.ts";

test("formats whole peso amounts without fractional zeroes", () => {
  assert.equal(formatArsAmount("105000.00"), "$ 105.000");
  assert.equal(formatArsAmount("0.00"), "$ 0");
});

test("preserves meaningful cents and groups large amounts", () => {
  assert.equal(formatArsAmount("30000.50"), "$ 30.000,50");
  assert.equal(formatArsAmount("30000.5"), "$ 30.000,50");
  assert.equal(formatArsAmount("1250.25"), "$ 1.250,25");
  assert.equal(formatArsAmount("9876543210.01"), "$ 9.876.543.210,01");
});

test("formats negative amounts without discarding cents", () => {
  assert.equal(formatArsAmount("-1250.25"), "-$ 1.250,25");
});
