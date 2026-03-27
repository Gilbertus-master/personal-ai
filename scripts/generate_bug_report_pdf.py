#!/usr/bin/env python3
"""Generate extraction bug report PDF using only stdlib (no external deps)."""

import sys


class SimplePDF:
    """Minimal PDF generator — no external dependencies."""

    def __init__(self):
        self.objects = []
        self.pages = []
        self.current_page_streams = []
        self.font_size = 11
        self.line_height = 14
        self.margin_left = 50
        self.margin_top = 50
        self.page_width = 595  # A4
        self.page_height = 842
        self.y = self.page_height - self.margin_top
        self.max_y = self.margin_top + 30

    def _add_object(self, content):
        self.objects.append(content)
        return len(self.objects)

    def _new_page(self):
        if self.current_page_streams:
            self._finish_page()
        self.current_page_streams = []
        self.y = self.page_height - self.margin_top

    def _finish_page(self):
        stream = "\n".join(self.current_page_streams)
        self.pages.append(stream)

    def _escape(self, text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _sanitize(self, text):
        # Map Polish chars to ASCII approximations for PDF core fonts
        mapping = {
            "\u0105": "a", "\u0107": "c", "\u0119": "e", "\u0142": "l",
            "\u0144": "n", "\u00f3": "o", "\u015b": "s", "\u017a": "z",
            "\u017c": "z", "\u0104": "A", "\u0106": "C", "\u0118": "E",
            "\u0141": "L", "\u0143": "N", "\u00d3": "O", "\u015a": "S",
            "\u0179": "Z", "\u017b": "Z",
            "\u2014": "--", "\u2013": "-", "\u2026": "...", "\u201e": '"',
            "\u201d": '"', "\u201c": '"', "\u2019": "'", "\u2018": "'",
            "\u00d7": "x",
        }
        result = []
        for ch in text:
            if ch in mapping:
                result.append(mapping[ch])
            elif ord(ch) > 127:
                result.append("?")
            else:
                result.append(ch)
        return "".join(result)

    def set_font_size(self, size):
        self.font_size = size
        self.line_height = size + 3
        self.current_page_streams.append(f"BT /F1 {size} Tf ET")

    def write_line(self, text, bold=False, indent=0):
        if self.y < self.max_y:
            self._new_page()

        clean = self._sanitize(text)
        escaped = self._escape(clean)
        x = self.margin_left + indent
        font = "/F2" if bold else "/F1"
        self.current_page_streams.append(
            f"BT {font} {self.font_size} Tf {x} {self.y:.0f} Td ({escaped}) Tj ET"
        )
        self.y -= self.line_height

    def write_blank(self, lines=1):
        self.y -= self.line_height * lines
        if self.y < self.max_y:
            self._new_page()

    def write_title(self, text):
        self.set_font_size(18)
        self.write_line(text, bold=True)
        self.set_font_size(11)

    def write_heading(self, text):
        self.write_blank()
        self.set_font_size(14)
        self.write_line(text, bold=True)
        self.set_font_size(11)

    def write_subheading(self, text):
        self.write_blank()
        self.set_font_size(12)
        self.write_line(text, bold=True)
        self.set_font_size(11)

    def write_paragraph(self, text, indent=0):
        max_chars = int((self.page_width - self.margin_left * 2 - indent) / (self.font_size * 0.5))
        words = text.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > max_chars:
                self.write_line(line, indent=indent)
                line = word
            else:
                line = f"{line} {word}" if line else word
        if line:
            self.write_line(line, indent=indent)

    def write_bullet(self, text):
        self.write_line(f"  * {text}", indent=10)

    def build(self):
        if self.current_page_streams:
            self._finish_page()

        objs = []
        offsets = []

        # Helper
        def add_obj(content):
            objs.append(content)
            return len(objs)

        # 1: Catalog
        add_obj("<< /Type /Catalog /Pages 2 0 R >>")

        # 2: Pages (placeholder)
        pages_idx = len(objs)  # index 1
        add_obj("")  # filled later

        # 3: Font Helvetica
        add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

        # 4: Font Helvetica-Bold
        add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

        # Build pages
        page_obj_ids = []
        for page_stream in self.pages:
            stream_bytes = page_stream.encode("latin-1", errors="replace")
            stream_id = add_obj(
                f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1")
                + stream_bytes
                + b"\nendstream"
            )
            page_id = add_obj(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_width} {self.page_height}] "
                f"/Contents {stream_id} 0 R "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>"
            )
            page_obj_ids.append(page_id)

        # Update pages object
        kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objs[pages_idx] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_ids)} >>"

        # Serialize
        output = b"%PDF-1.4\n"
        offsets = []
        for i, obj in enumerate(objs):
            offsets.append(len(output))
            obj_num = i + 1
            if isinstance(obj, bytes):
                output += f"{obj_num} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"
            else:
                output += f"{obj_num} 0 obj\n{obj}\nendobj\n".encode("latin-1")

        # xref
        xref_offset = len(output)
        output += b"xref\n"
        output += f"0 {len(objs) + 1}\n".encode("latin-1")
        output += b"0000000000 65535 f \n"
        for off in offsets:
            output += f"{off:010d} 00000 n \n".encode("latin-1")

        output += b"trailer\n"
        output += f"<< /Size {len(objs) + 1} /Root 1 0 R >>\n".encode("latin-1")
        output += b"startxref\n"
        output += f"{xref_offset}\n".encode("latin-1")
        output += b"%%EOF\n"

        return output


