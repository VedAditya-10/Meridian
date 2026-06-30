import { useState, useEffect, useCallback } from 'react';

interface UseApiDataResult<T> {
  data: T | null;
  loading: boolean;
  error: boolean;
}

/**
 * Generic polling hook that fetches a JSON endpoint on mount and on a
 * configurable interval.  Re-fetches whenever `url` changes.
 *
 * @param url        - Full URL to fetch, or `null` to skip fetching.
 * @param refreshMs  - Polling interval in milliseconds (default: 5000).
 */
export function useApiData<T>(
  url: string | null,
  refreshMs: number = 5000
): UseApiDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchData = useCallback(async () => {
    if (!url || document.visibilityState !== 'visible') return;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: T = await res.json();
      setData(json);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    if (!url) return;
    
    setLoading(true);
    setData(null);
    fetchData();
    
    const iv = setInterval(fetchData, refreshMs);

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchData();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearInterval(iv);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [fetchData, refreshMs, url]);

  return { data, loading, error };
}
