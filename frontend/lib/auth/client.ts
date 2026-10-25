export async function postAuth<T>(path: string, payload: unknown): Promise<T> {
  const csrfResponse = await fetch("/api/v1/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!csrfResponse.ok) throw new Error("No pudimos completar la solicitud.");
  const { csrfToken } = (await csrfResponse.json()) as { csrfToken: string };
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  const body = (await response.json()) as T & {
    detail?: string;
    errors?: Record<string, string[]>;
  };
  if (!response.ok) {
    if (body.errors) {
      const firstError = Object.values(body.errors).flat()[0];
      throw Object.assign(new Error(firstError || "Revisá los datos ingresados."), {
        fieldErrors: body.errors,
      });
    }
    throw new Error(body.detail || "No pudimos completar la solicitud.");
  }
  return body;
}

