import { redirect } from "next/navigation";
import { getSessionUser } from "../../../lib/auth/session";
import {
  getTicketingData,
  type TicketingVenue,
} from "../../../lib/admin-panel/ticketing";
import {
  TicketingHeader,
  VenueManagement,
} from "../../../features/admin-panel/ticketing-management";

export const metadata = {
  title: "Recintos | Panel administrativo | Cianci",
  robots: { index: false, follow: false },
};

export default async function VenuesPage() {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");
  let venues: TicketingVenue[] = [];
  let error = "";
  try {
    venues = await getTicketingData<TicketingVenue[]>(
      "/api/v1/admin/ticketing/venues",
    );
  } catch (reason) {
    error =
      reason instanceof Error
        ? reason.message
        : "No pudimos cargar los recintos.";
  }
  return (
    <main id="contenido" className="shell admin-panel-page">
      <TicketingHeader
        title="Recintos y mapas"
        description="Configurá los sectores, filas y butacas de cada espacio."
      />
      {error ? (
        <p className="admin-panel-message" role="alert">
          {error}
        </p>
      ) : (
        <VenueManagement venues={venues} />
      )}
    </main>
  );
}
