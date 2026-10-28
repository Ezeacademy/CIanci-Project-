import { SectionHeading } from "../components/ui/section-heading";
import {
  getPublicDisciplines,
  type PublicDiscipline,
} from "../lib/academic/public-disciplines";
import styles from "../features/home/home.module.css";
import { DisciplinesSection } from "../features/home/disciplines-section";
import { Hero } from "../features/home/hero";
import { HorizontalGallery } from "../features/home/horizontal-gallery";
import { RevealOnScroll } from "../features/home/scroll-reveal";
import Link from "next/link";
import Image from "next/image";

export const dynamic = "force-dynamic";

export default async function Home() {
  let disciplines: PublicDiscipline[] = [];
  let disciplinesUnavailable = false;
  try {
    disciplines = await getPublicDisciplines();
  } catch {
    disciplinesUnavailable = true;
  }

  return (
    <main id="contenido" className={styles.home} tabIndex={-1}>
      <Hero />
      <DisciplinesSection
        disciplines={disciplines}
        unavailable={disciplinesUnavailable}
      />
      <section
        id="instituto"
        className={styles.instituteSection}
        aria-labelledby="institute-title"
      >
        <div className={`shell ${styles.instituteInner}`}>
          <RevealOnScroll className={styles.instituteText}>
            <SectionHeading
              number="02"
              label="El instituto"
              title="Un lugar para estar en movimiento."
              id="institute-title"
            />
            <p className={styles.instituteLead}>
              La danza reúne técnica, expresión y encuentro.
            </p>
            <p className={styles.instituteBody}>
              Un espacio para explorar el movimiento y encontrar una voz propia,
              en cada gesto y en cada etapa.
            </p>
            <Link className={styles.instituteLink} href="#galeria">
              Mirar la galería <span aria-hidden="true">↗</span>
            </Link>
          </RevealOnScroll>

          <RevealOnScroll className={styles.instituteVisual}>
            <figure className={styles.instituteImage} data-reveal>
              <Image
                src="/images/dance/contemporary.webp"
                alt="Bailarines adultos ensayando en un estudio luminoso"
                fill
                sizes="(max-width: 767px) 100vw, 48vw"
              />
            </figure>
          </RevealOnScroll>
        </div>
      </section>

      <section
        id="galeria"
        className={`shell ${styles.gallerySection}`}
        aria-labelledby="gallery-title"
      >
        <div className={styles.galleryHeading}>
          <SectionHeading
            number="03"
            label="Una mirada"
            title="El movimiento deja su huella."
            id="gallery-title"
          />
          <p>Una pequeña ventana visual a la danza.</p>
        </div>
        <HorizontalGallery />
      </section>
    </main>
  );
}
