export interface StoreConfig {
  name: string;
  keyPath: string;
  indexes?: { name: string; keyPath: string }[];
}

const DB_NAME = 'gilbertus-offline';
const DB_VERSION = 1;

const STORES: StoreConfig[] = [
  { name: 'briefs', keyPath: 'date' },
  { name: 'dashboard', keyPath: 'key' },
  { name: 'conversations', keyPath: 'id' },
  {
    name: 'messages',
    keyPath: 'id',
    indexes: [{ name: 'by-conversation', keyPath: 'conversationId' }],
  },
  { name: 'people', keyPath: 'id' },
  {
    name: 'outbox',
    keyPath: 'id',
    indexes: [{ name: 'by-created', keyPath: 'createdAt' }],
  },
  { name: 'meta', keyPath: 'key' },
];

let dbInstance: IDBDatabase | null = null;

export function openDB(
  name: string = DB_NAME,
  version: number = DB_VERSION,
  stores: StoreConfig[] = STORES,
): Promise<IDBDatabase> {
  if (dbInstance) return Promise.resolve(dbInstance);

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, version);

    request.onupgradeneeded = () => {
      const db = request.result;
      for (const store of stores) {
        if (!db.objectStoreNames.contains(store.name)) {
          const objectStore = db.createObjectStore(store.name, {
            keyPath: store.keyPath,
          });
          for (const idx of store.indexes ?? []) {
            objectStore.createIndex(idx.name, idx.keyPath, { unique: false });
          }
        }
      }
    };

    request.onsuccess = () => {
      dbInstance = request.result;
      resolve(dbInstance);
    };

    request.onerror = () => {
      reject(request.error);
    };
  });
}

export function get<T>(
  db: IDBDatabase,
  store: string,
  key: IDBValidKey,
): Promise<T | undefined> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).get(key);
    req.onsuccess = () => resolve(req.result as T | undefined);
    req.onerror = () => reject(req.error);
  });
}

export function put(
  db: IDBDatabase,
  store: string,
  value: unknown,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    const req = tx.objectStore(store).put(value);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export function getAll<T>(db: IDBDatabase, store: string): Promise<T[]> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const req = tx.objectStore(store).getAll();
    req.onsuccess = () => resolve(req.result as T[]);
    req.onerror = () => reject(req.error);
  });
}

export function del(
  db: IDBDatabase,
  store: string,
  key: IDBValidKey,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    const req = tx.objectStore(store).delete(key);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export function getAllByIndex<T>(
  db: IDBDatabase,
  store: string,
  indexName: string,
  key: IDBValidKey,
): Promise<T[]> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readonly');
    const idx = tx.objectStore(store).index(indexName);
    const req = idx.getAll(key);
    req.onsuccess = () => resolve(req.result as T[]);
    req.onerror = () => reject(req.error);
  });
}

export function clearStore(db: IDBDatabase, store: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, 'readwrite');
    const req = tx.objectStore(store).clear();
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

export function getDB(): Promise<IDBDatabase> {
  return openDB();
}
