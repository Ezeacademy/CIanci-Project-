import { redirect } from "next/navigation";
import type { Metadata } from "next";

import {
  AcademicSessionExpiredError,
  getAccountAcademicData,
  type StudentWithEnrollments,
} from "../../../lib/academic/data";
import { getSessionUser } from "../../../lib/auth/session";
import { VerificationResendButton } from "../../../features/auth/password-reset-form";

export const metadata: Metadata = {
  title: "Mi cuenta | Cianci",
  robots: { index: false, follow: false },
};

export default async function AccountPage() {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");

  let students: StudentWithEnrollments[] = [];
  let academicError = false;
  try {
    students = await getAccountAcademicData();
  } catch (error) {
    if (error instanceof AcademicSessionExpiredError) redirect("/ingresar");
    academicError = true;
  }

  const ownStudents = students.filter(
    (student) => student.accessType === "self",
  );
  const studentsInCare = students.filter(
    (student) => student.accessType === "guardian",
  );
  const ownEnrollments = ownStudents.flatMap((student) => student.enrollments);

  return (
    <main id="contenido" className="shell account-page">
      <section className="account-card" aria-labelledby="account-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="account-title">Mi cuenta</h1>
        <dl className="account-details">
          <div>
            <dt>Email</dt>
            <dd>{account.email}</dd>
          </div>
          <div>
            <dt>Verificación del email</dt>
            <dd>{account.emailVerified ? "Verificado" : "Pendiente"}</dd>
          </div>
        </dl>
        {!account.emailVerified ? <VerificationResendButton /> : null}
      </section>

      <div className="account-academics">
        <section className="academic-section">
          <p className="eyebrow auth-eyebrow">Tu actividad en el instituto</p>
          <h2 id="academic-title">Información académica</h2>
          {academicError ? (
            <p className="academic-error" role="alert">
              No pudimos cargar tu información académica. Intentá de nuevo más
              tarde.
            </p>
          ) : students.length === 0 ? (
            <p className="academic-empty" role="status">
              Todavía no tenés información académica asociada a tu cuenta. Si
              creés que es un error, comunicate con la administración del
              instituto.
            </p>
          ) : (
            <div className="academic-sections">
              {ownStudents.length > 0 ? (
                <section aria-labelledby="own-disciplines-title">
                  <h3 id="own-disciplines-title">Mis disciplinas</h3>
                  {ownEnrollments.length === 0 ? (
                    <p className="academic-empty">
                      Todavía no tenés disciplinas activas.
                    </p>
                  ) : (
                    <ul className="academic-enrollment-list">
                      {ownEnrollments.map((enrollment) => (
                        <EnrollmentItem
                          key={enrollment.id}
                          name={enrollment.discipline.name}
                          status={enrollment.status}
                        />
                      ))}
                    </ul>
                  )}
                </section>
              ) : null}

              {studentsInCare.length > 0 ? (
                <section aria-labelledby="students-in-care-title">
                  <h3 id="students-in-care-title">Menores a mi cargo</h3>
                  <ul className="academic-student-list">
                    {studentsInCare.map((student) => (
                      <li className="academic-student" key={student.id}>
                        <h4>
                          {student.firstName} {student.lastName}
                        </h4>
                        {student.enrollments.length === 0 ? (
                          <p className="academic-empty">
                            Todavía no tiene disciplinas activas.
                          </p>
                        ) : (
                          <ul className="academic-enrollment-list">
                            {student.enrollments.map((enrollment) => (
                              <EnrollmentItem
                                key={enrollment.id}
                                name={enrollment.discipline.name}
                                status={enrollment.status}
                              />
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function EnrollmentItem({
  name,
  status,
}: {
  name: string;
  status: "active" | "history";
}) {
  return (
    <li className="academic-enrollment">
      <span>{name}</span>
      <span className="academic-enrollment-status">
        {status === "active" ? "Inscripción vigente" : "Inscripción finalizada"}
      </span>
    </li>
  );
}
