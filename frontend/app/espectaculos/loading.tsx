import styles from "../../features/tickets/public-ticketing.module.css";

export default function ShowsLoading() {
  return (
    <main id="contenido" className={`shell ${styles.page}`} aria-busy="true">
      <div className={styles.loadingHeading}>
        <span className={styles.skeletonLine} />
        <span className={`${styles.skeletonLine} ${styles.skeletonTitle}`} />
        <span className={`${styles.skeletonLine} ${styles.skeletonCopy}`} />
      </div>
      <p className={styles.loadingMessage} role="status">
        Cargando espectáculos…
      </p>
    </main>
  );
}
