# Part 9: Desktop Build & Polish

## Cel
Finalizacja: Tauri desktop build, offline support, animacje, error handling, end-to-end testing.

## Tauri Desktop
1. **Build config**: window size, title bar, system tray icon, menu
2. **System tray**: quick actions (new chat, voice, brief), notification badge
3. **Auto-update**: check for updates on startup (Tauri updater plugin)
4. **Deep links**: `gilbertus://ask?q=...` protocol handler
5. **Native notifications**: system-level toast for alerts
6. **Build**: .msi (Windows), .dmg (macOS), .AppImage (Linux)

## Offline Support
1. **IndexedDB cache**: recent dashboard, brief, conversations
2. **Service Worker**: cache static assets for instant load
3. **Offline indicator**: banner when API unreachable
4. **Queue**: messages typed offline → sent when back online

## Polish & UX
1. **Animations**: page transitions (fade), sidebar collapse (slide), card hover (scale)
2. **Skeleton loaders**: consistent across all views
3. **Error boundaries**: per-page catch with retry button
4. **Empty states**: illustrations + "no data yet" messages
5. **Responsive**: desktop-first, tablet OK, mobile basic
6. **Keyboard shortcuts**: documented, consistent
7. **Loading states**: button spinners, progress bars

## Testing
1. **Build gate**: `pnpm --filter web build` zero errors
2. **Lint**: `pnpm --filter web lint` zero warnings
3. **Type check**: `tsc --noEmit` zero errors
4. **Manual E2E**:
   - Login → dashboard loads with brief
   - Chat → create conversation, send message, get answer with sources
   - People → directory → profile → sentiment chart
   - Compliance → dashboard → matter detail
   - Voice → push-to-talk → transcription → answer
   - Settings → change language → UI switches to English
   - Desktop → open app, system tray, native notification

## Acceptance
- Windows .msi installer < 50MB
- App opens in < 2s, idle RAM < 100MB
- All 12 modules accessible and functional
- RBAC works: different roles see different sidebar items
- Polish default, English switchable
- Dark theme polished, light theme functional
