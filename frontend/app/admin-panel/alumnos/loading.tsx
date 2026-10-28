export default function AdminStudentsLoading() {
  return (
    <main id="contenido" className="shell admin-panel-page">
      <p className="admin-student-message" role="status" aria-busy="true">
        Cargando información de alumnos…
      </p>
    </main>
  );
}
