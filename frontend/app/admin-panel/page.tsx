import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { formatArsAmount } from "../../lib/format-money";
import { getSessionUser } from "../../lib/auth/session";
import type { AdminDashboardData } from "../../lib/admin-panel/data";
import {
  AdminDashboardAccessError,
  getAdminDashboardData,
} from "../../lib/admin-panel/data";

export const metadata = {
  title: "Panel administrativo | Cianci",
  robots: { index: false, follow: false },
};

export default async function AdminPanelPage() {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");
  if (!account.canAccessAdminPanel) return <AccessDenied />;

  const dashboardResult = await loadDashboard();
  if (dashboardResult.status === "access-denied") return <AccessDenied />;
  if (dashboardResult.status === "error") return <DashboardError />;
  return <AdminDashboard dashboard={dashboardResult.dashboard} />;
}

type DashboardLoadResult =
  | { status: "loaded"; dashboard: AdminDashboardData }
  | { status: "access-denied" }
  | { status: "error" };

async function loadDashboard(): Promise<DashboardLoadResult> {
  try {
    return {
      status: "loaded",
      dashboard: await getAdminDashboardData(),
    };
  } catch (error) {
    return {
      status:
        error instanceof AdminDashboardAccessError ? "access-denied" : "error",
    };
  }
}

function AccessDenied() {
  return (
    <main id="contenido" className="shell admin-panel-page">
      <p className="eyebrow auth-eyebrow">Gestión del instituto</p>
      <h1>Panel administrativo</h1>
      <p className="admin-panel-message" role="alert">
        Tu cuenta todavía no tiene permiso para acceder a este panel. Pedile a
        la persona responsable que revise tus permisos.
      </p>
    </main>
  );
}

function DashboardError() {
  return (
    <main id="contenido" className="shell admin-panel-page">
      <p className="eyebrow auth-eyebrow">Gestión del instituto</p>
      <h1>Panel administrativo</h1>
      <p className="admin-panel-message" role="alert">
        No pudimos cargar la información en este momento. Intentá nuevamente más
        tarde.
      </p>
    </main>
  );
}

