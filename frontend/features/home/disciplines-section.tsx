import { SectionHeading } from "../../components/ui/section-heading";

import type { PublicDiscipline } from "../../lib/academic/public-disciplines";
import { DisciplineCoverflow } from "./discipline-coverflow";
import styles from "./home.module.css";

export function DisciplinesSection({
  disciplines,
  unavailable,
}: {
  disciplines: PublicDiscipline[];
  unavailable: boolean;
}) {
  return (
    <section
      id="disciplinas"
      className={`shell ${styles.disciplinesSection}`}
      aria-labelledby="disciplines-title"
    >
      <div className={styles.disciplinesIntro}>
        <SectionHeading
          number="01"
          label="Disciplinas"
          title="Encontrá tu manera de moverte."
          id="disciplines-title"
        />
      </div>
      {unavailable ? (
        <p className={styles.disciplineState} role="status">
          La información de disciplinas no está disponible en este momento.
          Volvé a intentar más tarde.
        </p>
      ) : disciplines.length ? (
        <DisciplineCoverflow disciplines={disciplines} />
      ) : (
        <p className={styles.disciplineState} role="status">
          Estamos preparando la próxima propuesta de disciplinas.
        </p>
      )}
    </section>
  );
}