def main():
    pdf = SimplePDF()
    pdf._new_page()

    # Title
    pdf.write_title("Raport: Bugi w pipeline ekstrakcji eventow/entities")
    pdf.write_blank()
    pdf.write_line("Data: 2026-03-26")
    pdf.write_line("Status: Naprawione i wdrozone")
    pdf.write_line("Przygotowal: Sebastian Jablonski / Gilbertus AI")

    # Bug 1
    pdf.write_heading("Bug 1: Nieskonczona petla -- brak trackingu negatywnych wynikow")

    pdf.write_subheading("Objaw:")
    pdf.write_paragraph(
        "12 workerow dzialalo, ale przez 14 minut wyciagnely lacznie 1 event "
        "i 14 entities z ~100k chunkow do przetworzenia."
    )

    pdf.write_subheading("Przyczyna:")
    pdf.write_paragraph(
        "Gdy LLM ocenial chunk jako 'brak eventu' lub 'brak entity', ten wynik "
        "nie byl nigdzie zapisywany. Jedynie pozytywne wyniki (znalezione eventy/entities) "
        "trafialy do bazy. W efekcie query LEFT JOIN events ... WHERE e.id IS NULL "
        "za kazdym razem zwracalo te same chunki -- workery przetwarzaly w kolko "
        "te same ~5000 rekordow, za kazdym razem dostawaly 'nic tu nie ma' od LLM, "
        "i zaczynaly od nowa."
    )

    pdf.write_subheading("Fix:")
    pdf.write_paragraph(
        "Dwie nowe tabele: chunks_event_checked i chunks_entity_checked. "
        "Kazdy negatywny wynik jest rejestrowany, a query filtruje: "
        "LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id "
        "WHERE ... AND cec.chunk_id IS NULL."
    )

    # Bug 2
    pdf.write_heading("Bug 2: Brak partycjonowania -- 6 workerow robilo to samo")

    pdf.write_subheading("Objaw:")
    pdf.write_paragraph(
        "6 event workerow (i 6 entity workerow) mialo identyczne CPU time "
        "(~7s kazdy po 14 minutach), co wskazywalo na identyczna prace."
    )

    pdf.write_subheading("Przyczyna:")
    pdf.write_paragraph(
        "Kazdy worker wykonywal ten sam SQL: SELECT ... FROM chunks ... ORDER BY c.id LIMIT 5000. "
        "Wszystkie 6 workerow pobieralo identyczny zestaw 5000 chunkow. Poniewaz bug #1 "
        "powodowal brak zapisu negatywow, chunki nigdy nie 'znikaly' z kolejki -- workery "
        "krecily sie na tych samych danych w nieskonczonosc."
    )

    pdf.write_subheading("Fix:")
    pdf.write_paragraph(
        "Nowy parametr --worker X/N (np. --worker 2/6). Dodaje klauzule "
        "AND c.id %% N = X do query, wiec kazdy worker przetwarza wylacznie "
        "swoja partycje chunkow. Zero duplikacji."
    )

    # Bug 3
    pdf.write_heading("Bug 3: Zbyt restrykcyjny prompt LLM")

    pdf.write_subheading("Objaw:")
    pdf.write_paragraph(
        "Z przetwarzanych chunkow ~99% bylo odrzucanych jako 'brak eventu'. "
        "Nawet wartosciowe tresci (emaile biznesowe, decyzje w Teams) byly pomijane."
    )

    pdf.write_subheading("Przyczyna:")
    pdf.write_paragraph(
        "System prompt zawieral instrukcje 'Be conservative' oraz waska definicje "
        "eventow. W polaczeniu z faktem, ze workery zaczynaly od najstarszych chunkow "
        "(ChatGPT Q&A -- przepisy, pytania o prawo pracy), hit rate byl bliski zeru."
    )

    pdf.write_subheading("Fix:")
    pdf.write_bullet("Usunieto 'Be conservative' z promptow event i entity extraction")
    pdf.write_bullet("Rozszerzono definicje eventow o: commitments, deadlines,")
    pdf.write_line("    task assignments, status updates, negotiations, escalations,", indent=20)
    pdf.write_line("    approvals, rejections", indent=20)
    pdf.write_bullet("Dodano filtr MIN_TEXT_LENGTH = 50 chars")

    # Impact table
    pdf.write_heading("Wplyw")
    pdf.write_blank()
    pdf.write_line("Metryka                              | Przed          | Po", bold=True)
    pdf.write_line("---------------------------------------------------------------------")
    pdf.write_line("Nowe eventy/godzine                  | ~0 (petla)     | W trakcie weryfikacji")
    pdf.write_line("Duplikacja pracy workerow            | 6x (identyczne)| 0 (partycjonowanie)")
    pdf.write_line("Chunki do przetworzenia (events)     | 102,530        | ~102,500 (run w toku)")
    pdf.write_line("Chunki do przetworzenia (entities)   | 93,573         | ~93,500 (run w toku)")

    # Files changed
    pdf.write_heading("Pliki zmienione")
    pdf.write_bullet("app/extraction/events.py -- tracking negatywow, partycjonowanie, nowy prompt")
    pdf.write_bullet("app/extraction/entities.py -- tracking negatywow, partycjonowanie")
    pdf.write_bullet("scripts/turbo_extract.sh -- parametr num_workers, partycjonowanie")
    pdf.write_bullet("Nowe tabele DB: chunks_event_checked, chunks_entity_checked")

    # Write
    data = pdf.build()
    output_path = sys.argv[1] if len(sys.argv) > 1 else "bug_report.pdf"
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"PDF saved: {output_path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
