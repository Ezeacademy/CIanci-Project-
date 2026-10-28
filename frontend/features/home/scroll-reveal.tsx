"use client";

import { useEffect, useRef, type ReactNode } from "react";

import styles from "./home.module.css";

export function RevealOnScroll({
  children,
  className,
}: {
  children: ReactNode;
  className: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (
      !container ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    const elements = [
      container,
      ...container.querySelectorAll<HTMLElement>("[data-reveal]"),
    ];
    if (!("IntersectionObserver" in window)) {
      elements.forEach((element) => {
        element.dataset.visible = "true";
      });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).dataset.visible = "true";
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );

    container.dataset.revealReady = "true";
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  return (
    <div
      className={`${styles.revealRoot} ${className}`}
      data-reveal
      ref={containerRef}
    >
      {children}
    </div>
  );
}
