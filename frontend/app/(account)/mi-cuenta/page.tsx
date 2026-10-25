import { redirect } from "next/navigation";
import type { Metadata } from "next";

import { getSessionUser } from "../../../lib/auth/session";

export const metadata: Metadata = {
  title: "Mi cuenta | Cianci",
  robots: { index: false, follow: false },
};

export default async function AccountPage() {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");

  return (
    <main id="contenido" className="shell account-page">
      <section className="account-card" aria-labelledby="account-title">
        <p className="eyebrow auth-eyebrow">Tu espacio Cianci</p>
        <h1 id="account-title">Mi cuenta</h1>
        <dl className="account-details">
          <div>
            <dt>Email</dt>
            <dd>{account.email}</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
