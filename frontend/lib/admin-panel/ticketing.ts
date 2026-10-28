import { cookies } from "next/headers";

export type TicketingVenue = {
  id: number;
  name: string;
  location: string;
  versions: TicketingMapSummary[];
};

export type TicketingMapSummary = {
  id: number;
  venueId: number;
  venue: string;
  version: number;
  capacity: number;
  isFrozen: boolean;
};

export type TicketingSeatMap = TicketingMapSummary & {
  sections: Array<{
    id?: number;
    name: string;
    sortOrder: number;
    rows: Array<{
      id?: number;
      label: string;
      sortOrder: number;
      seats: Array<{
        id?: number;
        number: string;
        position: number;
        isAccessible: boolean;
        isOperational: boolean;
      }>;
      gaps: Array<{ position: number; width: number; kind: "aisle" | "empty" }>;
    }>;
  }>;
};

export type TicketingShow = {
  id: number;
  title: string;
  description: string;
  imageUrl: string;
  status: "draft" | "published" | "archived";
  functions: Array<{
    id: number;
    startsAt: string;
    venue: string;
    mapVersionId: number;
    capacity: number;
    sectionPrices: Array<{
      sectionId: number;
      section: string;
      amount: string;
    }>;
  }>;
};

export async function getTicketingData<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(`${backendUrl}${path}`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
    redirect: "manual",
  });
  if (!response.ok)
    throw new Error(`No se pudo cargar la información (${response.status}).`);
  return (await response.json()) as T;
}
