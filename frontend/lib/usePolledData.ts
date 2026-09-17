"use client";

import { useCallback, useEffect, useState } from "react";

/** Polls an async fetcher on an interval, exposing the latest value and any error. */
export function usePolledData<T>(fetcher: () => Promise<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    fetcher()
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [fetcher]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { data, error, refresh };
}
