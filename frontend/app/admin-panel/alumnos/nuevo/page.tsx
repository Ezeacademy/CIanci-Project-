import Link from "next/link";

import { StudentForm } from "../../../../features/admin-panel/student-form";

export default function NewStudentPage() {
  return (
    <main id="contenido" className="shell admin-panel-page">
      <header className="admin-panel-heading">
        <div>
          <p className="eyebrow auth-eyebrow">Gestión académica</p>
          <h1>Registrar alumno</h1>
          <p>Completá los datos para crear su ficha en el instituto.</p>
        </div>
        <Link className="calendar-back-link" href="/admin-panel/alumnos">
          ← Volver a alumnos
        </Link>
      </header>
      <section
        className="admin-student-panel"
        aria-labelledby="new-student-title"
      >
        <h2 id="new-student-title">Datos del alumno</h2>
        <StudentForm />
      </section>
    </main>
  );
}
