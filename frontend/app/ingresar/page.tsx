import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LoginForm } from "../../features/auth/login-form";
import { getSessionUser } from "../../lib/auth/session";

export const metadata: Metadata = {
  title: "Ingresar | Cianci",
  description: "Ingresá a tu cuenta de Cianci.",
  robots: { index: false, follow: false },
};

export default async function LoginPage() {
  if (await getSessionUser()) redirect("/mi-cuenta");
  return (
    <main id="contenido" className="shell auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="login-title">Qué bueno tenerte de vuelta.</h1>
        <p className="auth-intro">
          Ingresá con el email y la contraseña de tu cuenta.
        </p>
        <LoginForm />
        <a className="text-link auth-support-link" href="/recuperar-clave">
          ¿Olvidaste tu contraseña?
        </a>
      </section>
    </main>
  );
}
