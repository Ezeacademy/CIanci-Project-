import assert from "node:assert/strict";
import test from "node:test";

import {
  annularSectorPath,
  layoutSeatRows,
  sectionLabelPosition,
} from "../lib/tickets/map-geometry.ts";

const curvedSector = {
  shape: "arc",
  levelName: "Planta baja",
  levelOrder: 0,
  x: 100,
  y: 80,
  width: 400,
  height: 240,
  rotation: 0,
  innerRadiusRatio: 0.5,
  startAngle: 200,
  endAngle: 340,
};

test("curved sectors produce a ring-shaped SVG path", () => {
  const path = annularSectorPath(curvedSector);

  assert.match(path, /^M /);
  assert.equal((path.match(/ A /g) ?? []).length, 2);
  assert.match(path, / Z$/);
});

test("full-circle curved sectors split the SVG arc to avoid degenerate paths", () => {
  const path = annularSectorPath({
    ...curvedSector,
    startAngle: 0,
    endAngle: 360,
  });

  assert.equal((path.match(/ A /g) ?? []).length, 4);
});

test("labels for curved sectors sit between the inner and outer radii", () => {
  const [x, y] = sectionLabelPosition(curvedSector);
  const centerX = curvedSector.x + curvedSector.width / 2;
  const centerY = curvedSector.y + curvedSector.height / 2;
  const normalizedRadius = Math.hypot(
    (x - centerX) / (curvedSector.width / 2),
    (y - centerY) / (curvedSector.height / 2),
  );

  assert.ok(normalizedRadius > curvedSector.innerRadiusRatio);
  assert.ok(normalizedRadius < 1);
});

function seatSection({
  seatCount,
  rowCount = 1,
  shape = "straight",
  gaps = [],
}) {
  return {
    id: 1,
    functionId: 1,
    name: "Platea",
    sortOrder: 0,
    price: "9000.00",
    layout: { ...curvedSector, shape: "rectangle" },
    canvas: {
      width: 1200,
      height: 800,
      stage: { x: 400, y: 30, width: 400, height: 70, label: "ESCENARIO" },
    },
    rows: Array.from({ length: rowCount }, (_, rowIndex) => ({
      label: String.fromCharCode(65 + rowIndex),
      sortOrder: rowIndex,
      layout:
        shape === "arc"
          ? {
              shape,
              centerX: 200,
              centerY: 150,
              radiusX: 160,
              radiusY: 90,
              startAngle: 205,
              endAngle: 335,
            }
          : {
              shape,
              startX: 40,
              startY: 100 + rowIndex * 60,
              endX: 360,
              endY: 100 + rowIndex * 60,
            },
      seats: Array.from({ length: seatCount }, (_, index) => ({
        number: String(index + 1),
        position:
          index +
          1 +
          gaps.reduce(
            (total, gap) => total + (gap.position <= index + 1 ? gap.width : 0),
            0,
          ),
        isAccessible: false,
        isOperational: true,
        visual: {
          x: 40 + index * 20,
          y:
            100 +
            rowIndex * 60 +
            (shape === "arc" ? Math.abs(index - (seatCount - 1) / 2) * 3 : 0),
          rotation: 0,
        },
      })),
      gaps: rowIndex === 0 ? gaps : [],
    })),
  };
}

test("small seating rows get readable seats and compact centered row widths", () => {
  const layout = layoutSeatRows(seatSection({ seatCount: 4 }), 760);

  assert.equal(layout.seatSize, 48);
  assert.equal(layout.rows[0].slotCount, 4);
  assert.equal(layout.rows[0].items.length, 4);
});

test("seat sizes stay within usable bounds for large seating rows", () => {
  const layout = layoutSeatRows(seatSection({ seatCount: 60 }), 360);

  assert.ok(layout.seatSize >= 30);
  assert.ok(layout.seatSize <= 48);
  assert.equal(layout.rows[0].slotCount, 60);
});

test("only configured aisle gaps occupy and render row slots", () => {
  const layout = layoutSeatRows(
    seatSection({
      seatCount: 4,
      gaps: [{ position: 3, width: 2, kind: "aisle" }],
    }),
    760,
  );

  assert.equal(layout.rows[0].slotCount, 6);
  assert.deepEqual(
    layout.rows[0].items
      .filter((item) => item.kind !== "seat")
      .map((item) => [item.kind, item.column, item.columnSpan]),
    [["aisle", 3, 2]],
  );
});

test("curved rows retain a restrained arc between seats", () => {
  const layout = layoutSeatRows(
    seatSection({ seatCount: 7, shape: "arc" }),
    760,
  );
  const offsets = layout.rows[0].items.map((item) => item.curveOffset);

  assert.ok(Math.max(...offsets) <= 18);
  assert.ok(Math.max(...offsets) > 0);
  assert.ok(offsets[3] < offsets[0]);
});
