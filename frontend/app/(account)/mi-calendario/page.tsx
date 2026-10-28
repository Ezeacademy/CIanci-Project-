import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getSessionUser } from "../../../lib/auth/session";
import {
  CalendarSessionExpiredError,
  type CalendarEnrollment,
  findNextCalendarOccurrence,
  getAccountCalendarData,
  listCalendarOccurrences,
} from "../../../lib/academic/calendar";
import { CalendarWeekView } from "./calendar-week-view";
import { formatInstantDate } from "../../../lib/format-date";

const INSTITUTE_TIME_ZONE = "America/Argentina/Buenos_Aires";

export const metadata: Metadata = {
  title: "Mi calendario | Cianci",
  robots: { index: false, follow: false },
};

export default async function CalendarPage() {
  if (!(await getSessionUser())) redirect("/ingresar");

  let enrollments: CalendarEnrollment[];
  try {
    enrollments = await getAccountCalendarData();
  } catch (error) {
    if (error instanceof CalendarSessionExpiredError) redirect("/ingresar");
    return (
      <main id="contenido" className="shell calendar-page">
        <div className="calendar-page-heading">
          <p className="eyebrow auth-eyebrow">Tu actividad en el instituto</p>
          <h1>Mi calendario</h1>
        </div>
        <p className="academic-error" role="alert">
          No pudimos cargar tus horarios. Intentá de nuevo más tarde.
        </p>
      </main>
    );
  }

  const occurrences = listCalendarOccurrences(enrollments);
  const nextOccurrence = findNextCalendarOccurrence(occurrences);

  return (
    <main id="contenido" className="shell calendar-page">
      <div className="calendar-page-heading">
        <p className="eyebrow auth-eyebrow">Tu actividad en el instituto</p>
        <h1>Mi calendario</h1>
        <p>
          Estos son los horarios semanales de tus disciplinas. Son horarios
          habituales y no confirman que una clase específica vaya a dictarse.
        </p>
      </div>

      {nextOccurrence ? (
        <section
          className="calendar-next"
          aria-labelledby="calendar-next-title"
        >
          <p className="eyebrow auth-eyebrow">Próxima clase habitual</p>
          <h2 id="calendar-next-title">{nextOccurrence.discipline.name}</h2>
          <p className="calendar-next-date">
            {formatInstantDate(nextOccurrence.nextClass, { weekday: "long" })} ·{" "}
            {nextOccurrence.startTime}–{nextOccurrence.endTime}
          </p>
          <p>
            Profesora: {nextOccurrence.teacher.firstName}{" "}
            {nextOccurrence.teacher.lastName}
          </p>
          {nextOccurrence.student.accessType === "guardian" ? (
            <p>
              Alumna: {nextOccurrence.student.firstName}{" "}
              {nextOccurrence.student.lastName}
            </p>
          ) : null}
        </section>
      ) : null}

      <CalendarWeekView
        occurrences={occurrences}
        today={getInstituteDateKey()}
      />

      <Link className="calendar-back-link" href="/mi-cuenta">
        Volver a Mi cuenta
      </Link>
    </main>
  );
}

function getInstituteDateKey() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: INSTITUTE_TIME_ZONE,
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.map(({ type, value }) => [type, value]),
  );
  return `${values.year}-${values.month}-${values.day}`;
}
