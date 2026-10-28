"use client";

import { useEffect } from "react";
import { PublicErrorState } from "../../features/tickets/public-error-state";

export default function ShowsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unexpected public ticketing page error", {
      digest: error.digest,
    });
  }, [error]);

  return <PublicErrorState onRetry={reset} />;
}
