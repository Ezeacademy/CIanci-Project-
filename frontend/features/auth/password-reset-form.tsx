"use client";

import {
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
} from "react";
import { postAuth } from "../../lib/auth/client";

function subscribeToHash(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

function getHash() {
  return window.location.hash.slice(1);
}

export function PasswordResetRequestForm() {
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    const email = String(new FormData(event.currentTarget).get("email") || "").trim();
    try {
      const result = await postAuth<{ detail: string }>(
        "/api/v1/auth/password-reset",
        { email },
      );
      setMessage(result.detail);
    } catch {
      setMessage("No pudimos procesar la solicitud. Intentá de nuevo más tarde.");
    } finally {
      setPending(false);
      pendingRef.current = false;
    }
  }
  return (
    <form className="auth-form" onSubmit={submit}>
      <label htmlFor="reset-email">Email</label>
      <input id="reset-email" name="email" type="email" autoComplete="email" required maxLength={254} disabled={pending} />
      {message ? <p role="status" className="auth-message">{message}</p> : null}
      <button className="button-link auth-submit" disabled={pending} aria-busy={pending}>
        {pending ? "Enviando…" : "Enviar enlace"}
        {pending ? <span className="auth-spinner" aria-hidden="true" /> : null}
      </button>
    </form>
  );
}

export function PasswordResetConfirmForm() {
  const fragment = useSyncExternalStore(subscribeToHash, getHash, () => "");
  const [uid = "", token = ""] = fragment.split(".", 2);
  const link = uid && token ? `${uid}.${token}` : "";
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current || !link) return;
    pendingRef.current = true;
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      const [uid, token] = link.split(".", 2);
      const result = await postAuth<{ detail: string }>(
        "/api/v1/auth/password-reset/confirm",
        { uid, token, password: data.get("password"), passwordConfirmation: data.get("confirmation") },
      );
      setMessage(result.detail);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "No pudimos actualizar la contraseña.");
    } finally {
      setPending(false);
      pendingRef.current = false;
    }
  }
  return (
    <form className="auth-form" onSubmit={submit}>
      {!link ? <p className="auth-error" role="alert">El enlace no es válido o venció.</p> : null}
      <label htmlFor="new-password">Nueva contraseña</label>
      <input id="new-password" name="password" type="password" autoComplete="new-password" required disabled={pending || !link} />
      <label htmlFor="new-password-confirmation">Repetí la contraseña</label>
      <input id="new-password-confirmation" name="confirmation" type="password" autoComplete="new-password" required disabled={pending || !link} />
      {message ? <p role="status" className="auth-message">{message}</p> : null}
      <button className="button-link auth-submit" disabled={pending || !link} aria-busy={pending}>
        {pending ? "Actualizando…" : "Guardar contraseña"}
        {pending ? <span className="auth-spinner" aria-hidden="true" /> : null}
      </button>
    </form>
  );
}

export function EmailVerificationForm() {
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  async function submit() {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    try {
      const token = window.location.hash.slice(1);
      const result = await postAuth<{ detail: string }>(
        "/api/v1/auth/email-verification/confirm",
        { token },
      );
      setMessage(result.detail);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "El enlace no es válido o venció.");
    } finally {
      setPending(false);
      pendingRef.current = false;
    }
  }
  return (
    <div className="auth-form">
      <button type="button" className="button-link auth-submit" onClick={submit} disabled={pending} aria-busy={pending}>
        {pending ? "Verificando…" : "Verificar email"}
        {pending ? <span className="auth-spinner" aria-hidden="true" /> : null}
      </button>
      {message ? <p role="status" className="auth-message">{message}</p> : null}
    </div>
  );
}

export function VerificationResendButton() {
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  async function resend() {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    try {
      const result = await postAuth<{ detail: string }>(
        "/api/v1/auth/email-verification/resend",
        {},
      );
      setMessage(result.detail);
    } catch {
      setMessage("No pudimos enviar el correo. Intentá de nuevo más tarde.");
    } finally {
      setPending(false);
      pendingRef.current = false;
    }
  }
  return <div className="verification-resend"><button type="button" className="text-link" onClick={resend} disabled={pending}>{pending ? "Enviando…" : "Reenviar correo de verificación"}</button>{message ? <p role="status" className="auth-message">{message}</p> : null}</div>;
}
