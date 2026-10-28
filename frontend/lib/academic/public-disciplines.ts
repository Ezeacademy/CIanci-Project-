export type PublicDiscipline = {
  id: number;
  name: string;
};

export async function getPublicDisciplines(): Promise<PublicDiscipline[]> {
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(`${backendUrl}/api/v1/academy/disciplines`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("No se pudo cargar la oferta de disciplinas.");
  }
  return (await response.json()) as PublicDiscipline[];
}
