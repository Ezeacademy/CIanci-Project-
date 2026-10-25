"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
} from "react";

const TOKEN_PENDING = "__token_pending__";

function subscribeToLocationHash(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

function getLocationHash() {
  return window.location.hash.slice(1);
}

function getServerHash() {
  return TOKEN_PENDING;
}

type InvitationPreview = {
  email: string | null;
  emailBound: boolean;
  firstName: string;
  lastName: string;
};

type Fields = {
  email: string;
  firstName: string;
  lastName: string;
  password: string;
  passwordConfirmation: string;
};

type FieldErrors = Partial<Record<keyof Fields, string>>;

async function getCsrfToken() {
  const response = await fetch("/api/v1/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new Error("No se pudo validar la invitación.");
  return ((await response.json()) as { csrfToken: string }).csrfToken;
}

export function ActivationForm() {
  const router = useRouter();
  const inspectedToken = useRef("");
  const pendingRef = useRef(false);
  const token = useSyncExternalStore(
    subscribeToLocationHash,
    getLocationHash,
    getServerHash,
  );
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [fields, setFields] = useState<Fields>({
    email: "",
    firstName: "",
    lastName: "",
    password: "",
    passwordConfirmation: "",
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (!token || token === TOKEN_PENDING) return;
    if (inspectedToken.current === token) return;
    inspectedToken.current = token;

    let active = true;
    void (async () => {
      try {
        const csrfToken = await getCsrfToken();
        const response = await fetch("/api/v1/auth/invitations/inspect", {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ token }),
        });
        if (!response.ok) {
          throw new Error("Este enlace no es válido o ya no está disponible.");
        }
        const invitation = (await response.json()) as InvitationPreview;
        if (!active) return;
        setPreview(invitation);
        setFields((current) => ({
          ...current,
          email: invitation.email || "",
          firstName: invitation.firstName,
          lastName: invitation.lastName,
        }));
      } catch (cause) {
        if (active) {
          setFormError(
            cause instanceof Error
              ? cause.message
              : "No se pudo validar la invitación.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [token]);

  function updateField(field: keyof Fields, value: string) {
    setFields((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setFormError("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current || !preview) return;

    const fieldErrors: FieldErrors = {};
    if (!fields.email.trim()) fieldErrors.email = "Ingresá tu email.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email.trim())) {
      fieldErrors.email = "Revisá el formato del email.";
    }
    if (!fields.password) fieldErrors.password = "Ingresá una contraseña.";
    if (!fields.passwordConfirmation) {
      fieldErrors.passwordConfirmation = "Repetí la contraseña.";
    } else if (fields.password !== fields.passwordConfirmation) {
      fieldErrors.passwordConfirmation = "Las contraseñas no coinciden.";
    }
    setErrors(fieldErrors);
    setFormError("");
    if (Object.keys(fieldErrors).length) return;

    pendingRef.current = true;
    setPending(true);
    try {
      const csrfToken = await getCsrfToken();
      const response = await fetch("/api/v1/auth/invitations/activate", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          token,
          email: fields.email.trim(),
          firstName: fields.firstName.trim(),
          lastName: fields.lastName.trim(),
          password: fields.password,
          passwordConfirmation: fields.passwordConfirmation,
        }),
      });
      const body = (await response.json()) as {
        detail?: string;
        errors?: Partial<Record<keyof Fields, string[]>>;
      };
      if (!response.ok) {
        if (body.errors) {
          setErrors(
            Object.fromEntries(
              Object.entries(body.errors).map(([field, messages]) => [
                field,
                messages?.join(" "),
              ]),
            ) as FieldErrors,
          );
        } else {
          throw new Error(body.detail || "No se pudo activar la cuenta.");
        }
        pendingRef.current = false;
        setPending(false);
        return;
      }
      router.replace("/mi-cuenta");
      router.refresh();
    } catch (cause) {
      setFormError(
        cause instanceof Error
          ? cause.message
          : "No se pudo activar la cuenta. Intentá de nuevo.",
      );
      pendingRef.current = false;
      setPending(false);
    }
  }

  if (token === TOKEN_PENDING || (Boolean(token) && loading)) {
    return <p role="status">Validando invitación…</p>;
  }

  if (!token || !preview) {
    return (
      <div>
        <p className="auth-error" role="alert">
          {formError || "Este enlace no es válido o ya no está disponible."}
        </p>
        <p className="auth-intro">
          Solicitá una nueva invitación o <Link href="/ingresar">ingresá</Link>{" "}
          si ya tenés una cuenta.
        </p>
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <label htmlFor="activation-email">Email</label>
      <input
        autoComplete="email"
        autoFocus
        id="activation-email"
        name="email"
        type="email"
        required
        maxLength={254}
        readOnly={preview.emailBound}
        disabled={pending}
        value={fields.email}
        aria-invalid={Boolean(errors.email)}
        aria-describedby={errors.email ? "activation-email-error" : undefined}
        onChange={(event) => updateField("email", event.target.value)}
      />
      {errors.email ? (
        <p className="field-error" id="activation-email-error">
          {errors.email}
        </p>
      ) : null}

      <label htmlFor="activation-first-name">Nombre</label>
      <input
        autoComplete="given-name"
        id="activation-first-name"
        name="firstName"
        maxLength={150}
        disabled={pending}
        value={fields.firstName}
        onChange={(event) => updateField("firstName", event.target.value)}
      />
      <label htmlFor="activation-last-name">Apellido</label>
      <input
        autoComplete="family-name"
        id="activation-last-name"
        name="lastName"
        maxLength={150}
        disabled={pending}
        value={fields.lastName}
        onChange={(event) => updateField("lastName", event.target.value)}
      />

      <label htmlFor="activation-password">Contraseña</label>
      <input
        autoComplete="new-password"
        id="activation-password"
        name="password"
        type="password"
        required
        disabled={pending}
        value={fields.password}
        aria-invalid={Boolean(errors.password)}
        aria-describedby={
          errors.password ? "activation-password-error" : undefined
        }
        onChange={(event) => updateField("password", event.target.value)}
      />
      {errors.password ? (
        <p className="field-error" id="activation-password-error">
          {errors.password}
        </p>
      ) : null}

      <label htmlFor="activation-password-confirmation">
        Repetir contraseña
      </label>
      <input
        autoComplete="new-password"
        id="activation-password-confirmation"
        name="passwordConfirmation"
        type="password"
        required
        disabled={pending}
        value={fields.passwordConfirmation}
        aria-invalid={Boolean(errors.passwordConfirmation)}
        aria-describedby={
          errors.passwordConfirmation
            ? "activation-password-confirmation-error"
            : undefined
        }
        onChange={(event) =>
          updateField("passwordConfirmation", event.target.value)
        }
      />
      {errors.passwordConfirmation ? (
        <p className="field-error" id="activation-password-confirmation-error">
          {errors.passwordConfirmation}
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
        {pending ? "Activando…" : "Activar cuenta"}
        {pending ? <span className="auth-spinner" aria-hidden="true" /> : null}
      </button>
    </form>
  );
}
