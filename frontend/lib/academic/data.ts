import { cookies } from "next/headers";

import {
  getPrivateApiPages,
  PrivateApiSessionExpiredError,
} from "../api/private-pages";

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

export { PrivateApiSessionExpiredError as AcademicSessionExpiredError };

export async function getAccountAcademicData(): Promise<
  StudentWithEnrollments[]
> {
  const cookieHeader = (await cookies()).toString();
  const studentsPath = "/api/v1/academic/me/students";
  const students = await getPrivateApiPages<AccessibleStudent>(
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
        const enrollments = await getPrivateApiPages<AcademicEnrollment>(
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
