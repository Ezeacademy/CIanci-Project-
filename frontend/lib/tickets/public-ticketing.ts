export type PublicTicketFunctionSummary = {
  id: number;
  startsAt: string;
  venue: string;
  location: string;
  capacity: number;
  sectionPrices: Array<{ section: string; amount: string }>;
};

export type PublicTicketShow = {
  id: number;
  title: string;
  description: string;
  imageUrl: string;
  functions: PublicTicketFunctionSummary[];
  hasPastFunctions?: boolean;
};

export type PublicTicketSeatMap = PublicTicketFunctionSummary & {
  layout?: SeatMapCanvasLayout;
  sections: Array<{
    id?: number;
    name: string;
    sortOrder: number;
    price: string | null;
    layout?: SeatSectionGeometry;
    rows: Array<{
      label: string;
      sortOrder: number;
      layout?: SeatRowGeometry;
      seats: Array<{
        number: string;
        position: number;
        isAccessible: boolean;
        isOperational: boolean;
        visual?: SeatVisualPosition;
      }>;
      gaps: Array<{
        position: number;
        width: number;
        kind: "aisle" | "empty";
        visual?: SeatVisualPosition;
      }>;
    }>;
  }>;
};

export type SeatMapCanvasLayout = {
  width: number;
  height: number;
  stage: { x: number; y: number; width: number; height: number; label: string };
};

export type SeatSectionGeometry = {
  shape: "rectangle" | "arc";
  levelName: string;
  levelOrder: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  innerRadiusRatio: number;
  startAngle: number;
  endAngle: number;
};

export type SeatRowGeometry =
  | {
      shape: "straight";
      startX: number;
      startY: number;
      endX: number;
      endY: number;
    }
  | {
      shape: "arc";
      centerX: number;
      centerY: number;
      radiusX: number;
      radiusY: number;
      startAngle: number;
      endAngle: number;
    };

export type SeatVisualPosition = { x: number; y: number; rotation: number };

export type PublicSeatMapOverview = PublicTicketFunctionSummary & {
  layout: SeatMapCanvasLayout;
  sections: Array<{
    id: number;
    name: string;
    sortOrder: number;
    price: string | null;
    operationalSeatCount: number;
    layout: SeatSectionGeometry;
  }>;
};

export type PublicSeatMapSection = Omit<
  PublicTicketSeatMap["sections"][number],
  "id" | "layout"
> & {
  id: number;
  functionId: number;
  layout: SeatSectionGeometry;
  canvas: SeatMapCanvasLayout;
};

async function getPublicTicketingData<T>(path: string): Promise<T> {
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(`${backendUrl}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    throw new Error(
      `Public ticketing API returned HTTP ${response.status} for ${path}`,
    );
  }
  return (await response.json()) as T;
}

export function getPublicTicketShows(): Promise<PublicTicketShow[]> {
  return getPublicTicketingData("/api/v1/ticketing/shows");
}

export async function getPublicTicketShow(
  showId: number,
): Promise<PublicTicketShow | null> {
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(
    `${backendUrl}/api/v1/ticketing/shows/${showId}`,
    {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    },
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(
      `Public ticketing API returned HTTP ${response.status} for show ${showId}`,
    );
  }
  return (await response.json()) as PublicTicketShow;
}
