import assert from "node:assert/strict";
import test from "node:test";

import {
  formatCentsAsDecimal,
  sumSelectedSeatPricesCents,
  toggleSeatSelection,
} from "../lib/tickets/seat-selection.ts";

test("select and deselect only operational seats with configured prices", () => {
  const firstSeat = {
    key: "Platea/A/1",
    price: "12500.00",
    isOperational: true,
  };
  const closedSeat = {
    key: "Platea/A/2",
    price: "12500.00",
    isOperational: false,
  };
  const unpricedSeat = { key: "Palco/A/1", price: null, isOperational: true };

  assert.deepEqual(toggleSeatSelection([], firstSeat), ["Platea/A/1"]);
  assert.deepEqual(toggleSeatSelection([firstSeat.key], firstSeat), []);
  assert.deepEqual(toggleSeatSelection([], closedSeat), []);
  assert.deepEqual(toggleSeatSelection([], unpricedSeat), []);
});

test("selection total preserves exact pesos and centavos", () => {
  const seats = [
    { key: "A", price: "12500.25", isOperational: true },
    { key: "B", price: "9000", isOperational: true },
    { key: "C", price: "100.00", isOperational: false },
  ];
  const cents = sumSelectedSeatPricesCents(seats, ["A", "B", "C", "missing"]);

  assert.equal(cents, 2150025n);
  assert.equal(formatCentsAsDecimal(cents), "21500.25");
});
