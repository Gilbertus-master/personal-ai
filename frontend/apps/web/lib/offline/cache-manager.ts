import { get, put, del, clearStore, getDB } from './idb';

interface CacheMeta {
  key: string;
  store: string;
  timestamp: number;
}

const DEFAULT_TTL: Record<string, number> = {
  briefs: 4 * 60 * 60 * 1000,
  dashboard: 15 * 60 * 1000,
  conversations: 5 * 60 * 1000,
  people: 60 * 60 * 1000,
};

function metaKey(store: string, key: string): string {
  return `${store}:${key}`;
}

export async function cacheGet<T>(
  store: string,
  key: string,
  maxAgeMs?: number,
): Promise<T | null> {
  const db = await getDB();
  const ttl = maxAgeMs ?? DEFAULT_TTL[store] ?? 15 * 60 * 1000;
  const mk = metaKey(store, key);

  const meta = await get<CacheMeta>(db, 'meta', mk);
  if (!meta || Date.now() - meta.timestamp > ttl) {
    return null;
  }

  const data = await get<T>(db, store, key);
  return data ?? null;
}

export async function cacheSet(
  store: string,
  key: string,
  data: unknown,
): Promise<void> {
  const db = await getDB();

  await put(db, store, typeof data === 'object' && data !== null
    ? data
    : { key, value: data });

  const meta: CacheMeta = {
    key: metaKey(store, key),
    store,
    timestamp: Date.now(),
  };
  await put(db, 'meta', meta);
}

export async function cacheClear(store?: string): Promise<void> {
  const db = await getDB();

  if (store) {
    await clearStore(db, store);
    // Clear associated meta entries
    const allMeta = await import('./idb').then((m) => m.getAll<CacheMeta>(db, 'meta'));
    for (const m of allMeta) {
      if (m.store === store) {
        await del(db, 'meta', m.key);
      }
    }
  } else {
    const stores = ['briefs', 'dashboard', 'conversations', 'messages', 'people'];
    for (const s of stores) {
      await clearStore(db, s);
    }
    await clearStore(db, 'meta');
  }
}
