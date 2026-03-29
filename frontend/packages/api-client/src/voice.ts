import { getApiKey, clearApiKey } from './base';
import type {
  TranscribeResponse,
  VoiceAskResponse,
  VoiceCommandResponse,
  VoiceHealthResponse,
} from './voice-types';

declare const process: { env: Record<string, string | undefined> } | undefined;

const BASE_URL =
  typeof process !== 'undefined'
    ? process.env.NEXT_PUBLIC_GILBERTUS_API_URL ?? 'http://127.0.0.1:8000'
    : 'http://127.0.0.1:8000';

async function voiceFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = `${BASE_URL}${path}`;

  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) {
    headers['X-API-Key'] = key;
  }

  // Merge headers — do NOT set Content-Type (browser sets it for FormData)
  const merged: Record<string, string> = {
    ...headers,
    ...(init.headers as Record<string, string> | undefined),
  };

  const response = await fetch(url, { ...init, headers: merged });

  if (response.status === 401) {
    clearApiKey();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    throw new Error(`Voice API error: ${response.status} ${response.statusText}`);
  }

  return response;
}

export async function transcribeAudio(
  audio: Blob,
  language = 'pl',
  signal?: AbortSignal,
): Promise<TranscribeResponse> {
  const form = new FormData();
  form.append('audio', audio, 'recording.webm');
  form.append('language', language);

  const res = await voiceFetch('/voice/transcribe', {
    method: 'POST',
    body: form,
    signal,
  });
  return res.json() as Promise<TranscribeResponse>;
}

export async function voiceAsk(
  audio: Blob,
  language = 'pl',
  sessionId = 'web',
  signal?: AbortSignal,
): Promise<VoiceAskResponse> {
  const form = new FormData();
  form.append('audio', audio, 'recording.webm');
  form.append('language', language);
  form.append('session_id', sessionId);

  const res = await voiceFetch('/voice/ask', {
    method: 'POST',
    body: form,
    signal,
  });
  return res.json() as Promise<VoiceAskResponse>;
}

export async function voiceCommand(
  audio: Blob,
  language = 'pl',
  signal?: AbortSignal,
): Promise<{ json?: VoiceCommandResponse; audio?: Blob }> {
  const form = new FormData();
  form.append('audio', audio, 'recording.webm');
  form.append('language', language);

  const res = await voiceFetch('/voice/command', {
    method: 'POST',
    body: form,
    signal,
  });

  const contentType = res.headers.get('Content-Type') ?? '';

  if (contentType.includes('application/json')) {
    const json = (await res.json()) as VoiceCommandResponse;
    return { json };
  }

  // Audio response (MP3) — extract metadata from headers
  const audioBlob = await res.blob();
  const transcript = res.headers.get('X-Transcript') ?? '';
  const responseText = res.headers.get('X-Response-Text') ?? '';

  return {
    audio: audioBlob,
    json: {
      transcript,
      command_type: 'audio',
      response: responseText,
    },
  };
}

export async function textToSpeech(
  text: string,
  voice = 'pl-PL-ZofiaNeural',
  signal?: AbortSignal,
): Promise<Blob> {
  const body = new URLSearchParams({ text, voice });

  const res = await voiceFetch('/voice/tts', {
    method: 'POST',
    body,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    signal,
  });
  return res.blob();
}

export async function getVoiceHealth(
  signal?: AbortSignal,
): Promise<VoiceHealthResponse> {
  const res = await voiceFetch('/voice/health', { signal });
  return res.json() as Promise<VoiceHealthResponse>;
}

export function getVoiceWsUrl(conversationId?: string): string {
  const wsBase = BASE_URL.replace(/^http/, 'ws');
  const url = `${wsBase}/voice/ws`;
  if (conversationId) {
    return `${url}?conversation_id=${encodeURIComponent(conversationId)}`;
  }
  return url;
}
