"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { formatArsAmount } from "../../lib/format-money";
import {
  formatCentsAsDecimal,
  sumSelectedSeatPricesCents,
  toggleSeatSelection,
} from "../../lib/tickets/seat-selection";
import type {
  PublicTicketSeatMap,
  PublicTicketShow,
} from "../../lib/tickets/public-ticketing";
import { formatInstantDateTime } from "../../lib/format-date";
import styles from "./public-ticketing.module.css";

export function PublicShowsCatalog({ shows }: { shows: PublicTicketShow[] }) {
  return (
    <main id="contenido" className={`shell ${styles.page}`}>
      <header className={styles.pageHeading}>
        <p className="eyebrow">CIANCI · ENCUENTROS</p>
        <h1>Espectáculos</h1>
        <p>Elegí una función y explorá el mapa de butacas del teatro.</p>
      </header>

      {shows.length ? (
        <div className={styles.showGrid}>
          {shows.map((show) => (
            <article className={styles.showCard} key={show.id}>
              <Link
                className={styles.showImageLink}
                href={`/espectaculos/${show.id}`}
                aria-label={`Ver ${show.title}`}
              >
                {show.imageUrl ? (
                  // Arbitrary HTTPS image hosts are intentionally configured by the institute.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={show.imageUrl} alt={`Imagen de ${show.title}`} />
                ) : (
                  <span className={styles.imagePlaceholder} aria-hidden="true">
                    CIANCI
                  </span>
                )}
              </Link>
              <div className={styles.showCardBody}>
                <p className={styles.cardEyebrow}>ESPECTÁCULO</p>
                <h2>{show.title}</h2>
                <p className={styles.description}>
                  {show.description || "Una experiencia para compartir danza."}
                </p>
                {show.functions.length ? (
                  <ul className={styles.functionPreview}>
                    {show.functions.slice(0, 2).map((showFunction) => (
                      <li key={showFunction.id}>
                        <span>
                          {formatInstantDateTime(showFunction.startsAt)}
                        </span>
                        <span>{showFunction.venue}</span>
                      </li>
                    ))}
                    {show.functions.length > 2 ? (
                      <li className={styles.moreFunctions}>
                        +{show.functions.length - 2} funciones
                      </li>
                    ) : null}
                  </ul>
                ) : (
                  <p className={styles.noFunctions}>
                    Próximamente se anunciarán las funciones.
                  </p>
                )}
                <Link
                  className={styles.textLink}
                  href={`/espectaculos/${show.id}`}
                >
                  Ver espectáculo <span aria-hidden="true">→</span>
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <section className={styles.emptyState} aria-live="polite">
          <h2>Próximamente, nuevos encuentros</h2>
          <p>Cuando haya espectáculos publicados, los vas a encontrar acá.</p>
        </section>
      )}
    </main>
  );
}

export function PublicShowDetail({ show }: { show: PublicTicketShow }) {
  const [selectedFunctionId, setSelectedFunctionId] = useState(
    show.functions[0]?.id ?? 0,
  );
  const selectedFunction = show.functions.find(
    (showFunction) => showFunction.id === selectedFunctionId,
  );

  return (
    <main id="contenido" className={`shell ${styles.page}`}>
      <Link className={styles.backLink} href="/espectaculos">
        <span aria-hidden="true">←</span> Todos los espectáculos
      </Link>
      <header className={styles.detailHeading}>
        <p className="eyebrow">CIANCI · ESPECTÁCULOS</p>
        <h1>{show.title}</h1>
        {show.description ? <p>{show.description}</p> : null}
      </header>

      {show.functions.length ? (
        <>
          <section
            className={styles.functionChooser}
            aria-label="Elegí una función"
          >
            <label htmlFor="ticket-function">Función</label>
            <select
              id="ticket-function"
              value={selectedFunctionId}
              onChange={(event) =>
                setSelectedFunctionId(Number(event.target.value))
              }
            >
              {show.functions.map((showFunction) => (
                <option key={showFunction.id} value={showFunction.id}>
                  {formatInstantDateTime(showFunction.startsAt)}
                </option>
              ))}
            </select>
            {selectedFunction ? (
              <p>
                {selectedFunction.location || selectedFunction.venue} ·
                Capacidad {selectedFunction.capacity} butacas
              </p>
            ) : null}
          </section>

          <p className={styles.selectionNotice} role="status">
            La selección es solo visual: estas butacas todavía no están
            reservadas.
          </p>

          <FunctionSeatSelection
            key={selectedFunctionId}
            showId={show.id}
            functionId={selectedFunctionId}
          />
        </>
      ) : (
        <section className={styles.emptyState}>
          {show.hasPastFunctions ? (
            <>
              <h2>Las funciones de este espectáculo ya se realizaron</h2>
              <p>
                No hay funciones futuras publicadas por el momento. Cuando se
                anuncien nuevas fechas, aparecerán en esta página.
              </p>
            </>
          ) : (
            <>
              <h2>Todavía no hay funciones publicadas</h2>
              <p>
                Este espectáculo aún no tiene fechas anunciadas. Volvé a
                consultar más adelante.
              </p>
            </>
          )}
        </section>
      )}
    </main>
  );
}

function FunctionSeatSelection({
  showId,
  functionId,
}: {
  showId: number;
  functionId: number;
}) {
  const [seatMap, setSeatMap] = useState<PublicTicketSeatMap | null>(null);
  const [selectedSeatKeys, setSelectedSeatKeys] = useState<string[]>([]);
  const [isLoadingMap, setIsLoadingMap] = useState(true);
  const [mapError, setMapError] = useState("");
  const [seatSize, setSeatSize] = useState(2.65);
  const [mapRetry, setMapRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetch(
      `/api/v1/ticketing/shows/${showId}/functions/${functionId}/seat-map`,
      { signal: controller.signal, cache: "no-store" },
    )
      .then(async (response) => {
        if (!response.ok)
          throw new Error("No pudimos cargar el mapa de butacas.");
        return (await response.json()) as PublicTicketSeatMap;
      })
      .then((loadedSeatMap) => {
        setSeatMap(loadedSeatMap);
        setMapError("");
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMapError(
            error instanceof Error
              ? error.message
              : "No pudimos cargar el mapa de butacas.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingMap(false);
      });

    return () => controller.abort();
  }, [functionId, mapRetry, showId]);

  const selectableSeats = useMemo(() => {
    if (!seatMap) return [];
    return seatMap.sections.flatMap((section) =>
      section.rows.flatMap((row) =>
        row.seats.map((seat) => ({
          key: seatKey(section.name, row.label, seat.number),
          price: section.price,
          isOperational: seat.isOperational,
        })),
      ),
    );
  }, [seatMap]);
  const selectedTotalCents = sumSelectedSeatPricesCents(
    selectableSeats,
    selectedSeatKeys,
  );
  const selectedSeatDetails = seatMap
    ? seatMap.sections.flatMap((section) =>
        section.rows.flatMap((row) =>
          row.seats
            .filter((seat) =>
              selectedSeatKeys.includes(
                seatKey(section.name, row.label, seat.number),
              ),
            )
            .map((seat) => ({ section: section.name, row: row.label, seat })),
        ),
      )
    : [];

  if (isLoadingMap) {
    return (
      <div className={styles.mapMessage} role="status">
        Cargando el mapa de butacas…
      </div>
    );
  }
  if (mapError) {
    return (
      <div className={styles.mapError} role="alert">
        <p>{mapError}</p>
        <button
          type="button"
          onClick={() => {
            setIsLoadingMap(true);
            setMapError("");
            setMapRetry((current) => current + 1);
          }}
        >
          Volver a intentar
        </button>
      </div>
    );
  }
  if (!seatMap) return null;

  return (
    <div className={styles.selectionLayout}>
      <SeatMap
        seatMap={seatMap}
        selectedSeatKeys={selectedSeatKeys}
        seatSize={seatSize}
        onSeatToggle={(key, price, isOperational) =>
          setSelectedSeatKeys((current) =>
            toggleSeatSelection(current, { key, price, isOperational }),
          )
        }
        onZoomChange={setSeatSize}
      />
      <aside className={styles.selectionSummary} aria-live="polite">
        <p className={styles.cardEyebrow}>TU SELECCIÓN</p>
        <h2>Butacas elegidas</h2>
        {selectedSeatDetails.length ? (
          <ul className={styles.selectedList}>
            {selectedSeatDetails.map(({ section, row, seat }) => (
              <li key={seatKey(section, row, seat.number)}>
                <span>
                  {section} · Fila {row} · Butaca {seat.number}
                </span>
                <strong>
                  {formatArsAmount(
                    seatMap.sections.find((item) => item.name === section)
                      ?.price ?? "0",
                  )}
                </strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.summaryEmpty}>
            Elegí una o más butacas para ver el detalle y el total.
          </p>
        )}
        <div className={styles.totalLine}>
          <span>Total estimado</span>
          <strong>
            {formatArsAmount(formatCentsAsDecimal(selectedTotalCents))}
          </strong>
        </div>
        <p className={styles.noReservation}>
          Este importe es informativo. No se realizará una compra ni se guardará
          una reserva.
        </p>
      </aside>
    </div>
  );
}

function SeatMap({
  seatMap,
  selectedSeatKeys,
  seatSize,
  onSeatToggle,
  onZoomChange,
}: {
  seatMap: PublicTicketSeatMap;
  selectedSeatKeys: string[];
  seatSize: number;
  onSeatToggle: (
    key: string,
    price: string | null,
    isOperational: boolean,
  ) => void;
  onZoomChange: (value: number) => void;
}) {
  return (
    <section className={styles.mapPanel} aria-labelledby="seat-map-title">
      <div className={styles.mapHeader}>
        <div>
          <p className={styles.cardEyebrow}>MAPA DE BUTACAS</p>
          <h2 id="seat-map-title">Elegí tus lugares</h2>
        </div>
        <div className={styles.zoomControls} aria-label="Tamaño del mapa">
          <button
            type="button"
            aria-label="Alejar mapa"
            onClick={() => onZoomChange(Math.max(1.8, seatSize - 0.2))}
            disabled={seatSize <= 1.8}
          >
            −
          </button>
          <button
            type="button"
            aria-label="Acercar mapa"
            onClick={() => onZoomChange(Math.min(3.4, seatSize + 0.2))}
            disabled={seatSize >= 3.4}
          >
            +
          </button>
        </div>
      </div>
      <div className={styles.legend} aria-label="Referencias del mapa">
        <span>
          <i className={styles.legendSeat} /> Seleccionable
        </span>
        <span>
          <i className={styles.legendSelected} /> Elegida
        </span>
        <span>
          <i className={styles.legendBlocked} /> No operativa
        </span>
      </div>
      <div
        className={styles.mapViewport}
        tabIndex={0}
        aria-label="Mapa desplazable de butacas"
      >
        <div
          className={styles.mapCanvas}
          style={{ "--seat-size": `${seatSize}rem` } as CSSProperties}
        >
          <div className={styles.stage}>ESCENARIO</div>
          {seatMap.sections.map((section) => (
            <section className={styles.mapSection} key={section.name}>
              <header className={styles.sectionHeading}>
                <h3>{section.name}</h3>
                <span>
                  {section.price
                    ? formatArsAmount(section.price)
                    : "Precio pendiente"}
                </span>
              </header>
              <div className={styles.rows}>
                {section.rows.map((row) => {
                  const finalPosition = Math.max(
                    1,
                    ...row.seats.map((seat) => seat.position),
                    ...row.gaps.map((gap) => gap.position + gap.width - 1),
                  );
                  return (
                    <div
                      className={styles.seatRow}
                      key={`${section.name}-${row.label}`}
                    >
                      <span className={styles.rowLabel}>Fila {row.label}</span>
                      <div
                        className={styles.seatCells}
                        style={{
                          gridTemplateColumns: `repeat(${finalPosition}, var(--seat-size))`,
                        }}
                      >
                        {row.gaps.map((gap) => (
                          <span
                            className={
                              gap.kind === "aisle"
                                ? styles.aisle
                                : styles.emptyGap
                            }
                            key={`gap-${gap.position}`}
                            style={{
                              gridColumn: `${gap.position} / span ${gap.width}`,
                            }}
                            aria-label={
                              gap.kind === "aisle" ? "Pasillo" : "Espacio vacío"
                            }
                            title={
                              gap.kind === "aisle" ? "Pasillo" : "Espacio vacío"
                            }
                          />
                        ))}
                        {row.seats.map((seat) => {
                          const key = seatKey(
                            section.name,
                            row.label,
                            seat.number,
                          );
                          const isSelected = selectedSeatKeys.includes(key);
                          const isSelectable =
                            seat.isOperational && section.price !== null;
                          const accessibleMark = seat.isAccessible ? " ♿" : "";
                          return (
                            <button
                              className={`${styles.seat} ${isSelected ? styles.seatSelected : ""} ${!isSelectable ? styles.seatBlocked : ""}`}
                              key={key}
                              type="button"
                              style={{ gridColumn: String(seat.position) }}
                              disabled={!isSelectable}
                              aria-pressed={
                                isSelectable ? isSelected : undefined
                              }
                              aria-label={`${section.name}, fila ${row.label}, butaca ${seat.number}${seat.isAccessible ? ", accesible" : ""}${!seat.isOperational ? ", no operativa" : section.price === null ? ", precio pendiente" : `, ${formatArsAmount(section.price)}`}`}
                              onClick={() =>
                                onSeatToggle(
                                  key,
                                  section.price,
                                  seat.isOperational,
                                )
                              }
                            >
                              {seat.number}
                              {accessibleMark ? (
                                <span
                                  className={styles.accessibleMark}
                                  aria-hidden="true"
                                >
                                  ♿
                                </span>
                              ) : null}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
      <p className={styles.mapHint}>
        En pantallas pequeñas podés desplazar el mapa con el dedo. Usá + y −
        para ajustar el tamaño.
      </p>
    </section>
  );
}

function seatKey(section: string, row: string, number: string): string {
  return `${section}::${row}::${number}`;
}
