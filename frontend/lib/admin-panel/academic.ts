import { cookies } from "next/headers";
import { formatDescriptiveDate } from "../format-date";

export type StudentListItem = {
  id: number;
  firstName: string;
  lastName: string;
  activeEnrollmentCount: number;
  disciplines: string[];
};

export type StudentDisciplineOption = { id: number; name: string };

export type StudentListData = {
  count: number;
  next: string | null;
  previous: string | null;
  results: StudentListItem[];
  filters: {
    disciplines: StudentDisciplineOption[];
    canAddStudent: boolean;
  };
};

export type StudentDetailData = {
  id: number;
  today: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string | null;
  activeEnrollmentCount: number;
  enrollments: {
    id: number;
    discipline: string;
    disciplineIsActive: boolean;
    enrolledAt: string;
    endedAt: string | null;
    isActive: boolean;
  }[];
  guardians: { name: string; isActive: boolean }[];
  accountAccess: {
    status: "none" | "pending" | "expired" | "linked";
    email: string | null;
    expiresAt: string | null;
    invitationId: number | null;
  } | null;
  canInviteStudentAccount: boolean;
  canRevokeStudentAccount: boolean;
  canChangeStudent: boolean;
  canAddEnrollment: boolean;
  canFinishEnrollment: boolean;
  availableDisciplines: StudentDisciplineOption[];
};

export class AdminAcademicDataError extends Error {
  constructor(public readonly status: number) {
    super("No se pudo cargar la información académica.");
  }
}

export async function getAdminStudentList(
  query: URLSearchParams,
): Promise<StudentListData> {
  return getAdminData<StudentListData>(
    `/api/v1/admin/academic/students?${query.toString()}`,
  );
}

export async function getAdminStudent(
  studentId: string,
): Promise<StudentDetailData> {
  return getAdminData<StudentDetailData>(
    `/api/v1/admin/academic/students/${studentId}`,
  );
}

async function getAdminData<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  const backendUrl = (
    process.env.BACKEND_INTERNAL_URL || "http://backend:8000"
  ).replace(/\/$/, "");
  const response = await fetch(`${backendUrl}${path}`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
    redirect: "manual",
  });
  if (!response.ok) throw new AdminAcademicDataError(response.status);
  return (await response.json()) as T;
}

export function formatAcademicDate(value: string | null): string {
  return formatDescriptiveDate(value);
}
