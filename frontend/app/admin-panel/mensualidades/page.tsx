import Link from "next/link";

import {
  AdminMonthlyChargeDataError,
  getAdminMonthlyCharges,
} from "../../../lib/admin-panel/monthly-charges";
import { formatArsAmount } from "../../../lib/format-money";
import styles from "./monthly-charges.module.css";

type MonthlyChargesPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AdminMonthlyChargesPage({
  searchParams,
}: MonthlyChargesPageProps) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["q", "period", "discipline", "status", "page"]) {
    const value = params[key];
    if (typeof value === "string" && value) query.set(key, value);
  }

  let data;
  try {
    data = await getAdminMonthlyCharges(query);
  } catch (error) {
    const isForbidden =
      error instanceof AdminMonthlyChargeDataError && error.status === 403;
    return (
      <main id="contenido" className="shell admin-panel-page">
        <PageHeading />
        <p className={styles.message} role="alert">
          {isForbidden
            ? "Tu usuario no tiene permiso para consultar las mensualidades."
            : "No pudimos cargar las mensualidades. Actualizá la página e intentá nuevamente."}
        </p>
      </main>
    );
  }

  const currentPage = Math.max(1, Number(params.page) || 1);
  const pageCount = Math.max(1, Math.ceil(data.count / data.pageSize));
  const hasActiveFilters = Boolean(
    (typeof params.q === "string" && params.q) ||
    (typeof params.period === "string" && params.period) ||
    (typeof params.discipline === "string" && params.discipline) ||
    (typeof params.status === "string" && params.status !== "all"),
  );
  const previousQuery = new URLSearchParams(query);
  previousQuery.delete("page");
  const previousHref = pageHref(previousQuery, currentPage - 1);
  const nextHref = pageHref(previousQuery, currentPage + 1);

  return (
    <main id="contenido" className="shell admin-panel-page">
      <PageHeading />

      <section className={styles.panel} aria-labelledby="monthly-charges-title">
        <div className={styles.sectionHeading}>
          <div>
            <p className="eyebrow auth-eyebrow">Consulta financiera</p>
            <h2 id="monthly-charges-title">Mensualidades</h2>
            <p>
              {data.count} {data.count === 1 ? "mensualidad" : "mensualidades"}{" "}
              en los resultados
            </p>
          </div>
        </div>

        <dl className={styles.totals}>
          <div>
            <dt>Pendiente en estos resultados</dt>
            <dd>{formatArsAmount(data.summary.outstanding)}</dd>
          </div>
          <div>
            <dt>Abonado en estos resultados</dt>
            <dd>{formatArsAmount(data.summary.paidAmount)}</dd>
          </div>
        </dl>

        <form className={styles.filters} method="get">
          <label className={styles.searchField}>
            <span>Buscar alumno</span>
            <input
              type="search"
              name="q"
              placeholder="Nombre o apellido"
              defaultValue={typeof params.q === "string" ? params.q : ""}
            />
          </label>
          <label>
            <span>Período</span>
            <select
              name="period"
              defaultValue={
                typeof params.period === "string" ? params.period : ""
              }
            >
              <option value="">Todos</option>
              {data.filters.periods.map((period) => (
                <option key={period} value={period}>
                  {formatPeriod(period)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Disciplina</span>
            <select
              name="discipline"
              defaultValue={
                typeof params.discipline === "string" ? params.discipline : ""
              }
            >
              <option value="">Todas</option>
              {data.filters.disciplines.map((discipline) => (
                <option key={discipline.id} value={discipline.id}>
                  {discipline.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Estado</span>
            <select
              name="status"
              defaultValue={
                typeof params.status === "string" ? params.status : "all"
              }
            >
              {data.filters.statuses.map((status) => (
                <option key={status.value} value={status.value}>
                  {status.label}
                </option>
              ))}
            </select>
          </label>
          <button className="admin-student-button is-primary">
            Aplicar filtros
          </button>
          <Link className={styles.resetLink} href="/admin-panel/mensualidades">
            Limpiar
          </Link>
        </form>

        {data.results.length ? (
          <>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">Alumno</th>
                    <th scope="col">Período y disciplina</th>
                    <th scope="col">Importe original</th>
                    <th scope="col">Descuentos y ajustes</th>
                    <th scope="col">Abonado / pendiente</th>
                    <th scope="col">Estado</th>
                    <th scope="col">
                      <span className={styles.visuallyHidden}>Detalle</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((charge) => {
                    const detailQuery = query.toString();
                    const detailHref =
                      "/admin-panel/mensualidades/" +
                      charge.id +
                      (detailQuery
                        ? "?back=" + encodeURIComponent(detailQuery)
                        : "");
                    return (
                      <tr key={charge.id}>
                        <td data-label="Alumno">
                          <Link
                            href={"/admin-panel/alumnos/" + charge.studentId}
                          >
                            {charge.studentName}
                          </Link>
                        </td>
                        <td data-label="Período y disciplina">
                          <strong>{formatPeriod(charge.period)}</strong>
                          <span>{charge.discipline}</span>
                        </td>
                        <td data-label="Importe original">
                          <span>
                            Base: {formatArsAmount(charge.baseAmount)}
                          </span>
                          <strong>
                            Emitido: {formatArsAmount(charge.originalAmount)}
                          </strong>
                        </td>
                        <td data-label="Descuentos y ajustes">
                          <span>
                            Beca: {formatArsAmount(charge.discountAmount)}
                          </span>
                          <span>
                            Ajustes:{" "}
                            {formatSignedAmount(charge.adjustmentAmount)}
                          </span>
                        </td>
                        <td data-label="Abonado / pendiente">
                          <span>
                            Abonado: {formatArsAmount(charge.paidAmount)}
                          </span>
                          <strong>
                            Pendiente: {formatArsAmount(charge.outstanding)}
                          </strong>
                        </td>
                        <td data-label="Estado">
                          <span className={styles.status}>
                            {statusLabel(charge.status)}
                          </span>
                        </td>
                        <td data-label="Detalle">
                          <Link className={styles.detailLink} href={detailHref}>
                            Ver detalle <span aria-hidden="true">→</span>
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <nav
              className={styles.pagination}
              aria-label="Páginas de mensualidades"
            >
              {data.previous ? (
                <Link href={previousHref}>← Anterior</Link>
              ) : (
                <span aria-hidden="true" />
              )}
              <span>
                Página {currentPage} de {pageCount}
              </span>
              {data.next ? (
                <Link href={nextHref}>Siguiente →</Link>
              ) : (
                <span aria-hidden="true" />
              )}
            </nav>
          </>
        ) : (
          <div className={styles.emptyState} role="status">
            <h3>
              {hasActiveFilters
                ? "No hay resultados con estos filtros"
                : "Todavía no hay mensualidades"}
            </h3>
            <p>
              {hasActiveFilters
                ? "Probá cambiar o limpiar los filtros para ver otras mensualidades."
                : "Cuando se emitan mensualidades, vas a poder consultarlas acá."}
            </p>
            {hasActiveFilters ? (
              <Link href="/admin-panel/mensualidades">Limpiar filtros</Link>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}

function PageHeading() {
  return (
    <header className="admin-panel-heading">
      <div>
        <p className="eyebrow auth-eyebrow">Gestión financiera</p>
        <h1>Mensualidades</h1>
        <p>Consultá importes emitidos, pagos y saldos pendientes.</p>
      </div>
      <Link className={styles.backLink} href="/admin-panel">
        ← Volver al panel
      </Link>
    </header>
  );
}

function pageHref(query: URLSearchParams, page: number) {
  const pageQuery = new URLSearchParams(query);
  pageQuery.set("page", String(page));
  return "/admin-panel/mensualidades?" + pageQuery.toString();
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
