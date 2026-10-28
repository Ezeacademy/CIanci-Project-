export class AdminAcademicRequestError extends Error {
  constructor(
    message: string,
    public readonly fieldErrors: Record<string, string>,
  ) {
    super(message);
  }
}

export async function submitAdminAcademicRequest<T>(
  path: string,
  method: "POST" | "PATCH" | "PUT",
  payload: unknown = {},
): Promise<T> {
  const csrfResponse = await fetch("/api/v1/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!csrfResponse.ok) {
    throw new AdminAcademicRequestError(
      "No pudimos validar la sesión. Actualizá la página e intentá nuevamente.",
      {},
    );
  }
  const { csrfToken } = (await csrfResponse.json()) as { csrfToken: string };
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  const body = (await response.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  if (!response.ok) {
    const fieldErrors: Record<string, string> = {};
    for (const [field, messages] of Object.entries(body)) {
      if (Array.isArray(messages) && typeof messages[0] === "string") {
        fieldErrors[field] = messages[0];
      }
    }
    const message =
      (typeof body.detail === "string" && body.detail) ||
      Object.values(fieldErrors)[0] ||
      "No pudimos guardar los cambios. Revisá los datos e intentá nuevamente.";
    throw new AdminAcademicRequestError(message, fieldErrors);
  }
  return body as T;
}