function AdminDashboard({ dashboard }: { dashboard: AdminDashboardData }) {
  const links = dashboard.links;
  const hasAttention =
    (dashboard.pendingTransfers > 0 && links.transfers) ||
    (Number(dashboard.outstandingAmount) > 0 && links.monthlyCharges);
  const navigation = [
    { label: "Inicio", href: "#inicio" },
    links.students ? { label: "Alumnos", href: "#alumnos" } : null,
    links.disciplines || links.teachers
      ? { label: "Disciplinas y horarios", href: "#disciplinas-horarios" }
      : null,
    links.monthlyCharges || links.chargeGeneration
      ? { label: "Mensualidades", href: "#mensualidades" }
      : null,
    links.transfers || links.cashPayments || links.payments || links.credits
      ? { label: "Pagos y transferencias", href: "#pagos-transferencias" }
      : null,
  ].filter((item): item is { label: string; href: string } => item !== null);

  return (
    <main id="contenido" className="shell admin-panel-page">
      <header className="admin-panel-heading" id="inicio">
        <div>
          <p className="eyebrow auth-eyebrow">Gestión del instituto</p>
          <h1>Panel administrativo</h1>
          <p>Un resumen claro de lo que pasa hoy en Cianci.</p>
        </div>
        <p className="admin-panel-date">
          {formatDashboardDate(dashboard.date)}
        </p>
      </header>

      <nav className="admin-panel-nav" aria-label="Secciones administrativas">
        {navigation.map((item) => (
          <a key={item.href} href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      <section
        className="admin-panel-attention"
        aria-labelledby="admin-attention-title"
      >
        <div>
          <p className="eyebrow auth-eyebrow">Prioridad</p>
          <h2 id="admin-attention-title">Requiere tu atención</h2>
        </div>
        {hasAttention ? (
          <ul>
            {dashboard.pendingTransfers > 0 && links.transfers ? (
              <li>
                <div>
                  <strong>
                    {dashboard.pendingTransfers === 1
                      ? "Hay una transferencia pendiente"
                      : `Hay ${dashboard.pendingTransfers} transferencias pendientes`}
                  </strong>
                  <p>
                    {links.canResolveTransfers
                      ? "Revisá los datos antes de confirmarlas o rechazarlas."
                      : "Hay transferencias que debe revisar una persona autorizada."}
                  </p>
                </div>
                <a className="admin-panel-action" href={links.transfers}>
                  {links.canResolveTransfers
                    ? "Revisar transferencias"
                    : "Consultar transferencias"}{" "}
                  <span aria-hidden="true">→</span>
                </a>
              </li>
            ) : null}
            {Number(dashboard.outstandingAmount) > 0 && links.monthlyCharges ? (
              <li>
                <div>
                  <strong>Hay mensualidades con saldo pendiente</strong>
                  <p>
                    El total pendiente es{" "}
                    {formatArsAmount(dashboard.outstandingAmount)}.
                  </p>
                </div>
                <a className="admin-panel-action" href={links.monthlyCharges}>
                  Ver mensualidades <span aria-hidden="true">→</span>
                </a>
              </li>
            ) : null}
          </ul>
        ) : (
          <p className="admin-panel-empty">
            No hay tareas pendientes para revisar en este momento.
          </p>
        )}
      </section>

      <section aria-labelledby="admin-overview-title">
        <div className="admin-panel-section-heading">
          <p className="eyebrow auth-eyebrow">Resumen</p>
          <h2 id="admin-overview-title">El instituto hoy</h2>
        </div>
        <dl className="admin-panel-metrics">
          <div>
            <dt>Alumnos activos</dt>
            <dd>{dashboard.activeStudents}</dd>
            <p>Con una inscripción vigente.</p>
          </div>
          <div>
            <dt>Pendiente de cobro</dt>
            <dd>{formatArsAmount(dashboard.outstandingAmount)}</dd>
            <p>Saldo de mensualidades emitidas, luego de pagos y ajustes.</p>
          </div>
          <div>
            <dt>Transferencias por revisar</dt>
            <dd>{dashboard.pendingTransfers}</dd>
            <p>Operaciones informadas que todavía no se resolvieron.</p>
          </div>
          <div>
            <dt>Horarios habituales hoy</dt>
            <dd>{dashboard.recurringSchedulesToday}</dd>
            <p>La cantidad no confirma que las clases se dicten.</p>
          </div>
        </dl>
      </section>

      <section
        className="admin-panel-tasks"
        aria-labelledby="admin-tasks-title"
      >
        <div className="admin-panel-section-heading">
          <p className="eyebrow auth-eyebrow">Operaciones</p>
          <h2 id="admin-tasks-title">¿Qué necesitás hacer?</h2>
        </div>
        <div className="admin-panel-task-groups">
          {links.students || links.guardians ? (
            <TaskGroup id="alumnos" title="Alumnos">
              {links.students ? (
                <TaskLink href={links.students}>
                  Gestionar alumnos e inscripciones
                </TaskLink>
              ) : null}
              {links.guardians ? (
                <TaskLink href={links.guardians}>Consultar tutores</TaskLink>
              ) : null}
            </TaskGroup>
          ) : null}
          {links.disciplines || links.teachers ? (
            <TaskGroup id="disciplinas-horarios" title="Disciplinas y horarios">
              {links.disciplines ? (
                <TaskLink href={links.disciplines}>
                  Gestionar disciplinas y horarios
                </TaskLink>
              ) : null}
              {links.teachers ? (
                <TaskLink href={links.teachers}>Consultar profesores</TaskLink>
              ) : null}
            </TaskGroup>
          ) : null}
          {links.monthlyCharges || links.chargeGeneration ? (
            <TaskGroup id="mensualidades" title="Mensualidades">
              {links.monthlyCharges ? (
                <TaskLink href={links.monthlyCharges}>
                  Consultar mensualidades y saldos
                </TaskLink>
              ) : null}
              {links.chargeGeneration ? (
                <TaskLink href={links.chargeGeneration}>
                  Generar mensualidades
                </TaskLink>
              ) : null}
            </TaskGroup>
          ) : null}
          {links.transfers ||
          links.cashPayments ||
          links.payments ||
          links.credits ? (
            <TaskGroup id="pagos-transferencias" title="Pagos y transferencias">
              {links.transfers ? (
                <TaskLink href={links.transfers}>
                  Revisar transferencias
                </TaskLink>
              ) : null}
              {links.cashPayments ? (
                <TaskLink href={links.cashPayments}>
                  Registrar pago en efectivo
                </TaskLink>
              ) : null}
              {links.payments ? (
                <TaskLink href={links.payments}>
                  Consultar pagos registrados
                </TaskLink>
              ) : null}
              {links.credits ? (
                <TaskLink href={links.credits}>
                  Consultar saldos a favor
                </TaskLink>
              ) : null}
            </TaskGroup>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function TaskGroup({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      className="admin-panel-task-group"
      aria-labelledby={`${id}-title`}
    >
      <h3 id={`${id}-title`}>{title}</h3>
      <ul>{children}</ul>
    </section>
  );
}

function TaskLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <li>
      <a href={href}>
        {children} <span aria-hidden="true">→</span>
      </a>
    </li>
  );
}

function formatDashboardDate(value: string) {
  return new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(`${value}T12:00:00-03:00`));
}
