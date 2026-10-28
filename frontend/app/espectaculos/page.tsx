import type { Metadata } from "next";
import { PublicShowsCatalog } from "../../features/tickets/public-ticketing";
import { PublicErrorState } from "../../features/tickets/public-error-state";
import {
  getPublicTicketShows,
  type PublicTicketShow,
} from "../../lib/tickets/public-ticketing";

export const metadata: Metadata = {
  title: "Espectáculos | Cianci",
  description: "Conocé los próximos espectáculos de danza de Cianci.",
};

export const dynamic = "force-dynamic";

export default async function PublicShowsPage() {
  let shows: PublicTicketShow[];
  try {
    shows = await getPublicTicketShows();
  } catch (error) {
    console.error("Failed to load public shows", error);
    return <PublicErrorState title="No pudimos cargar los espectáculos" />;
  }
  return <PublicShowsCatalog shows={shows} />;
}
