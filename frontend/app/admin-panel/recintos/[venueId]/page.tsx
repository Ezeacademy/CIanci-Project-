import { notFound, redirect } from "next/navigation";
import { getSessionUser } from "../../../../lib/auth/session";
import {
  getTicketingData,
  type TicketingMapSummary,
  type TicketingSeatMap,
} from "../../../../lib/admin-panel/ticketing";
import {
  SeatMapEditor,
  TicketingHeader,
} from "../../../../features/admin-panel/ticketing-management";

type Props = {
  params: Promise<{ venueId: string }>;
  searchParams: Promise<{ map?: string }>;
};
export const metadata = {
  title: "Mapa de butacas | Panel administrativo | Cianci",
  robots: { index: false, follow: false },
};

export default async function VenueMapPage({ params, searchParams }: Props) {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");
  const { venueId } = await params;
  const query = await searchParams;
  let result: {
    venue: { id: number; name: string; location: string };
    versions: TicketingMapSummary[];
  };
  let initialMap: TicketingSeatMap | undefined;
  try {
    result = await getTicketingData(
      `/api/v1/admin/ticketing/venues/${venueId}/maps`,
    );
    if (query.map) {
      const loadedMap = await getTicketingData<TicketingSeatMap>(
        `/api/v1/admin/ticketing/maps/${query.map}`,
      );
      if (loadedMap.venueId !== result.venue.id) notFound();
      initialMap = loadedMap;
    }
  } catch {
    notFound();
  }
  if (!result!) notFound();
  return (
    <main id="contenido" className="shell admin-panel-page">
      <TicketingHeader
        title={result.venue.name}
        description="Diseñá una distribución física reutilizable. Los mapas asociados a funciones quedan protegidos."
      />
      <SeatMapEditor
        key={initialMap?.id ?? "new-map"}
        venue={result.venue}
        versions={result.versions}
        initialMap={initialMap}
      />
    </main>
  );
}
