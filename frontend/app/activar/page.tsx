import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ActivationForm } from "../../features/auth/activation-form";
import { getSessionUser } from "../../lib/auth/session";

export const metadata: Metadata = {
  title: "Activar cuenta | Cianci",
  description: "Activá tu cuenta de Cianci mediante una invitación.",
  robots: { index: false, follow: false },
};

export default async function ActivationPage() {
  if (await getSessionUser()) redirect("/mi-cuenta");

  return (
    <main id="contenido" className="shell auth-page">
      <section className="auth-card" aria-labelledby="activation-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="activation-title">Activá tu cuenta.</h1>
        <p className="auth-intro">
          Completá tus datos para acceder a tu cuenta de Cianci.
        </p>
        <ActivationForm />
      </section>
    </main>
  );
}
