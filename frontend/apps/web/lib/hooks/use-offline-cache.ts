'use client';

import { useEffect, useState } from 'react';
import { useQuery, type QueryKey } from '@tanstack/react-query';
import { cacheGet, cacheSet } from '@/lib/offline/cache-manager';

interface OfflineCacheResult<T> {
  data: T | undefined;
  isLoading: boolean;
  isOfflineData: boolean;
  error: Error | null;
}

export function useOfflineCache<T extends Record<string, unknown>>(
  queryKey: QueryKey,
  fetchFn: () => Promise<T>,
  store: string,
  cacheKey: string,
  ttlMs?: number,
): OfflineCacheResult<T> {
  const [cachedData, setCachedData] = useState<T | undefined>(undefined);
  const [idbLoaded, setIdbLoaded] = useState(false);

  // Load from IDB on mount (instant)
  useEffect(() => {
    let cancelled = false;
    cacheGet<T>(store, cacheKey, ttlMs)
      .then((data) => {
        if (!cancelled && data !== null) {
          setCachedData(data);
        }
      })
      .finally(() => {
        if (!cancelled) setIdbLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [store, cacheKey, ttlMs]);

  const query = useQuery({
    queryKey,
    queryFn: fetchFn,
    enabled: idbLoaded,
  });

  // Update IDB when fresh data arrives
  useEffect(() => {
    if (query.data && query.isFetched) {
      const dataWithKey = { ...query.data, [getKeyPath(store)]: cacheKey };
      void cacheSet(store, cacheKey, dataWithKey);
      setCachedData(undefined);
    }
  }, [query.data, query.isFetched, store, cacheKey]);

  const isOfflineData =
    !!query.error && !!cachedData && query.data === undefined;
  const data = query.data ?? (query.error ? cachedData : query.data);

  return {
    data,
    isLoading: !idbLoaded || (query.isLoading && !cachedData),
    isOfflineData,
    error: query.error,
  };
}

function getKeyPath(store: string): string {
  const keyPaths: Record<string, string> = {
    briefs: 'date',
    dashboard: 'key',
    conversations: 'id',
    messages: 'id',
    people: 'id',
    meta: 'key',
  };
  return keyPaths[store] ?? 'key';
}
