# Part 7: Voice & Real-time

## Cel
Interfejs głosowy: push-to-talk, real-time transcription, TTS playback, voice commands.

## Funkcjonalności
1. **Push-to-Talk** — przycisk (lub skrót klawiszowy Space) nagrywa audio via MediaRecorder API
2. **WebSocket voice** — stream audio chunks do `/ws/voice`, receive transcription + answer w real-time
3. **Waveform** — wizualizacja audio (during recording + playback)
4. **TTS playback** — odpowiedź AI odczytywana głosem (edge-tts, MP3)
5. **Voice commands** — "brief", "status", "market scan" → quick actions
6. **Floating voice button** — dostępny z każdej strony (FAB w prawym dolnym rogu)
7. **Transcript history** — lista voice sessions z transcriptions

## API Endpoints
- `POST /voice/transcribe` — audio → text
- `POST /voice/ask` — audio → text → answer → optional TTS
- `POST /voice/command` — voice command
- `POST /voice/tts` — text → MP3
- `GET /voice/health` — pipeline status
- `WebSocket /voice/ws` — real-time bidirectional

## Tech
- `MediaRecorder` API (browser) / Tauri audio plugin (desktop)
- WebSocket binary frames (audio chunks) + JSON text frames (responses)
- Audio playback: `HTMLAudioElement` with MP3 blobs
- Waveform: Canvas API or `wavesurfer.js`

## RBAC
- Voice: board+ (same as chat, but more resource-intensive)
