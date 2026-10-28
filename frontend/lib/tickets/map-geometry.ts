import type { SeatSectionGeometry } from "./public-ticketing";

/** Build a safe SVG path from validated numeric sector geometry. */
export function annularSectorPath(geometry: SeatSectionGeometry): string {
  const centerX = geometry.x + geometry.width / 2;
  const centerY = geometry.y + geometry.height / 2;
  const radiusX = geometry.width / 2;
  const radiusY = geometry.height / 2;
  const point = (radiusRatio: number, angle: number) => {
    const radians = (angle * Math.PI) / 180;
    return [
      centerX + radiusX * radiusRatio * Math.cos(radians),
      centerY + radiusY * radiusRatio * Math.sin(radians),
    ];
  };
  const startOuter = point(1, geometry.startAngle);
  const endOuter = point(1, geometry.endAngle);
  const startInner = point(geometry.innerRadiusRatio, geometry.endAngle);
  const endInner = point(geometry.innerRadiusRatio, geometry.startAngle);
  const sweep = geometry.endAngle - geometry.startAngle;
  const largeArc = sweep > 180 ? 1 : 0;

  if (sweep >= 359.99) {
    const middleOuter = point(1, geometry.startAngle + 180);
    const middleInner = point(
      geometry.innerRadiusRatio,
      geometry.startAngle + 180,
    );
    return `M ${startOuter[0]} ${startOuter[1]} A ${radiusX} ${radiusY} 0 1 1 ${middleOuter[0]} ${middleOuter[1]} A ${radiusX} ${radiusY} 0 1 1 ${endOuter[0]} ${endOuter[1]} L ${startInner[0]} ${startInner[1]} A ${radiusX * geometry.innerRadiusRatio} ${radiusY * geometry.innerRadiusRatio} 0 1 0 ${middleInner[0]} ${middleInner[1]} A ${radiusX * geometry.innerRadiusRatio} ${radiusY * geometry.innerRadiusRatio} 0 1 0 ${endInner[0]} ${endInner[1]} Z`;
  }
  return `M ${startOuter[0]} ${startOuter[1]} A ${radiusX} ${radiusY} 0 ${largeArc} 1 ${endOuter[0]} ${endOuter[1]} L ${startInner[0]} ${startInner[1]} A ${radiusX * geometry.innerRadiusRatio} ${radiusY * geometry.innerRadiusRatio} 0 ${largeArc} 0 ${endInner[0]} ${endInner[1]} Z`;
}

/** Place curved-sector labels midway through the visible ring. */
export function sectionLabelPosition(
  geometry: SeatSectionGeometry,
): [number, number] {
  const centerX = geometry.x + geometry.width / 2;
  const centerY = geometry.y + geometry.height / 2;
  if (geometry.shape === "rectangle") return [centerX, centerY];

  const radiusRatio = (1 + geometry.innerRadiusRatio) / 2;
  const angle =
    ((geometry.startAngle + geometry.endAngle) / 2 + geometry.rotation) *
    (Math.PI / 180);
  return [
    centerX + (geometry.width / 2) * radiusRatio * Math.cos(angle),
    centerY + (geometry.height / 2) * radiusRatio * Math.sin(angle),
  ];
}
