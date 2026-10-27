import { cookies } from "next/headers";

export type AdminDashboardData = {
  date: string;
  activeStudents: number;
  outstandingAmount: string;
  pendingTransfers: number;
  recurringSchedulesToday: number;
  links: {
    students: string | null;
    disciplines: string | null;
    teachers: string | null;
    guardians: string | null;
    enrollments: string | null;
    monthlyCharges: string | null;
    chargeGeneration: string | null;
    transfers: string | null;
    canResolveTransfers: boolean;
    cashPayments: string | null;
    payments: string | null;
    credits: string | null;
  };
};

export class AdminDashboardAccessError extends Error {}

export async function getAdminDashboardData(): Promise<AdminDashboardData> {
  const cookieHeader = (await cookies()).toString();
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(`${backendUrl}/api/v1/admin-panel/dashboard`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
    redirect: "manual",
  });

  if (response.status === 401 || response.status === 403) {
    throw new AdminDashboardAccessError();
  }
  if (!response.ok) {
    throw new Error("No se pudo cargar el panel administrativo.");
  }
  return (await response.json()) as AdminDashboardData;
}
