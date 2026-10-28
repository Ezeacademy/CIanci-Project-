import assert from "node:assert/strict";
import test from "node:test";

import {
  formatDescriptiveDate,
  formatInstantDate,
  formatInstantDateTime,
  formatNumericDate,
  parseArgentineDate,
} from "../lib/format-date.ts";

test("Argentine date fields round-trip normal and zero-padded dates", () => {
  assert.equal(parseArgentineDate("28/10/2026"), "2026-10-28");
  assert.equal(parseArgentineDate("05/03/2026"), "2026-03-05");
  assert.equal(formatNumericDate("2026-10-28"), "28/10/2026");
  assert.equal(formatNumericDate("2026-03-05"), "05/03/2026");
});

test("Argentine date parser accepts leap days and rejects impossible dates", () => {
  assert.equal(parseArgentineDate("29/02/2028"), "2028-02-29");
  assert.equal(parseArgentineDate("31/02/2026"), null);
  assert.equal(parseArgentineDate("29/02/2026"), null);
  assert.equal(parseArgentineDate("1/2/2026"), null);
});

test("ISO calendar dates keep their day and descriptive output includes the year", () => {
  assert.equal(formatNumericDate("2026-10-28"), "28/10/2026");
  assert.match(formatDescriptiveDate("2026-10-28"), /28 de octubre de 2026/);
  assert.equal(
    formatInstantDate("2026-10-28T01:30:00Z"),
    "27 de octubre de 2026",
  );
});

test("formats date and time in Argentine numeric and 24-hour conventions", () => {
  assert.equal(
    formatInstantDateTime("2027-02-01T23:00:00Z"),
    "01/02/2027, 20:00",
  );
});
