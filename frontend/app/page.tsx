import { SectionHeading } from "../components/ui/section-heading";
import { DisciplinesSection } from "../features/home/disciplines-section";
import { Hero } from "../features/home/hero";

export default function Home() {
  return (
    <main id="contenido" tabIndex={-1}>
      <Hero />
      <DisciplinesSection />
      <section
        id="instituto"
        className="institute-section"
        aria-labelledby="institute-title"
      >
        <div className="shell institute-inner">
          <SectionHeading
            number="02"
            label="El instituto"
            title="La danza, en el centro."
            id="institute-title"
          />
          <div className="institute-copy">
            <p className="editorial-copy">
              Un espacio para el arte.
              <br />
              Una identidad en movimiento.
            </p>
            <p className="institute-note">
              Presentación visual de Cianci. Próximamente, su historia y
              propuesta institucional con información validada por el instituto.
            </p>
            <a className="text-link" href="#disciplinas">
              Explorar la propuesta visual <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
