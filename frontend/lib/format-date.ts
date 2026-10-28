const ARGENTINA_TIME_ZONE = "America/Argentina/Buenos_Aires";

type DescriptiveDateOptions = {
  weekday?: "long" | "short";
};

/** Formats an ISO calendar date as the numeric Argentine form used in fields. */
export function formatNumericDate(value: string | null | undefined): string {
  const dateParts = getIsoDateParts(value);
  if (!dateParts) return "";
  return `${dateParts.dayText}/${dateParts.monthText}/${dateParts.year}`;
}

/** Formats an ISO calendar date without interpreting it as a UTC instant. */
export function formatDescriptiveDate(
  value: string | null | undefined,
  options: DescriptiveDateOptions = {},
): string {
  const dateParts = getIsoDateParts(value);
  if (!dateParts) return value ? "Fecha no disponible" : "Sin registrar";

  return new Intl.DateTimeFormat("es-AR", {
    ...options,
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(
    createUtcCalendarDate(
      dateParts.year,
      dateParts.month,
      Number(dateParts.dayText),
    ),
  );
}

/** Formats the calendar date represented by a timestamp in the institute timezone. */
export function formatInstantDate(
  value: string,
  options: DescriptiveDateOptions = {},
): string {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return "Fecha no disponible";

  return new Intl.DateTimeFormat("es-AR", {
    ...options,
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: ARGENTINA_TIME_ZONE,
  }).format(instant);
}

/** Formats an instant in Argentine numeric date and 24-hour time conventions. */
export function formatInstantDateTime(value: string): string {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return "Fecha no disponible";

  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: ARGENTINA_TIME_ZONE,
  }).format(instant);
}

/** Parses a strict DD/MM/YYYY value into an ISO date, or returns null if invalid. */
export function parseArgentineDate(value: string): string | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;

  const [, dayText, monthText, yearText] = match;
  const day = Number(dayText);
  const month = Number(monthText);
  const year = Number(yearText);
  const date = createUtcCalendarDate(year, month, day);

  if (
    year < 1 ||
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }

  return `${yearText}-${monthText}-${dayText}`;
}

function getIsoDateParts(value: string | null | undefined) {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;

  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = createUtcCalendarDate(year, month, day);
  if (
    year < 1 ||
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }

  return { year, month, dayText, monthText };
}

function createUtcCalendarDate(year: number, month: number, day: number): Date {
  const date = new Date(0);
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCFullYear(year, month - 1, day);
  return date;
}
