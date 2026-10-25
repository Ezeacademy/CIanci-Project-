import { cookies } from "next/headers";

export type AccessibleStudent = {
  id: number;
  firstName: string;
  lastName: string;
  accessType: "self" | "guardian";
};

type AcademicEnrollment = {
  id: number;
  discipline: { id: number; name: string };
  enrolledAt: string;
  endedAt: string | null;
  status: "active" | "history";
};

export type StudentWithEnrollments = AccessibleStudent & {
  enrollments: AcademicEnrollment[];
};

type ApiPage<T> = {
  next: string | null;
  results: T[];
};

export class AcademicSessionExpiredError extends Error {}

function getBackendUrl() {
  return (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(
    /\/$/,
    "",
  );
}

async function getAllPages<T>(
  path: string,
  expectedPath: string,
  cookieHeader: string,
): Promise<T[]> {
  const backendUrl = getBackendUrl();
  const backendOrigin = new URL(backendUrl).origin;
  const visited = new Set<string>();
  const results: T[] = [];
  let url: URL | null = new URL(path, backendUrl);

  while (url) {
    if (
      url.origin !== backendOrigin ||
      url.pathname !== expectedPath ||
      url.username ||
      url.password ||
      visited.has(url.href)
    ) {
      throw new Error("Respuesta de paginación inválida.");
    }
    visited.add(url.href);

    const response = await fetch(url, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
      redirect: "manual",
    });
    if (response.status === 401 || response.status === 403) {
      throw new AcademicSessionExpiredError();
    }
    if (!response.ok)
      throw new Error("No se pudo cargar la información académica.");

    const page = (await response.json()) as ApiPage<T>;
    if (!Array.isArray(page.results)) {
      throw new Error("Respuesta académica inválida.");
    }
    results.push(...page.results);
    url = page.next ? new URL(page.next, backendUrl) : null;
  }

  return results;
}

export async function getAccountAcademicData(): Promise<
  StudentWithEnrollments[]
> {
  const cookieHeader = (await cookies()).toString();
  const studentsPath = "/api/v1/academic/me/students";
  const students = await getAllPages<AccessibleStudent>(
    studentsPath,
    studentsPath,
    cookieHeader,
  );
  const studentsWithEnrollments: StudentWithEnrollments[] = [];

  for (let start = 0; start < students.length; start += 5) {
    const batch = students.slice(start, start + 5);
    const loadedBatch = await Promise.all(
      batch.map(async (student) => {
        const path = `/api/v1/academic/students/${student.id}/enrollments`;
        const enrollments = await getAllPages<AcademicEnrollment>(
          path,
          path,
          cookieHeader,
        );
        return { ...student, enrollments };
      }),
    );
    studentsWithEnrollments.push(...loadedBatch);
  }

  return studentsWithEnrollments;
}
