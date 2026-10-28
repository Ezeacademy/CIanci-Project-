import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PublicShowDetail } from "../../../features/tickets/public-ticketing";
import { PublicErrorState } from "../../../features/tickets/public-error-state";
import {
  getPublicTicketShow,
  type PublicTicketShow,
} from "../../../lib/tickets/public-ticketing";

export const dynamic = "force-dynamic";

type ShowPageProps = { params: Promise<{ showId: string }> };

export async function generateMetadata({
  params,
}: ShowPageProps): Promise<Metadata> {
  const { showId } = await params;
  const id = Number(showId);
  if (!Number.isInteger(id) || id < 1) return { title: "Espectáculo | Cianci" };
  try {
    const show = await getPublicTicketShow(id);
    return { title: show ? `${show.title} | Cianci` : "Espectáculo | Cianci" };
  } catch (error) {
    console.error("Failed to load public show metadata", error);
    return { title: "Espectáculo | Cianci" };
  }
}

export default async function PublicShowPage({ params }: ShowPageProps) {
  const { showId } = await params;
  const id = Number(showId);
  if (!Number.isInteger(id) || id < 1) notFound();

  let show: PublicTicketShow | null = null;
  let hasLoadError = false;
  try {
    show = await getPublicTicketShow(id);
  } catch (error) {
    console.error("Failed to load public show", error);
    hasLoadError = true;
  }
  if (hasLoadError) {
    return <PublicErrorState title="No pudimos cargar este espectáculo" />;
  }
  if (!show) notFound();
  return <PublicShowDetail show={show} />;
}
