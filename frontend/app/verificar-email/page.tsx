import type { Metadata } from "next";
import { EmailVerificationForm } from "../../features/auth/password-reset-form";

export const metadata: Metadata = {
  title: "Verificar email | Cianci",
  robots: { index: false, follow: false },
};

export default function VerifyEmailPage() {
  return (
    <main id="contenido" className="shell auth-page">
      <section className="auth-card" aria-labelledby="verify-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="verify-title">Verificá tu email.</h1>
        <p className="auth-intro">Confirmá que podés recibir mensajes en esta dirección.</p>
        <EmailVerificationForm />
      </section>
    </main>
  );
}
