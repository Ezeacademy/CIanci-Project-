import Link from "next/link";

import {
  AdminAcademicDataError,
  getAdminStudentList,
} from "../../../lib/admin-panel/academic";

type StudentsPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AdminStudentsPage({
  searchParams,
}: StudentsPageProps) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["q", "status", "discipline", "page"]) {
    const value = params[key];
    if (typeof value === "string" && value) query.set(key, value);
  }
  if (!query.has("status")) query.set("status", "all");

  let data;
  try {
    data = await getAdminStudentList(query);
  } catch (error) {
    return (
      <main id="contenido" className="shell admin-panel-page">
        <AdminStudentsHeader />
        <p className="admin-student-message is-error" role="alert">
          {error instanceof AdminAcademicDataError && error.status === 403
            ? "Tu usuario no tiene permiso para consultar el listado de alumnos."
            : "No pudimos cargar el listado. Actualizá la página e intentá nuevamente."}
        </p>
      </main>
    );
  }

  const currentPage = Math.max(1, Number(params.page) || 1);
  const pageCount = Math.max(1, Math.ceil(data.count / 20));
  const baseParams = new URLSearchParams(query);
  baseParams.delete("page");

  return (
    <main id="contenido" className="shell admin-panel-page">
      <AdminStudentsHeader />
      <section className="admin-student-list" aria-labelledby="students-title">
        <div className="admin-student-section-heading">
          <div>
            <p className="eyebrow auth-eyebrow">Gestión académica</p>
            <h2 id="students-title">Alumnos</h2>
            <p>
              {data.count} {data.count === 1 ? "alumno" : "alumnos"} en el
              listado
            </p>
          </div>
          {data.filters.canAddStudent ? (
            <Link
              className="admin-student-button is-primary"
              href="/admin-panel/alumnos/nuevo"
            >
              Registrar alumno
            </Link>
          ) : null}
        </div>

        <form className="admin-student-filters" method="get">
          <label className="admin-student-search">
            <span>Buscar por nombre o apellido</span>
            <input
              type="search"
              name="q"
              defaultValue={typeof params.q === "string" ? params.q : ""}
              placeholder="Ej.: Candela Manzo"
            />
          </label>
          <label>
            <span>Inscripciones</span>
            <select
              name="status"
              defaultValue={
                typeof params.status === "string" ? params.status : "all"
              }
            >
              <option value="all">Todas</option>
              <option value="active">Con inscripciones activas</option>
              <option value="inactive">Sin inscripciones activas</option>
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
          <button className="admin-student-button is-secondary">Buscar</button>
        </form>

        {data.results.length ? (
          <>
            <ul className="admin-student-results">
              {data.results.map((student) => (
                <li key={student.id}>
                  <Link href={`/admin-panel/alumnos/${student.id}`}>
                    <span className="admin-student-result-name">
                      {student.firstName} {student.lastName}
                    </span>
                    <span className="admin-student-result-meta">
                      {student.activeEnrollmentCount
                        ? `${student.activeEnrollmentCount} ${student.activeEnrollmentCount === 1 ? "inscripción activa" : "inscripciones activas"}`
                        : "Sin inscripciones activas"}
                    </span>
                    <span className="admin-student-result-disciplines">
                      {student.disciplines.length
                        ? student.disciplines.join(" · ")
                        : "Sin disciplinas actuales"}
                    </span>
                    <span className="admin-student-result-open">
                      Ver ficha →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <nav
              className="admin-student-pagination"
              aria-label="Paginación de alumnos"
            >
              <span>
                Página {Math.min(currentPage, pageCount)} de {pageCount}
              </span>
              <div>
                {currentPage > 1 ? (
                  <Link href={pageHref(baseParams, currentPage - 1)}>
                    Anterior
                  </Link>
                ) : null}
                {currentPage < pageCount ? (
                  <Link href={pageHref(baseParams, currentPage + 1)}>
                    Siguiente
                  </Link>
                ) : null}
              </div>
            </nav>
          </>
        ) : (
          <div className="admin-student-empty-state">
            <h3>
              {query.has("q") || params.discipline
                ? "No encontramos alumnos"
                : "Todavía no hay alumnos registrados"}
            </h3>
            <p>
              {query.has("q") || params.discipline
                ? "Probá con otro nombre o cambiá los filtros."
                : "Cuando registres un alumno, vas a poder consultar acá su ficha e inscripciones."}
            </p>
            {data.filters.canAddStudent &&
            !query.has("q") &&
            !params.discipline ? (
              <Link
                className="admin-student-button is-primary"
                href="/admin-panel/alumnos/nuevo"
              >
                Registrar primer alumno
              </Link>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}

function AdminStudentsHeader() {
  return (
    <header className="admin-panel-heading">
      <div>
        <p className="eyebrow auth-eyebrow">Gestión del instituto</p>
        <h1>Alumnos</h1>
        <p>Consultá sus datos e inscripciones en un solo lugar.</p>
      </div>
      <Link className="calendar-back-link" href="/admin-panel">
        ← Volver al panel
      </Link>
    </header>
  );
}

function pageHref(params: URLSearchParams, page: number) {
  const nextParams = new URLSearchParams(params);
  nextParams.set("page", String(page));
  return `/admin-panel/alumnos?${nextParams.toString()}`;
}
