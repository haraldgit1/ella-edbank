# RAG Document Type Enhancement — Phase 1

Erweiterung des RAG-Importers um zusätzliche Dokumenttypen mit geringem Implementierungsaufwand.
Stand: 2026-07-21

---

## Ausgangslage

Der aktuelle Importer (`app/src/edbank/rag/importer.py`) ist hart auf ORA-CSV verdrahtet:

- Pflichtfelder `error_code` + `description` (ORA-spezifisch)
- Validierung auf Pattern `ORA-NNNNN`
- Chunk-Text wird aus festen Feldern zusammengebaut (`_build_rag_text`)
- Quelle (`source_name`) wird korrekt gespeichert, aber der RAG-Retriever
  filtert nur nach `record_key` — die tatsächliche Quelldatei erscheint
  in der Antwort immer korrekt, solange `source_name` im Chunk-Metadatum stimmt

**Bekannter Schönheitsfehler:** Beim Import mehrerer ORA-CSV-Dateien
(ora_sample.csv, ora_sample_v2.csv, ora_sample_v3.csv) wurde als Quellenangabe
in der Antwort stets die erste Datei angezeigt. Ursache: Der Retriever liefert
`source_name` aus `rag.chunk.metadata`, aber die Anzeige im Frontend greift
auf das erste Suchergebnis. Wird im Zuge dieser Erweiterung behoben.

---

## Ziel

- Generischer Importer: kein ORA-spezifisches Hard-Coding mehr im Kern
- Neue Dokumenttypen über dedizierte Parser einbinden
- ORA-CSV bleibt vollständig unterstützt (Parser als Spezialfall)
- Korrekte Quellenangabe pro Chunk in Antwort und Metadaten

---

## Zu implementierende Dokumenttypen (Phase 1)

| # | Typ | Endungen | Parser-Strategie |
|---|---|---|---|
| 1 | **Plain-Text** | `.txt`, `.md` | Absätze (Leerzeilen) als Chunks; bei `.md` Markdown-Überschriften als Chunk-Grenzen |
| 2 | **CSV (generisch)** | `.csv` | Jede Zeile = ein Chunk; Spaltenname + Wert ergeben lesbaren Text; ORA-Sonderlogik optional aktivierbar |
| 3 | **RTF** | `.rtf` | RTF-Tags entfernen → Plain-Text → wie Plain-Text-Parser behandeln |
| 4 | **HTML** | `.html`, `.htm` | Tags entfernen (BeautifulSoup); sichtbarer Text in Absätze zerlegen |

---

## Architektur

### Parser-Interface

Jeder Parser ist eine Python-Funktion mit einheitlicher Signatur:

```python
def parse(content: bytes, filename: str) -> list[ParsedChunk]:
    ...
```

```python
@dataclass
class ParsedChunk:
    record_key: str          # eindeutiger Schlüssel innerhalb des Dokuments
    content: str             # der Text, der eingebettet wird
    metadata: dict           # beliebige Zusatzinfos (z.B. Überschrift, Zeilennummer)
```

### Dispatcher

`app/src/edbank/rag/parsers/__init__.py` wählt den Parser anhand der Dateiendung:

```python
PARSERS = {
    ".csv":  parse_csv,
    ".txt":  parse_plaintext,
    ".md":   parse_plaintext,
    ".rtf":  parse_rtf,
    ".html": parse_html,
    ".htm":  parse_html,
}
```

### Angepasster Importer

`importer.py` wird auf die generische Pipeline umgestellt:

1. Dateiendung bestimmen → Parser auswählen
2. Parser liefert `list[ParsedChunk]`
3. Embedding für alle Chunks berechnen
4. In `rag.document` + `rag.chunk` speichern (unveränderte DB-Struktur)

ORA-spezifische Validierung (Pattern-Check, Pflichtfelder) wandert in den CSV-Parser.

### Upload-Endpunkt

`/api/rag/import` akzeptiert künftig alle unterstützten MIME-Types.
Dateiendung entscheidet den Parser — keine MIME-Type-Erkennung nötig.

---

## Neue Python-Abhängigkeiten

| Paket | Version | Zweck |
|---|---|---|
| `beautifulsoup4` | `>=4.12` | HTML-Parsing |
| `striprtf` | `>=0.0.26` | RTF → Plain-Text |

Zu ergänzen in `app/pyproject.toml`.

---

## Chunking-Strategie je Typ

### Plain-Text / Markdown

- Trennung an Leerzeilen (Absätze)
- Mindestlänge: 50 Zeichen (kürzere Absätze werden mit dem nächsten zusammengeführt)
- Maximallänge: 1000 Zeichen (längere Absätze werden an Satzgrenzen geteilt)
- `record_key`: `{filename}#{chunk_index:04d}`

### CSV (generisch)

- Eine Zeile = ein Chunk
- Chunk-Text: `Spaltenname: Wert\nSpaltenname: Wert\n...` (alle nicht-leeren Spalten)
- ORA-Modus wird automatisch aktiviert, wenn Spalten `error_code` + `description` vorhanden
  und `error_code` dem Pattern `ORA-NNNNN` entspricht
- `record_key`: Wert der ersten Spalte, sonst `{filename}#{zeilennummer}`

### RTF

- RTF-Tags via `striprtf` entfernen → resultierender Plain-Text
- Dann identisch wie Plain-Text-Parser behandeln

### HTML

- BeautifulSoup: `<script>`, `<style>`, `<nav>`, `<footer>` entfernen
- Sichtbaren Text extrahieren
- Dann identisch wie Plain-Text-Parser behandeln

---

## Behobene Schönheitsfehler

1. **Quellenangabe:** `source_name` wird pro Chunk aus `metadata['source_name']` gelesen,
   nicht mehr aus dem ersten Suchergebnis. Der Retriever gibt `source_name` bereits korrekt
   zurück — Anzeige im Frontend wird entsprechend sichergestellt.

2. **ORA-CSV-Hardcoding:** Fällt weg aus dem Kern-Importer; ORA-Logik lebt nur noch
   im CSV-Parser als Spezialfall.

---

## Nicht im Scope (Phase 1)

- PDF (erfordert `pypdf`/`pdfplumber` — mittlerer Aufwand, Phase 2)
- Word .docx (erfordert `python-docx` — mittlerer Aufwand, Phase 2)
- Excel .xlsx / XML (erfordert `openpyxl` — mittlerer Aufwand, Phase 2)
- Chunk-Overlap / Sliding-Window-Chunking
- Automatische Sprach­erkennung
- Duplikat-Erkennung auf Chunk-Ebene (aktuell nur auf Dokument-Ebene via SHA-256)

---

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `app/pyproject.toml` | `beautifulsoup4`, `striprtf` hinzufügen |
| `app/src/edbank/rag/importer.py` | Generische Pipeline, ORA-Logik entfernen |
| `app/src/edbank/rag/parsers/__init__.py` | Neu: Dispatcher |
| `app/src/edbank/rag/parsers/csv_parser.py` | Neu: generisch + ORA-Spezialfall |
| `app/src/edbank/rag/parsers/plaintext_parser.py` | Neu |
| `app/src/edbank/rag/parsers/rtf_parser.py` | Neu |
| `app/src/edbank/rag/parsers/html_parser.py` | Neu |
| `app/src/edbank/api/rag.py` | MIME-Type-Liste für Upload erweitern |
| `app/tests/test_rag_import.py` | Tests für neue Parser ergänzen |
