import { redirect } from "next/navigation";
import type { Metadata } from "next";

import {
  AcademicSessionExpiredError,
  getAccountAcademicData,
  type StudentWithEnrollments,
} from "../../../lib/academic/data";
import {
  getAccountBillingData,
  type BillingSummary,
  type ConfirmedPaymentView,
  type MonthlyChargeView,
  type PaymentIntentView,
} from "../../../lib/billing/data";
import { getSessionUser } from "../../../lib/auth/session";
import { VerificationResendButton } from "../../../features/auth/password-reset-form";
import { formatArsAmount } from "../../../lib/format-money";

export const metadata: Metadata = {
  title: "Mi cuenta | Cianci",
  robots: { index: false, follow: false },
};

export default async function AccountPage() {
  const account = await getSessionUser();
  if (!account) redirect("/ingresar");

  let students: StudentWithEnrollments[] = [];
  let academicError = false;
  let billingError = false;
  let billing: {
    summary: BillingSummary;
    charges: MonthlyChargeView[];
    payments: ConfirmedPaymentView[];
    intents: PaymentIntentView[];
  } | null = null;
  const [academicResult, billingResult] = await Promise.allSettled([
    getAccountAcademicData(),
    getAccountBillingData(),
  ]);

  if (academicResult.status === "fulfilled") {
    students = academicResult.value;
  } else {
    if (academicResult.reason instanceof AcademicSessionExpiredError) {
      redirect("/ingresar");
    }
    academicError = true;
  }
  if (billingResult.status === "fulfilled") {
    billing = billingResult.value;
  } else {
    if (billingResult.reason instanceof AcademicSessionExpiredError) {
      redirect("/ingresar");
    }
    billingError = true;
  }

  const ownStudents = students.filter(
    (student) => student.accessType === "self",
  );
  const studentsInCare = students.filter(
    (student) => student.accessType === "guardian",
  );
  const ownEnrollments = ownStudents.flatMap((student) => student.enrollments);

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
          <div>
            <dt>Verificación del email</dt>
            <dd>{account.emailVerified ? "Verificado" : "Pendiente"}</dd>
          </div>
        </dl>
        {!account.emailVerified ? <VerificationResendButton /> : null}
      </section>

      <div className="account-academics">
        <section className="academic-section">
          <p className="eyebrow auth-eyebrow">Tu actividad en el instituto</p>
          <h2 id="academic-title">Información académica</h2>
          {academicError ? (
            <p className="academic-error" role="alert">
              No pudimos cargar tu información académica. Intentá de nuevo más
              tarde.
            </p>
          ) : students.length === 0 ? (
            <p className="academic-empty" role="status">
              Todavía no tenés información académica asociada a tu cuenta. Si
              creés que es un error, comunicate con la administración del
              instituto.
            </p>
          ) : (
            <div className="academic-sections">
              {ownStudents.length > 0 ? (
                <section aria-labelledby="own-disciplines-title">
                  <h3 id="own-disciplines-title">Mis disciplinas</h3>
                  {ownEnrollments.length === 0 ? (
                    <p className="academic-empty">
                      Todavía no tenés disciplinas activas.
                    </p>
                  ) : (
                    <ul className="academic-enrollment-list">
                      {ownEnrollments.map((enrollment) => (
                        <EnrollmentItem
                          key={enrollment.id}
                          name={enrollment.discipline.name}
                          status={enrollment.status}
                        />
                      ))}
                    </ul>
                  )}
                </section>
              ) : null}

              {studentsInCare.length > 0 ? (
                <section aria-labelledby="students-in-care-title">
                  <h3 id="students-in-care-title">Menores a mi cargo</h3>
                  <ul className="academic-student-list">
                    {studentsInCare.map((student) => (
                      <li className="academic-student" key={student.id}>
                        <h4>
                          {student.firstName} {student.lastName}
                        </h4>
                        {student.enrollments.length === 0 ? (
                          <p className="academic-empty">
                            Todavía no tiene disciplinas activas.
                          </p>
                        ) : (
                          <ul className="academic-enrollment-list">
                            {student.enrollments.map((enrollment) => (
                              <EnrollmentItem
                                key={enrollment.id}
                                name={enrollment.discipline.name}
                                status={enrollment.status}
                              />
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          )}
        </section>
      </div>

      <FinancialSection billing={billing} hasError={billingError} />
    </main>
  );
}

function FinancialSection({
  billing,
  hasError,
}: {
  billing: {
    summary: BillingSummary;
    charges: MonthlyChargeView[];
    payments: ConfirmedPaymentView[];
    intents: PaymentIntentView[];
  } | null;
  hasError: boolean;
}) {
  return (
    <section className="financial-section" aria-labelledby="financial-title">
      <p className="eyebrow auth-eyebrow">Tu cuenta en el instituto</p>
      <h2 id="financial-title">Mensualidades y pagos</h2>
      {hasError || !billing ? (
        <p className="academic-error" role="alert">
          No pudimos cargar tu información de pagos. Intentá de nuevo más tarde.
        </p>
      ) : (
        <>
          <div
            className="financial-summary"
            aria-label="Resumen de mensualidades"
          >
            <SummaryAmount
              label="Importe emitido"
              amount={billing.summary.amount}
            />
            <SummaryAmount label="Pagado" amount={billing.summary.paidAmount} />
            <SummaryAmount
              label="Saldo pendiente"
              amount={billing.summary.balance}
            />
          </div>

          <section
            className="financial-subsection"
            aria-labelledby="charges-title"
          >
            <h3 id="charges-title">Mensualidades</h3>
            {billing.charges.length === 0 ? (
              <p className="academic-empty" role="status">
                Todavía no hay mensualidades emitidas para tu cuenta.
              </p>
            ) : (
              <ul className="financial-list">
                {billing.charges.map((charge, index) => (
                  <li
                    className="financial-charge"
                    key={`${charge.firstName}-${charge.lastName}-${charge.period}-${charge.discipline}-${index}`}
                  >
                    <div>
                      <h4>{charge.discipline}</h4>
                      <p>
                        {charge.firstName} {charge.lastName} ·{" "}
                        {formatPeriod(charge.period)}
                      </p>
                    </div>
                    <dl className="financial-amounts">
                      <div>
                        <dt>Precio</dt>
                        <dd>{formatArsAmount(charge.baseAmount)}</dd>
                      </div>
                      {charge.scholarshipPercentage !== null ? (
                        <div>
                          <dt>Beca ({charge.scholarshipPercentage} %)</dt>
                          <dd>−{formatArsAmount(charge.discountAmount)}</dd>
                        </div>
                      ) : null}
                      <div>
                        <dt>Total a pagar</dt>
                        <dd>{formatArsAmount(charge.amount)}</dd>
                      </div>
                      <div>
                        <dt>Pagado</dt>
                        <dd>{formatArsAmount(charge.paidAmount)}</dd>
                      </div>
                      <div>
                        <dt>Pendiente</dt>
                        <dd>{formatArsAmount(charge.balance)}</dd>
                      </div>
                      {charge.scholarshipPercentage !== null &&
                      charge.amount === "0.00" ? (
                        <div>
                          <dt>Estado</dt>
                          <dd>Cubierta por beca</dd>
                        </div>
                      ) : null}
                    </dl>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section
            className="financial-subsection"
            aria-labelledby="transfers-title"
          >
            <h3 id="transfers-title">Transferencias informadas</h3>
            {billing.intents.length === 0 ? (
              <p className="financial-muted">
                No hay transferencias pendientes de revisión.
              </p>
            ) : (
              <ul className="financial-list">
                {billing.intents.map((intent, index) => (
                  <li
                    className="financial-activity"
                    key={`${intent.createdAt}-${intent.amount}-${intent.firstName}-${index}`}
                  >
                    <span>
                      {intent.firstName} {intent.lastName} ·{" "}
                      {formatDate(intent.createdAt)}
                    </span>
                    <span>{formatArsAmount(intent.amount)}</span>
                    <strong>
                      {intent.status === "pending"
                        ? "Pendiente de verificación"
                        : "Rechazada"}
                    </strong>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section
            className="financial-subsection"
            aria-labelledby="payments-title"
          >
            <h3 id="payments-title">Historial de pagos</h3>
            {billing.payments.length === 0 ? (
              <p className="financial-muted">
                Todavía no hay pagos confirmados.
              </p>
            ) : (
              <ul className="financial-list">
                {billing.payments.map((payment, index) => (
                  <li
                    className="financial-activity"
                    key={`${payment.receivedAt}-${payment.amount}-${payment.firstName}-${index}`}
                  >
                    <div>
                      <strong>
                        {payment.firstName} {payment.lastName} ·{" "}
                        {formatDate(payment.receivedAt)}
                      </strong>
                      <p>
                        {payment.allocations
                          .map(
                            (allocation) =>
                              `${allocation.discipline} (${formatPeriod(allocation.period)})`,
                          )
                          .join(", ")}{" "}
                        · {methodName(payment.method)}
                      </p>
                    </div>
                    <span>{formatArsAmount(payment.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  );
}

function SummaryAmount({ label, amount }: { label: string; amount: string }) {
  return (
    <div className="financial-summary-item">
      <span>{label}</span>
      <strong>{formatArsAmount(amount)}</strong>
    </div>
  );
}

function formatPeriod(period: string) {
  const [year, month] = period.split("-").map(Number);
  return new Intl.DateTimeFormat("es-AR", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, 1)));
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeZone: "America/Argentina/Buenos_Aires",
  }).format(new Date(value));
}

function methodName(method: string) {
  if (method === "cash") return "Efectivo";
  if (method === "bank_transfer") return "Transferencia bancaria";
  if (method === "mercado_pago") return "Mercado Pago";
  return "Medio de pago";
}

function EnrollmentItem({
  name,
  status,
}: {
  name: string;
  status: "active" | "history";
}) {
  return (
    <li className="academic-enrollment">
      <span>{name}</span>
      <span className="academic-enrollment-status">
        {status === "active" ? "Inscripción vigente" : "Inscripción finalizada"}
      </span>
    </li>
  );
}
