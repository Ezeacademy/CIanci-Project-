"use client";

import Image from "next/image";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef } from "react";

import styles from "./home.module.css";

const galleryImages = [
  {
    source: "/images/dance/jazz.webp",
    description: "Bailarines adultos en movimiento",
    caption: "Movimiento en escena",
  },
  {
    source: "/images/dance/classical.webp",
    description: "Bailarina adulta durante un ensayo",
    caption: "En el estudio",
  },
  {
    source: "/images/dance/contemporary.webp",
    description: "Bailarines adultos en una composición contemporánea",
    caption: "Cuerpos que cuentan",
  },
  {
    source: "/images/dance/hero.webp",
    description: "Bailarines adultos en escena",
    caption: "La danza nos encuentra",
  },
];

export function HorizontalGallery() {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    const scrollArea = scrollAreaRef.current;
    const viewport = viewportRef.current;
    const track = trackRef.current;

    if (!scrollArea || !viewport || !track) return;

    media.add(
      "(min-width: 768px) and (prefers-reduced-motion: no-preference)",
      () => {
        const getScrollDistance = () =>
          Math.max(
            0,
            track.scrollWidth - viewport.getBoundingClientRect().width,
          );

        if (getScrollDistance() === 0) return;

        const animation = gsap.to(track, {
          x: () => -getScrollDistance(),
          ease: "none",
          scrollTrigger: {
            trigger: scrollArea,
            start: "top top+=112",
            end: () => `+=${getScrollDistance()}`,
            scrub: 0.65,
            pin: viewport,
            anticipatePin: 1,
            invalidateOnRefresh: true,
          },
        });
        scrollArea.dataset.scrollAnimation = "enabled";

        return () => {
          delete scrollArea.dataset.scrollAnimation;
          animation.scrollTrigger?.kill();
          animation.kill();
        };
      },
    );

    return () => media.revert();
  }, []);

  return (
    <div className={styles.galleryScrollArea} ref={scrollAreaRef}>
      <div
        className={styles.galleryPin}
        role="region"
        aria-label="Galería de danza"
        tabIndex={0}
        ref={viewportRef}
      >
        <div className={styles.galleryTrack} ref={trackRef}>
          {galleryImages.map((image) => (
            <figure className={styles.galleryCard} key={image.source}>
              <Image
                src={image.source}
                alt={image.description}
                fill
                sizes="(max-width: 767px) 82vw, (max-width: 1100px) 55vw, 45rem"
              />
              <figcaption>{image.caption}</figcaption>
            </figure>
          ))}
        </div>
      </div>
      <p className={styles.galleryScrollHint}>
        Deslizá para recorrer las imágenes
      </p>
    </div>
  );
}
