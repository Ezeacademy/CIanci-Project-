export type StudentCredit = {
  student: {
    id: number;
    firstName: string;
    lastName: string;
    accessType: "self" | "guardian";
  };
  availableAmount: string;
};

export class PrivateApiSessionExpiredError extends Error {}

function getBackendUrl() {
  return (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(
    /\/$/,
    "",
  );
}

export async function getPrivateApiPages<T>(
  path: string,
  expectedPath: string,
  cookieHeader: string,
): Promise<T[]> {
  return (
    await getPrivateApiPageCollection<T>(path, expectedPath, cookieHeader)
  ).results;
}

export async function getPrivateApiPageCollection<T>(
  path: string,
  expectedPath: string,
  cookieHeader: string,
): Promise<{
  results: T[];
  summary?: { amount: string; paidAmount: string; balance: string };
  credits?: StudentCredit[];
}> {
  const backendUrl = getBackendUrl();
  const backendOrigin = new URL(backendUrl).origin;
  const visited = new Set<string>();
  const results: T[] = [];
  let credits: StudentCredit[] | undefined;
  let summary:
    { amount: string; paidAmount: string; balance: string } | undefined;
  let url: URL | null = new URL(path, backendUrl);

  while (url) {
    if (
      url.origin !== backendOrigin ||
      url.pathname !== expectedPath ||
      url.username ||
      url.password ||
      visited.has(url.href)
    ) {
      throw new Error("Respuesta de paginación privada inválida.");
    }
    visited.add(url.href);

    const response = await fetch(url, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
      redirect: "manual",
    });
    if (response.status === 401 || response.status === 403) {
      throw new PrivateApiSessionExpiredError();
    }
    if (!response.ok)
      throw new Error("No se pudo cargar la información privada.");

    const page = (await response.json()) as {
      next: string | null;
      results: T[];
      summary?: { amount: string; paidAmount: string; balance: string };
      credits?: StudentCredit[];
    };
    if (!Array.isArray(page.results)) {
      throw new Error("Respuesta privada inválida.");
    }
    summary ??= page.summary;
    credits ??= page.credits;
    results.push(...page.results);
    url = page.next ? new URL(page.next, backendUrl) : null;
  }

  return { results, summary, credits };
}
