"use client";

import Image from "next/image";
import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import type { PublicDiscipline } from "../../lib/academic/public-disciplines";
import { getDisciplineDescription, getDisciplineImage } from "./home-content";
import styles from "./home.module.css";

type CardPosition = "active" | "previous" | "next";

export function DisciplineCoverflow({
  disciplines,
}: {
  disciplines: PublicDiscipline[];
}) {
  const [activeIndex, setActiveIndex] = useState(
    Math.floor(disciplines.length / 2),
  );
  const pointerStartX = useRef<number | null>(null);
  const lastSwipeAt = useRef(0);

  function moveBy(direction: -1 | 1) {
    if (disciplines.length < 2) return;

    setActiveIndex((currentIndex) => {
      const nextIndex = currentIndex + direction;
      if (nextIndex < 0) return disciplines.length - 1;
      if (nextIndex >= disciplines.length) return 0;
      return nextIndex;
    });
  }

  function getCardPosition(index: number): CardPosition {
    if (index === activeIndex) return "active";
    if (index === (activeIndex - 1 + disciplines.length) % disciplines.length) {
      return "previous";
    }
    return "next";
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      moveBy(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      moveBy(1);
    }
  }

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    pointerStartX.current = event.clientX;
  }

  function handlePointerUp(event: PointerEvent<HTMLDivElement>) {
    if (pointerStartX.current === null) return;

    const horizontalDistance = event.clientX - pointerStartX.current;
    pointerStartX.current = null;

    if (Math.abs(horizontalDistance) < 44) return;

    lastSwipeAt.current = Date.now();
    moveBy(horizontalDistance < 0 ? 1 : -1);
  }

  function handlePointerCancel() {
    pointerStartX.current = null;
  }

  return (
    <div
      className={styles.coverflow}
      role="region"
      aria-label="Explorar disciplinas"
      aria-roledescription="carrusel"
      onKeyDown={handleKeyDown}
    >
      <div
        className={styles.coverflowViewport}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
      >
        <div className={styles.coverflowStage}>
          {disciplines.map((discipline, index) => {
            const cardPosition = getCardPosition(index);
            const isActive = cardPosition === "active";
            const cardPositionClass =
              cardPosition === "active"
                ? styles.coverflowCardActive
                : cardPosition === "previous"
                  ? styles.coverflowCardPrevious
                  : styles.coverflowCardNext;

            return (
              <button
                key={discipline.id}
                className={`${styles.coverflowCard} ${cardPositionClass}`}
                type="button"
                aria-label={`Mostrar disciplina ${discipline.name}`}
                aria-pressed={isActive}
                onClick={() => {
                  if (Date.now() - lastSwipeAt.current < 250) return;
                  setActiveIndex(index);
                }}
              >
                <span className={styles.disciplineImage}>
                  <Image
                    src={getDisciplineImage(discipline.name, index)}
                    alt=""
                    fill
                    sizes="(max-width: 640px) 76vw, (max-width: 1100px) 70vw, 52rem"
                    draggable={false}
                  />
                  <span className={styles.disciplineNumber} aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </span>
                <span className={styles.disciplineCardCopy}>
                  <span className={styles.disciplineCardTitle}>
                    {discipline.name}
                  </span>
                  <span>{getDisciplineDescription(discipline.name)}</span>
                </span>
              </button>
            );
          })}
        </div>

        <button
          className={`${styles.coverflowArrow} ${styles.coverflowArrowPrevious}`}
          type="button"
          onClick={() => moveBy(-1)}
          aria-label="Disciplina anterior"
          disabled={disciplines.length < 2}
        >
          <span aria-hidden="true">←</span>
        </button>
        <button
          className={`${styles.coverflowArrow} ${styles.coverflowArrowNext}`}
          type="button"
          onClick={() => moveBy(1)}
          aria-label="Disciplina siguiente"
          disabled={disciplines.length < 2}
        >
          <span aria-hidden="true">→</span>
        </button>
      </div>

      <p className={styles.coverflowPosition} aria-live="polite">
        <span>{String(activeIndex + 1).padStart(2, "0")}</span>
        <span aria-hidden="true"> / </span>
        {String(disciplines.length).padStart(2, "0")} ·{" "}
        {disciplines[activeIndex]?.name}
      </p>
    </div>
  );
}
