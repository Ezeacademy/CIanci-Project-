"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { formatArsAmount } from "../../lib/format-money";
import {
  annularSectorPath,
  sectionLabelPosition,
} from "../../lib/tickets/map-geometry";
import {
  formatCentsAsDecimal,
  sumSelectedSeatPricesCents,
} from "../../lib/tickets/seat-selection";
import type {
  PublicSeatMapOverview,
  PublicSeatMapSection,
  PublicTicketShow,
  SeatMapCanvasLayout,
  SeatSectionGeometry,
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
  const [overview, setOverview] = useState<PublicSeatMapOverview | null>(null);
  const [sectionMap, setSectionMap] = useState<PublicSeatMapSection | null>(
    null,
  );
  const [selectedSeats, setSelectedSeats] = useState<
    Record<string, SelectedSeat>
  >({});
  const [activeLevel, setActiveLevel] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingSection, setIsLoadingSection] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [useSeatList, setUseSeatList] = useState(false);
  const sectionRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(
      `/api/v1/ticketing/shows/${showId}/functions/${functionId}/seat-map/overview`,
      { signal: controller.signal, cache: "no-store" },
    )
      .then(async (response) => {
        if (!response.ok)
          throw new Error("No pudimos cargar el plano del teatro.");
        return (await response.json()) as PublicSeatMapOverview;
      })
      .then((loadedOverview) => {
        setOverview(loadedOverview);
        setActiveLevel(loadedOverview.sections[0]?.layout.levelOrder ?? 0);
        setError("");
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error
              ? cause.message
              : "No pudimos cargar el plano del teatro.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => {
      controller.abort();
      sectionRequest.current?.abort();
    };
  }, [functionId, retry, showId]);

  const levels = useMemo(() => {
    if (!overview) return [];
    return [
      ...new Map(
        overview.sections.map((section) => [
          section.layout.levelOrder,
          { order: section.layout.levelOrder, name: section.layout.levelName },
        ]),
      ).values(),
    ].sort((left, right) => left.order - right.order);
  }, [overview]);
  const visibleSections =
    overview?.sections.filter(
      (section) => section.layout.levelOrder === activeLevel,
    ) ?? [];
  const selectedSeatKeys = Object.keys(selectedSeats);
  const selectedTotalCents = sumSelectedSeatPricesCents(
    Object.entries(selectedSeats).map(([key, seat]) => ({
      key,
      price: seat.price,
      isOperational: true,
    })),
    selectedSeatKeys,
  );
  const selectedSeatDetails = Object.entries(selectedSeats);

  async function openSection(
    section: PublicSeatMapOverview["sections"][number],
  ) {
    sectionRequest.current?.abort();
    const controller = new AbortController();
    sectionRequest.current = controller;
    setIsLoadingSection(true);
    setError("");
    try {
      const response = await fetch(
        `/api/v1/ticketing/shows/${showId}/functions/${functionId}/seat-map/sections/${section.id}`,
        { signal: controller.signal, cache: "no-store" },
      );
      if (!response.ok)
        throw new Error("No pudimos cargar las butacas de este sector.");
      const data = (await response.json()) as PublicSeatMapSection;
      setSectionMap(data);
      setUseSeatList(
        data.rows.reduce((count, row) => count + row.seats.length, 0) > 500,
      );
    } catch (cause: unknown) {
      if (!controller.signal.aborted) {
        setError(
          cause instanceof Error
            ? cause.message
            : "No pudimos cargar las butacas de este sector.",
        );
      }
    } finally {
      if (!controller.signal.aborted) setIsLoadingSection(false);
    }
  }

  function toggleSeat(
    sectionName: string,
    rowLabel: string,
    seat: PublicSeatMapSection["rows"][number]["seats"][number],
    price: string | null,
  ) {
    const key = seatKey(sectionName, rowLabel, seat.number);
    setSelectedSeats((current) => {
      if (current[key]) {
        const next = { ...current };
        delete next[key];
        return next;
      }
      if (!seat.isOperational || price === null) return current;
      return {
        ...current,
        [key]: {
          key,
          section: sectionName,
          row: rowLabel,
          number: seat.number,
          price,
        },
      };
    });
  }

  if (isLoading) {
    return (
      <div className={styles.mapMessage} role="status">
        Cargando el plano del teatro…
      </div>
    );
  }
  if (error && !overview) {
    return (
      <div className={styles.mapError} role="alert">
        <p>{error}</p>
        <button
          type="button"
          onClick={() => {
            setIsLoading(true);
            setError("");
            setRetry((current) => current + 1);
          }}
        >
          Volver a intentar
        </button>
      </div>
    );
  }
  if (!overview) return null;

  return (
    <div className={styles.selectionLayout}>
      <section className={styles.mapPanel} aria-labelledby="seat-map-title">
        <div className={styles.mapHeader}>
          <div>
            <p className={styles.cardEyebrow}>MAPA DE BUTACAS</p>
            <h2 id="seat-map-title">
              {sectionMap ? sectionMap.name : "Elegí un sector"}
            </h2>
          </div>
          <div className={styles.zoomControls} aria-label="Tamaño del mapa">
            <button
              type="button"
              aria-label="Alejar mapa"
              onClick={() => setZoom((current) => Math.max(0.8, current - 0.1))}
              disabled={zoom <= 0.8}
            >
              −
            </button>
            <button
              type="button"
              aria-label="Acercar mapa"
              onClick={() => setZoom((current) => Math.min(1.8, current + 0.1))}
              disabled={zoom >= 1.8}
            >
              +
            </button>
          </div>
        </div>
        {levels.length > 1 ? (
          <div className={styles.levelTabs} aria-label="Nivel del teatro">
            {levels.map((level) => (
              <button
                key={level.order}
                type="button"
                aria-pressed={activeLevel === level.order}
                onClick={() => {
                  sectionRequest.current?.abort();
                  setIsLoadingSection(false);
                  setActiveLevel(level.order);
                  setSectionMap(null);
                }}
              >
                {level.name}
              </button>
            ))}
          </div>
        ) : null}
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
        {error ? (
          <p className={styles.mapInlineError} role="alert">
            {error}
          </p>
        ) : null}
        {isLoadingSection ? (
          <p className={styles.mapMessage} role="status">
            Cargando las butacas del sector…
          </p>
        ) : null}
        <div
          className={styles.mapViewport}
          aria-label="Plano interactivo del teatro"
        >
          {sectionMap ? (
            <>
              <button
                type="button"
                className={styles.mapBackButton}
                onClick={() => setSectionMap(null)}
              >
                ← Todos los sectores
              </button>
              <SeatSectionSvg
                section={sectionMap}
                zoom={zoom}
                selectedSeats={selectedSeats}
                useSeatList={useSeatList}
                onToggle={toggleSeat}
              />
              <button
                className={styles.listModeButton}
                type="button"
                aria-pressed={useSeatList}
                onClick={() => setUseSeatList((current) => !current)}
              >
                {useSeatList
                  ? "Ver plano interactivo"
                  : "Ver butacas en una lista"}
              </button>
            </>
          ) : (
            <SeatMapOverview
              canvas={overview.layout}
              sections={visibleSections}
              zoom={zoom}
              onSectionSelect={openSection}
            />
          )}
        </div>
        <p className={styles.mapHint}>
          La selección es visual y no reserva butacas. Podés elegir otro nivel o
          volver al plano general.
        </p>
      </section>
      <aside className={styles.selectionSummary} aria-live="polite">
        <p className={styles.cardEyebrow}>TU SELECCIÓN</p>
        <h2>Butacas elegidas</h2>
        {selectedSeatDetails.length ? (
          <ul className={styles.selectedList}>
            {selectedSeatDetails.map(([key, seat]) => (
              <li key={key}>
                <span>
                  {seat.section} · Fila {seat.row} · Butaca {seat.number}
                </span>
                <strong>{formatArsAmount(seat.price)}</strong>
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

type SelectedSeat = {
  key: string;
  section: string;
  row: string;
  number: string;
  price: string;
};

function SeatMapOverview({
  canvas,
  sections,
  zoom,
  onSectionSelect,
}: {
  canvas: SeatMapCanvasLayout;
  sections: PublicSeatMapOverview["sections"];
  zoom: number;
  onSectionSelect: (section: PublicSeatMapOverview["sections"][number]) => void;
}) {
  return (
    <svg
      className={styles.theatrePlan}
      viewBox={`0 0 ${canvas.width} ${canvas.height}`}
      style={{ width: `${zoom * 100}%` }}
      role="group"
      aria-label="Sectores del teatro"
    >
      <StageShape stage={canvas.stage} />
      {sections.map((section) => {
        const [labelX, labelY] = sectionLabelPosition(section.layout);
        return (
          <g
            key={section.id}
            className={styles.planSection}
            role="button"
            tabIndex={0}
            aria-label={`${section.name}, ${section.operationalSeatCount} butacas operativas${section.price ? `, ${formatArsAmount(section.price)}` : ", precio pendiente"}`}
            onClick={() => onSectionSelect(section)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSectionSelect(section);
              }
            }}
          >
            <SectionShape geometry={section.layout} />
            <text
              x={labelX}
              y={labelY - 4}
              textAnchor="middle"
              className={styles.planSectionName}
            >
              {section.name}
            </text>
            <text
              x={labelX}
              y={labelY + 22}
              textAnchor="middle"
              className={styles.planSectionCount}
            >
              {section.operationalSeatCount} lugares
            </text>
          </g>
        );
      })}
      {!sections.length ? (
        <text x={canvas.width / 2} y={canvas.height / 2} textAnchor="middle">
          No hay sectores en este nivel.
        </text>
      ) : null}
    </svg>
  );
}

function SeatSectionSvg({
  section,
  zoom,
  selectedSeats,
  useSeatList,
  onToggle,
}: {
  section: PublicSeatMapSection;
  zoom: number;
  selectedSeats: Record<string, SelectedSeat>;
  useSeatList: boolean;
  onToggle: (
    sectionName: string,
    rowLabel: string,
    seat: PublicSeatMapSection["rows"][number]["seats"][number],
    price: string | null,
  ) => void;
}) {
  const seatCount = section.rows.reduce(
    (count, row) => count + row.seats.length,
    0,
  );
  return (
    <>
      <svg
        className={`${styles.theatrePlan} ${styles.seatPlan}`}
        viewBox={`${section.layout.x - 36} ${section.layout.y - 36} ${section.layout.width + 72} ${section.layout.height + 72}`}
        style={{ width: `${zoom * 100}%` }}
        role="group"
        aria-label={`Butacas del sector ${section.name}`}
      >
        <SectionShape geometry={section.layout} />
        {!useSeatList
          ? section.rows.map((row) => (
              <g key={row.label}>
                <text
                  x={
                    row.layout?.shape === "straight"
                      ? row.layout.startX - 20
                      : row.layout?.centerX
                  }
                  y={
                    row.layout?.shape === "straight"
                      ? row.layout.startY
                      : row.layout?.centerY
                  }
                  className={styles.svgRowLabel}
                >
                  {row.label}
                </text>
                {row.gaps.map((gap) =>
                  gap.visual ? (
                    <rect
                      key={`gap-${gap.position}`}
                      x={gap.visual.x - gap.width * 7}
                      y={gap.visual.y - 5}
                      width={gap.width * 14}
                      height={10}
                      rx={4}
                      className={
                        gap.kind === "aisle"
                          ? styles.svgAisle
                          : styles.svgEmptyGap
                      }
                    />
                  ) : null,
                )}
                {row.seats.map((seat) => {
                  const key = seatKey(section.name, row.label, seat.number);
                  const isSelected = Boolean(selectedSeats[key]);
                  const canSelect =
                    seat.isOperational && section.price !== null;
                  return seat.visual ? (
                    <g
                      key={key}
                      className={`${styles.svgSeat} ${isSelected ? styles.svgSeatSelected : ""} ${!canSelect ? styles.svgSeatBlocked : ""}`}
                      role="checkbox"
                      aria-checked={isSelected}
                      aria-disabled={!canSelect}
                      aria-label={`${section.name}, fila ${row.label}, butaca ${seat.number}${seat.isAccessible ? ", accesible" : ""}${!seat.isOperational ? ", no operativa" : section.price === null ? ", precio pendiente" : `, ${formatArsAmount(section.price)}`}`}
                      tabIndex={canSelect ? 0 : -1}
                      transform={`translate(${seat.visual.x} ${seat.visual.y}) rotate(${seat.visual.rotation})`}
                      onClick={() =>
                        onToggle(section.name, row.label, seat, section.price)
                      }
                      onKeyDown={(event) => {
                        if (
                          canSelect &&
                          (event.key === "Enter" || event.key === " ")
                        ) {
                          event.preventDefault();
                          onToggle(
                            section.name,
                            row.label,
                            seat,
                            section.price,
                          );
                        }
                      }}
                    >
                      <rect x={-9} y={-7} width={18} height={14} rx={4} />
                      <text textAnchor="middle" dominantBaseline="central">
                        {seat.number}
                      </text>
                    </g>
                  ) : null;
                })}
              </g>
            ))
          : null}
      </svg>
      {useSeatList ? (
        <div
          className={styles.accessibleSeatList}
          aria-label={`Lista de butacas de ${section.name}`}
        >
          {section.rows.map((row) => (
            <fieldset key={row.label}>
              <legend>Fila {row.label}</legend>
              <div>
                {row.seats.map((seat) => {
                  const key = seatKey(section.name, row.label, seat.number);
                  const canSelect =
                    seat.isOperational && section.price !== null;
                  return (
                    <button
                      key={key}
                      type="button"
                      disabled={!canSelect}
                      aria-pressed={Boolean(selectedSeats[key])}
                      onClick={() =>
                        onToggle(section.name, row.label, seat, section.price)
                      }
                    >
                      Butaca {seat.number}
                      {seat.isAccessible ? " · Accesible" : ""}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </div>
      ) : null}
      {seatCount > 500 && !useSeatList ? (
        <p className={styles.mapHint}>
          Este sector es grande. También podés elegir las butacas desde una
          lista accesible.
        </p>
      ) : null}
    </>
  );
}

function StageShape({ stage }: { stage: SeatMapCanvasLayout["stage"] }) {
  return (
    <g className={styles.svgStage}>
      <rect
        x={stage.x}
        y={stage.y}
        width={stage.width}
        height={stage.height}
        rx={stage.height / 2}
      />
      <text
        x={stage.x + stage.width / 2}
        y={stage.y + stage.height / 2}
        textAnchor="middle"
        dominantBaseline="central"
      >
        {stage.label}
      </text>
    </g>
  );
}

function SectionShape({ geometry }: { geometry: SeatSectionGeometry }) {
  if (geometry.shape === "rectangle") {
    return (
      <rect
        className={styles.svgSectionShape}
        x={geometry.x}
        y={geometry.y}
        width={geometry.width}
        height={geometry.height}
        rx={12}
        transform={`rotate(${geometry.rotation} ${geometry.x + geometry.width / 2} ${geometry.y + geometry.height / 2})`}
      />
    );
  }
  return (
    <path
      className={styles.svgSectionShape}
      d={annularSectorPath(geometry)}
      transform={`rotate(${geometry.rotation} ${geometry.x + geometry.width / 2} ${geometry.y + geometry.height / 2})`}
    />
  );
}

function seatKey(section: string, row: string, number: string): string {
  return `${section}::${row}::${number}`;
}
