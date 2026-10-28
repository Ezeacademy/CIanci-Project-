"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import type { StudentDisciplineOption } from "../../lib/admin-panel/academic";
import { submitAdminAcademicRequest } from "../../lib/admin-panel/academic-client";

type EnrollmentActionsProps = {
  studentId: number;
  today: string;
  disciplines: StudentDisciplineOption[];
  activeEnrollments: { id: number; discipline: string }[];
  showEnrollmentForm?: boolean;
};

export function EnrollmentActions({
  studentId,
  today,
  disciplines,
  activeEnrollments,
  showEnrollmentForm = true,
}: EnrollmentActionsProps) {
  const router = useRouter();
  const submitGuard = useRef(false);
  const [pendingAction, setPendingAction] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [finishId, setFinishId] = useState<number | null>(null);

  async function createEnrollment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitGuard.current) return;
    submitGuard.current = true;
    setPendingAction("create");
    setError("");
    setMessage("");
    const values = new FormData(event.currentTarget);
    const form = event.currentTarget;
    try {
      const result = await submitAdminAcademicRequest<{
        initialChargeStatus: string;
      }>(`/api/v1/admin/academic/students/${studentId}/enrollments`, "POST", {
        discipline_id: Number(values.get("discipline_id")),
        enrolled_at: String(values.get("enrolled_at")),
      });
      setMessage(
        result.initialChargeStatus === "created"
          ? "Inscripción registrada y mensualidad del mes generada."
          : result.initialChargeStatus === "missing_price"
            ? "Inscripción registrada. No hay una tarifa vigente para generar la mensualidad de este mes."
            : "Inscripción registrada.",
      );
      form.reset();
      router.refresh();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "No se pudo registrar la inscripción.",
      );
    } finally {
      submitGuard.current = false;
      setPendingAction("");
    }
  }

  async function finishEnrollment(enrollmentId: number) {
    if (submitGuard.current) return;
    submitGuard.current = true;
    setPendingAction(`finish-${enrollmentId}`);
    setError("");
    try {
      await submitAdminAcademicRequest(
        `/api/v1/admin/academic/students/${studentId}/enrollments/${enrollmentId}/finish`,
        "POST",
      );
      setMessage(
        "La inscripción quedó finalizada y se conservó en el historial.",
      );
      setFinishId(null);
      router.refresh();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "No se pudo finalizar la inscripción.",
      );
    } finally {
      submitGuard.current = false;
      setPendingAction("");
    }
  }

  return (
    <div className="admin-student-actions">
      {error ? (
        <p className="admin-student-message is-error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="admin-student-message" role="status">
          {message}
        </p>
      ) : null}

      {showEnrollmentForm && disciplines.length ? (
        <form className="admin-student-inline-form" onSubmit={createEnrollment}>
          <label>
            <span>Disciplina</span>
            <select name="discipline_id" required defaultValue="">
              <option value="" disabled>
                Elegir disciplina
              </option>
              {disciplines.map((discipline) => (
                <option key={discipline.id} value={discipline.id}>
                  {discipline.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Fecha de inscripción</span>
            <input
              name="enrolled_at"
              type="date"
              required
              defaultValue={today}
            />
          </label>
          <button
            className="admin-student-button is-primary"
            disabled={Boolean(pendingAction)}
          >
            {pendingAction === "create"
              ? "Guardando…"
              : "Inscribir en disciplina"}
          </button>
        </form>
      ) : showEnrollmentForm ? (
        <p className="admin-student-empty">
          No hay disciplinas activas disponibles para una nueva inscripción.
        </p>
      ) : null}

      {activeEnrollments.map((enrollment) => (
        <div className="admin-student-finish" key={enrollment.id}>
          {finishId === enrollment.id ? (
            <div
              className="admin-student-confirm"
              role="group"
              aria-label={`Confirmar baja de ${enrollment.discipline}`}
            >
              <p>
                ¿Finalizar la inscripción de{" "}
                <strong>{enrollment.discipline}</strong>? Dejará de figurar como
                activa; la baja se registrará hoy y quedará en el historial.
              </p>
              <button
                className="admin-student-button is-danger"
                disabled={Boolean(pendingAction)}
                onClick={() => finishEnrollment(enrollment.id)}
              >
                {pendingAction === `finish-${enrollment.id}`
                  ? "Finalizando…"
                  : "Sí, finalizar inscripción"}
              </button>
              <button
                className="admin-student-text-button"
                disabled={Boolean(pendingAction)}
                onClick={() => setFinishId(null)}
              >
                Volver
              </button>
            </div>
          ) : (
            <button
              className="admin-student-text-button"
              disabled={Boolean(pendingAction)}
              onClick={() => setFinishId(enrollment.id)}
              aria-label={`Finalizar inscripción de ${enrollment.discipline}`}
            >
              Finalizar inscripción
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
