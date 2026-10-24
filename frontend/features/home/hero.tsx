export function Hero() {
  return (
    <section className="hero shell" aria-labelledby="hero-title">
      <div className="hero-topline">
        <p className="eyebrow">Instituto de Danzas Cianci</p>
        <span className="edition">Una expresión. Infinitas posibilidades.</span>
      </div>
      <div className="hero-body">
        <h1 id="hero-title">
          El arte de
          <br />
          <em>estar en</em>
          <br />
          movimiento<span className="hero-period">.</span>
        </h1>
        <div className="hero-aside">
          <span className="hero-rule" aria-hidden="true" />
          <p>
            La danza como lenguaje.
            <br />
            El movimiento como expresión.
          </p>
          <a className="button-link" href="#disciplinas">
            Explorar disciplinas <span aria-hidden="true">↗</span>
          </a>
          <a className="text-link" href="#instituto">
            Conocer el instituto <span aria-hidden="true">↓</span>
          </a>
        </div>
      </div>
      <div className="hero-bottom">
        <span className="eyebrow">Cuerpo · Arte · Expresión</span>
        <span aria-hidden="true">↓</span>
      </div>
    </section>
  );
}
