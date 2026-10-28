import assert from "node:assert/strict";
import test from "node:test";

import {
  annularSectorPath,
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
