"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

type FieldErrors = { email?: string; password?: string };

export function LoginForm() {
  const router = useRouter();
  const pendingRef = useRef(false);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;

    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");
    const fieldErrors: FieldErrors = {};
    if (!email) fieldErrors.email = "Ingresá tu email.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      fieldErrors.email = "Revisá el formato del email.";
    }
    if (!password) fieldErrors.password = "Ingresá tu contraseña.";
    setErrors(fieldErrors);
    setFormError("");
    if (Object.keys(fieldErrors).length) return;

    pendingRef.current = true;
    setPending(true);
    try {
      const csrfResponse = await fetch("/api/v1/auth/csrf", {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!csrfResponse.ok) throw new Error("No pudimos iniciar el acceso.");
      const { csrfToken } = (await csrfResponse.json()) as {
        csrfToken: string;
      };

      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        if (response.status === 403) {
          throw new Error(
            "La verificación de seguridad venció. Intentá de nuevo.",
          );
        }
        const body = (await response.json()) as { detail?: string };
        throw new Error(body.detail || "No pudimos iniciar el acceso.");
      }
      router.replace("/mi-cuenta");
      router.refresh();
    } catch (cause) {
      setFormError(
        cause instanceof Error
          ? cause.message
          : "No pudimos iniciar el acceso. Intentá de nuevo.",
      );
      pendingRef.current = false;
      setPending(false);
    }
  }

  function clearValidation(field: keyof FieldErrors) {
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFormError("");
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <label htmlFor="email">Email</label>
      <input
        autoComplete="email"
        autoFocus
        id="email"
        name="email"
        type="email"
        required
        maxLength={254}
        disabled={pending}
        aria-invalid={Boolean(errors.email)}
        aria-describedby={errors.email ? "email-error" : undefined}
        onChange={() => clearValidation("email")}
      />
      {errors.email ? (
        <p className="field-error" id="email-error">
          {errors.email}
        </p>
      ) : null}
      <label htmlFor="password">Contraseña</label>
      <input
        autoComplete="current-password"
        id="password"
        name="password"
        type="password"
        required
        disabled={pending}
        aria-invalid={Boolean(errors.password)}
        aria-describedby={errors.password ? "password-error" : undefined}
        onChange={() => clearValidation("password")}
      />
      {errors.password ? (
        <p className="field-error" id="password-error">
          {errors.password}
        </p>
      ) : null}
      {formError ? (
        <p className="auth-error" role="alert" aria-live="polite">
          {formError}
        </p>
      ) : null}
      <button
        className="button-link auth-submit"
        type="submit"
        disabled={pending}
        aria-busy={pending}
      >
        {pending ? "Ingresando…" : "Ingresar"}
        {pending ? (
          <span className="auth-spinner" aria-hidden="true" />
        ) : (
          <span aria-hidden="true">↗</span>
        )}
      </button>
    </form>
  );
}
