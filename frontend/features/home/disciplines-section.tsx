import { SectionHeading } from "../../components/ui/section-heading";
import { disciplineExamples } from "./home-content";

export function DisciplinesSection() {
  return (
    <section
      id="disciplinas"
      className="section-block shell"
      aria-labelledby="disciplines-title"
    >
      <div className="section-intro">
        <SectionHeading
          number="01"
          label="Disciplinas"
          title="Un lenguaje para cada movimiento."
          id="disciplines-title"
        />
        <p className="sample-note">
          <span className="sample-label">Muestra de diseño</span>Estas
          disciplinas y descripciones son ejemplos. La oferta del instituto está
          pendiente de confirmación.
        </p>
      </div>
      <ul className="discipline-list">
        {disciplineExamples.map((discipline, index) => (
          <li key={discipline.id} className="discipline-row">
            <span className="discipline-number" aria-hidden="true">
              0{index + 1}
            </span>
            <h3>{discipline.name}</h3>
            <p>{discipline.description}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
