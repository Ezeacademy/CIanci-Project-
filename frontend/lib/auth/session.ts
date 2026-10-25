import { cache } from "react";
import { cookies } from "next/headers";

export type SessionUser = {
  id: number;
  email: string;
  firstName: string;
  lastName: string;
};

export const getSessionUser = cache(async (): Promise<SessionUser | null> => {
  const cookieHeader = (await cookies()).toString();
  if (
    !cookieHeader
      .split(";")
      .some((cookie) => cookie.trim().startsWith("sessionid="))
  ) {
    return null;
  }

  const backendUrl = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";
  const response = await fetch(`${backendUrl}/api/v1/me`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("No se pudo verificar la sesión.");
  return (await response.json()) as SessionUser;
});
