# D24: Korekta językowa i ortograficzna wszystkich dokumentów

## Zadanie
Przejrzyj WSZYSTKIE wygenerowane dokumenty w folderach Omnius_REH i Omnius_REF. Dla każdego dokumentu:
1. Sprawdź ortografię i gramatykę (język polski)
2. Sprawdź spójność terminologii między dokumentami
3. Popraw błędy interpunkcyjne
4. Sprawdź poprawność odniesień do aktów prawnych (numery artykułów, nazwy ustaw)
5. Sprawdź czy nazwy spółek są poprawne (REH = Respect Energy Holding S.A., REF = Respect Energy Fuels sp. z o.o.)
6. Sprawdź numerację paragrafów i sekcji
7. Popraw formatowanie Markdown (nagłówki, tabele, listy)

## Procedura

### Krok 1: Lista plików
```bash
echo "=== REH ===" && ls -1 /mnt/c/Users/jablo/Desktop/Omnius_REH/*.md 2>/dev/null && echo "=== REF ===" && ls -1 /mnt/c/Users/jablo/Desktop/Omnius_REF/*.md 2>/dev/null
```

### Krok 2: Dla KAŻDEGO pliku

Przeczytaj plik narzędziem Read, następnie sprawdź i popraw:

**Ortografia i gramatyka:**
- Polskie znaki diakrytyczne (ą, ę, ć, ł, ń, ó, ś, ź, ż) — czy są wszędzie poprawne
- Odmiana przypadków (dopełniacz, celownik, biernik) — szczególnie w kontekście prawnym
- Spójność form (np. nie mieszać "Pracodawca" z "pracodawca" w tym samym kontekście)
- Poprawność form czasowników (strona bierna vs czynna)
- Przecinki przed "który/która/które", "że", "aby", "żeby"
- Przecinki w wyliczeniach
- Kropki na końcu punktów w wyliczeniach (spójnie)

**Terminologia prawna (spójność w WSZYSTKICH dokumentach):**
- "Administrator danych" (nie "administrator", nie "Admin")
- "Podmiot przetwarzający" (nie "procesor")
- "Osoba, której dane dotyczą" lub "podmiot danych"
- "Inspektor Ochrony Danych" / "IOD" (nie "DPO" w polskich dokumentach)
- "Organ nadzorczy" / "UODO" (nie "urząd")
- "Naruszenie ochrony danych osobowych" (nie "breach" w polskim tekście)
- "Ocena skutków dla ochrony danych" (nie "DPIA" w treści — DPIA tylko jako skrót w nawiasie)
- "Rozporządzenie AI Act" lub "Rozporządzenie w sprawie sztucznej inteligencji" (nie "AI Act" samodzielnie)
- "Kodeks pracy" z małej litery "pracy" (zgodnie z polską konwencją)
- "RODO" lub "Rozporządzenie 2016/679" (nie "GDPR" w polskich dokumentach)

**Odniesienia prawne — poprawność:**
- Art. 35 RODO (nie "Art. 35 GDPR")
- Art. 22³ Kodeksu pracy (nie "Art. 22(3) KP" — ale format 22² i 22³ jest OK w tekście technicznym)
- Dz.U. — format: "Dz.U. 2024 poz. 266" (nie "Dz.U.2024.266")
- EU 2016/679 — format: "Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2016/679" (pierwsze użycie), potem "RODO"
- EU 2024/1689 — "Rozporządzenie (UE) 2024/1689 w sprawie sztucznej inteligencji" (pierwsze użycie), potem "Rozporządzenie AI" lub "AI Act"

**Nazwy spółek — weryfikacja:**
- Dokumenty REH: "Respect Energy Holding S.A." (nie "sp. z o.o.", nie "Sp. z o.o.")
- Dokumenty REF: "Respect Energy Fuels sp. z o.o." (nie "S.A.", nie "Sp. z o.o.")
- KRS REH: 0000935926
- Adres REH: ul. Podskarbińska 2, 03-833 Warszawa

**Formatowanie Markdown:**
- Nagłówki: # Tytuł dokumentu, ## Sekcja, ### Podsekcja (spójne)
- Tabele: poprawne wyrównanie kolumn, separator `|---|---|`
- Listy: spójne markery (-, 1., a), ☐)
- Brak podwójnych spacji, brak trailing whitespace
- Brak pustych linii na końcu/początku

### Krok 3: Zapisz poprawiony plik
Użyj narzędzia Write aby nadpisać plik poprawioną wersją. Nie zmieniaj treści merytorycznej — TYLKO korekta językowa i formatowania.

### Krok 4: Raport korekt
Na końcu wygeneruj plik `/mnt/c/Users/jablo/Desktop/Omnius_REH/00_RAPORT_KOREKTY.md` i `/mnt/c/Users/jablo/Desktop/Omnius_REF/00_RAPORT_KOREKTY.md` z listą:
- Ile plików sprawdzono
- Ile poprawek w każdym pliku
- Najczęstsze typy błędów
- Czy terminologia jest spójna między dokumentami
- Lista ewentualnych problemów merytorycznych (do weryfikacji przez prawnika)

## WAŻNE:
- NIE zmieniaj treści merytorycznej dokumentów
- NIE dodawaj nowych sekcji
- NIE usuwaj istniejących treści
- Poprawiaj TYLKO: ortografię, gramatykę, interpunkcję, formatowanie, spójność terminologii
- Jeśli znajdziesz BŁĄD MERYTORYCZNY (np. złe powołanie artykułu), zanotuj w raporcie ale NIE poprawiaj samodzielnie
