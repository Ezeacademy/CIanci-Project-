"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { submitAdminAcademicRequest } from "../../lib/admin-panel/academic-client";

type StudentFormProps = {
  studentId?: number;
  firstName?: string;
  lastName?: string;
  dateOfBirth?: string | null;
};

export function StudentForm({
  studentId,
  firstName = "",
  lastName = "",
  dateOfBirth = "",
}: StudentFormProps) {
  const router = useRouter();
  const isSubmitting = useRef(false);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [createdStudent, setCreatedStudent] = useState<{
    id: number;
    canInviteStudentAccount: boolean;
  } | null>(null);
  const isEditing = studentId !== undefined;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting.current) return;
    isSubmitting.current = true;
    setIsPending(true);
    setError("");
    setFieldErrors({});
    const values = new FormData(event.currentTarget);
    const payload = {
      first_name: String(values.get("first_name") ?? "").trim(),
      last_name: String(values.get("last_name") ?? "").trim(),
      date_of_birth: String(values.get("date_of_birth") ?? "") || null,
    };
    try {
      const result = await submitAdminAcademicRequest<{
        id: number;
        canInviteStudentAccount: boolean;
      }>(
        isEditing
          ? `/api/v1/admin/academic/students/${studentId}`
          : "/api/v1/admin/academic/students",
        isEditing ? "PATCH" : "POST",
        payload,
      );
      if (isEditing) {
        router.push(`/admin-panel/alumnos/${result.id}?guardado=1`);
        router.refresh();
      } else {
        setCreatedStudent(result);
      }
    } catch (caughtError) {
      if (caughtError instanceof Error) setError(caughtError.message);
      if (
        caughtError &&
        typeof caughtError === "object" &&
        "fieldErrors" in caughtError
      ) {
        setFieldErrors(
          (caughtError as { fieldErrors: Record<string, string> }).fieldErrors,
        );
      }
    } finally {
      isSubmitting.current = false;
      setIsPending(false);
    }
  }

  if (createdStudent) {
    const studentUrl = `/admin-panel/alumnos/${createdStudent.id}`;
    return (
      <section className="admin-student-created" role="status">
        <h3>Alumno registrado correctamente</h3>
        {createdStudent.canInviteStudentAccount ? (
          <>
            <p>¿Querés invitarlo a acceder a Cianci?</p>
            <div className="admin-student-form-actions">
              <Link
                className="admin-student-button is-primary"
                href={`${studentUrl}?invitar=1#student-access-title`}
              >
                Enviar invitación
              </Link>
              <Link
                className="admin-student-button is-secondary"
                href={`${studentUrl}?guardado=1`}
              >
                Ahora no
              </Link>
            </div>
          </>
        ) : (
          <>
            <p>
              La ficha ya está lista para continuar con la gestión académica.
            </p>
            <Link
              className="admin-student-button is-primary"
              href={`${studentUrl}?guardado=1`}
            >
              Ver ficha del alumno
            </Link>
          </>
        )}
      </section>
    );
  }

  return (
    <form className="admin-student-form" onSubmit={handleSubmit}>
      {error ? (
        <p className="admin-student-message is-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="admin-student-form-grid">
        <label>
          <span>Nombre</span>
          <input
            name="first_name"
            autoComplete="given-name"
            maxLength={150}
            required
            defaultValue={firstName}
            aria-invalid={Boolean(fieldErrors.first_name)}
            aria-describedby={
              fieldErrors.first_name ? "student-first-error" : undefined
            }
          />
          {fieldErrors.first_name ? (
            <small id="student-first-error">{fieldErrors.first_name}</small>
          ) : null}
        </label>
        <label>
          <span>Apellido</span>
          <input
            name="last_name"
            autoComplete="family-name"
            maxLength={150}
            required
            defaultValue={lastName}
            aria-invalid={Boolean(fieldErrors.last_name)}
            aria-describedby={
              fieldErrors.last_name ? "student-last-error" : undefined
            }
          />
          {fieldErrors.last_name ? (
            <small id="student-last-error">{fieldErrors.last_name}</small>
          ) : null}
        </label>
        <label>
          <span>
            Fecha de nacimiento <em>(opcional)</em>
          </span>
          <input
            name="date_of_birth"
            type="date"
            autoComplete="bday"
            defaultValue={dateOfBirth ?? ""}
            aria-invalid={Boolean(fieldErrors.date_of_birth)}
            aria-describedby={
              fieldErrors.date_of_birth ? "student-dob-error" : undefined
            }
          />
          {fieldErrors.date_of_birth ? (
            <small id="student-dob-error">{fieldErrors.date_of_birth}</small>
          ) : null}
        </label>
      </div>
      <p className="admin-student-form-note">
        Antes de registrar, podés buscar en el listado si ya existe una ficha
        con este nombre. Esta ficha no crea una cuenta de acceso.
      </p>
      <div className="admin-student-form-actions">
        <button
          className="admin-student-button is-primary"
          disabled={isPending}
        >
          {isPending
            ? "Guardando…"
            : isEditing
              ? "Guardar cambios"
              : "Registrar alumno"}
        </button>
        <Link
          className="admin-student-button is-secondary"
          href="/admin-panel/alumnos"
        >
          Cancelar
        </Link>
      </div>
    </form>
  );
}
