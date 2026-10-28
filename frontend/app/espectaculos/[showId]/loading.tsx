import styles from "../../../features/tickets/public-ticketing.module.css";

export default function ShowLoading() {
  return (
    <main id="contenido" className={`shell ${styles.page}`} aria-busy="true">
      <p className={styles.loadingMessage} role="status">
        Cargando espectáculo…
      </p>
    </main>
  );
}
