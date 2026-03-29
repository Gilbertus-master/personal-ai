import { useCallback, useRef, useEffect } from 'react';
import { useVoiceStore } from '@/lib/stores/voice-store';
import {
  voiceAsk,
  textToSpeech,
  getVoiceWsUrl,
} from '@gilbertus/api-client';
import type { WsServerMessage } from '@gilbertus/api-client';

const PREFERRED_MIME = 'audio/webm;codecs=opus';
const FALLBACK_MIME = 'audio/webm';
const WS_TIMESLICE_MS = 250;
const WS_RECONNECT_BASE_MS = 1000;
const WS_RECONNECT_MAX_MS = 16000;

function getRecorderMime(): string {
  if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(PREFERRED_MIME)) {
    return PREFERRED_MIME;
  }
  return FALLBACK_MIME;
}

function isInputFocused(): boolean {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || (el as HTMLElement).isContentEditable;
}

export function useVoice() {
  const store = useVoiceStore();
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const wsReconnectAttempt = useRef(0);
  const wsReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stable refs for store values used in effects
  const storeRef = useRef(store);
  storeRef.current = store;

  // --- Audio context (lazy) ---
  const ensureAudioContext = useCallback(() => {
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContext();
    }
    if (audioContextRef.current.state === 'suspended') {
      void audioContextRef.current.resume();
    }
    return audioContextRef.current;
  }, []);

  const connectAnalyser = useCallback(
    (stream: MediaStream) => {
      const ctx = ensureAudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
    },
    [ensureAudioContext],
  );

  // --- Audio Playback ---
  const playAudio = useCallback((blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioRef.current = audio;

    audio.onplay = () => storeRef.current.setPlaying(true);
    audio.onended = () => {
      storeRef.current.setPlaying(false);
      URL.revokeObjectURL(url);
    };
    audio.onerror = () => {
      storeRef.current.setPlaying(false);
      URL.revokeObjectURL(url);
    };

    void audio.play();
  }, []);

  const stopPlayback = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    storeRef.current.setPlaying(false);
  }, []);

  // --- Ensure session exists ---
  const ensureSession = useCallback((): string => {
    const s = storeRef.current;
    if (s.activeSessionId) return s.activeSessionId;
    return s.createSession();
  }, []);

  // --- Recording (HTTP mode) ---
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getRecorderMime();
      const recorder = new MediaRecorder(stream, { mimeType });

      chunksRef.current = [];
      connectAnalyser(stream);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      storeRef.current.setRecording(true);
      storeRef.current.setError(null);
    } catch (err) {
      storeRef.current.setError(
        err instanceof Error ? err.message : 'Nie udało się uzyskać dostępu do mikrofonu',
      );
    }
  }, [connectAnalyser]);

  const stopRecording = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;

    storeRef.current.setRecording(false);
    storeRef.current.setProcessing(true);

    const blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        resolve(new Blob(chunksRef.current, { type: recorder.mimeType }));
      };
      recorder.stop();
    });

    // Stop mic tracks
    recorder.stream.getTracks().forEach((t) => t.stop());

    try {
      const sessionId = ensureSession();
      const s = storeRef.current;
      const result = await voiceAsk(blob, s.language, sessionId);

      s.addMessage(sessionId, { role: 'user', text: result.transcript });
      s.addMessage(sessionId, { role: 'assistant', text: result.answer });

      if (s.autoPlayTts && result.tts_available) {
        const ttsBlob = await textToSpeech(result.answer, s.voiceName);
        playAudio(ttsBlob);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      storeRef.current.setError(
        err instanceof Error ? err.message : 'Błąd przetwarzania nagrania',
      );
    } finally {
      storeRef.current.setProcessing(false);
    }
  }, [ensureSession, playAudio]);

  // --- Recording (WebSocket mode) ---
  const connectWs = useCallback(() => {
    if (wsReconnectTimer.current) {
      clearTimeout(wsReconnectTimer.current);
      wsReconnectTimer.current = null;
    }

    const s = storeRef.current;
    const url = getVoiceWsUrl(s.conversationId ?? undefined);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      wsReconnectAttempt.current = 0;
      ws.send(
        JSON.stringify({
          action: 'start',
          conversation_id: s.conversationId,
        }),
      );
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const audioBlob = new Blob([event.data], { type: 'audio/mpeg' });
        playAudio(audioBlob);
        return;
      }

      const msg = JSON.parse(event.data as string) as WsServerMessage;
      const cur = storeRef.current;
      const sessionId = cur.activeSessionId;

      switch (msg.type) {
        case 'ready':
          cur.setWsConnected(true);
          cur.setConversationId(msg.conversation_id);
          break;
        case 'transcript':
          if (sessionId) {
            cur.addMessage(sessionId, { role: 'user', text: msg.text });
          }
          break;
        case 'response':
          if (sessionId) {
            cur.addMessage(sessionId, { role: 'assistant', text: msg.text });
          }
          break;
        case 'done':
          cur.setProcessing(false);
          break;
        case 'error':
          cur.setError(msg.message);
          cur.setProcessing(false);
          break;
      }
    };

    ws.onclose = () => {
      storeRef.current.setWsConnected(false);
      // Reconnect with exponential backoff if still in ws mode
      if (storeRef.current.mode === 'websocket') {
        const delay = Math.min(
          WS_RECONNECT_BASE_MS * 2 ** wsReconnectAttempt.current,
          WS_RECONNECT_MAX_MS,
        );
        wsReconnectAttempt.current += 1;
        wsReconnectTimer.current = setTimeout(() => connectWs(), delay);
      }
    };

    ws.onerror = () => {
      storeRef.current.setError('Błąd połączenia WebSocket');
    };
  }, [playAudio]);

  const startRecordingWs = useCallback(async () => {
    try {
      ensureSession();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getRecorderMime();
      const recorder = new MediaRecorder(stream, { mimeType });

      chunksRef.current = [];
      connectAnalyser(stream);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start(WS_TIMESLICE_MS);
      storeRef.current.setRecording(true);
      storeRef.current.setError(null);
    } catch (err) {
      storeRef.current.setError(
        err instanceof Error ? err.message : 'Nie udało się uzyskać dostępu do mikrofonu',
      );
    }
  }, [connectAnalyser, ensureSession]);

  const stopRecordingWs = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;

    recorder.stop();
    recorder.stream.getTracks().forEach((t) => t.stop());

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send('END');
    }

    storeRef.current.setRecording(false);
    storeRef.current.setProcessing(true);
  }, []);

  // --- Voice Command (for command chips) ---
  const executeCommand = useCallback(
    async (commandText: string) => {
      const s = storeRef.current;
      s.setProcessing(true);
      s.setError(null);

      try {
        const sessionId = ensureSession();
        s.addMessage(sessionId, { role: 'user', text: commandText });

        // Use TTS to speak the command and play back
        const ttsBlob = await textToSpeech(commandText, s.voiceName);
        // Create a temporary audio blob to send as a voice command
        // For text-based commands, we add the text directly and use TTS for response
        s.addMessage(sessionId, {
          role: 'assistant',
          text: `Wykonuję: ${commandText}`,
        });

        if (s.autoPlayTts) {
          playAudio(ttsBlob);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        storeRef.current.setError(
          err instanceof Error ? err.message : 'Błąd wykonania komendy',
        );
      } finally {
        storeRef.current.setProcessing(false);
      }
    },
    [ensureSession, playAudio],
  );

  // --- Keyboard shortcut (Space = push-to-talk) ---
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && !isInputFocused()) {
        e.preventDefault();
        if (storeRef.current.mode === 'http') {
          void startRecording();
        } else {
          void startRecordingWs();
        }
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !isInputFocused()) {
        e.preventDefault();
        if (storeRef.current.mode === 'http') {
          void stopRecording();
        } else {
          stopRecordingWs();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [startRecording, stopRecording, startRecordingWs, stopRecordingWs]);

  // --- WS lifecycle ---
  useEffect(() => {
    if (store.mode === 'websocket') {
      connectWs();
    }
    return () => {
      wsRef.current?.close();
      if (wsReconnectTimer.current) {
        clearTimeout(wsReconnectTimer.current);
      }
    };
  }, [store.mode, connectWs]);

  // --- Cleanup on unmount ---
  useEffect(() => {
    return () => {
      void audioContextRef.current?.close();
      mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return {
    // State from store
    isRecording: store.isRecording,
    isProcessing: store.isProcessing,
    isPlaying: store.isPlaying,
    error: store.error,
    wsConnected: store.wsConnected,
    mode: store.mode,
    language: store.language,
    autoPlayTts: store.autoPlayTts,
    voiceName: store.voiceName,
    sessions: store.sessions,
    activeSessionId: store.activeSessionId,
    conversationId: store.conversationId,

    // Store actions
    setMode: store.setMode,
    setLanguage: store.setLanguage,
    setAutoPlayTts: store.setAutoPlayTts,
    setVoiceName: store.setVoiceName,
    setActiveSession: store.setActiveSession,
    deleteSession: store.deleteSession,
    clearSessions: store.clearSessions,
    setError: store.setError,

    // Hook-provided
    analyserNode: analyserRef.current,
    startRecording: store.mode === 'http' ? startRecording : startRecordingWs,
    stopRecording: store.mode === 'http' ? stopRecording : stopRecordingWs,
    playAudio,
    stopPlayback,
    executeCommand,
  };
}
