import { put, getAll, del, clearStore, getDB } from './idb';
import { uuid } from '@/lib/uuid';

const MAX_RETRIES = 3;

export interface OutboxMessage {
  id: string;
  type: 'chat' | 'voice';
  payload: unknown;
  createdAt: string;
  retries: number;
}

function uuid(): string {
  return uuid();
}

export async function enqueue(message: {
  type: 'chat' | 'voice';
  payload: unknown;
}): Promise<string> {
  const db = await getDB();
  const id = uuid();
  const entry: OutboxMessage = {
    id,
    type: message.type,
    payload: message.payload,
    createdAt: new Date().toISOString(),
    retries: 0,
  };
  await put(db, 'outbox', entry);
  return id;
}

export async function flush(
  sendFn: (msg: OutboxMessage) => Promise<void>,
): Promise<{ sent: number; failed: number }> {
  const db = await getDB();
  const all = await getAll<OutboxMessage>(db, 'outbox');
  const sorted = all.sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  );

  let sent = 0;
  let failed = 0;

  for (const msg of sorted) {
    if (msg.retries > MAX_RETRIES) {
      continue;
    }

    try {
      await sendFn(msg);
      await del(db, 'outbox', msg.id);
      sent++;
    } catch {
      failed++;
      await put(db, 'outbox', { ...msg, retries: msg.retries + 1 });
    }
  }

  return { sent, failed };
}

export async function getQueueSize(): Promise<number> {
  const db = await getDB();
  const all = await getAll<OutboxMessage>(db, 'outbox');
  return all.length;
}

export async function clearQueue(): Promise<void> {
  const db = await getDB();
  await clearStore(db, 'outbox');
}
