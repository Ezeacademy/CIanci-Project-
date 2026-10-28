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
  sections: Array<{
    name: string;
    sortOrder: number;
    price: string | null;
    rows: Array<{
      label: string;
      sortOrder: number;
      seats: Array<{
        number: string;
        position: number;
        isAccessible: boolean;
        isOperational: boolean;
      }>;
      gaps: Array<{
        position: number;
        width: number;
        kind: "aisle" | "empty";
      }>;
    }>;
  }>;
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
