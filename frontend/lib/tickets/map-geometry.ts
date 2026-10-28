import type {
  PublicSeatMapSection,
  SeatSectionGeometry,
} from "./public-ticketing";

export type SeatGridItem = {
  kind: "seat" | "aisle" | "empty";
  key: string;
  column: number;
  columnSpan: number;
  curveOffset: number;
  seat?: PublicSeatMapSection["rows"][number]["seats"][number];
};

export type SeatGridRow = {
  label: string;
  slotCount: number;
  items: SeatGridItem[];
};

export type SeatGridLayout = {
  seatSize: number;
  seatPitch: number;
  rows: SeatGridRow[];
};

/**
 * Arrange normalized seat and gap positions into compact, centered theatre rows.
 * The returned dimensions affect presentation only; seat identity and pricing
 * continue to come from the API.
 */
export function layoutSeatRows(
  section: PublicSeatMapSection,
  availableWidth: number,
  zoom = 1,
): SeatGridLayout {
  const largestRowSlots = Math.max(
    1,
    ...section.rows.map((row) =>
      Math.max(
        0,
        ...row.seats.map((seat) => seat.position),
        ...row.gaps.map((gap) => gap.position + gap.width - 1),
      ),
    ),
  );
  const seatSize =
    Math.min(
      48,
      Math.max(30, (Math.max(280, availableWidth) - 72) / largestRowSlots),
    ) * zoom;
  const seatPitch = seatSize + 8 * zoom;

  const rows = section.rows.map((row) => {
    const slotCount = Math.max(
      1,
      ...row.seats.map((seat) => seat.position),
      ...row.gaps.map((gap) => gap.position + gap.width - 1),
    );
    const seatYValues = row.seats
      .map((seat) => seat.visual?.y)
      .filter((value): value is number => value !== undefined);
    const middleY = seatYValues.length
      ? seatYValues.reduce((total, value) => total + value, 0) /
        seatYValues.length
      : 0;
    const maximumCurve = Math.max(
      1,
      ...seatYValues.map((value) => Math.abs(value - middleY)),
    );
    const curveScale = Math.min(1, 18 / maximumCurve);
    const isCurved = row.layout?.shape === "arc";

    const items: SeatGridItem[] = [
      ...row.seats.map((seat) => ({
        kind: "seat" as const,
        key: seat.number,
        column: seat.position,
        columnSpan: 1,
        curveOffset:
          isCurved && seat.visual ? (seat.visual.y - middleY) * curveScale : 0,
        seat,
      })),
      ...row.gaps.map((gap) => ({
        kind: gap.kind,
        key: `gap-${gap.position}`,
        column: gap.position,
        columnSpan: gap.width,
        curveOffset: 0,
      })),
    ].sort((left, right) => left.column - right.column);

    return { label: row.label, slotCount, items };
  });

  return { seatSize, seatPitch, rows };
}

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
