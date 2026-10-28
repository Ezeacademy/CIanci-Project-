import type { Metadata } from "next";
import { PublicShowsCatalog } from "../../features/tickets/public-ticketing";
import {
  getPublicTicketShows,
  type PublicTicketShow,
} from "../../lib/tickets/public-ticketing";

export const metadata: Metadata = {
  title: "Espectáculos | Cianci",
  description: "Conocé los próximos espectáculos de danza de Cianci.",
};

export default async function PublicShowsPage() {
  let shows: PublicTicketShow[];
  try {
    shows = await getPublicTicketShows();
  } catch {
    return (
      <main id="contenido" className="shell section-block">
        <h1>Espectáculos</h1>
        <p role="alert">
          No pudimos cargar los espectáculos. Intentá nuevamente.
        </p>
      </main>
    );
  }
  return <PublicShowsCatalog shows={shows} />;
}
