import assert from "node:assert/strict";
import test from "node:test";

import {
  formatCompactCalendarDateRange,
  getCalendarWeekDays,
  getVisibleCalendarHours,
  positionCalendarOverlaps,
  shiftCalendarWeek,
  startOfCalendarWeek,
} from "../lib/academic/calendar-layout.ts";

test("calendar weeks include correct dates across month and year boundaries", () => {
  const octoberWeekStart = startOfCalendarWeek("2026-10-28");
  assert.equal(octoberWeekStart, "2026-10-26");
  assert.deepEqual(
    getCalendarWeekDays(octoberWeekStart).map(({ date }) => date),
    [
      "2026-10-26",
      "2026-10-27",
      "2026-10-28",
      "2026-10-29",
      "2026-10-30",
      "2026-10-31",
      "2026-11-01",
    ],
  );

  const newYearWeekStart = startOfCalendarWeek("2027-01-01");
  assert.equal(newYearWeekStart, "2026-12-28");
  assert.equal(shiftCalendarWeek(newYearWeekStart, 1), "2027-01-04");
  assert.equal(getCalendarWeekDays(newYearWeekStart).at(-1).date, "2027-01-03");
  assert.match(
    formatCompactCalendarDateRange("2026-12-28", "2027-01-03"),
    /2026 — .*2027/,
  );
});

test("calendar hour range adds context without expanding to the whole day", () => {
  assert.deepEqual(getVisibleCalendarHours([]), []);
  assert.deepEqual(
    getVisibleCalendarHours([makeOccurrence(1, "09:30", "10:30")]),
    [7, 8, 9, 10, 11, 12],
  );
  assert.deepEqual(
    getVisibleCalendarHours([makeOccurrence(2, "23:30", "23:59")]),
    [18, 19, 20, 21, 22, 23],
  );
});

test("overlapping classes receive separate deterministic columns", () => {
  const occurrences = [
    makeOccurrence(1, "18:00", "19:00"),
    makeOccurrence(2, "18:30", "20:00", "Clásico"),
    makeOccurrence(3, "20:00", "21:00", "Jazz Intermedio"),
  ];

  const positioned = positionCalendarOverlaps(occurrences, 0);

  assert.deepEqual(
    positioned.map(({ id, columnIndex, columnCount }) => ({
      id,
      columnIndex,
      columnCount,
    })),
    [
      { id: 1, columnIndex: 0, columnCount: 2 },
      { id: 2, columnIndex: 1, columnCount: 2 },
      { id: 3, columnIndex: 0, columnCount: 1 },
    ],
  );
});

function makeOccurrence(
  id,
  startTime,
  endTime,
  disciplineName = `Disciplina ${id}`,
) {
  return {
    id,
    weekday: 0,
    weekdayName: "Lunes",
    startTime,
    endTime,
    nextClass: "2026-10-26T18:00:00-03:00",
    teacher: { firstName: "Loli", lastName: "Fernández" },
    student: {
      id: 1,
      firstName: "Candela",
      lastName: "Manzo",
      accessType: "guardian",
    },
    discipline: { id, name: disciplineName },
  };
}
