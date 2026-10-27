import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getSessionUser } from "../../../lib/auth/session";
import {
  CalendarSessionExpiredError,
  findNextCalendarOccurrence,
  getAccountCalendarData,
  listCalendarOccurrences,
} from "../../../lib/academic/calendar";

export const metadata: Metadata = {
  title: "Mi calendario | Cianci",
  robots: { index: false, follow: false },
};

const WEEKDAYS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

export default async function CalendarPage() {
  if (!(await getSessionUser())) redirect("/ingresar");

  let enrollments;
  try {
    enrollments = await getAccountCalendarData();
  } catch (error) {
    if (error instanceof CalendarSessionExpiredError) redirect("/ingresar");
    return (
      <main id="contenido" className="shell calendar-page">
        <p className="eyebrow auth-eyebrow">Tu actividad en el instituto</p>
        <h1>Mi calendario</h1>
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
          <p>
            {formatOccurrence(nextOccurrence.nextClass)} ·{" "}
            {nextOccurrence.teacher.firstName} {nextOccurrence.teacher.lastName}
            {nextOccurrence.student.accessType === "guardian"
              ? ` · ${nextOccurrence.student.firstName} ${nextOccurrence.student.lastName}`
              : ""}
          </p>
        </section>
      ) : null}

      {occurrences.length === 0 ? (
        <p className="academic-empty" role="status">
          Todavía no hay horarios semanales activos para tus inscripciones.
        </p>
      ) : (
        <div className="calendar-week" aria-label="Horarios semanales">
          {WEEKDAYS.map((weekday, weekdayIndex) => {
            const dayOccurrences = occurrences.filter(
              (occurrence) => occurrence.weekday === weekdayIndex,
            );
            return (
              <section className="calendar-day" key={weekday}>
                <h2>{weekday}</h2>
                {dayOccurrences.length === 0 ? (
                  <p className="calendar-day-empty">Sin clases habituales</p>
                ) : (
                  <ul>
                    {dayOccurrences.map((occurrence) => (
                      <li
                        className="calendar-class"
                        key={`${occurrence.student.id}-${occurrence.id}`}
                      >
                        <p className="calendar-class-time">
                          {occurrence.startTime}–{occurrence.endTime}
                        </p>
                        <h3>{occurrence.discipline.name}</h3>
                        <p>
                          {occurrence.teacher.firstName}{" "}
                          {occurrence.teacher.lastName}
                        </p>
                        {occurrence.student.accessType === "guardian" ? (
                          <p>
                            {occurrence.student.firstName}{" "}
                            {occurrence.student.lastName}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}

      <Link className="calendar-back-link" href="/mi-cuenta">
        Volver a Mi cuenta
      </Link>
    </main>
  );
}

function formatOccurrence(value: string) {
  return new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(value));
}
