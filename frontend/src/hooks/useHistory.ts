import { useEffect, useState } from "react";
import { getHistory } from "../services/historyService";
import { ApiError } from "../services/api";
import type { HistoryItem } from "../types/history";

// loads the saved analyses of the signed-in user
export function useHistory() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getHistory()
      .then((list) => {
        if (!cancelled) setItems(list);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load your history. Try again.");
        }
      });

    // ignore the answer if the page was closed meanwhile
    return () => {
      cancelled = true;
    };
  }, []);

  return { items, loading: items === null && error === null, error };
}