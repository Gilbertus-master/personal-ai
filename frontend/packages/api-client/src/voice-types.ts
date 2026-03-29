export interface TranscribeResponse {
  text: string;
  language: string;
}

export interface VoiceAskResponse {
  transcript: string;
  answer: string;
  tts_available: boolean;
  meta: Record<string, unknown> | null;
}

export interface VoiceCommandResponse {
  transcript: string;
  command_type: string;
  response: string;
}

export interface VoiceHealthResponse {
  whisper: 'ok' | 'down';
  whisper_url: string;
  tts: string;
  tts_voice: string;
  mode: string;
  features: string[];
}

// WebSocket message types
export type WsServerMessage =
  | { type: 'ready'; conversation_id: string }
  | { type: 'transcript'; text: string }
  | { type: 'response'; text: string }
  | { type: 'done' }
  | { type: 'error'; message: string };
