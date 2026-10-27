import type { Metadata } from "next";
import { SiteHeader } from "../components/layout/site-header";
import { SiteFooter } from "../components/layout/site-footer";
import { getSessionUser } from "../lib/auth/session";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cianci | Instituto de Danzas — Vista de diseño",
  description:
    "Propuesta visual del Instituto de Danzas Cianci. Contenido institucional en proceso de validación.",
  robots: { index: false, follow: false },
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const user = await getSessionUser();
  return (
    <html lang="es">
      <body id="inicio">
        <a className="skip-link" href="#contenido">
          Saltar al contenido
        </a>
        <SiteHeader
          authenticated={Boolean(user)}
          canAccessAdminPanel={user?.canAccessAdminPanel ?? false}
        />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
