import type { Metadata } from "next";
import { PasswordResetRequestForm } from "../../features/auth/password-reset-form";

export const metadata: Metadata = {
  title: "Recuperar contraseña | Cianci",
  robots: { index: false, follow: false },
};

export default function PasswordResetPage() {
  return (
    <main id="contenido" className="shell auth-page">
      <section className="auth-card" aria-labelledby="reset-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="reset-title">Recuperá tu contraseña.</h1>
        <p className="auth-intro">Te enviaremos un enlace si la cuenta puede recuperar su acceso.</p>
        <PasswordResetRequestForm />
      </section>
    </main>
  );
}
