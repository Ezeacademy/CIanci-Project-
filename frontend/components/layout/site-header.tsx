export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <a className="wordmark" href="#inicio" aria-label="Cianci — inicio">
          <span className="wordmark-name">
            Cianci<span aria-hidden="true">.</span>
          </span>
          <span className="wordmark-caption">Instituto de Danzas</span>
        </a>
        <nav aria-label="Navegación principal" className="site-nav">
          <a href="#instituto">El instituto</a>
          <a href="#disciplinas">
            Disciplinas <span aria-hidden="true">↗</span>
          </a>
        </nav>
      </div>
    </header>
  );
}
