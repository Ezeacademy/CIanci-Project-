import styles from "./monthly-charges.module.css";

export default function AdminMonthlyChargesLoading() {
  return (
    <main id="contenido" className="shell admin-panel-page" aria-busy="true">
      <p className="eyebrow auth-eyebrow">Gestión financiera</p>
      <h1>Mensualidades</h1>
      <p className={styles.message} role="status">
        Cargando mensualidades…
      </p>
    </main>
  );
}
