import { cookies } from "next/headers";

import {
  getPrivateApiPages,
  PrivateApiSessionExpiredError,
} from "../api/private-pages";

export type CalendarSchedule = {
  id: number;
  weekday: number;
  weekdayName: string;
  startTime: string;
  endTime: string;
  nextClass: string;
  teacher: { firstName: string; lastName: string };
};

export type CalendarEnrollment = {
  id: number;
  student: {
    id: number;
    firstName: string;
    lastName: string;
    accessType: "self" | "guardian";
  };
  discipline: { id: number; name: string };
  schedules: CalendarSchedule[];
};

export type CalendarOccurrence = CalendarSchedule & {
  student: CalendarEnrollment["student"];
  discipline: CalendarEnrollment["discipline"];
};

export { PrivateApiSessionExpiredError as CalendarSessionExpiredError };

export async function getAccountCalendarData(): Promise<CalendarEnrollment[]> {
  const cookieHeader = (await cookies()).toString();
  const path = "/api/v1/academic/me/calendar";
  return getPrivateApiPages<CalendarEnrollment>(path, path, cookieHeader);
}

export function listCalendarOccurrences(
  enrollments: CalendarEnrollment[],
): CalendarOccurrence[] {
  return enrollments
    .flatMap((enrollment) =>
      enrollment.schedules.map((schedule) => ({
        ...schedule,
        student: enrollment.student,
        discipline: enrollment.discipline,
      })),
    )
    .sort(
      (first, second) =>
        first.weekday - second.weekday ||
        first.startTime.localeCompare(second.startTime),
    );
}

export function findNextCalendarOccurrence(
  occurrences: CalendarOccurrence[],
): CalendarOccurrence | null {
  return (
    [...occurrences].sort(
      (first, second) =>
        Date.parse(first.nextClass) - Date.parse(second.nextClass),
    )[0] ?? null
  );
}
