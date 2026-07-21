# Ella-DemoBank

Lokaler Proof of Concept für die ELLA-Architektur:
**Lokales LLM + RAG + MCP + Function Calling** — vollständig offline, kein Cloud-API-Schlüssel.

---

## Architektur

```
Browser
  ↓
NGINX  (127.0.0.1:8080)
  ↓
edbank-app  (FastAPI, Python 3.12)
  ├── RAG  → PostgreSQL/pgvector  (intfloat/multilingual-e5-small, 384-dim)
  ├── MCP-Client → mcp-server → PostgreSQL  (read-only, edbank_reader)
  └── LLM-API  → LM Studio auf macOS  (Mistral 7B, Metal, http://127.0.0.1:1234/v1)
```

| Service | Technologie |
|---|---|
| LLM | LM Studio · Mistral-7B-Instruct-v0.3 Q4\_K\_M · Metal |
| App | FastAPI · Uvicorn · SQLAlchemy 2 · psycopg 3 |
| Embedding | intfloat/multilingual-e5-small (CPU, 384-dim) |
| MCP | FastMCP 1.28.1 · Streamable HTTP · stateless |
| Datenbank | pgvector/pgvector:0.8.5-pg16 · Schemas `banking` + `rag` |
| Frontend | NGINX · Vanilla HTML/JS |

---

## Voraussetzungen

| Werkzeug | Version |
|---|---|
| Docker Desktop | 4.x (Mac, ARM64) |
| LM Studio | aktuell |
| macOS | Apple Silicon (M1/M2/M3) |

---

## Einrichtung

### 1 — Modell in LM Studio laden

1. LM Studio öffnen → **Discover** → `mistralai/Mistral-7B-Instruct-v0.3`
2. GGUF-Variante wählen: **Q4\_K\_M** (ca. 4,1 GB)
3. Modell laden → **Developer** → **Local Server starten**
4. Sicherstellen: Server läuft auf `http://127.0.0.1:1234`

### 2 — Umgebungsvariablen anlegen

```bash
cp .env.example .env
```

Die Standardwerte funktionieren sofort für die lokale Entwicklung.
Passwörter in `.env` vor einem Produktiveinsatz ändern.

### 3 — Container starten

```bash
docker compose up -d
```

Beim ersten Start werden alle Images gebaut (inkl. Embedding-Modell-Download, ca. 90 MB).

### 4 — Status prüfen

```bash
curl http://localhost:8080/api/health
```

Erwartete Antwort wenn alle Komponenten bereit sind:

```json
{
  "status": "ok",
  "components": {
    "app": "ok",
    "postgres": "ok",
    "pgvector": "ok",
    "mcp_server": "ok",
    "llm_server": "ok"
  }
}
```

### 5 — Weboberfläche öffnen

```
http://localhost:8080
```

---

## Wissensbasis importieren

Im Browser: **ORA-CSV importieren** → `data/samples/ora_sample.csv` hochladen.

Oder per API:

```bash
curl -X POST http://localhost:8080/api/rag/import \
  -F "file=@data/samples/ora_sample.csv"
```

---

## Beispielanfragen

**Oracle-Fehler (RAG):**
```
Was bedeutet ORA-01555 und was kann ich dagegen tun?
```

**Bankkonten (MCP):**
```
Welchen IBAN hat Herr Hannes Meier?
```

---

## Tests ausführen

```bash
# App-Tests (40 Tests, inkl. Embedding-Modell)
PYTHONPATH=app/src \
APP_DATABASE_URL="postgresql+psycopg://x:x@localhost/x" \
MCP_DATABASE_URL="postgresql+psycopg://x:x@localhost/x" \
python3 -m pytest app/tests/ -v

# MCP-Server-Tests (4 Tests)
PYTHONPATH=mcp-server/src \
MCP_DATABASE_URL="postgresql+psycopg://x:x@localhost/x" \
python3 -m pytest mcp-server/tests/ -v
```

---

## Datenbankzugriff (Entwicklung)

Der Dev-Port ist in `docker-compose.yml` aktiviert:

| Feld | Wert |
|---|---|
| Host | `127.0.0.1` |
| Port | `5432` |
| Datenbank | `edbank` |
| Benutzer | `edbank_owner` |
| Passwort | `change-me-owner` (aus `.env`) |

Weitere Rollen: `edbank_app` (RAG r/w), `edbank_reader` (MCP, banking read-only).

---

## Netzwerk

| Komponente | Erreichbar von |
|---|---|
| NGINX `:8080` | Host (Browser) |
| edbank-app `:8000` | NGINX, intern |
| mcp-server `:8001` | edbank-app, intern |
| postgres `:5432` | edbank-app, mcp-server, intern (+ Dev-Host) |
| LM Studio `:1234` | edbank-app via `host.docker.internal` |

PostgreSQL und MCP-Server sind **nicht** aus dem Internet erreichbar.

---

## Ressourcen (Mac M1 16 GB)

| Komponente | Speicher |
|---|---|
| Mistral 7B Q4\_K\_M | ~5,5 GB (Unified Memory, Metal) |
| Docker Desktop | 4–6 GB RAM |
| Embedding-Modell (CPU) | ~90 MB |
| PostgreSQL + pgvector | ~100 MB |

**Empfehlung:** Docker Desktop RAM-Limit auf 5 GB setzen.
Bei starkem Swap: Kontext in LM Studio auf 2048 reduzieren.

---

## Phasen

| Phase | Inhalt | Status |
|---|---|---|
| 1 | Infrastruktur, Docker Compose, PostgreSQL, NGINX | ✓ |
| 2 | LLM-Client, Chat-API, Streaming, Frontend | ✓ |
| 3 | CSV-Import, Embeddings, pgvector, RAG-Retrieval | ✓ |
| 4 | MCP-Server, Function Calling (manual tool-use) | ✓ |
| 5 | Tests, Härtung, Dokumentation | ✓ |
