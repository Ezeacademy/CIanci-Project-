import { cookies } from "next/headers";

import {
  getPrivateApiPageCollection,
  getPrivateApiPages,
} from "../api/private-pages";

type ApiStudent = {
  firstName: string;
  lastName: string;
  accessType: "self" | "guardian";
};

export type BillingSummary = {
  amount: string;
  paidAmount: string;
  balance: string;
};

export type MonthlyChargeView = ApiStudent & {
  id: number;
  originalAmount: string;
  releasedAmount: string;
  status: "adjusted_to_zero" | "scholarship" | "paid" | "pending";
  adjustments: {
    id: number;
    previousAmount: string;
    resultingAmount: string;
    difference: string;
    createdAt: string;
  }[];
  discipline: string;
  period: string;
  baseAmount: string;
  scholarshipPercentage: number | null;
  discountAmount: string;
  amount: string;
  paidAmount: string;
  balance: string;
};

export type ConfirmedPaymentView = ApiStudent & {
  amount: string;
  currency: "ARS";
  method: string;
  receivedAt: string;
  allocations: { period: string; discipline: string; amount: string }[];
};

export type PaymentIntentView = ApiStudent & {
  amount: string;
  currency: "ARS";
  method: string;
  status: "pending" | "rejected";
  createdAt: string;
};

type ChargeApiRow = { student: ApiStudent } & Omit<
  MonthlyChargeView,
  keyof ApiStudent
>;
type PaymentApiRow = { student: ApiStudent } & Omit<
  ConfirmedPaymentView,
  keyof ApiStudent
>;
type IntentApiRow = { student: ApiStudent } & Omit<
  PaymentIntentView,
  keyof ApiStudent
>;

export async function getAccountBillingData() {
  const cookieHeader = (await cookies()).toString();
  const [chargePage, payments, intents] = await Promise.all([
    getPrivateApiPageCollection<ChargeApiRow>(
      "/api/v1/billing/me/charges",
      "/api/v1/billing/me/charges",
      cookieHeader,
    ),
    getPrivateApiPages<PaymentApiRow>(
      "/api/v1/payments/me/confirmed",
      "/api/v1/payments/me/confirmed",
      cookieHeader,
    ),
    getPrivateApiPages<IntentApiRow>(
      "/api/v1/payments/me/intents",
      "/api/v1/payments/me/intents",
      cookieHeader,
    ),
  ]);
  if (!chargePage.summary) {
    throw new Error("La API no devolvió el resumen de mensualidades.");
  }

  return {
    summary: chargePage.summary,
    credits: chargePage.credits ?? [],
    charges: chargePage.results.map(({ student, ...charge }) => ({
      ...student,
      ...charge,
    })),
    payments: payments.map(({ student, ...payment }) => ({
      ...student,
      ...payment,
    })),
    intents: intents.map(({ student, ...intent }) => ({
      ...student,
      ...intent,
    })),
  };
}
