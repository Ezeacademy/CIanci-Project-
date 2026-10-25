"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export function LogoutButton() {
  const router = useRouter();
  const pendingRef = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function handleLogout() {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setError("");
    try {
      const csrfResponse = await fetch("/api/v1/auth/csrf", {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!csrfResponse.ok) throw new Error();
      const { csrfToken } = (await csrfResponse.json()) as {
        csrfToken: string;
      };
      const response = await fetch("/api/v1/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: "{}",
      });
      if (!response.ok) throw new Error();
      router.replace("/");
      router.refresh();
    } catch {
      setError("No pudimos cerrar la sesión. Intentá de nuevo.");
      pendingRef.current = false;
      setPending(false);
    }
  }

  return (
    <div className="logout-area">
      <button
        className="account-nav-link"
        type="button"
        onClick={handleLogout}
        disabled={pending}
        aria-busy={pending}
      >
        {pending ? "Cerrando sesión…" : "Cerrar sesión"}
        {pending ? <span className="auth-spinner" aria-hidden="true" /> : null}
      </button>
      {error ? (
        <p className="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
