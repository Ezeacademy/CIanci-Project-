"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import styles from "./public-error-state.module.css";

type PublicErrorStateProps = {
  title?: string;
  message?: string;
  onRetry?: () => void;
};

export function PublicErrorState({
  title = "No pudimos cargar esta página",
  message = "Hubo un problema momentáneo. Podés intentarlo nuevamente o volver al inicio.",
  onRetry,
}: PublicErrorStateProps) {
  const router = useRouter();

  return (
    <main id="contenido" className={`shell ${styles.errorPage}`}>
      <section className={styles.errorCard} role="alert" aria-live="assertive">
        <span className={styles.mark} aria-hidden="true">
          !
        </span>
        <p className="eyebrow">CIANCI · UN MOMENTO</p>
        <h1>{title}</h1>
        <p className={styles.message}>{message}</p>
        <div className={styles.actions}>
          <button
            className={styles.retryButton}
            type="button"
            onClick={onRetry ?? (() => router.refresh())}
          >
            Reintentar
          </button>
          <Link className={styles.homeLink} href="/">
            Volver al inicio
          </Link>
        </div>
      </section>
    </main>
  );
}
