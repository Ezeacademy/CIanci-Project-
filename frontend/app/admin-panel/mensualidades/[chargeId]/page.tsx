import Link from "next/link";

import {
  AdminMonthlyChargeDataError,
  getAdminMonthlyCharge,
} from "../../../../lib/admin-panel/monthly-charges";
import { formatInstantDate } from "../../../../lib/format-date";
import { formatArsAmount } from "../../../../lib/format-money";
import styles from "../monthly-charges.module.css";

type MonthlyChargeDetailPageProps = {
  params: Promise<{ chargeId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AdminMonthlyChargeDetailPage({
  params,
  searchParams,
}: MonthlyChargeDetailPageProps) {
  const [{ chargeId }, query] = await Promise.all([params, searchParams]);
  const backHref = getListHref(query.back);
  let charge;
  try {
    charge = await getAdminMonthlyCharge(chargeId);
  } catch (error) {
    const isForbidden =
      error instanceof AdminMonthlyChargeDataError && error.status === 403;
    const isMissing =
      error instanceof AdminMonthlyChargeDataError && error.status === 404;
    return (
      <main id="contenido" className="shell admin-panel-page">
        <Link className={styles.backLink} href={backHref}>
          ← Volver a mensualidades
        </Link>
        <p className={styles.message} role="alert">
          {isForbidden
            ? "Tu usuario no tiene permiso para consultar esta mensualidad."
            : isMissing
              ? "No encontramos la mensualidad solicitada."
              : "No pudimos cargar el detalle. Actualizá la página e intentá nuevamente."}
        </p>
      </main>
    );
  }

  return (
    <main id="contenido" className="shell admin-panel-page">
      <Link className={styles.backLink} href={backHref}>
        ← Volver a mensualidades
      </Link>
      <header className="admin-panel-heading">
        <div>
          <p className="eyebrow auth-eyebrow">Detalle de mensualidad</p>
          <h1>{charge.discipline}</h1>
          <p>
            {formatPeriod(charge.period)} · {charge.studentName}
          </p>
        </div>
        <Link
          className="admin-student-button is-secondary"
          href={"/admin-panel/alumnos/" + charge.studentId}
        >
          Ver ficha del alumno
        </Link>
      </header>

      <section className={styles.panel} aria-labelledby="charge-summary-title">
        <div className={styles.sectionHeading}>
          <div>
            <p className="eyebrow auth-eyebrow">Resumen económico</p>
            <h2 id="charge-summary-title">Importes de la mensualidad</h2>
            <p>
              Emitida el {formatInstantDate(charge.createdAt)} · Estado:{" "}
              {statusLabel(charge.status)}
            </p>
          </div>
        </div>
        <dl className={styles.chargeFacts}>
          <div>
            <dt>Precio base</dt>
            <dd>{formatArsAmount(charge.baseAmount)}</dd>
          </div>
          <div>
            <dt>
              Descuento por beca
              {charge.scholarshipPercentage
                ? " (" + charge.scholarshipPercentage + " %)"
                : ""}
            </dt>
            <dd>{formatArsAmount(charge.discountAmount)}</dd>
          </div>
          <div>
            <dt>Importe emitido</dt>
            <dd>{formatArsAmount(charge.originalAmount)}</dd>
          </div>
          <div>
            <dt>Ajustes acumulados</dt>
            <dd>{formatSignedAmount(charge.adjustmentAmount)}</dd>
          </div>
          <div>
            <dt>Total actualizado</dt>
            <dd>{formatArsAmount(charge.currentAmount)}</dd>
          </div>
          <div>
            <dt>Abonado</dt>
            <dd>{formatArsAmount(charge.paidAmount)}</dd>
          </div>
          <div className={styles.balanceFact}>
            <dt>Saldo pendiente</dt>
            <dd>{formatArsAmount(charge.outstanding)}</dd>
          </div>
        </dl>
      </section>

      <section className={styles.panel} aria-labelledby="charge-payments-title">
        <div className={styles.sectionHeading}>
          <div>
            <p className="eyebrow auth-eyebrow">Trazabilidad de cobros</p>
            <h2 id="charge-payments-title">Pagos aplicados</h2>
          </div>
        </div>
        {charge.payments.length ? (
          <ul className={styles.historyList}>
            {charge.payments.map((payment) => (
              <li key={payment.id}>
                <div>
                  <strong>{payment.method}</strong>
                  <span>{formatInstantDate(payment.receivedAt)}</span>
                  <span>Registrado por {payment.responsible}</span>
                </div>
                <dl>
                  <div>
                    <dt>Asignado</dt>
                    <dd>{formatArsAmount(payment.allocatedAmount)}</dd>
                  </div>
                  {Number(payment.releasedAmount) > 0 ? (
                    <div>
                      <dt>Liberado como saldo a favor</dt>
                      <dd>{formatArsAmount(payment.releasedAmount)}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt>Aplicado a esta mensualidad</dt>
                    <dd>{formatArsAmount(payment.appliedAmount)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.emptyMessage}>Todavía no hay pagos aplicados.</p>
        )}
      </section>

      <section
        className={styles.panel}
        aria-labelledby="charge-adjustments-title"
      >
        <div className={styles.sectionHeading}>
          <div>
            <p className="eyebrow auth-eyebrow">Historial económico</p>
            <h2 id="charge-adjustments-title">Ajustes registrados</h2>
          </div>
        </div>
        {charge.adjustments.length ? (
          <ul className={styles.historyList}>
            {charge.adjustments.map((adjustment) => (
              <li key={adjustment.id}>
                <div>
                  <strong>
                    {adjustment.isReversal
                      ? "Ajuste compensatorio"
                      : "Ajuste de mensualidad"}
                  </strong>
                  <span>{formatInstantDate(adjustment.createdAt)}</span>
                  <span>Registrado por {adjustment.responsible}</span>
                  <p>{adjustment.reason}</p>
                </div>
                <dl>
                  <div>
                    <dt>Antes</dt>
                    <dd>{formatArsAmount(adjustment.previousAmount)}</dd>
                  </div>
                  <div>
                    <dt>Variación</dt>
                    <dd>{formatSignedAmount(adjustment.difference)}</dd>
                  </div>
                  <div>
                    <dt>Después</dt>
                    <dd>{formatArsAmount(adjustment.resultingAmount)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.emptyMessage}>
            Esta mensualidad no tiene ajustes registrados.
          </p>
        )}
      </section>
    </main>
  );
}

function getListHref(rawBackQuery: string | string[] | undefined) {
  const backQuery = new URLSearchParams();
  const source =
    typeof rawBackQuery === "string" ? new URLSearchParams(rawBackQuery) : null;
  for (const key of ["q", "period", "discipline", "status", "page"]) {
    const value = source?.get(key);
    if (value) backQuery.set(key, value);
  }
  const queryString = backQuery.toString();
  return "/admin-panel/mensualidades" + (queryString ? "?" + queryString : "");
}

function formatPeriod(value: string) {
  const [year, month] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("es-AR", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
}

function formatSignedAmount(value: string) {
  const amount = Number(value);
  const formattedAmount = formatArsAmount(value);
  return amount > 0 ? "+" + formattedAmount : formattedAmount;
}

function statusLabel(status: string) {
  if (status === "paid") return "Pagada";
  if (status === "scholarship") return "Cubierta por beca";
  if (status === "adjusted_to_zero") return "Anulada";
  return "Pendiente";
}
