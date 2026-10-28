import Link from "next/link";

import { EnrollmentActions } from "../../../../features/admin-panel/enrollment-actions";
import { StudentAccountAccess } from "../../../../features/admin-panel/student-account-access";
import {
  AdminAcademicDataError,
  formatAcademicDate,
  getAdminStudent,
} from "../../../../lib/admin-panel/academic";

type StudentPageProps = {
  params: Promise<{ studentId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AdminStudentPage({
  params,
  searchParams,
}: StudentPageProps) {
  const [{ studentId }, query] = await Promise.all([params, searchParams]);
  let student;
  try {
    student = await getAdminStudent(studentId);
  } catch (error) {
    const isMissing =
      error instanceof AdminAcademicDataError && error.status === 404;
    const hasAccess =
      error instanceof AdminAcademicDataError && error.status === 403;
    return (
      <main id="contenido" className="shell admin-panel-page">
        <Link className="calendar-back-link" href="/admin-panel/alumnos">
          ← Volver a alumnos
        </Link>
        <p className="admin-student-message is-error" role="alert">
          {isMissing
            ? "No encontramos la ficha solicitada."
            : hasAccess
              ? "Tu usuario no tiene permiso para consultar esta ficha."
              : "No pudimos cargar la ficha. Intentá nuevamente."}
        </p>
      </main>
    );
  }
  const hasActiveEnrollments = student.activeEnrollmentCount > 0;
  const activeEnrollments = student.enrollments
    .filter((enrollment) => enrollment.isActive)
    .map(({ id, discipline }) => ({ id, discipline }));

  return (
    <main id="contenido" className="shell admin-panel-page">
      <nav className="admin-student-breadcrumb" aria-label="Ruta de navegación">
        <Link href="/admin-panel">Panel administrativo</Link>
        <span aria-hidden="true">/</span>
        <Link href="/admin-panel/alumnos">Alumnos</Link>
      </nav>
      {query.guardado === "1" ? (
        <p className="admin-student-message" role="status">
          Los datos del alumno se guardaron correctamente.
        </p>
      ) : null}

      <header className="admin-student-detail-heading">
        <div>
          <p className="eyebrow auth-eyebrow">Ficha del alumno</p>
          <h1>
            {student.firstName} {student.lastName}
          </h1>
          <span
            className={`admin-student-status ${hasActiveEnrollments ? "is-active" : "is-inactive"}`}
          >
            {hasActiveEnrollments
              ? "Con inscripciones activas"
              : "Sin inscripciones activas"}
          </span>
        </div>
        <div className="admin-student-heading-actions">
          <Link
            className="admin-student-button is-secondary"
            href="/admin-panel/alumnos"
          >
            Volver al listado
          </Link>
          {student.canChangeStudent ? (
            <Link
              className="admin-student-button is-primary"
              href={`/admin-panel/alumnos/${student.id}/editar`}
            >
              Editar datos
            </Link>
          ) : null}
        </div>
      </header>

      <div className="admin-student-detail-grid">
        <section
          className="admin-student-panel"
          aria-labelledby="student-info-title"
        >
          <div className="admin-student-section-heading">
            <div>
              <p className="eyebrow auth-eyebrow">Información personal</p>
              <h2 id="student-info-title">Datos del alumno</h2>
            </div>
          </div>
          <dl className="admin-student-facts">
            <div>
              <dt>Nombre</dt>
              <dd>{student.firstName}</dd>
            </div>
            <div>
              <dt>Apellido</dt>
              <dd>{student.lastName}</dd>
            </div>
            <div>
              <dt>Fecha de nacimiento</dt>
              <dd>{formatAcademicDate(student.dateOfBirth)}</dd>
            </div>
          </dl>
        </section>

        {student.accountAccess ? (
          <StudentAccountAccess
            studentId={student.id}
            studentName={`${student.firstName} ${student.lastName}`}
            access={student.accountAccess}
            canInvite={student.canInviteStudentAccount}
            canRevoke={student.canRevokeStudentAccount}
          />
        ) : null}

        <section
          className="admin-student-panel"
          aria-labelledby="guardians-title"
        >
          <div className="admin-student-section-heading">
            <div>
              <p className="eyebrow auth-eyebrow">Vínculos registrados</p>
              <h2 id="guardians-title">Tutores</h2>
            </div>
          </div>
          {student.guardians.length ? (
            <ul className="admin-student-guardian-list">
              {student.guardians.map((guardian, index) => (
                <li key={`${guardian.name}-${index}`}>
                  <span>{guardian.name}</span>
                  <span
                    className={`admin-student-status ${guardian.isActive ? "is-active" : "is-inactive"}`}
                  >
                    {guardian.isActive
                      ? "Vínculo vigente"
                      : "Vínculo finalizado"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="admin-student-empty">
              Este alumno no tiene tutores vinculados.
            </p>
          )}
        </section>

        <section
          className="admin-student-panel"
          aria-labelledby="summary-title"
        >
          <div className="admin-student-section-heading">
            <div>
              <p className="eyebrow auth-eyebrow">Estado académico</p>
              <h2 id="summary-title">Resumen</h2>
            </div>
          </div>
          <dl className="admin-student-summary">
            <div>
              <dt>Inscripciones activas</dt>
              <dd>{student.activeEnrollmentCount}</dd>
            </div>
            <div>
              <dt>Inscripciones finalizadas</dt>
              <dd>
                {
                  student.enrollments.filter(
                    (enrollment) => !enrollment.isActive,
                  ).length
                }
              </dd>
            </div>
          </dl>
        </section>
      </div>

      <section
        className="admin-student-panel admin-student-enrollments"
        aria-labelledby="enrollments-title"
      >
        <div className="admin-student-section-heading">
          <div>
            <p className="eyebrow auth-eyebrow">Trayectoria académica</p>
            <h2 id="enrollments-title">Inscripciones</h2>
            <p>Las inscripciones finalizadas permanecen en el historial.</p>
          </div>
        </div>
        {student.enrollments.length ? (
          <ul className="admin-student-enrollment-list">
            {student.enrollments.map((enrollment) => (
              <li key={enrollment.id}>
                <div className="admin-student-enrollment-main">
                  <div>
                    <h3>{enrollment.discipline}</h3>
                    <span
                      className={`admin-student-status ${enrollment.isActive ? "is-active" : "is-inactive"}`}
                    >
                      {enrollment.isActive ? "Activa" : "Finalizada"}
                    </span>
                  </div>
                  <dl>
                    <div>
                      <dt>Desde</dt>
                      <dd>{formatAcademicDate(enrollment.enrolledAt)}</dd>
                    </div>
                    {enrollment.endedAt ? (
                      <div>
                        <dt>Hasta</dt>
                        <dd>{formatAcademicDate(enrollment.endedAt)}</dd>
                      </div>
                    ) : null}
                  </dl>
                </div>
                {enrollment.isActive && student.canFinishEnrollment ? (
                  <EnrollmentActions
                    studentId={student.id}
                    today={student.today}
                    disciplines={[]}
                    activeEnrollments={[
                      { id: enrollment.id, discipline: enrollment.discipline },
                    ]}
                    showEnrollmentForm={false}
                  />
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="admin-student-empty">
            Este alumno todavía no tiene inscripciones registradas.
          </p>
        )}
        {student.canAddEnrollment ? (
          <div className="admin-student-new-enrollment">
            <h3>Inscribir en una disciplina</h3>
            <EnrollmentActions
              studentId={student.id}
              today={student.today}
              disciplines={student.availableDisciplines.filter(
                (discipline) =>
                  !activeEnrollments.some(
                    (enrollment) => enrollment.discipline === discipline.name,
                  ),
              )}
              activeEnrollments={[]}
            />
          </div>
        ) : null}
      </section>
    </main>
  );
}
