const disciplineImages = [
  "/images/dance/classical.webp",
  "/images/dance/contemporary.webp",
  "/images/dance/jazz.webp",
];

export function getDisciplineImage(name: string, index: number): string {
  const normalizedName = normalizeDisciplineName(name);
  if (normalizedName.includes("jazz")) return disciplineImages[2];
  if (normalizedName.includes("contempo")) return disciplineImages[1];
  if (normalizedName.includes("clasica") || normalizedName.includes("ballet")) {
    return disciplineImages[0];
  }
  return disciplineImages[index % disciplineImages.length];
}

export function getDisciplineDescription(name: string): string {
  const normalizedName = normalizeDisciplineName(name);
  if (normalizedName.includes("jazz")) {
    return "Ritmo, energía y expresión en cada secuencia.";
  }
  if (normalizedName.includes("contempo")) {
    return "Exploración corporal, fluidez y creación desde el movimiento.";
  }
  if (normalizedName.includes("clasica") || normalizedName.includes("ballet")) {
    return "Técnica, musicalidad y sensibilidad en cada movimiento.";
  }
  return "Una práctica para descubrir nuevas formas de movimiento.";
}

function normalizeDisciplineName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es-AR");
}
