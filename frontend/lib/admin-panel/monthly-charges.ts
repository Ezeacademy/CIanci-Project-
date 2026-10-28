import { cookies } from "next/headers";

export type MonthlyChargeStatus =
  "pending" | "paid" | "scholarship" | "adjusted_to_zero";

export type AdminMonthlyChargeSummary = {
  id: number;
  studentId: number;
  studentName: string;
  discipline: string;
  period: string;
  baseAmount: string;
  discountAmount: string;
  originalAmount: string;
  adjustmentAmount: string;
  currentAmount: string;
  paidAmount: string;
  outstanding: string;
  status: MonthlyChargeStatus;
};

export type AdminMonthlyChargeDetail = AdminMonthlyChargeSummary & {
  createdAt: string;
  scholarshipPercentage: number | null;
  adjustments: {
    id: number;
    previousAmount: string;
    resultingAmount: string;
    difference: string;
    reason: string;
    createdAt: string;
    responsible: string;
    isReversal: boolean;
  }[];
  payments: {
    id: number;
    receivedAt: string;
    method: string;
    allocatedAmount: string;
    releasedAmount: string;
    appliedAmount: string;
    responsible: string;
  }[];
};

export type AdminMonthlyChargeFilters = {
  periods: string[];
  disciplines: { id: number; name: string }[];
  statuses: { value: string; label: string }[];
};

export type AdminMonthlyChargeList = {
  count: number;
  next: string | null;
  previous: string | null;
  pageSize: number;
  results: AdminMonthlyChargeSummary[];
  summary: {
    currentAmount: string;
    paidAmount: string;
    outstanding: string;
  };
  filters: AdminMonthlyChargeFilters;
};

export class AdminMonthlyChargeDataError extends Error {
  constructor(public readonly status: number) {
    super("No se pudieron cargar las mensualidades.");
  }
}

export async function getAdminMonthlyCharges(
  query: URLSearchParams,
): Promise<AdminMonthlyChargeList> {
  return getAdminBillingData<AdminMonthlyChargeList>(
    `/api/v1/admin/billing/monthly-charges?${query.toString()}`,
  );
}

export async function getAdminMonthlyCharge(
  chargeId: string,
): Promise<AdminMonthlyChargeDetail> {
  return getAdminBillingData<AdminMonthlyChargeDetail>(
    `/api/v1/admin/billing/monthly-charges/${chargeId}`,
  );
}

async function getAdminBillingData<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(`${backendUrl}${path}`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
    redirect: "manual",
  });
  if (!response.ok) throw new AdminMonthlyChargeDataError(response.status);
  return (await response.json()) as T;
}
