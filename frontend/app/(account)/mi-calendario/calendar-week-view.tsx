"use client";

import { useState } from "react";

import type { CalendarOccurrence } from "../../../lib/academic/calendar";
import {
  compareCalendarOccurrences,
  formatCompactCalendarDateRange,
  getCalendarDateAtUtc,
  getCalendarWeekDays,
  getMinutesOfDay,
  getVisibleCalendarHours,
  positionCalendarOverlaps,
  shiftCalendarWeek,
  startOfCalendarWeek,
  type PositionedOccurrence,
} from "../../../lib/academic/calendar-layout";

const HOUR_HEIGHT_PX = 72;

export function CalendarWeekView({
  occurrences,
  today,
}: {
  occurrences: CalendarOccurrence[];
  today: string;
}) {
  const [weekStart, setWeekStart] = useState(() => startOfCalendarWeek(today));
  const weekDays = getCalendarWeekDays(weekStart);
  const dateRangeLabel = formatDateRange(weekDays[0].date, weekDays[6].date);
  const hours = getVisibleCalendarHours(occurrences);

  function moveWeek(weeks: number) {
    setWeekStart(shiftCalendarWeek(weekStart, weeks));
  }

  function showCurrentWeek() {
    setWeekStart(startOfCalendarWeek(today));
  }

  return (
    <section className="calendar-widget" aria-label="Calendario semanal">
      <div className="calendar-toolbar">
        <div
          className="calendar-week-navigation"
          aria-label="Cambiar de semana"
        >
          <button
            className="calendar-navigation-button"
            type="button"
            aria-label="Semana anterior"
            onClick={() => moveWeek(-1)}
          >
            ‹
          </button>
          <button
            className="calendar-navigation-button"
            type="button"
            aria-label="Semana siguiente"
            onClick={() => moveWeek(1)}
          >
            ›
          </button>
        </div>
        <h2 className="calendar-date-range" aria-live="polite">
          <span className="calendar-date-range-full">{dateRangeLabel}</span>
          <span className="calendar-date-range-compact">
            {formatCompactCalendarDateRange(weekDays[0].date, weekDays[6].date)}
          </span>
        </h2>
        <button
          className="calendar-today-button"
          type="button"
          onClick={showCurrentWeek}
        >
          Hoy
        </button>
      </div>

      {occurrences.length === 0 ? (
        <p className="calendar-empty" role="status">
          Todavía no hay horarios semanales activos para tus inscripciones.
        </p>
      ) : (
        <>
          <div
            className="calendar-desktop"
            aria-label="Vista semanal por horas"
          >
            <div className="calendar-grid-header">
              <div aria-hidden="true" />
              {weekDays.map((weekDay) => (
                <div
                  className={`calendar-date-heading${weekDay.date === today ? " is-today" : ""}`}
                  key={weekDay.date}
                >
                  <span>{formatWeekday(weekDay.date, "short")}</span>
                  <span>{formatDayNumber(weekDay.date)}</span>
                </div>
              ))}
            </div>

            <div className="calendar-grid-body">
              <div
                className="calendar-time-axis"
                style={{ height: `${hours.length * HOUR_HEIGHT_PX}px` }}
                aria-hidden="true"
              >
                {hours.map((hour, index) => (
                  <span
                    className="calendar-hour-label"
                    key={hour}
                    style={{ top: `${index * HOUR_HEIGHT_PX}px` }}
                  >
                    {formatHour(hour)}
                  </span>
                ))}
              </div>
              <div className="calendar-week-columns">
                {weekDays.map((weekDay) => (
                  <div
                    className={`calendar-day-track${weekDay.date === today ? " is-today" : ""}`}
                    key={weekDay.date}
                    style={{ height: `${hours.length * HOUR_HEIGHT_PX}px` }}
                    aria-label={formatWeekday(weekDay.date, "long")}
                  >
                    {positionCalendarOverlaps(occurrences, weekDay.weekday).map(
                      (occurrence) => (
                        <CalendarBlock
                          occurrence={occurrence}
                          rangeStartHour={hours[0]}
                          key={`${occurrence.student.id}-${occurrence.id}`}
                        />
                      ),
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="calendar-agenda" aria-label="Agenda semanal">
            {weekDays
              .map((weekDay) => ({
                weekDay,
                dayOccurrences: occurrences
                  .filter(
                    (occurrence) => occurrence.weekday === weekDay.weekday,
                  )
                  .sort(compareCalendarOccurrences),
              }))
              .filter(({ dayOccurrences }) => dayOccurrences.length > 0)
              .map(({ weekDay, dayOccurrences }) => (
                <section className="calendar-agenda-day" key={weekDay.date}>
                  <h3
                    className={weekDay.date === today ? "is-today" : undefined}
                  >
                    <span>{formatWeekday(weekDay.date, "long")}</span>
                    <span>{formatAgendaDate(weekDay.date)}</span>
                  </h3>
                  <ul>
                    {dayOccurrences.map((occurrence) => (
                      <li
                        className="calendar-agenda-class"
                        key={`${occurrence.student.id}-${occurrence.id}`}
                      >
                        <p className="calendar-agenda-time">
                          {occurrence.startTime}–{occurrence.endTime}
                        </p>
                        <div>
                          <h4>{occurrence.discipline.name}</h4>
                          <p>
                            Profesora: {occurrence.teacher.firstName}{" "}
                            {occurrence.teacher.lastName}
                          </p>
                          {occurrence.student.accessType === "guardian" ? (
                            <p>
                              Alumna: {occurrence.student.firstName}{" "}
                              {occurrence.student.lastName}
                            </p>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
          </div>
        </>
      )}
    </section>
  );
}

function CalendarBlock({
  occurrence,
  rangeStartHour,
}: {
  occurrence: PositionedOccurrence;
  rangeStartHour: number;
}) {
  const startMinutes = getMinutesOfDay(occurrence.startTime);
  const endMinutes = getMinutesOfDay(occurrence.endTime);
  const top = ((startMinutes - rangeStartHour * 60) / 60) * HOUR_HEIGHT_PX;
  const height = ((endMinutes - startMinutes) / 60) * HOUR_HEIGHT_PX;

  return (
    <article
      className="calendar-week-block"
      style={{
        top: `${top}px`,
        height: `${height}px`,
        left: `${(occurrence.columnIndex / occurrence.columnCount) * 100}%`,
        width: `${100 / occurrence.columnCount}%`,
      }}
      aria-label={`${occurrence.discipline.name}, ${occurrence.startTime} a ${occurrence.endTime}, ${occurrence.teacher.firstName} ${occurrence.teacher.lastName}${occurrence.student.accessType === "guardian" ? `, ${occurrence.student.firstName} ${occurrence.student.lastName}` : ""}`}
    >
      <h3>{occurrence.discipline.name}</h3>
      <p className="calendar-week-block-time">
        {occurrence.startTime}–{occurrence.endTime}
      </p>
      <p>
        {occurrence.teacher.firstName} {occurrence.teacher.lastName}
      </p>
      {occurrence.student.accessType === "guardian" ? (
        <p>
          {occurrence.student.firstName} {occurrence.student.lastName}
        </p>
      ) : null}
    </article>
  );
}

function formatDateRange(start: string, end: string) {
  return `${formatFullDate(start)} — ${formatFullDate(end)}`;
}

function formatFullDate(date: string) {
  return new Intl.DateTimeFormat("es-AR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(getCalendarDateAtUtc(date));
}

function formatWeekday(date: string, weekday: "short" | "long") {
  return new Intl.DateTimeFormat("es-AR", {
    weekday,
    timeZone: "UTC",
  }).format(getCalendarDateAtUtc(date));
}

function formatDayNumber(date: string) {
  return new Intl.DateTimeFormat("es-AR", {
    day: "numeric",
    timeZone: "UTC",
  }).format(getCalendarDateAtUtc(date));
}

function formatAgendaDate(date: string) {
  return new Intl.DateTimeFormat("es-AR", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(getCalendarDateAtUtc(date));
}

function formatHour(hour: number) {
  return `${String(hour).padStart(2, "0")}:00`;
}
