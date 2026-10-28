import Image from "next/image";
import Link from "next/link";

import styles from "./home.module.css";

export function Hero() {
  return (
    <section className={styles.hero} aria-labelledby="hero-title">
      <Image
        src="/images/dance/hero.webp"
        alt="Bailarines adultos en una composición de danza contemporánea"
        fill
        preload
        sizes="100vw"
        className={styles.heroImage}
      />
      <div className={styles.heroShade} aria-hidden="true" />
      <div className={`shell ${styles.heroContent}`}>
        <div className={styles.heroTopline}>
          <p className="eyebrow">Instituto de Danzas Cianci</p>
          <span>Una expresión. Infinitas posibilidades.</span>
        </div>
        <div className={styles.heroCopy}>
          <p className={styles.heroKicker}>Danza · Arte · Expresión</p>
          <h1 id="hero-title" aria-label="El cuerpo en movimiento">
            <span className={styles.heroTitleLine}>El cuerpo</span>
            <span
              className={`${styles.heroTitleLine} ${styles.heroTitleLineSecond}`}
            >
              <em>en movimiento.</em>
            </span>
          </h1>
          <p className={styles.heroDescription}>
            Un lenguaje propio para explorar, crear y compartir.
          </p>
          <Link className={styles.heroCta} href="#disciplinas">
            Explorar disciplinas <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </div>
    </section>
  );
}
