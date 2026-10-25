import type { Metadata } from "next";
import { PasswordResetConfirmForm } from "../../features/auth/password-reset-form";

export const metadata: Metadata = {
  title: "Nueva contraseña | Cianci",
  robots: { index: false, follow: false },
};

export default function PasswordResetConfirmPage() {
  return (
    <main id="contenido" className="shell auth-page">
      <section className="auth-card" aria-labelledby="new-password-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="new-password-title">Elegí una contraseña nueva.</h1>
        <PasswordResetConfirmForm />
      </section>
    </main>
  );
}
