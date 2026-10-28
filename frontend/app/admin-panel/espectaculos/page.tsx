import { redirect } from "next/navigation";
import { getSessionUser } from "../../../lib/auth/session";
import {
  getTicketingData,
  type TicketingSeatMap,
  type TicketingShow,
  type TicketingVenue,
} from "../../../lib/admin-panel/ticketing";
import {
  ShowManagement,
  TicketingHeader,
} from "../../../features/admin-panel/ticketing-management";

export const metadata = {
  title: "Espectáculos | Panel administrativo | Cianci",
  robots: { index: false, follow: false },
};

export default async function ShowsPage() {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");
  let shows: TicketingShow[] = [];
  let venues: TicketingVenue[] = [];
  let maps: TicketingSeatMap[] = [];
  let error = "";
  try {
    [shows, venues] = await Promise.all([
      getTicketingData<TicketingShow[]>("/api/v1/admin/ticketing/shows"),
      getTicketingData<TicketingVenue[]>("/api/v1/admin/ticketing/venues"),
    ]);
    maps = await Promise.all(
      venues.flatMap((venue) =>
        venue.versions.map((version) =>
          getTicketingData<TicketingSeatMap>(
            `/api/v1/admin/ticketing/maps/${version.id}`,
          ),
        ),
      ),
    );
  } catch (reason) {
    error =
      reason instanceof Error
        ? reason.message
        : "No pudimos cargar los espectáculos.";
  }
  return (
    <main id="contenido" className="shell admin-panel-page">
      <TicketingHeader
        title="Espectáculos"
        description="Organizá las funciones y los recintos del instituto."
      />
      {error ? (
        <p className="admin-panel-message" role="alert">
          {error}
        </p>
      ) : (
        <ShowManagement shows={shows} venues={venues} maps={maps} />
      )}
    </main>
  );
}
