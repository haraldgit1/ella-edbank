# Ella-DemoBank — Migrationspfad & Erweiterungsoptionen

Dokumentiert mögliche Erweiterungen und Migrationspfade für spätere Phasen.
Stand: 2026-07-21

---

## 1. RAG — Unterstützbare Dokumenttypen

Aktuell importiert der RAG-Importer ausschließlich ORA-CSV-Dateien mit fester Struktur
(`error_code`, `description`, optional `cause`/`action`). Der Importer prüft das `ORA-NNNNN`-Pattern
hart im Code (`app/src/edbank/rag/importer.py`).

Das Embedding-Modell (`intfloat/multilingual-e5-large`, 384-dim) versteht Semantik — nicht
Dokumentstruktur. Alles, was als Text extrahiert und als Chunk gespeichert wird, kann inhaltlich
abgefragt werden.

### Erweiterbare Dokumenttypen

| Dokumenttyp | Extraktion | Python-Paket | Aufwand |
|---|---|---|---|
| **Plain-Text (.txt, .md)** | Direkt lesen, in Absätze zerlegen | — | sehr gering |
| **CSV (generisch)** | Spalten frei konfigurierbar, nicht nur ORA | — | gering |
| **PDF** | Text extrahieren | `pypdf` oder `pdfplumber` | mittel |
| **Word (.docx)** | XML-Struktur lesen | `python-docx` | mittel |
| **Excel (.xlsx)** | Tabellenzeilen als Chunks | `openpyxl` | mittel |
| **Excel XML (.xml)** | SpreadsheetML parsen | `lxml` / `openpyxl` | mittel |
| **RTF** | RTF → Plain-Text | `striprtf` | gering |
| **HTML** | Tags entfernen | `beautifulsoup4` | gering |

### Hinweis zur Qualität

Tabellenzellen ohne Kontext werden schlechter gefunden als Fließtext. Für strukturierte
Stammdaten (z.B. Konten, Mitarbeiter, Produkte) ist MCP die bessere Wahl — RAG ist für
Wissensdokumente optimiert.

### Umsetzung

- Neuen Parser pro Dokumenttyp in `app/src/edbank/rag/` anlegen
- `importer.py` verallgemeinern: ORA-Pflichtfelder herauslösen, generische Chunk-Pipeline bauen
- Upload-Endpunkt (`/api/rag/import`) auf mehrere MIME-Types erweitern

---

## 2. PostgreSQL — Migration auf größeren Rechner

**Kein Codeaufwand.** Das System ist sauber über Verbindungsstrings abstrahiert.

### Schritte

1. pgvector auf dem Zielserver installieren (gleiche oder höhere Version, kompatibel ab 0.8.x)
2. Daten migrieren:
   ```bash
   # Option A: Docker-Volume kopieren (einfachste Methode)
   docker run --rm -v edbank_postgres_data:/data -v $(pwd):/backup \
     alpine tar czf /backup/postgres_backup.tar.gz /data

   # Option B: logischer Dump
   pg_dump -h 127.0.0.1 -U edbank_owner edbank > edbank_dump.sql
   psql -h NEUER_HOST -U edbank_owner edbank < edbank_dump.sql
   ```
3. Verbindungsstrings in `.env` anpassen:
   ```dotenv
   APP_DATABASE_URL=postgresql+psycopg://edbank_app:PW@NEUER_HOST:5432/edbank
   MCP_DATABASE_URL=postgresql+psycopg://edbank_reader:PW@NEUER_HOST:5432/edbank
   POSTGRES_HOST=NEUER_HOST
   ```
4. Container neu starten — fertig.

Schema (banking + rag), Rollen (`edbank_owner`, `edbank_app`, `edbank_reader`) und alle Daten
wandern 1:1 mit.

---

## 3. Sprachmodell — Migration auf stärkeres Modell

**Kein Codeaufwand**, solange das Modell eine OpenAI-kompatible API anbietet.

### Konfiguration (nur `.env`)

```dotenv
LLM_MODEL=neues-modell-name
LLM_BASE_URL=http://NEUE_ADRESSE:PORT/v1
LLM_API_KEY=optional-falls-erforderlich
```

### Szenarien

| Szenario | Änderung | Hinweis |
|---|---|---|
| Stärkeres Modell in LM Studio (z.B. Mistral 22B, Llama 3 70B) | `LLM_MODEL` in `.env` | Muss `<tool_call>`-Tags erzeugen — Prompt testen |
| vLLM / Ollama auf GPU-Server | `LLM_BASE_URL` + `LLM_MODEL` | Gleiche OpenAI-kompatible API |
| Echte OpenAI API (cloud) | `LLM_BASE_URL=https://api.openai.com/v1` + API-Key | Native tool-use möglich → siehe unten |
| Anderes cloud-Modell (Azure OpenAI, Anthropic via Proxy) | URL + Key | Je nach API-Kompatibilität |

### Optionale Code-Anpassung: Native Tool-Use

Der aktuelle `<tool_call>`-Parsing-Mechanismus in `app/src/edbank/llm/tool_loop.py` wurde
für Mistral v0.3 entwickelt, weil dieses Modell die OpenAI `tools`-API ablehnt.

Modelle mit nativer Tool-Use-Unterstützung (GPT-4o, Llama 3.1+, Mistral Large) können
direkt über die OpenAI `tools`-API angebunden werden. Das wäre eine überschaubare
Refaktorierung von `tool_loop.py` (~80 Zeilen) — kein Eingriff in die restliche Architektur.

---

## Zusammenfassung

| Bereich | Aufwand für Migration |
|---|---|
| PostgreSQL auf neuen Host | Nur `.env` anpassen + Datenmigration |
| Stärkeres Modell (gleicher API-Typ) | Nur `.env` anpassen |
| Modell mit nativer Tool-Use | `tool_loop.py` refaktorieren (~80 Zeilen) |
| Neue Dokumenttypen im RAG | Neuer Parser + Importer verallgemeinern |
