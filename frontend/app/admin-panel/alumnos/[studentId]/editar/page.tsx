import Link from "next/link";

import { StudentForm } from "../../../../../features/admin-panel/student-form";
import {
  AdminAcademicDataError,
  getAdminStudent,
} from "../../../../../lib/admin-panel/academic";

type EditStudentPageProps = { params: Promise<{ studentId: string }> };

export default async function EditStudentPage({
  params,
}: EditStudentPageProps) {
  const { studentId } = await params;
  let student;
  try {
    student = await getAdminStudent(studentId);
  } catch (error) {
    return (
      <main id="contenido" className="shell admin-panel-page">
        <Link className="calendar-back-link" href="/admin-panel/alumnos">
          ← Volver a alumnos
        </Link>
        <p className="admin-student-message is-error" role="alert">
          {error instanceof AdminAcademicDataError && error.status === 403
            ? "Tu usuario no tiene permiso para consultar esta ficha."
            : "No pudimos cargar la ficha para editarla."}
        </p>
      </main>
    );
  }
  if (!student.canChangeStudent) {
    return (
      <main id="contenido" className="shell admin-panel-page">
        <p className="admin-student-message is-error" role="alert">
          Tu usuario no tiene permiso para editar los datos de este alumno.
        </p>
        <Link
          className="calendar-back-link"
          href={`/admin-panel/alumnos/${student.id}`}
        >
          Volver a la ficha
        </Link>
      </main>
    );
  }

  return (
    <main id="contenido" className="shell admin-panel-page">
      <header className="admin-panel-heading">
        <div>
          <p className="eyebrow auth-eyebrow">Ficha del alumno</p>
          <h1>Editar datos</h1>
          <p>
            {student.firstName} {student.lastName}
          </p>
        </div>
        <Link
          className="calendar-back-link"
          href={`/admin-panel/alumnos/${student.id}`}
        >
          ← Volver a la ficha
        </Link>
      </header>
      <section
        className="admin-student-panel"
        aria-labelledby="edit-student-title"
      >
        <h2 id="edit-student-title">Datos personales</h2>
        <StudentForm
          studentId={student.id}
          firstName={student.firstName}
          lastName={student.lastName}
          dateOfBirth={student.dateOfBirth}
        />
      </section>
    </main>
  );
}
