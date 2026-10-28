"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { submitAdminAcademicRequest } from "../../lib/admin-panel/academic-client";
import { formatInstantDateTime } from "../../lib/format-date";
import { formatArsAmount } from "../../lib/format-money";
import type {
  TicketingMapSummary,
  TicketingSeatMap,
  TicketingShow,
  TicketingVenue,
} from "../../lib/admin-panel/ticketing";
import styles from "./ticketing-management.module.css";

type SeatDraft = {
  number: string;
  position: number;
  isAccessible: boolean;
  isOperational: boolean;
};
type GapDraft = { position: number; width: number; kind: "aisle" | "empty" };
type RowDraft = { label: string; seats: SeatDraft[]; gaps: GapDraft[] };
type SectionDraft = { name: string; rows: RowDraft[] };

export function TicketingHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className={styles.header}>
      <div>
        <p className="eyebrow auth-eyebrow">Gestión del instituto</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <Link className="calendar-back-link" href="/admin-panel">
        ← Volver al panel
      </Link>
    </header>
  );
}

export function ShowManagement({
  shows,
  venues,
  maps,
}: {
  shows: TicketingShow[];
  venues: TicketingVenue[];
  maps: TicketingSeatMap[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function createShow(form: FormData) {
    setSaving(true);
    setError("");
    try {
      await submitAdminAcademicRequest(
        "/api/v1/admin/ticketing/shows",
        "POST",
        {
          title: form.get("title"),
          description: form.get("description"),
          imageUrl: form.get("imageUrl"),
        },
      );
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo guardar el espectáculo.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className={styles.pageContent}>
      <section className={styles.panel}>
        <div className={styles.panelHeading}>
          <h2>Nuevo espectáculo</h2>
          <Link
            className="admin-student-button is-secondary"
            href="/admin-panel/recintos"
          >
            Gestionar recintos
          </Link>
        </div>
        <form action={createShow} className={styles.formGrid}>
          <label>
            Título
            <input name="title" required maxLength={180} />
          </label>
          <label>
            Imagen (URL HTTPS)
            <input name="imageUrl" type="url" placeholder="https://…" />
          </label>
          <label className={styles.wide}>
            Descripción
            <textarea name="description" rows={3} />
          </label>
          <button disabled={saving}>
            {saving ? "Guardando…" : "Crear espectáculo"}
          </button>
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
        </form>
      </section>
      <section className={styles.panel}>
        <h2>Espectáculos</h2>
        {shows.length ? (
          <ul className={styles.showList}>
            {shows.map((show) => (
              <li key={show.id}>
                <div className={styles.showItemHeader}>
                  <div className={styles.showItemInfo}>
                    <strong>{show.title}</strong>
                    <span>
                      {statusLabel(show.status)} · {show.functions.length}{" "}
                      {show.functions.length === 1 ? "función" : "funciones"}
                    </span>
                    {show.description ? <span>{show.description}</span> : null}
                  </div>
                  <div className={styles.showItemActions}>
                    <ShowStatusForm show={show} />
                    {show.imageUrl ? (
                      <a href={show.imageUrl} target="_blank" rel="noreferrer">
                        Ver imagen
                      </a>
                    ) : null}
                    <CreateFunctionForm show={show} maps={maps} />
                  </div>
                </div>
                {show.functions.length ? (
                  <ul className={styles.functionList}>
                    {show.functions.map((fn) => (
                      <li key={fn.id}>
                        <span>
                          {formatInstantDateTime(fn.startsAt)} · {fn.venue} ·{" "}
                          {fn.capacity} butacas
                        </span>
                        <span>
                          {fn.sectionPrices.length
                            ? "Precios: "
                            : "Sin precios definidos"}
                          {fn.sectionPrices
                            .map(
                              (price) =>
                                `${price.section}: ${formatArsAmount(price.amount)}`,
                            )
                            .join(" · ")}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p>
            Todavía no hay espectáculos. Podés crear el primero desde este
            formulario.
          </p>
        )}
        <h3>Recintos disponibles</h3>
        {venues.length ? (
          <ul>
            {venues.map((venue) => (
              <li key={venue.id}>
                <Link
                  className={styles.inlineLink}
                  href={`/admin-panel/recintos/${venue.id}`}
                >
                  {venue.name}
                </Link>{" "}
                · {venue.versions.length} versiones de mapa
              </li>
            ))}
          </ul>
        ) : (
          <p>Primero configurá un recinto y su mapa de butacas.</p>
        )}
      </section>
    </div>
  );
}

function ShowStatusForm({ show }: { show: TicketingShow }) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function save(form: FormData) {
    setSaving(true);
    setError("");
    try {
      await submitAdminAcademicRequest(
        `/api/v1/admin/ticketing/shows/${show.id}`,
        "PATCH",
        {
          title: form.get("title"),
          description: form.get("description"),
          imageUrl: form.get("imageUrl"),
          status: form.get("status"),
        },
      );
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudieron guardar los cambios.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <details className={styles.inlineEditor}>
      <summary>Editar espectáculo</summary>
      <form action={save} className={styles.formGrid}>
        <label>
          Título
          <input name="title" required defaultValue={show.title} />
        </label>
        <label>
          Imagen HTTPS
          <input name="imageUrl" type="url" defaultValue={show.imageUrl} />
        </label>
        <label>
          Estado
          <select name="status" defaultValue={show.status}>
            <option value="draft">Borrador</option>
            <option value="published">Publicado</option>
            <option value="archived">Archivado</option>
          </select>
        </label>
        <label className={styles.wide}>
          Descripción
          <textarea
            name="description"
            rows={2}
            defaultValue={show.description}
          />
        </label>
        <button disabled={saving}>
          {saving ? "Guardando…" : "Guardar cambios"}
        </button>
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
      </form>
    </details>
  );
}

function CreateFunctionForm({
  show,
  maps,
}: {
  show: TicketingShow;
  maps: TicketingSeatMap[];
}) {
  const router = useRouter();
  const [mapId, setMapId] = useState(String(maps[0]?.id ?? ""));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selectedMap = maps.find((map) => String(map.id) === mapId);
  async function create(form: FormData) {
    setSaving(true);
    setError("");
    try {
      const sectionPrices = (selectedMap?.sections ?? []).map((section) => ({
        sectionId: section.id,
        amount: form.get(`price-${section.id}`),
      }));
      await submitAdminAcademicRequest(
        `/api/v1/admin/ticketing/shows/${show.id}/functions`,
        "POST",
        {
          mapVersionId: Number(form.get("mapVersionId")),
          startsAt: form.get("startsAt"),
          sectionPrices,
        },
      );
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo guardar la función.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <details className={styles.inlineEditor}>
      <summary>Agregar función</summary>
      {maps.length ? (
        <form action={create} className={styles.formGrid}>
          <label>
            Recinto y mapa
            <select
              name="mapVersionId"
              value={mapId}
              onChange={(event) => setMapId(event.target.value)}
            >
              {maps.map((map) => (
                <option key={map.id} value={map.id}>
                  {map.venue} · versión {map.version} · {map.capacity} butacas
                </option>
              ))}
            </select>
          </label>
          <label>
            Fecha y hora
            <input type="datetime-local" name="startsAt" required />
          </label>
          {selectedMap?.sections.map((section) => (
            <label key={section.id}>
              Precio · {section.name} (ARS)
              <input
                name={`price-${section.id}`}
                type="number"
                min="0"
                step="0.01"
                required
              />
            </label>
          ))}
          <button disabled={saving}>
            {saving ? "Guardando…" : "Guardar función"}
          </button>
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
        </form>
      ) : (
        <p>
          Para agregar una función, primero configurá un recinto con al menos un
          mapa.
        </p>
      )}
    </details>
  );
}

export function VenueManagement({ venues }: { venues: TicketingVenue[] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function createVenue(form: FormData) {
    setSaving(true);
    setError("");
    try {
      await submitAdminAcademicRequest(
        "/api/v1/admin/ticketing/venues",
        "POST",
        { name: form.get("name"), location: form.get("location") },
      );
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo guardar el recinto.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className={styles.pageContent}>
      <section className={styles.panel}>
        <h2>Agregar recinto</h2>
        <form action={createVenue} className={styles.formGrid}>
          <label>
            Nombre
            <input name="name" required maxLength={160} />
          </label>
          <label>
            Ubicación
            <input name="location" maxLength={240} />
          </label>
          <button disabled={saving}>
            {saving ? "Guardando…" : "Crear recinto"}
          </button>
          {error ? (
            <p role="alert" className={styles.error}>
              {error}
            </p>
          ) : null}
        </form>
      </section>
      <section className={styles.panel}>
        <h2>Recintos y mapas</h2>
        {venues.length ? (
          <ul className={styles.venueList}>
            {venues.map((venue) => (
              <li key={venue.id}>
                <div>
                  <h3>{venue.name}</h3>
                  <p>{venue.location || "Ubicación sin especificar"}</p>
                </div>
                <EditVenueForm venue={venue} />
                <div>
                  <span>
                    {venue.versions.length}{" "}
                    {venue.versions.length === 1 ? "versión" : "versiones"}
                  </span>
                  <Link
                    className="admin-student-button is-secondary"
                    href={`/admin-panel/recintos/${venue.id}`}
                  >
                    Configurar mapa
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p>
            Creá un recinto para comenzar a diseñar una distribución de butacas.
          </p>
        )}
      </section>
    </div>
  );
}

function EditVenueForm({ venue }: { venue: TicketingVenue }) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function save(form: FormData) {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await submitAdminAcademicRequest(
        `/api/v1/admin/ticketing/venues/${venue.id}`,
        "PATCH",
        { name: form.get("name"), location: form.get("location") },
      );
      setMessage("Recinto actualizado.");
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo actualizar el recinto.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <details className={styles.inlineEditor}>
      <summary>Editar recinto</summary>
      <form action={save} className={styles.formGrid}>
        <label>
          Nombre
          <input name="name" required defaultValue={venue.name} />
        </label>
        <label>
          Ubicación
          <input name="location" defaultValue={venue.location} />
        </label>
        <button disabled={saving}>
          {saving ? "Guardando…" : "Guardar cambios"}
        </button>
        {message ? (
          <p role="status" className={styles.success}>
            {message}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        ) : null}
      </form>
    </details>
  );
}

export function SeatMapEditor({
  venue,
  versions,
  initialMap,
}: {
  venue: { id: number; name: string; location: string };
  versions: TicketingMapSummary[];
  initialMap?: TicketingSeatMap;
}) {
  const router = useRouter();
  const [sections, setSections] = useState<SectionDraft[]>(
    initialMap?.sections.map((section) => ({
      name: section.name,
      rows: section.rows.map((row) => ({
        label: row.label,
        seats: row.seats.map((seat) => ({
          number: seat.number,
          position: seat.position,
          isAccessible: seat.isAccessible,
          isOperational: seat.isOperational,
        })),
        gaps: row.gaps.map((gap) => ({ ...gap })),
      })),
    })) ?? [
      {
        name: "Platea",
        rows: [
          {
            label: "A",
            seats: Array.from({ length: 12 }, (_, index) => ({
              number: String(index + 1),
              position: index + 1,
              isAccessible: false,
              isOperational: true,
            })),
            gaps: [],
          },
        ],
      },
    ],
  );
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const frozen = initialMap?.isFrozen ?? false;
  const editorSections = () =>
    sections.map((section, sectionIndex) => ({
      name: section.name,
      sortOrder: sectionIndex,
      rows: section.rows.map((row, rowIndex) => ({
        label: row.label,
        sortOrder: rowIndex,
        seats: row.seats,
        gaps: row.gaps,
      })),
    }));
  async function saveMap() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const body = { sections: editorSections() };
      if (initialMap)
        await submitAdminAcademicRequest(
          `/api/v1/admin/ticketing/maps/${initialMap.id}`,
          "PUT",
          body,
        );
      else {
        const created = await submitAdminAcademicRequest<TicketingSeatMap>(
          `/api/v1/admin/ticketing/venues/${venue.id}/maps`,
          "POST",
          body,
        );
        router.push(`/admin-panel/recintos/${venue.id}?map=${created.id}`);
      }
      setMessage(
        "Mapa guardado. El sistema calculó la capacidad desde las butacas operativas.",
      );
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo guardar el mapa.",
      );
    } finally {
      setSaving(false);
    }
  }
  async function newVersion(versionId: number) {
    setSaving(true);
    setError("");
    try {
      const created = await submitAdminAcademicRequest<TicketingSeatMap>(
        `/api/v1/admin/ticketing/venues/${venue.id}/maps`,
        "POST",
        { copyVersionId: versionId },
      );
      setMessage("Se creó una nueva versión editable del mapa.");
      router.push(`/admin-panel/recintos/${venue.id}?map=${created.id}`);
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo crear la versión.",
      );
    } finally {
      setSaving(false);
    }
  }
  function updateSection(index: number, next: SectionDraft) {
    setSections((current) =>
      current.map((section, item) => (item === index ? next : section)),
    );
  }
  function updateSeat(
    sectionIndex: number,
    rowIndex: number,
    oldPosition: number,
    changes: Partial<SeatDraft>,
  ) {
    setSections((current) =>
      current.map((section, currentSection) =>
        currentSection !== sectionIndex
          ? section
          : {
              ...section,
              rows: section.rows.map((row, currentRow) =>
                currentRow !== rowIndex
                  ? row
                  : {
                      ...row,
                      seats: row.seats.map((seat) =>
                        seat.position === oldPosition
                          ? { ...seat, ...changes }
                          : seat,
                      ),
                    },
              ),
            },
      ),
    );
  }
  function updateGap(
    sectionIndex: number,
    rowIndex: number,
    oldPosition: number,
    changes: Partial<GapDraft>,
  ) {
    setSections((current) =>
      current.map((section, currentSection) =>
        currentSection !== sectionIndex
          ? section
          : {
              ...section,
              rows: section.rows.map((row, currentRow) =>
                currentRow !== rowIndex
                  ? row
                  : {
                      ...row,
                      gaps: row.gaps.map((gap) =>
                        gap.position === oldPosition
                          ? { ...gap, ...changes }
                          : gap,
                      ),
                    },
              ),
            },
      ),
    );
  }
  return (
    <div className={styles.pageContent}>
      <section className={styles.panel}>
        <div className={styles.panelHeading}>
          <div>
            <p className="eyebrow auth-eyebrow">{venue.name}</p>
            <h2>
              {initialMap
                ? `Mapa · versión ${initialMap.version}`
                : "Nueva versión de mapa"}
            </h2>
            <p>{venue.location}</p>
          </div>
          <span className={styles.capacity}>
            {initialMap?.capacity ?? capacityFromDraft(sections)} butacas
            operativas
          </span>
        </div>
        {frozen ? (
          <p className={styles.notice}>
            Esta versión ya está asociada a una función y quedó protegida. Creá
            otra versión para cambiar su estructura.
          </p>
        ) : null}
        {!frozen ? (
          <>
            {sections.map((section, sectionIndex) => (
              <fieldset
                className={styles.sectionEditor}
                key={`section-${sectionIndex}`}
              >
                <legend>Sector {sectionIndex + 1}</legend>
                <div className={styles.formGrid}>
                  <label>
                    Nombre del sector
                    <input
                      value={section.name}
                      onChange={(event) =>
                        updateSection(sectionIndex, {
                          ...section,
                          name: event.target.value,
                        })
                      }
                    />
                  </label>
                  <button
                    type="button"
                    className="admin-student-button is-secondary"
                    onClick={() =>
                      setSections((current) =>
                        current.filter((_, index) => index !== sectionIndex),
                      )
                    }
                  >
                    Quitar sector
                  </button>
                </div>
                {section.rows.map((row, rowIndex) => (
                  <div
                    className={styles.rowEditor}
                    key={`row-${sectionIndex}-${rowIndex}`}
                  >
                    <label>
                      Fila
                      <input
                        value={row.label}
                        onChange={(event) => {
                          const rows = [...section.rows];
                          rows[rowIndex] = {
                            ...row,
                            label: event.target.value,
                          };
                          updateSection(sectionIndex, { ...section, rows });
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() =>
                        updateSection(sectionIndex, {
                          ...section,
                          rows: section.rows.filter(
                            (_, index) => index !== rowIndex,
                          ),
                        })
                      }
                    >
                      Quitar fila
                    </button>
                    <div
                      className={styles.seatEditor}
                      aria-label={`Distribución de la fila ${row.label}`}
                    >
                      {[
                        ...row.seats.map((seat) => ({
                          type: "seat" as const,
                          position: seat.position,
                          data: seat,
                        })),
                        ...row.gaps.map((gap) => ({
                          type: "gap" as const,
                          position: gap.position,
                          data: gap,
                        })),
                      ]
                        .sort((left, right) => left.position - right.position)
                        .map((item) =>
                          item.type === "seat" ? (
                            <div
                              className={`${styles.seatControl} ${item.data.isOperational ? "" : styles.seatDisabled}`}
                              key={`seat-${item.position}`}
                            >
                              <label>
                                Butaca
                                <input
                                  aria-label={`Número de butaca, fila ${row.label}`}
                                  value={item.data.number}
                                  onChange={(event) =>
                                    updateSeat(
                                      sectionIndex,
                                      rowIndex,
                                      item.position,
                                      { number: event.target.value },
                                    )
                                  }
                                />
                              </label>
                              <label>
                                Posición
                                <input
                                  aria-label={`Posición de butaca ${item.data.number}`}
                                  type="number"
                                  min={1}
                                  value={item.position}
                                  onChange={(event) =>
                                    updateSeat(
                                      sectionIndex,
                                      rowIndex,
                                      item.position,
                                      { position: Number(event.target.value) },
                                    )
                                  }
                                />
                              </label>
                              <label className={styles.checkLabel}>
                                <input
                                  type="checkbox"
                                  checked={item.data.isAccessible}
                                  onChange={(event) =>
                                    updateSeat(
                                      sectionIndex,
                                      rowIndex,
                                      item.position,
                                      { isAccessible: event.target.checked },
                                    )
                                  }
                                />
                                Accesible
                              </label>
                              <label className={styles.checkLabel}>
                                <input
                                  type="checkbox"
                                  checked={item.data.isOperational}
                                  onChange={(event) =>
                                    updateSeat(
                                      sectionIndex,
                                      rowIndex,
                                      item.position,
                                      { isOperational: event.target.checked },
                                    )
                                  }
                                />
                                Operativa
                              </label>
                            </div>
                          ) : (
                            <div
                              className={styles.gapControl}
                              key={`gap-${item.position}`}
                            >
                              <label>
                                {item.data.kind === "aisle"
                                  ? "Pasillo"
                                  : "Espacio"}
                                <input
                                  type="number"
                                  min={1}
                                  value={item.position}
                                  onChange={(event) =>
                                    updateGap(
                                      sectionIndex,
                                      rowIndex,
                                      item.position,
                                      { position: Number(event.target.value) },
                                    )
                                  }
                                />
                              </label>
                              <label>
                                Ancho
                                <input
                                  type="number"
                                  min={1}
                                  max={50}
                                  value={item.data.width}
                                  onChange={(event) =>
                                    updateGap(
                                      sectionIndex,
                                      rowIndex,
                                      item.position,
                                      {
                                        width: Math.min(
                                          50,
                                          Math.max(
                                            1,
                                            Number(event.target.value),
                                          ),
                                        ),
                                      },
                                    )
                                  }
                                />
                              </label>
                              <button
                                type="button"
                                aria-label="Quitar pasillo o espacio"
                                onClick={() =>
                                  updateSection(sectionIndex, {
                                    ...section,
                                    rows: section.rows.map((current, index) =>
                                      index === rowIndex
                                        ? {
                                            ...current,
                                            gaps: current.gaps.filter(
                                              (gap) =>
                                                gap.position !== item.position,
                                            ),
                                          }
                                        : current,
                                    ),
                                  })
                                }
                              >
                                Quitar
                              </button>
                            </div>
                          ),
                        )}
                    </div>
                    <div className={styles.rowActions}>
                      <button
                        type="button"
                        className="admin-student-button is-secondary"
                        onClick={() =>
                          updateSection(sectionIndex, {
                            ...section,
                            rows: section.rows.map((current, index) =>
                              index === rowIndex
                                ? {
                                    ...current,
                                    seats: [
                                      ...current.seats,
                                      {
                                        number: String(
                                          current.seats.length + 1,
                                        ),
                                        position: nextPosition(current),
                                        isAccessible: false,
                                        isOperational: true,
                                      },
                                    ],
                                  }
                                : current,
                            ),
                          })
                        }
                      >
                        Agregar butaca
                      </button>
                      <button
                        type="button"
                        className="admin-student-button is-secondary"
                        onClick={() =>
                          updateSection(sectionIndex, {
                            ...section,
                            rows: section.rows.map((current, index) =>
                              index === rowIndex
                                ? {
                                    ...current,
                                    gaps: [
                                      ...current.gaps,
                                      {
                                        position: nextPosition(current),
                                        width: 1,
                                        kind: "aisle",
                                      },
                                    ],
                                  }
                                : current,
                            ),
                          })
                        }
                      >
                        Agregar pasillo
                      </button>
                      <button
                        type="button"
                        className="admin-student-button is-secondary"
                        onClick={() =>
                          updateSection(sectionIndex, {
                            ...section,
                            rows: section.rows.map((current, index) =>
                              index === rowIndex
                                ? {
                                    ...current,
                                    gaps: [
                                      ...current.gaps,
                                      {
                                        position: nextPosition(current),
                                        width: 1,
                                        kind: "empty",
                                      },
                                    ],
                                  }
                                : current,
                            ),
                          })
                        }
                      >
                        Agregar espacio
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="admin-student-button is-secondary"
                  onClick={() =>
                    updateSection(sectionIndex, {
                      ...section,
                      rows: [
                        ...section.rows,
                        defaultRow(
                          String.fromCharCode(65 + section.rows.length),
                          10,
                        ),
                      ],
                    })
                  }
                >
                  Agregar fila
                </button>
              </fieldset>
            ))}
            <button
              type="button"
              className="admin-student-button is-secondary"
              onClick={() =>
                setSections((current) => [
                  ...current,
                  {
                    name: `Sector ${current.length + 1}`,
                    rows: [defaultRow("A", 10)],
                  },
                ])
              }
            >
              Agregar sector
            </button>
            <div className={styles.stage}>ESCENARIO</div>
            <button
              type="button"
              disabled={
                saving ||
                sections.length === 0 ||
                sections.some(
                  (section) => !section.name.trim() || !section.rows.length,
                )
              }
              onClick={saveMap}
            >
              {saving ? "Guardando…" : "Guardar mapa"}
            </button>
          </>
        ) : null}
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        {message ? (
          <p className={styles.success} role="status">
            {message}
          </p>
        ) : null}
      </section>
      <section className={styles.panel}>
        <h2>Versiones guardadas</h2>
        {versions.length ? (
          <ul className={styles.versionList}>
            {versions.map((version) => (
              <li key={version.id}>
                <Link
                  href={`/admin-panel/recintos/${venue.id}?map=${version.id}`}
                >
                  Versión {version.version} · {version.capacity} butacas
                </Link>
                {version.isFrozen ? " · Asociada a función" : " · Editable"}
                <button
                  type="button"
                  onClick={() => newVersion(version.id)}
                  disabled={saving}
                >
                  Crear nueva versión a partir de esta
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p>Este recinto todavía no tiene mapas.</p>
        )}
      </section>
    </div>
  );
}

function capacityFromDraft(sections: SectionDraft[]) {
  return sections.reduce(
    (total, section) =>
      total +
      section.rows.reduce(
        (sum, row) =>
          sum + row.seats.filter((seat) => seat.isOperational).length,
        0,
      ),
    0,
  );
}
function defaultRow(label: string, count: number): RowDraft {
  return {
    label,
    gaps: [],
    seats: Array.from({ length: count }, (_, index) => ({
      number: String(index + 1),
      position: index + 1,
      isAccessible: false,
      isOperational: true,
    })),
  };
}
function nextPosition(row: RowDraft) {
  return (
    Math.max(
      0,
      ...row.seats.map((seat) => seat.position),
      ...row.gaps.map((gap) => gap.position + gap.width - 1),
    ) + 1
  );
}
function statusLabel(status: TicketingShow["status"]) {
  return status === "published"
    ? "Publicado"
    : status === "archived"
      ? "Archivado"
      : "Borrador";
}
