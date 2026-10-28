import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { getSessionUser } from "../../../lib/auth/session";

export const metadata = {
  title: "Alumnos | Panel administrativo | Cianci",
  robots: { index: false, follow: false },
};

export default async function AdminStudentsLayout({
  children,
}: {
  children: ReactNode;
}) {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");
  return children;
}
