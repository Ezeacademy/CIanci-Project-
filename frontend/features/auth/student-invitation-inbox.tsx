"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { postAuth } from "../../lib/auth/client";
import { formatInstantDate } from "../../lib/format-date";

type Invitation = {
  id: number;
  studentName: string;
  expiresAt: string;
  status: "pending" | "expired";
};

type InvitationList = {
  emailVerified: boolean;
  invitations: Invitation[];
};

export function StudentInvitationInbox({
  emailVerified,
}: {
  emailVerified: boolean;
}) {
  const router = useRouter();
  const [data, setData] = useState<InvitationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedInvitation, setSelectedInvitation] = useState<number | null>(
    null,
  );
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const isEmailVerified = data?.emailVerified ?? emailVerified;

  useEffect(() => {
    let active = true;
    void fetch("/api/v1/auth/student-invitations", {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok)
          throw new Error("No pudimos consultar las invitaciones.");
        return (await response.json()) as InvitationList;
      })
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active)
          setError(
            "No pudimos consultar las invitaciones. Intentá nuevamente más tarde.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function acceptInvitation(invitationId: number) {
    if (pending) return;
    if (selectedInvitation !== invitationId) {
      setSelectedInvitation(invitationId);
      setError("");
      return;
    }
    setPending(true);
    setError("");
    try {
      const result = await postAuth<{ detail: string }>(
        `/api/v1/auth/student-invitations/${invitationId}/accept`,
        {},
      );
      setMessage(result.detail);
      setData((current) =>
        current
          ? {
              ...current,
              invitations: current.invitations.filter(
                (invitation) => invitation.id !== invitationId,
              ),
            }
          : current,
      );
      setSelectedInvitation(null);
      router.refresh();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se pudo aceptar la invitación.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      className="student-invitation-inbox"
      aria-labelledby="student-invitation-title"
    >
      <p className="eyebrow auth-eyebrow">Acceso académico</p>
      <h2 id="student-invitation-title">
        Invitaciones para vincular un alumno
      </h2>
      {error ? (
        <p className="academic-error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="academic-empty" role="status">
          {message}
        </p>
      ) : null}
      {loading ? (
        <p className="student-invitation-state" role="status">
          Revisando invitaciones…
        </p>
      ) : null}
      {!loading && !error && !message && data?.invitations.length === 0 ? (
        <p className="student-invitation-state">
          No tenés invitaciones académicas pendientes.
        </p>
      ) : null}
      {data?.invitations.map((invitation) => (
        <article className="student-invitation-item" key={invitation.id}>
          <div>
            <h3>{invitation.studentName}</h3>
            {invitation.status === "expired" ? (
              <p>
                La invitación venció. Contactá a la administración para recibir
                una nueva.
              </p>
            ) : (
              <p>
                La administración te invita a consultar la información académica
                y económica de este alumno y sus horarios. Vence el{" "}
                {formatDate(invitation.expiresAt)}.
              </p>
            )}
          </div>
          {invitation.status === "pending" && !isEmailVerified ? (
            <p role="status">
              Primero verificá tu correo desde esta cuenta. Después vas a poder
              aceptar.
            </p>
          ) : invitation.status === "pending" ? (
            selectedInvitation === invitation.id ? (
              <div
                className="student-invitation-confirm"
                role="group"
                aria-label="Confirmar vínculo"
              >
                <p>
                  Al aceptar, esta cuenta podrá consultar los datos de{" "}
                  {invitation.studentName}.
                </p>
                <button
                  type="button"
                  className="text-link"
                  onClick={() => setSelectedInvitation(null)}
                  disabled={pending}
                >
                  Volver
                </button>
                <button
                  type="button"
                  className="button-link auth-submit"
                  onClick={() => acceptInvitation(invitation.id)}
                  disabled={pending}
                >
                  {pending ? "Vinculando…" : "Confirmar vínculo"}
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="button-link auth-submit"
                onClick={() => acceptInvitation(invitation.id)}
              >
                Revisar invitación
              </button>
            )
          ) : null}
        </article>
      ))}
    </section>
  );
}

function formatDate(value: string): string {
  return formatInstantDate(value);
}
