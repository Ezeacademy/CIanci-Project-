export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <div>
          <p className="footer-name">Cianci.</p>
          <p className="eyebrow">Instituto de Danzas</p>
        </div>
        <p className="footer-note">
          Vista de diseño · Identidad y contenido sujetos a validación
          institucional.
        </p>
        <a className="text-link" href="#inicio">
          Volver al inicio <span aria-hidden="true">↑</span>
        </a>
      </div>
    </footer>
  );
}
