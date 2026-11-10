import { useEffect, useState } from "react";
import { getHistory } from "../services/historyService";
import type { AnalysisRecord } from "../types";

// loads the analysis list. Both History and Analytics use it.
export function useHistory() {
  const [records, setRecords] = useState<AnalysisRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getHistory()
      .then((list) => {
        if (!cancelled) setRecords(list);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load analysis history. Try again.");
      });

    // ignore the answer if the page was closed meanwhile
    return () => {
      cancelled = true;
    };
  }, []);

  return { records, loading: records === null && error === null, error };
}