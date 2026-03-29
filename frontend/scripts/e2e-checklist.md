# Gilbertus Frontend — Manual E2E Test Checklist

Run through each section after a new build. Check off each item as it passes.

---

## Auth & Access

- [ ] Login with API key → redirects to dashboard
- [ ] Invalid API key → shows error
- [ ] RBAC: CEO role sees all sidebar items
- [ ] RBAC: Specialist role sees limited sidebar

## Dashboard

- [ ] Dashboard loads with morning brief
- [ ] Widgets show real data (entities, events, chunks counts)
- [ ] Alerts section shows active alerts
- [ ] Loading skeleton appears before data

## Chat

- [ ] Create new conversation
- [ ] Send message, receive AI answer with sources
- [ ] Conversation persists in list
- [ ] Voice button activates push-to-talk

## People

- [ ] Directory loads with list/table
- [ ] Click person → profile page with sentiment chart
- [ ] Network graph renders

## Compliance

- [ ] Dashboard shows compliance status
- [ ] Matter detail page loads
- [ ] Obligations list renders

## Other Modules

- [ ] Intelligence page loads
- [ ] Market page with alerts
- [ ] Finance/costs page
- [ ] Process page
- [ ] Decisions page
- [ ] Documents page
- [ ] Calendar page
- [ ] Admin pages (status, crons, users)

## Settings & i18n

- [ ] Settings page loads
- [ ] Change language to English → all UI switches
- [ ] Change back to Polish → all UI switches
- [ ] Dark theme is polished (no white flashes)
- [ ] Light theme is functional

## Polish & UX

- [ ] Page transitions animate (fade in)
- [ ] Sidebar collapse animates smoothly
- [ ] Error boundary works (force error → retry button)
- [ ] Empty states show when no data
- [ ] Offline banner appears when API down
- [ ] Command palette opens with Ctrl+K

## Desktop (Tauri)

- [ ] App opens in < 2s
- [ ] System tray icon appears
- [ ] Tray menu: Brief, New Chat, Voice, Close
- [ ] Native notification on critical alert
- [ ] Deep link: gilbertus://ask?q=test
- [ ] Idle RAM < 100MB
- [ ] Windows .msi installer < 50MB
