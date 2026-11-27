import { useEffect, useState } from "react";
import { getAnalytics } from "../services/historyService";
import { ApiError } from "../services/api";
import type { AnalyticsData } from "../types/history";

export function useAnalytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getAnalytics()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load the analytics. Try again.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading: data === null && error === null, error };
}