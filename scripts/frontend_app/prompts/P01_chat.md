# Part 1: Chat Core — Multi-conversation AI Assistant

## Cel
Zbuduj główny moduł czatu — serce aplikacji. Multi-conversation, streaming, attachments, historia, source references.

## Funkcjonalności
1. **Lista konwersacji** (lewy panel): tworzenie nowych, przełączanie, usuwanie, szukanie w historii
2. **Okno czatu** (środek): wiadomości user/assistant, Markdown rendering, code blocks, tabele
3. **Source references**: po każdej odpowiedzi AI — lista źródeł (email, Teams, dokument) z linkami
4. **Attachments**: upload plików (PDF, DOCX, XLSX, IMG) — załączane do wiadomości
5. **Streaming**: odpowiedzi AI pojawiają się token po tokenie (SSE lub polling)
6. **Conversation context**: follow-up questions, "expand on that" — sliding window 20 messages
7. **Persist**: conversations w Zustand + localStorage, sync z backendem
8. **Quick actions**: w input field — `/brief`, `/timeline`, `/meeting-prep` jako shortcuts

## API Endpoints
- `POST /ask` — główne zapytanie (query, top_k, source_types, date_from/to, answer_length, channel, session_id)
- `GET /conversation/windows` — lista aktywnych konwersacji
- Response shape: `{answer, sources[], matches[], meta, run_id}`

## Komponenty (assistant-ui)
- Użyj `assistant-ui` dla: message list, input field, streaming display
- Custom: conversation sidebar, source cards, attachment chips, quick action buttons

## RBAC
- Wszyscy zalogowani użytkownicy mają dostęp do chatu
- `source_types` filtrowane per rola (specialist nie widzi confidential sources)
- `answer_length` domyślnie "long" dla CEO, "medium" dla specialist

## State (Zustand)
```typescript
interface ChatStore {
  conversations: Conversation[]
  activeId: string | null
  createConversation: () => string
  sendMessage: (text: string, attachments?: File[]) => Promise<void>
  // ...
}
```

## UX
- Nowa konwersacja: duże pole input na środku (jak ChatGPT)
- W konwersacji: messages scroll, input fixed na dole
- Sources: collapsible panel pod odpowiedzią, ikona źródła (email/teams/doc/whatsapp)
- Attachments: drag-and-drop lub button, preview przed wysłaniem
- Loading: skeleton + typing indicator
- Error: toast + retry button
