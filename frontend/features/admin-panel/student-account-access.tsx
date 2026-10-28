"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { postAuth } from "../../lib/auth/client";

export type StudentAccountAccessData = {
  status: "none" | "pending" | "expired" | "linked";
  email: string | null;
  expiresAt: string | null;
  invitationId: number | null;
};

type StudentAccountAccessProps = {
  studentId: number;
  studentName: string;
  access: StudentAccountAccessData;
  canInvite: boolean;
  canRevoke: boolean;
};

export function StudentAccountAccess({
  studentId,
  studentName,
  access,
  canInvite,
  canRevoke,
}: StudentAccountAccessProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [confirmSend, setConfirmSend] = useState(false);
  const [confirmAction, setConfirmAction] = useState<
    "cancel" | "revoke" | null
  >(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function sendInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmSend) {
      setConfirmSend(true);
      setError("");
      return;
    }
    setPending(true);
    setError("");
    try {
      const result = await postAuth<{ detail: string }>(
        `/api/v1/admin/academic/students/${studentId}/account-invitations`,
        { email },
      );
      setMessage(result.detail);
      setConfirmSend(false);
      setEmail("");
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No pudimos enviar la invitación.",
      );
    } finally {
      setPending(false);
    }
  }

  async function confirmCurrentAction() {
    if (!confirmAction) return;
    setPending(true);
    setError("");
    try {
      const path =
        confirmAction === "revoke"
          ? `/api/v1/admin/academic/students/${studentId}/account-access/revoke`
          : `/api/v1/admin/academic/students/${studentId}/account-invitations/${access.invitationId}/cancel`;
      const result = await postAuth<{ detail: string }>(path, {});
      setMessage(result.detail);
      setConfirmAction(null);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo actualizar el acceso.",
      );
    } finally {
      setPending(false);
    }
  }

  const statusText = {
    none: "Sin cuenta vinculada",
    pending: "Invitación pendiente",
    expired: "Invitación vencida",
    linked: "Cuenta vinculada",
  }[access.status];

  return (
    <section
      className="admin-student-panel admin-student-access"
      aria-labelledby="student-access-title"
    >
      <div className="admin-student-section-heading">
        <div>
          <p className="eyebrow auth-eyebrow">Acceso digital</p>
          <h2 id="student-access-title">Acceso a la plataforma</h2>
        </div>
        <span
          className={`admin-student-status ${access.status === "linked" ? "is-active" : "is-inactive"}`}
        >
          {statusText}
        </span>
      </div>

      {access.status === "linked" ? (
        <div className="admin-student-access-content">
          <p>
            La cuenta vinculada puede consultar la información académica y
            económica de {studentName}, además de sus horarios.
          </p>
          <p>
            <strong>Correo:</strong> {access.email}
          </p>
          {canRevoke ? (
            confirmAction === "revoke" ? (
              <div
                className="admin-student-access-confirm"
                role="group"
                aria-label="Confirmar revocación"
              >
                <p>
                  La cuenta dejará de ver la información de este alumno en sus
                  próximas consultas. Los registros académicos y económicos se
                  conservan.
                </p>
                <button
                  className="admin-student-button is-secondary"
                  type="button"
                  onClick={() => setConfirmAction(null)}
                  disabled={pending}
                >
                  Volver
                </button>
                <button
                  className="admin-student-button is-danger"
                  type="button"
                  onClick={confirmCurrentAction}
                  disabled={pending}
                >
                  {pending ? "Revocando…" : "Confirmar revocación"}
                </button>
              </div>
            ) : (
              <button
                className="admin-student-button is-secondary"
                type="button"
                onClick={() => setConfirmAction("revoke")}
              >
                Revocar acceso
              </button>
            )
          ) : null}
        </div>
      ) : access.status === "pending" ? (
        <div className="admin-student-access-content">
          <p>
            Enviamos la invitación a <strong>{access.email}</strong>. Vence el{" "}
            {formatDate(access.expiresAt)}.
          </p>
          {canInvite ? (
            confirmAction === "cancel" ? (
              <div
                className="admin-student-access-confirm"
                role="group"
                aria-label="Confirmar cancelación"
              >
                <p>La persona ya no podrá aceptar esta invitación.</p>
                <button
                  className="admin-student-button is-secondary"
                  type="button"
                  onClick={() => setConfirmAction(null)}
                  disabled={pending}
                >
                  Volver
                </button>
                <button
                  className="admin-student-button is-danger"
                  type="button"
                  onClick={confirmCurrentAction}
                  disabled={pending}
                >
                  {pending ? "Cancelando…" : "Confirmar cancelación"}
                </button>
              </div>
            ) : (
              <button
                className="admin-student-button is-secondary"
                type="button"
                onClick={() => setConfirmAction("cancel")}
              >
                Cancelar invitación
              </button>
            )
          ) : null}
        </div>
      ) : (
        <div className="admin-student-access-content">
          {access.status === "expired" ? (
            <p>
              La invitación enviada a {access.email} venció. Podés enviar una
              nueva.
            </p>
          ) : (
            <p>
              La cuenta podrá consultar la información académica y económica de{" "}
              {studentName}, además de sus horarios. La persona deberá verificar
              su correo y aceptar el vínculo.
            </p>
          )}
          {canInvite ? (
            <form
              className="admin-student-access-form"
              onSubmit={sendInvitation}
            >
              <label htmlFor={`student-invite-email-${studentId}`}>
                Correo de la persona invitada
              </label>
              <input
                id={`student-invite-email-${studentId}`}
                type="email"
                autoComplete="email"
                required
                maxLength={254}
                value={email}
                disabled={pending}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setConfirmSend(false);
                }}
              />
              {confirmSend ? (
                <div
                  className="admin-student-access-confirm"
                  role="group"
                  aria-label="Confirmar envío"
                >
                  <p>
                    Se invitará a <strong>{email}</strong> a consultar los datos
                    de <strong>{studentName}</strong>. Confirmá que verificaste
                    institucionalmente a la persona destinataria.
                  </p>
                  <button
                    className="admin-student-button is-secondary"
                    type="button"
                    onClick={() => setConfirmSend(false)}
                    disabled={pending}
                  >
                    Revisar correo
                  </button>
                  <button
                    className="admin-student-button is-primary"
                    type="submit"
                    disabled={pending}
                  >
                    {pending ? "Enviando…" : "Confirmar y enviar"}
                  </button>
                </div>
              ) : (
                <button
                  className="admin-student-button is-primary"
                  type="submit"
                  disabled={pending}
                >
                  Invitar a la plataforma
                </button>
              )}
            </form>
          ) : null}
        </div>
      )}
      {message ? (
        <p className="admin-student-message" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="admin-student-message is-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "";
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "long" }).format(
    new Date(value),
  );
}
