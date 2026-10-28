"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { submitAdminAcademicRequest } from "../../lib/admin-panel/academic-client";
import {
  formatInstantDateTime,
  parseArgentineDate,
} from "../../lib/format-date";
import { formatArsAmount } from "../../lib/format-money";
import type {
  TicketingMapSummary,
  TicketingSeatMap,
  TicketingShow,
  TicketingVenue,
} from "../../lib/admin-panel/ticketing";
import { DateField } from "./date-field";
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
  const [openEditors, setOpenEditors] = useState<Record<number, string>>({});
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
                    <div className={styles.showStatusLine}>
                      <StatusBadge status={show.status} />
                      <span>
                        {show.functions.length}{" "}
                        {show.functions.length === 1 ? "función" : "funciones"}
                      </span>
                    </div>
                    {show.description ? <span>{show.description}</span> : null}
                  </div>
                  {show.imageUrl ? (
                    <a href={show.imageUrl} target="_blank" rel="noreferrer">
                      Ver imagen
                    </a>
                  ) : null}
                </div>
                <div className={styles.showManagementActions}>
                  <ShowStatusForm
                    show={show}
                    isOpen={openEditors[show.id] === "show-edit"}
                    onToggle={() =>
                      setOpenEditors((current) => {
                        const next = { ...current };
                        if (next[show.id] === "show-edit") delete next[show.id];
                        else next[show.id] = "show-edit";
                        return next;
                      })
                    }
                  />
                  <CreateFunctionForm
                    show={show}
                    maps={maps}
                    isOpen={openEditors[show.id] === "function-create"}
                    onToggle={() =>
                      setOpenEditors((current) => {
                        const next = { ...current };
                        if (next[show.id] === "function-create")
                          delete next[show.id];
                        else next[show.id] = "function-create";
                        return next;
                      })
                    }
                  />
                  {show.canDelete ? (
                    <DeleteTicketingRecordButton
                      endpoint={`/api/v1/admin/ticketing/shows/${show.id}`}
                      confirmation={`¿Eliminar el espectáculo «${show.title}»? No se puede deshacer. Si tiene funciones, el sistema lo conservará y te explicará por qué.`}
                      disabledReason={
                        show.functions.length
                          ? "Este espectáculo tiene funciones. Archivarlo conserva el historial."
                          : undefined
                      }
                    />
                  ) : null}
                </div>
                {show.functions.length ? (
                  <ul className={styles.functionList}>
                    {show.functions.map((fn) => {
                      const mapVersion = maps.find(
                        (map) => map.id === fn.mapVersionId,
                      );
                      return (
                        <li key={fn.id}>
                          <div className={styles.functionSummaryHeader}>
                            <strong>
                              {formatInstantDateTime(fn.startsAt)}
                            </strong>
                            <span>{fn.capacity} butacas</span>
                          </div>
                          <dl className={styles.functionSummaryGrid}>
                            <div>
                              <dt>Recinto</dt>
                              <dd>{fn.venue}</dd>
                            </div>
                            <div>
                              <dt>Mapa asociado</dt>
                              <dd>
                                {mapVersion
                                  ? `Versión ${mapVersion.version}`
                                  : "Versión no disponible"}
                              </dd>
                            </div>
                            <div className={styles.functionPrices}>
                              <dt>Precios por sector</dt>
                              <dd>
                                {fn.sectionPrices.length ? (
                                  <ul>
                                    {fn.sectionPrices.map((price) => (
                                      <li key={price.section}>
                                        {price.section}:{" "}
                                        {formatArsAmount(price.amount)}
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  "Sin precios definidos"
                                )}
                              </dd>
                            </div>
                          </dl>
                          <FunctionEditForm
                            key={`${fn.id}:${fn.startsAt}:${fn.sectionPrices.map((price) => `${price.sectionId}-${price.amount}`).join(",")}`}
                            fn={fn}
                            map={mapVersion}
                            isOpen={
                              openEditors[show.id] === `function-edit-${fn.id}`
                            }
                            onToggle={() =>
                              setOpenEditors((current) => {
                                const next = { ...current };
                                if (
                                  next[show.id] === `function-edit-${fn.id}`
                                ) {
                                  delete next[show.id];
                                } else {
                                  next[show.id] = `function-edit-${fn.id}`;
                                }
                                return next;
                              })
                            }
                          />
                          {fn.canDelete ? (
                            <DeleteTicketingRecordButton
                              endpoint={`/api/v1/admin/ticketing/functions/${fn.id}`}
                              confirmation={`¿Eliminar la función del ${formatInstantDateTime(fn.startsAt)}? Se quitarán también sus precios configurados. Si hay reservas, ventas o entradas, la eliminación se rechazará.`}
                            />
                          ) : null}
                        </li>
                      );
                    })}
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

function ShowStatusForm({
  show,
  isOpen,
  onToggle,
}: {
  show: TicketingShow;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function save(form: FormData) {
    setSaving(true);
    setError("");
    setMessage("");
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
      setMessage("Espectáculo actualizado.");
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
    <details className={styles.inlineEditor} open={isOpen}>
      <summary
        onClick={(event) => {
          event.preventDefault();
          onToggle();
        }}
      >
        <span>Editar espectáculo</span>
        <span className={styles.disclosureIcon} aria-hidden="true" />
      </summary>
      <div className={styles.disclosureContent}>
        <form ref={formRef} action={save} className={styles.editShowForm}>
          <div className={styles.editShowFields}>
            <label>
              Título
              <input name="title" required defaultValue={show.title} />
            </label>
            <label>
              Estado del espectáculo
              <select name="status" defaultValue={show.status}>
                <option value="draft">Borrador</option>
                <option value="published">Publicado</option>
                <option value="archived">Archivado</option>
              </select>
            </label>
            <label>
              Imagen HTTPS
              <input name="imageUrl" type="url" defaultValue={show.imageUrl} />
            </label>
            <label className={styles.wide}>
              Descripción
              <textarea
                name="description"
                rows={3}
                defaultValue={show.description}
              />
            </label>
          </div>
          <div className={styles.formActions}>
            <div className={styles.formFeedback}>
              {message ? (
                <p className={styles.success} role="status">
                  {message}
                </p>
              ) : null}
              {error ? (
                <p className={styles.error} role="alert">
                  {error}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={() => {
                formRef.current?.reset();
                setError("");
                setMessage("");
                onToggle();
              }}
            >
              Cancelar
            </button>
            <button disabled={saving}>
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </form>
      </div>
    </details>
  );
}

function FunctionEditForm({
  fn,
  map,
  isOpen,
  onToggle,
}: {
  fn: TicketingShow["functions"][number];
  map: TicketingSeatMap | undefined;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [formKey, setFormKey] = useState(0);
  const dateTime = getFunctionDateTimeInputs(fn.startsAt);
  const existingPrices = new Map(
    fn.sectionPrices.map((price) => [price.sectionId, price.amount]),
  );

  async function save(form: FormData) {
    setError("");
    setMessage("");
    const isoDate = parseArgentineDate(
      String(form.get(`function-date-${fn.id}`) ?? ""),
    );
    const startTime = String(form.get(`function-time-${fn.id}`) ?? "");
    if (!isoDate) {
      setError("Ingresá una fecha válida con el formato DD/MM/AAAA.");
      return;
    }
    if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(startTime)) {
      setError("Ingresá una hora válida en formato de 24 horas.");
      return;
    }

    const sectionPrices = (map?.sections ?? [])
      .map((section) => {
        if (section.id === undefined) return null;
        const amount = String(
          form.get(`function-price-${section.id}`) ?? "",
        ).trim();
        return amount ? { sectionId: section.id, amount } : null;
      })
      .filter((price) => price !== null);

    setSaving(true);
    try {
      await submitAdminAcademicRequest(
        `/api/v1/admin/ticketing/functions/${fn.id}`,
        "PATCH",
        {
          startsAt: `${isoDate}T${startTime}:00`,
          ...(sectionPrices.length ? { sectionPrices } : {}),
        },
      );
      setMessage("Función actualizada.");
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo actualizar la función.",
      );
    } finally {
      setSaving(false);
    }
  }

  function cancelChanges() {
    setError("");
    setMessage("");
    setFormKey((current) => current + 1);
    onToggle();
  }

  return (
    <details className={styles.inlineEditor} open={isOpen}>
      <summary
        onClick={(event) => {
          event.preventDefault();
          onToggle();
        }}
      >
        <span>Editar función</span>
        <span className={styles.disclosureIcon} aria-hidden="true" />
      </summary>
      <div className={styles.disclosureContent}>
        <form key={formKey} action={save} className={styles.functionForm}>
          <fieldset className={styles.formGroup}>
            <legend>Fecha y horario</legend>
            <div className={styles.dateTimeFields}>
              <DateField
                key={`${fn.id}:${fn.startsAt}`}
                name={`function-date-${fn.id}`}
                label="Fecha de la función"
                defaultValue={dateTime.date}
                required
              />
              <label>
                Hora (24 horas)
                <input
                  name={`function-time-${fn.id}`}
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="HH:MM"
                  maxLength={5}
                  pattern="(?:[01][0-9]|2[0-3]):[0-5][0-9]"
                  defaultValue={dateTime.time}
                  required
                />
              </label>
            </div>
          </fieldset>
          <fieldset className={styles.formGroup}>
            <legend>Precios por sector</legend>
            {map?.sections.length ? (
              <>
                <p className={styles.fieldHelp}>
                  Dejá un importe sin cambios si querés conservar el precio
                  actual de ese sector.
                </p>
                <div className={styles.priceFields}>
                  {map.sections.map((section) => {
                    if (section.id === undefined) return null;
                    return (
                      <label key={section.id}>
                        {section.name} (ARS)
                        <input
                          name={`function-price-${section.id}`}
                          type="number"
                          min="0"
                          step="0.01"
                          defaultValue={existingPrices.get(section.id) ?? ""}
                        />
                      </label>
                    );
                  })}
                </div>
              </>
            ) : (
              <p>No pudimos cargar los sectores asociados a esta función.</p>
            )}
          </fieldset>
          <div className={styles.formActions}>
            <div className={styles.formFeedback}>
              {message ? (
                <p className={styles.success} role="status">
                  {message}
                </p>
              ) : null}
              {error ? (
                <p className={styles.error} role="alert">
                  {error}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              className={styles.cancelButton}
              disabled={saving}
              onClick={cancelChanges}
            >
              Cancelar
            </button>
            <button disabled={saving}>
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </form>
      </div>
    </details>
  );
}

function CreateFunctionForm({
  show,
  maps,
  isOpen,
  onToggle,
}: {
  show: TicketingShow;
  maps: TicketingSeatMap[];
  isOpen: boolean;
  onToggle: () => void;
}) {
  const router = useRouter();
  const [mapId, setMapId] = useState(String(maps[0]?.id ?? ""));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [formKey, setFormKey] = useState(0);
  const selectedMap = maps.find((map) => String(map.id) === mapId);
  const dateFieldName = `startsAtDate-${show.id}`;
  const timeFieldName = `startsAtTime-${show.id}`;
  async function create(form: FormData) {
    setError("");
    setMessage("");
    const isoDate = parseArgentineDate(String(form.get(dateFieldName) ?? ""));
    const startTime = String(form.get(timeFieldName) ?? "");
    if (!isoDate) {
      setError("Ingresá una fecha válida con el formato DD/MM/AAAA.");
      return;
    }
    if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(startTime)) {
      setError("Elegí una hora válida en formato de 24 horas.");
      return;
    }
    setSaving(true);
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
          startsAt: `${isoDate}T${startTime}:00`,
          sectionPrices,
        },
      );
      setMessage("Función creada correctamente.");
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
  function cancelChanges() {
    setError("");
    setMessage("");
    setMapId(String(maps[0]?.id ?? ""));
    setFormKey((current) => current + 1);
    onToggle();
  }
  return (
    <details className={styles.inlineEditor} open={isOpen}>
      <summary
        onClick={(event) => {
          event.preventDefault();
          onToggle();
        }}
      >
        <span>Agregar función</span>
        <span className={styles.disclosureIcon} aria-hidden="true" />
      </summary>
      {maps.length ? (
        <div className={styles.disclosureContent}>
          <form key={formKey} action={create} className={styles.functionForm}>
            <fieldset className={styles.formGroup}>
              <legend>Recinto y mapa</legend>
              <label>
                Seleccioná el recinto y la versión del mapa
                <select
                  name="mapVersionId"
                  value={mapId}
                  onChange={(event) => setMapId(event.target.value)}
                >
                  {maps.map((map) => (
                    <option key={map.id} value={map.id}>
                      {map.venue} · versión {map.version} · {map.capacity}{" "}
                      butacas
                    </option>
                  ))}
                </select>
              </label>
              {selectedMap ? (
                <div className={styles.selectedMapSummary} aria-live="polite">
                  <span>Recinto seleccionado</span>
                  <strong>{selectedMap.venue}</strong>
                  <span>
                    Mapa versión {selectedMap.version} · {selectedMap.capacity}{" "}
                    butacas
                  </span>
                </div>
              ) : null}
            </fieldset>
            <fieldset className={styles.formGroup}>
              <legend>Fecha y horario</legend>
              <div className={styles.dateTimeFields}>
                <DateField
                  name={dateFieldName}
                  label="Fecha de la función"
                  required
                />
                <label>
                  Hora (24 horas)
                  <input
                    name={timeFieldName}
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="HH:MM"
                    maxLength={5}
                    pattern="(?:[01][0-9]|2[0-3]):[0-5][0-9]"
                    required
                  />
                </label>
              </div>
            </fieldset>
            <fieldset className={styles.formGroup}>
              <legend>Precios por sector</legend>
              {selectedMap?.sections.length ? (
                <div className={styles.priceFields}>
                  {selectedMap.sections.map((section) => (
                    <label key={section.id}>
                      {section.name} (ARS)
                      <input
                        name={`price-${section.id}`}
                        type="number"
                        min="0"
                        step="0.01"
                        required
                      />
                    </label>
                  ))}
                </div>
              ) : (
                <p>
                  El mapa seleccionado todavía no tiene sectores configurados.
                </p>
              )}
            </fieldset>
            <div className={styles.formActions}>
              <div className={styles.formFeedback}>
                {message ? (
                  <p className={styles.success} role="status">
                    {message}
                  </p>
                ) : null}
                {error ? (
                  <p className={styles.error} role="alert">
                    {error}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                className={styles.cancelButton}
                disabled={saving}
                onClick={cancelChanges}
              >
                Cancelar
              </button>
              <button disabled={saving}>
                {saving ? "Guardando…" : "Guardar función"}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div className={styles.disclosureContent}>
          <p>
            Para agregar una función, primero configurá un recinto con al menos
            un mapa.
          </p>
        </div>
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
                  {venue.canDelete ? (
                    <DeleteTicketingRecordButton
                      endpoint={`/api/v1/admin/ticketing/venues/${venue.id}`}
                      confirmation={`¿Eliminar el recinto «${venue.name}»? No se puede deshacer.`}
                      disabledReason={
                        venue.versions.length
                          ? "Eliminá primero sus mapas no asociados. Las versiones vinculadas a funciones están protegidas."
                          : undefined
                      }
                    />
                  ) : null}
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
  const formRef = useRef<HTMLFormElement>(null);
  const [isOpen, setIsOpen] = useState(false);
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
    <details className={styles.inlineEditor} open={isOpen}>
      <summary
        onClick={(event) => {
          event.preventDefault();
          setIsOpen((current) => !current);
        }}
      >
        <span>Editar recinto</span>
        <span className={styles.disclosureIcon} aria-hidden="true" />
      </summary>
      <div className={styles.disclosureContent}>
        <form ref={formRef} action={save} className={styles.venueEditForm}>
          <label>
            Nombre del recinto
            <input name="name" required defaultValue={venue.name} />
          </label>
          <label>
            Ubicación
            <input name="location" defaultValue={venue.location} />
          </label>
          <div className={styles.formActions}>
            <div className={styles.formFeedback}>
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
            </div>
            <button
              type="button"
              className={styles.cancelButton}
              disabled={saving}
              onClick={() => {
                formRef.current?.reset();
                setMessage("");
                setError("");
                setIsOpen(false);
              }}
            >
              Cancelar
            </button>
            <button disabled={saving}>
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </form>
      </div>
    </details>
  );
}

function DeleteTicketingRecordButton({
  endpoint,
  confirmation,
  disabledReason,
}: {
  endpoint: string;
  confirmation: string;
  disabledReason?: string;
}) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState("");

  async function removeRecord() {
    if (!window.confirm(confirmation)) return;
    setIsDeleting(true);
    setError("");
    try {
      await submitAdminAcademicRequest(endpoint, "DELETE");
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No se pudo eliminar. Revisá si el registro tiene información vinculada.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className={styles.deleteAction}>
      <button
        type="button"
        className={styles.dangerButton}
        disabled={isDeleting || Boolean(disabledReason)}
        aria-describedby={disabledReason ? `${endpoint}-blocked` : undefined}
        onClick={removeRecord}
      >
        {isDeleting ? "Eliminando…" : "Eliminar"}
      </button>
      {disabledReason ? (
        <p id={`${endpoint}-blocked`} className={styles.deleteHint}>
          {disabledReason}
        </p>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
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
            <div className={styles.formActions}>
              <button
                type="button"
                className={styles.cancelButton}
                disabled={saving}
                onClick={() => router.push(`/admin-panel/recintos/${venue.id}`)}
              >
                Cancelar cambios
              </button>
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
            </div>
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
                  className="admin-student-button is-secondary"
                  href={`/admin-panel/recintos/${venue.id}?map=${version.id}`}
                >
                  {version.isFrozen ? "Ver mapa protegido" : "Editar mapa"}
                </Link>
                <span>
                  Versión {version.version} · {version.capacity} butacas ·{" "}
                  {version.isFrozen ? "asociada a una función" : "editable"}
                </span>
                <button
                  type="button"
                  onClick={() => newVersion(version.id)}
                  disabled={saving}
                >
                  Crear nueva versión a partir de esta
                </button>
                {version.canDelete ? (
                  <DeleteTicketingRecordButton
                    endpoint={`/api/v1/admin/ticketing/maps/${version.id}`}
                    confirmation={`¿Eliminar la versión ${version.version} del mapa de ${venue.name}? Esta acción no se puede deshacer.`}
                    disabledReason={
                      version.isFrozen
                        ? "Esta versión está asociada a una función y no se puede eliminar."
                        : undefined
                    }
                  />
                ) : null}
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

function StatusBadge({ status }: { status: TicketingShow["status"] }) {
  const variant =
    status === "published"
      ? styles.publishedBadge
      : status === "archived"
        ? styles.archivedBadge
        : styles.draftBadge;

  return (
    <span className={`${styles.statusBadge} ${variant}`}>
      {statusLabel(status)}
    </span>
  );
}

function getFunctionDateTimeInputs(value: string) {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return { date: "", time: "" };

  const parts = new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "America/Argentina/Buenos_Aires",
  }).formatToParts(instant);
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );

  return {
    date: `${values.year}-${values.month}-${values.day}`,
    time: `${values.hour}:${values.minute}`,
  };
}
