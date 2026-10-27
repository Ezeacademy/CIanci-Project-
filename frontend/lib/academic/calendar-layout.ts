import type { CalendarOccurrence } from "./calendar";

export type PositionedOccurrence = CalendarOccurrence & {
  columnIndex: number;
  columnCount: number;
};

export type CalendarWeekDay = {
  date: string;
  weekday: number;
};

const MINIMUM_VISIBLE_HOURS = 6;

export function startOfCalendarWeek(date: string) {
  const weekday = (getCalendarDateAtUtc(date).getUTCDay() + 6) % 7;
  return addDays(date, -weekday);
}

export function shiftCalendarWeek(weekStart: string, weeks: number) {
  return addDays(weekStart, weeks * 7);
}

export function getCalendarWeekDays(weekStart: string): CalendarWeekDay[] {
  return Array.from({ length: 7 }, (_, index) => {
    const date = addDays(weekStart, index);
    return {
      date,
      weekday: (getCalendarDateAtUtc(date).getUTCDay() + 6) % 7,
    };
  });
}

export function formatCompactCalendarDateRange(start: string, end: string) {
  const startDate = getCalendarDateAtUtc(start);
  const endDate = getCalendarDateAtUtc(end);
  const startLabel = formatCompactDayMonth(startDate);
  const endLabel = formatCompactDayMonth(endDate);
  const startYear = startDate.getUTCFullYear();
  const endYear = endDate.getUTCFullYear();

  if (startYear !== endYear) {
    return `${startLabel} ${startYear} — ${endLabel} ${endYear}`;
  }
  return `${startLabel} — ${endLabel} ${endYear}`;
}

export function getVisibleCalendarHours(occurrences: CalendarOccurrence[]) {
  if (occurrences.length === 0) return [];

  const starts = occurrences.map((occurrence) =>
    getMinutesOfDay(occurrence.startTime),
  );
  const ends = occurrences.map((occurrence) =>
    getMinutesOfDay(occurrence.endTime),
  );
  let startHour = Math.max(0, Math.floor(Math.min(...starts) / 60) - 1);
  let endHour = Math.min(24, Math.ceil(Math.max(...ends) / 60) + 1);

  if (endHour - startHour < MINIMUM_VISIBLE_HOURS) {
    const additionalHours = MINIMUM_VISIBLE_HOURS - (endHour - startHour);
    const extendBefore = Math.min(startHour, Math.ceil(additionalHours / 2));
    startHour -= extendBefore;
    endHour = Math.min(24, endHour + additionalHours - extendBefore);
    startHour = Math.max(0, endHour - MINIMUM_VISIBLE_HOURS);
  }

  return Array.from(
    { length: endHour - startHour },
    (_, index) => startHour + index,
  );
}

export function positionCalendarOverlaps(
  occurrences: CalendarOccurrence[],
  weekday: number,
): PositionedOccurrence[] {
  const dayOccurrences = occurrences
    .filter((occurrence) => occurrence.weekday === weekday)
    .sort(compareCalendarOccurrences);
  const positioned: PositionedOccurrence[] = [];
  let overlapGroup: CalendarOccurrence[] = [];
  let overlapGroupEnd = -1;

  function positionGroup() {
    if (overlapGroup.length === 0) return;

    const laneEndTimes: number[] = [];
    const laneAssignments = new Map<string, number>();
    for (const occurrence of overlapGroup) {
      const start = getMinutesOfDay(occurrence.startTime);
      let laneIndex = laneEndTimes.findIndex((end) => end <= start);
      if (laneIndex === -1) laneIndex = laneEndTimes.length;
      laneEndTimes[laneIndex] = getMinutesOfDay(occurrence.endTime);
      laneAssignments.set(getOccurrenceKey(occurrence), laneIndex);
    }

    for (const occurrence of overlapGroup) {
      positioned.push({
        ...occurrence,
        columnIndex: laneAssignments.get(getOccurrenceKey(occurrence)) ?? 0,
        columnCount: laneEndTimes.length,
      });
    }
    overlapGroup = [];
    overlapGroupEnd = -1;
  }

  for (const occurrence of dayOccurrences) {
    const start = getMinutesOfDay(occurrence.startTime);
    const end = getMinutesOfDay(occurrence.endTime);
    if (overlapGroup.length > 0 && start >= overlapGroupEnd) positionGroup();
    overlapGroup.push(occurrence);
    overlapGroupEnd = Math.max(overlapGroupEnd, end);
  }
  positionGroup();

  return positioned.sort(compareCalendarOccurrences);
}

export function compareCalendarOccurrences(
  first: CalendarOccurrence,
  second: CalendarOccurrence,
) {
  return (
    first.startTime.localeCompare(second.startTime) ||
    first.endTime.localeCompare(second.endTime) ||
    first.discipline.name.localeCompare(second.discipline.name) ||
    first.student.id - second.student.id
  );
}

function getOccurrenceKey(occurrence: CalendarOccurrence) {
  return `${occurrence.student.id}:${occurrence.id}`;
}

export function getMinutesOfDay(time: string) {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

function addDays(date: string, days: number) {
  const value = getCalendarDateAtUtc(date);
  value.setUTCDate(value.getUTCDate() + days);
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}-${String(value.getUTCDate()).padStart(2, "0")}`;
}

export function getCalendarDateAtUtc(date: string) {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function formatCompactDayMonth(date: Date) {
  const parts = new Intl.DateTimeFormat("es-AR", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).formatToParts(date);
  const day = parts.find((part) => part.type === "day")?.value;
  const month = parts
    .find((part) => part.type === "month")
    ?.value.replaceAll(".", "");
  return `${day} ${month}`;
}
