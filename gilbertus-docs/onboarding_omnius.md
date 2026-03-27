# Omnius — Przewodnik dla Operatorów

## Co to jest Omnius?

Omnius to asystent AI Twojej spółki. Działa jak wirtualny analityk, który:
- Przeszukuje dokumenty firmowe, emaile, Teams, SharePoint
- Odpowiada na pytania o sprawy spółki
- Tworzy tickety, wysyła emaile, planuje spotkania
- Raportuje do Sebastiana (owner) w formie zagregowanych podsumowań

**Omnius REH** — dla Respect Energy Holding (operator: Roch)
**Omnius REF** — dla Respect Energy Fuels (operator: Krystian)

---

## Jak korzystać

### Pytania (search + answer)
Napisz pytanie w naturalnym języku:

```
Jakie mamy aktywne kontrakty PPA?
Kiedy upływa termin na ofertę dla Taurona?
Podsumuj emaile z URE z ostatniego tygodnia
Co ustaliliśmy na ostatnim spotkaniu z Eneą?
```

Omnius przeszuka dostępne dokumenty i odpowie z podaniem źródeł.

### Komendy (actions)
```
ticket: Sprawdzić warunki kontraktu XYZ — deadline piątek
email: roch@reh.pl — temat: Status projektu Qaira — treść: ...
spotkanie: z Markiem Kulpą, temat PPA, przyszły wtorek 10:00
```

### Status
```
status          — stan systemu Omnius
moje tickety    — lista otwartych zadań
```

---

## Co Omnius widzi (i czego nie widzi)

### Widzi:
- Dokumenty firmowe (SharePoint, shared drives)
- Teams channels (grupowe, nie prywatne)
- Emaile firmowe (shared mailbox)
- Kalendarz firmowy
- Tickety i zadania

### NIE widzi:
- Prywatnych wiadomości Sebastiana
- Danych z drugiej spółki (REH nie widzi REF i odwrotnie)
- Danych osobowych pracowników (wynagrodzenia, oceny, zwolnienia)
- Konta bankowe, przelewy

---

## Role i uprawnienia

| Rola | Kto | Co może |
|------|-----|---------|
| **Admin** | Sebastian | Wszystko: konfiguracja, prompty, użytkownicy, audit log |
| **Operator** | Roch / Krystian | Pytania, tickety, emaile, spotkania. Nie: konfiguracja, dane innych spółek |

---

## Gilbertus vs Omnius

| | Gilbertus | Omnius |
|---|-----------|--------|
| **Dla kogo** | Sebastian (owner) | Roch / Krystian (operatorzy) |
| **Dane** | Wszystko (prywatne + firmowe + cross-company) | Tylko jedna spółka |
| **Cel** | Strategiczne zarządzanie, decyzje | Operacyjne wsparcie spółki |
| **Interfejs** | WhatsApp, MCP, Voice, API | Teams / WhatsApp / Web |

Omnius raportuje do Gilbertusa (podsumowania, nie raw data).
Gilbertus zarządza Omniusami (konfiguracja, prompty, monitoring).

---

## FAQ

**Czy Omnius czyta moje prywatne wiadomości?**
Nie. Omnius ma dostęp tylko do danych firmowych (shared channels, shared mailbox).

**Czy Sebastian widzi moje rozmowy z Omniusem?**
Tak — w audit logu. To narzędzie firmowe, nie prywatne.

**Czy mogę poprosić Omniusa o ocenę pracownika?**
Nie. People analytics wymagają osobnego uprawnienia i nie są dostępne w V1.

**Co jeśli Omnius odpowie źle?**
Napisz: "To nieprawda" lub "Błąd: [co jest źle]". Feedback jest logowany i poprawia przyszłe odpowiedzi.

**Jak dodać nowe dokumenty?**
Wgraj na SharePoint / shared drive. Omnius indeksuje automatycznie co godzinę.

---

## Kontakt

Problemy techniczne → Sebastian (przez Gilbertusa)
Sugestie → kanał Teams: #omnius-feedback
