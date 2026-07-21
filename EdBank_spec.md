# Ella-DemoBank – Technische Spezifikation

**Dateiname:** `EdBank_spec.md`  
**Projektname:** Ella-DemoBank  
**Kurzname:** `edbank`  
**Dokumentstatus:** Entwurf für Proof of Concept  
**Zielplattform:** Apple Mac M1, 16 GB Unified Memory  
**Betriebsmodell:** vollständig lokal, ohne Cloud-Abhängigkeit im laufenden Betrieb  
**Sprache der Benutzeroberfläche:** Deutsch  
**Stand:** 20. Juli 2026

---

## 1. Zielsetzung

Ella-DemoBank ist eine lokale Demonstrationsanwendung für drei zentrale ELLA-Technologien:

1. **Lokales Sprachmodell**  
   Verwendung von `Mistral-7B-Instruct-v0.3` als lokal ausgeführtes Large Language Model.

2. **RAG – Retrieval-Augmented Generation**  
   Einlesen einer lokalen CSV-Datei mit Oracle-Fehlercodes und Erklärungen.  
   Bei Fragen zu einem ORA-Fehler soll die Anwendung relevante Inhalte aus der Datei suchen und dem Sprachmodell als überprüfbaren Kontext bereitstellen.

3. **MCP und Function Calling**  
   Zugriff auf eine lokale PostgreSQL-Datenbank über einen eigenständigen MCP-Server.  
   Das Sprachmodell darf keine beliebigen SQL-Befehle ausführen, sondern ausschließlich klar definierte, validierte und read-only MCP-Werkzeuge aufrufen.

Die Anwendung dient als technischer Proof of Concept für die ELLA-Architektur:

```text
Lokales LLM
    +
RAG-Wissensbasis
    +
Agenten-/Orchestrierungslogik
    +
MCP-Werkzeuge
    +
deterministische Business-Services
```

---

## 2. Beispielanwendungsfälle

### 2.1 RAG-Anwendungsfall: Oracle-Fehler

Die Datei `ora.csv` enthält Oracle-Fehlercodes und Erklärtexte.

Beispiel:

```csv
error_code,description,cause,action
ORA-00001,Unique constraint violated,A duplicate key was inserted,Use a different key or update the existing row
ORA-01555,Snapshot too old,Required undo information was overwritten,Increase undo retention or optimize the query
ORA-12154,TNS could not resolve connect identifier,The connect identifier is unknown,Check tnsnames.ora and the connection string
```

Beispielfrage:

```text
Was bedeutet ORA-01555 und was kann ich dagegen tun?
```

Erwartete Antwort:

```text
ORA-01555 bedeutet „Snapshot too old“.

Ursache:
Die für eine konsistente Abfrage benötigten Undo-Informationen wurden bereits
überschrieben.

Mögliche Maßnahme:
Undo Retention erhöhen und die betroffene Abfrage beziehungsweise Transaktion
optimieren.

Quelle: ora.csv, Datensatz ORA-01555
```

Die Antwort darf nicht ausschließlich aus dem allgemeinen Modellwissen erzeugt werden.  
Sie muss sich auf den lokal gefundenen Datensatz stützen.

---

### 2.2 MCP-Anwendungsfall: Bankverbindungen

Die lokale PostgreSQL-Datenbank enthält folgende Tabellen:

- `person`
- `bank`
- `account`

Beispielfrage:

```text
Welchen IBAN hat Herr Hannes Meier?
```

Hannes Meier besitzt zwei Bankkonten.

Erwartete Antwort:

| IBAN | Bank | BIC |
|---|---|---|
| AT611904300234573201 | Musterbank Wien | BAWAATWW |
| AT483200000012345864 | Regionalbank Süd | RLNWATWW |

Die Daten müssen über einen MCP-Tool-Aufruf gelesen werden.  
Das Sprachmodell darf IBAN, Banknamen oder BIC nicht erfinden.

---

## 3. Abgrenzung

### 3.1 Bestandteil des Proof of Concept

- lokales Chatfenster im Browser
- lokales Mistral-7B-Modell
- lokale OpenAI-kompatible LLM-API
- Import einer CSV-Datei
- Erzeugung lokaler Embeddings
- Speicherung von RAG-Dokumenten und Vektoren in PostgreSQL mit pgvector
- semantische Suche nach Oracle-Fehlern
- MCP-Server als eigener Docker-Container
- Function Calling zur Auswahl eines MCP-Tools
- read-only Datenbankabfrage über ein fest definiertes MCP-Tool
- Anzeige verwendeter RAG-Quellen
- optionale Anzeige der ausgeführten MCP-Tools
- Health- und Statusanzeige

### 3.2 Nicht Bestandteil der ersten Version

- Fine-Tuning oder Training des Mistral-Modells
- automatische Veränderung der Modellgewichte
- allgemeiner SQL-Agent
- schreibender Datenbankzugriff
- Benutzerverwaltung mit mehreren Mandanten
- Zugriff aus dem Internet
- produktive Verarbeitung realer Bankkundendaten
- OCR-Verarbeitung
- PDF-, Word- oder Excel-Import
- autonome Aktionen ohne Benutzerfrage
- Speicherung historischer Chatantworten als neues RAG-Wissen
- Hochverfügbarkeits- oder Clusterbetrieb

---

## 4. Grundsatz: RAG ist kein Modelltraining

Das Einlesen von `ora.csv` verändert nicht die Parameter oder Gewichte von Mistral 7B.

Der Ablauf lautet:

```text
ora.csv
   ↓
Validierung und Normalisierung
   ↓
Textrepräsentation je Datensatz
   ↓
Embedding-Modell
   ↓
Vektor
   ↓
PostgreSQL + pgvector
```

Bei einer Benutzerfrage:

```text
Frage
   ↓
Query-Embedding
   ↓
Vektorsuche in pgvector
   ↓
relevante ORA-Datensätze
   ↓
Kontext für Mistral 7B
   ↓
belegte Antwort
```

Die Anwendung „lernt“ im fachlichen Sinn durch eine erweiterte lokale Wissensbasis, nicht durch ein erneutes Training des Sprachmodells.

---

## 5. Architekturentscheidung für den Mac M1

### 5.1 LLM nicht in Docker

Das Sprachmodell soll auf dem Mac **nativ unter macOS** laufen.

Empfohlene Laufzeit:

- LM Studio
- llama.cpp als zugrunde liegende Engine
- Metal-Beschleunigung auf Apple Silicon
- OpenAI-kompatible lokale HTTP-API

Begründung:

- bessere Nutzung der Apple-GPU und des Unified Memory
- weniger Container-Overhead
- einfachere Beobachtung des Speicherverbrauchs
- einfacher Wechsel der Quantisierung
- stabilere Ausführung auf einem Mac M1 mit 16 GB

Der laufende LLM-Server ist von den Docker-Containern erreichbar unter:

```text
http://host.docker.internal:1234/v1
```

Der LLM-Server darf ausschließlich lokal beziehungsweise über die Docker-Host-Bridge erreichbar sein.

### 5.2 Docker-Services

Folgende Services laufen als eigenständige lokale Docker-Container:

1. `nginx`
2. `edbank-app`
3. `postgres`
4. `mcp-server`

Die explizit geforderten Services `nginx`, `postgres` und `mcp-server` bleiben technisch und betrieblich getrennt.

---

## 6. Systemübersicht

```mermaid
flowchart LR
    U[Browser] -->|HTTP localhost| N[NGINX Container]
    N --> A[edbank-app Container]

    A -->|OpenAI-kompatible API| L[LM Studio auf macOS<br>Mistral 7B]
    A -->|RAG SQL + pgvector| P[(PostgreSQL + pgvector)]
    A -->|MCP Streamable HTTP| M[MCP Server Container]
    M -->|parametrisierte read-only SQL-Abfrage| P

    F[ora.csv] -->|Upload oder Import-Verzeichnis| A
```

---

## 7. Komponenten

## 7.1 LM Studio / Mistral 7B

### Modell

```text
mistralai/Mistral-7B-Instruct-v0.3
```

### Empfohlene lokale Variante

```text
Format: GGUF
Quantisierung: Q4_K_M
Alternative: Q5_K_M, falls genügend freier Speicher vorhanden ist
```

### Startkonfiguration

| Parameter | Startwert |
|---|---:|
| Kontextfenster | 4.096 Tokens |
| maximale Antwort | 1.024 Tokens |
| Temperatur | 0,1 |
| Top-P | 0,9 |
| parallele Anfragen | 1 |
| GPU-Offload | maximal, soweit LM Studio stabil bleibt |
| lokale API | `http://127.0.0.1:1234/v1` |

### Anforderungen

- Function Calling muss aktiviert beziehungsweise vom Chat-Template unterstützt werden.
- Das korrekte Mistral-v0.3-Chat-Template muss verwendet werden.
- Der Modellalias wird über Konfiguration festgelegt.
- Bei fehlender LLM-Verbindung zeigt die Webanwendung einen verständlichen Fehler.
- Im laufenden Demo-Betrieb ist keine Internetverbindung erforderlich.

---

## 7.2 `edbank-app`

### Technologie

Empfehlung:

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic
- OpenAI-Python-Client gegen die lokale LM-Studio-API
- offizielles MCP Python SDK als MCP-Client
- SQLAlchemy 2
- psycopg 3
- pgvector-python
- sentence-transformers
- einfache Weboberfläche mit React oder serverseitig ausgeliefertem HTML/JavaScript

Für den ersten Proof of Concept ist eine kompakte React-Oberfläche sinnvoll.  
Der statische Build kann vom `edbank-app`-Container ausgeliefert und über NGINX veröffentlicht werden.

### Verantwortlichkeiten

- Chat-API
- Gesprächskontext
- System Prompt
- CSV-Import
- RAG-Aufbereitung
- Embedding-Erzeugung
- Vektorsuche
- MCP-Client
- Function-Calling-Schleife
- Validierung von Tool-Aufrufen
- Aufbereitung der finalen Antwort
- Quellenanzeige
- Health-Status

---

## 7.3 PostgreSQL mit pgvector

### Container

Bevorzugtes Image:

```text
pgvector/pgvector:pg16
```

Vor Projektstart ist zu verifizieren, dass das verwendete Image als ARM64-Image auf Apple Silicon verfügbar ist.

Fallback:

- eigenes ARM64-kompatibles Image auf Basis von `postgres:16-bookworm`
- Installation der pgvector-Erweiterung im Image
- keine Emulation über `linux/amd64`, sofern vermeidbar

### Datenbanken und Rollen

Eine Datenbank:

```text
edbank
```

Rollen:

```text
edbank_owner   – Eigentümer der Schemata und Tabellen
edbank_app     – Lesen und Schreiben der RAG-Tabellen
edbank_reader  – ausschließlich SELECT auf den Bank-Demotabellen
```

Der MCP-Server verwendet ausschließlich `edbank_reader`.

### PostgreSQL-Erweiterung

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 7.4 MCP-Server

### Technologie

- Python 3.12
- offizielles MCP Python SDK
- `FastMCP`
- Streamable HTTP als Containertransport
- SQLAlchemy oder psycopg
- Pydantic-Eingabevalidierung

### Interne Adresse

```text
http://mcp-server:8001/mcp
```

### Verantwortlichkeiten

- Bereitstellung der Tool-Metadaten
- Validierung der Tool-Parameter
- read-only Datenbankzugriff
- parametrisierte SQL-Abfragen
- Normalisierung der Ergebnisse
- kontrollierte Fehlerantworten
- technische Protokollierung ohne unnötige personenbezogene Inhalte

### Nicht zulässig

- Tool `execute_sql`
- freie SQL-Eingaben
- INSERT, UPDATE, DELETE oder DDL
- Auswahl beliebiger Tabellen
- Rückgabe von Daten außerhalb des festgelegten Ergebnisschemas
- Verwendung eines Datenbank-Superusers

---

## 7.5 NGINX

### Verantwortlichkeiten

- lokaler HTTP-Einstiegspunkt
- Reverse Proxy für `/api`
- Auslieferung der Benutzeroberfläche
- Begrenzung der Uploadgröße
- Timeouts für gestreamte Chatantworten
- Sicherheitsheader
- kein direkter Zugriff auf PostgreSQL oder MCP vom Browser

### Lokale Adresse

```text
http://localhost:8080
```

### Routing

| Pfad | Ziel |
|---|---|
| `/` | Weboberfläche |
| `/api/*` | `edbank-app:8000` |
| `/health` | `edbank-app:8000/api/health` |

Der MCP-Endpunkt wird nicht durch NGINX öffentlich weitergereicht.

---

## 8. Docker-Netzwerke

Empfohlene Netzwerke:

```text
edbank_frontend
edbank_backend
```

Zuordnung:

| Service | frontend | backend |
|---|---:|---:|
| nginx | ja | nein |
| edbank-app | ja | ja |
| mcp-server | nein | ja |
| postgres | nein | ja |

PostgreSQL erhält standardmäßig keine Portfreigabe zum Mac-Host.

Optional für Entwicklung:

```yaml
ports:
  - "127.0.0.1:5432:5432"
```

Diese Freigabe darf nicht in der Standardkonfiguration aktiviert sein.

---

## 9. Vorgeschlagene Projektstruktur

```text
edbank/
├── EdBank_spec.md
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── data/
│   ├── import/
│   │   └── ora.csv
│   └── samples/
│       └── ora_sample.csv
├── docker/
│   ├── nginx/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   ├── app/
│   │   └── Dockerfile
│   ├── mcp-server/
│   │   └── Dockerfile
│   └── postgres/
│       └── init/
│           ├── 001_extensions.sql
│           ├── 010_schema_bank.sql
│           ├── 020_schema_rag.sql
│           ├── 030_roles.sql
│           └── 100_seed_demo.sql
├── app/
│   ├── pyproject.toml
│   ├── src/
│   │   └── edbank/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── api/
│   │       │   ├── chat.py
│   │       │   ├── rag.py
│   │       │   └── health.py
│   │       ├── llm/
│   │       │   ├── client.py
│   │       │   ├── prompts.py
│   │       │   └── tool_loop.py
│   │       ├── rag/
│   │       │   ├── importer.py
│   │       │   ├── embeddings.py
│   │       │   ├── retriever.py
│   │       │   └── schemas.py
│   │       ├── mcp/
│   │       │   ├── client.py
│   │       │   └── validator.py
│   │       └── db/
│   │           ├── session.py
│   │           └── models.py
│   └── tests/
├── mcp-server/
│   ├── pyproject.toml
│   ├── src/
│   │   └── edbank_mcp/
│   │       ├── server.py
│   │       ├── config.py
│   │       ├── db.py
│   │       ├── tools/
│   │       │   └── bank_accounts.py
│   │       └── schemas.py
│   └── tests/
└── web/
    ├── package.json
    ├── src/
    └── tests/
```

---

## 10. Datenbankschema

## 10.1 Bank-Demodaten

```sql
CREATE SCHEMA IF NOT EXISTS banking;

CREATE TABLE banking.person (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE INDEX ix_person_name_lower
    ON banking.person (lower(name));

CREATE TABLE banking.bank (
    bic         VARCHAR(11) PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE TABLE banking.account (
    id          BIGSERIAL PRIMARY KEY,
    person_id   BIGINT NOT NULL
                REFERENCES banking.person(id),
    bank_bic    VARCHAR(11) NOT NULL
                REFERENCES banking.bank(bic),
    iban        VARCHAR(34) NOT NULL UNIQUE
);
```

### Demodaten

```sql
INSERT INTO banking.person (id, name)
VALUES (1, 'Hannes Meier');

INSERT INTO banking.bank (bic, name)
VALUES
    ('BAWAATWW', 'Musterbank Wien'),
    ('RLNWATWW', 'Regionalbank Süd');

INSERT INTO banking.account (person_id, bank_bic, iban)
VALUES
    (1, 'BAWAATWW', 'AT611904300234573201'),
    (1, 'RLNWATWW', 'AT483200000012345864');
```

Die Werte sind ausschließlich synthetische Demodaten.

---

## 10.2 RAG-Datenmodell

### Dokumente

```sql
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE rag.document (
    id              UUID PRIMARY KEY,
    source_name     TEXT NOT NULL,
    source_sha256   CHAR(64) NOT NULL,
    imported_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    record_count    INTEGER NOT NULL,
    status          TEXT NOT NULL,
    UNIQUE (source_name, source_sha256)
);
```

### Chunks

Für `intfloat/multilingual-e5-small` werden 384-dimensionale Vektoren verwendet.

```sql
CREATE TABLE rag.chunk (
    id              UUID PRIMARY KEY,
    document_id     UUID NOT NULL
                    REFERENCES rag.document(id)
                    ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    record_key      TEXT,
    content         TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding       vector(384) NOT NULL,
    UNIQUE (document_id, chunk_index)
);
```

### Vektorindex

Für die kleine Demo-Datenmenge ist zunächst eine exakte Suche ausreichend.

Optional:

```sql
CREATE INDEX ix_rag_chunk_embedding_hnsw
ON rag.chunk
USING hnsw (embedding vector_cosine_ops);
```

Der HNSW-Index soll erst aktiviert werden, wenn eine relevante Datenmenge vorliegt.

---

## 11. Format von `ora.csv`

### 11.1 Erforderliche Spalten

```text
error_code
description
```

### 11.2 Optionale Spalten

```text
cause
action
category
version
source
```

### 11.3 Regeln

- Zeichencodierung: UTF-8
- Trennzeichen: automatisch erkennen, bevorzugt Komma oder Semikolon
- erste Zeile enthält Spaltennamen
- leere Zeilen ignorieren
- `error_code` muss dem Muster `ORA-\d{5}` entsprechen
- Fehlercodes werden in Großbuchstaben normalisiert
- doppelte Fehlercodes werden als Importwarnung gemeldet
- maximal 5 MB in Version 1
- Import wird transaktional durchgeführt
- bei einem Validierungsfehler wird die Datei nicht teilweise übernommen

### 11.4 RAG-Text je Datensatz

Aus einer CSV-Zeile wird ein selbstbeschreibender Text erzeugt:

```text
Oracle error code: ORA-01555
Description: Snapshot too old
Cause: Required undo information was overwritten
Action: Increase undo retention or optimize the query
```

Ein Oracle-Fehlerdatensatz bildet in Version 1 genau einen Chunk.

---

## 12. Embedding-Modell

Empfohlen:

```text
intfloat/multilingual-e5-small
```

Gründe:

- lokaler Betrieb
- kleines Modell
- Deutsch und Englisch
- geeignet für semantische Suche
- geringe zusätzliche Speicherbelastung
- 384-dimensionale Vektoren
- MIT-Lizenz laut Modellkarte

### Eingabepräfixe

Für E5-Modelle:

```text
query: <Benutzerfrage>
passage: <Dokumenttext>
```

### Ausführung

Das Embedding-Modell läuft im `edbank-app`-Container auf CPU.

Da die CSV-Datenmenge klein ist, wird das Modell beim ersten Import geladen und anschließend im Prozessspeicher gehalten.

---

## 13. RAG-Ablauf

```mermaid
sequenceDiagram
    participant U as Benutzer
    participant A as edbank-app
    participant E as Embedding-Modell
    participant P as PostgreSQL/pgvector
    participant L as Mistral 7B

    U->>A: Was bedeutet ORA-01555?
    A->>E: Query-Embedding erzeugen
    E-->>A: Vektor
    A->>P: Top-K Cosine-Suche
    P-->>A: relevante ORA-Datensätze
    A->>L: Frage + Quellenkontext + Regeln
    L-->>A: belegte Antwort
    A-->>U: Antwort + Quellen
```

### Retrieval-Parameter

| Parameter | Startwert |
|---|---:|
| Top-K | 4 |
| Mindestähnlichkeit | konfigurierbar, initial 0,70 |
| maximaler RAG-Kontext | 1.500 Tokens |
| Chunk-Deduplizierung | nach `record_key` |
| Quellennachweis | verpflichtend |

### Verhalten ohne Treffer

Wenn kein Datensatz den Mindestwert erreicht:

```text
In der lokalen ORA-Wissensbasis wurde dazu kein ausreichend passender Eintrag gefunden.
```

Das Modell darf danach optional allgemeines Wissen ergänzen, muss dies aber ausdrücklich kennzeichnen:

```text
Allgemeiner Hinweis des Sprachmodells, nicht aus ora.csv:
...
```

Für Version 1 wird empfohlen, bei ORA-Fragen ohne Treffer keine freie fachliche Antwort zu erzeugen.

---

## 14. MCP-Tool

## 14.1 Toolname

```text
get_bank_accounts_by_person_name
```

## 14.2 Beschreibung für das Sprachmodell

```text
Returns all bank accounts for one person from the local demo database.
Use this tool when the user asks for IBANs, bank accounts, bank names or BICs
belonging to a named person. This is a read-only lookup.
```

## 14.3 Eingabeschema

```json
{
  "type": "object",
  "properties": {
    "person_name": {
      "type": "string",
      "description": "Full name of the person, for example Hannes Meier",
      "minLength": 2,
      "maxLength": 200
    }
  },
  "required": ["person_name"],
  "additionalProperties": false
}
```

## 14.4 Ausgabeschema

```json
{
  "person_name": "Hannes Meier",
  "match_count": 2,
  "accounts": [
    {
      "iban": "AT611904300234573201",
      "bank_name": "Musterbank Wien",
      "bic": "BAWAATWW"
    },
    {
      "iban": "AT483200000012345864",
      "bank_name": "Regionalbank Süd",
      "bic": "RLNWATWW"
    }
  ]
}
```

## 14.5 SQL-Implementierung

```sql
SELECT
    p.name AS person_name,
    a.iban,
    b.name AS bank_name,
    b.bic
FROM banking.person p
JOIN banking.account a
    ON a.person_id = p.id
JOIN banking.bank b
    ON b.bic = a.bank_bic
WHERE lower(p.name) = lower(%(person_name)s)
ORDER BY b.name, a.iban;
```

Die Abfrage muss parameterisiert ausgeführt werden.

---

## 15. Behandlung mehrdeutiger Personennamen

Version 1 verwendet den vollständigen Namen.

Mögliche Ergebnisse:

### Kein Treffer

```json
{
  "person_name": "Max Beispiel",
  "match_count": 0,
  "accounts": []
}
```

Antwort:

```text
Für Max Beispiel wurden in der lokalen Datenbank keine Konten gefunden.
```

### Genau eine Person

Alle Konten werden zurückgegeben.

### Mehrere Personen mit demselben Namen

Der MCP-Server gibt einen kontrollierten Fehler zurück:

```json
{
  "error": "AMBIGUOUS_PERSON",
  "message": "Multiple persons have the same name.",
  "candidate_count": 2
}
```

Die Anwendung fordert eine zusätzliche Identifikation an.  
Für den Proof of Concept werden keine Geburtsdaten oder Adressen ergänzt.

---

## 16. Chat-Orchestrierung

### 16.1 Grundablauf

1. Benutzer sendet eine Nachricht.
2. `edbank-app` validiert Länge und Inhalt.
3. Die Anwendung führt eine RAG-Suche aus.
4. Die Anwendung liest die vom MCP-Server veröffentlichten Tool-Schemas.
5. Die Frage, die RAG-Treffer und die Tool-Schemas werden an Mistral 7B gesendet.
6. Das Modell entscheidet:
   - direkte Antwort aus dem RAG-Kontext oder
   - Function Call für das MCP-Tool.
7. Bei einem Function Call:
   - Toolname validieren
   - Argumente gegen JSON-Schema validieren
   - MCP-Tool aufrufen
   - Tool-Ergebnis als Tool-Message an das Modell zurückgeben
8. Das Modell formuliert die finale Antwort.
9. Die Anwendung zeigt Antwort, Quellen und optional Tool-Spur an.

### 16.2 Begrenzung

```text
maximale Tool-Runden pro Benutzerfrage: 3
maximale MCP-Laufzeit: 10 Sekunden
maximale Gesamtantwortzeit: 120 Sekunden
```

Nach Überschreitung:

```text
Die Anfrage konnte nicht innerhalb der zulässigen Verarbeitungsschritte abgeschlossen werden.
```

### 16.3 Kein versteckter SQL-Zugriff

Das LLM erhält:

- Namen des MCP-Tools
- Beschreibung
- Eingabeschema

Das LLM erhält nicht:

- PostgreSQL-Passwort
- Datenbankverbindung
- frei verwendbare SQL-Schnittstelle
- Berechtigung zum Lesen beliebiger Tabellen

---

## 17. System Prompt

Vorgeschlagener System Prompt:

```text
Du bist Ella-DemoBank, ein lokaler deutschsprachiger Assistent.

Verbindliche Regeln:

1. Verwende für Oracle-Fehler ausschließlich die bereitgestellten RAG-Quellen.
2. Erfinde keine ORA-Erklärung, keine IBAN, keinen Banknamen und keinen BIC.
3. Verwende das Tool get_bank_accounts_by_person_name, wenn nach Konten,
   IBANs, Banknamen oder BICs einer namentlich genannten Person gefragt wird.
4. Gib alle vom Tool zurückgegebenen Konten vollständig wieder.
5. Ändere Tool-Ergebnisse nicht.
6. Wenn keine Daten gefunden wurden, sage klar, dass keine Daten gefunden wurden.
7. Zeige RAG-Quellen am Ende der Antwort an.
8. Antworte auf Deutsch, sofern der Benutzer keine andere Sprache verlangt.
9. Führe keine schreibenden oder nicht angebotenen Datenbankaktionen aus.
10. Behandle alle Daten als vertraulich und lokal.
```

---

## 18. API der Webanwendung

## 18.1 Chat

### Request

```http
POST /api/chat
Content-Type: application/json
```

```json
{
  "conversation_id": "f58572f8-3840-47d7-bfe9-7b42fad81da6",
  "message": "Welchen IBAN hat Herr Hannes Meier?"
}
```

### Response

```json
{
  "conversation_id": "f58572f8-3840-47d7-bfe9-7b42fad81da6",
  "answer_markdown": "| IBAN | Bank | BIC |\n|---|---|---|...",
  "sources": [],
  "tool_calls": [
    {
      "name": "get_bank_accounts_by_person_name",
      "status": "success",
      "duration_ms": 34
    }
  ],
  "model": "mistral-7b-instruct-v0.3",
  "finish_reason": "stop"
}
```

Für Streaming kann zusätzlich Server-Sent Events verwendet werden:

```http
POST /api/chat/stream
```

---

## 18.2 CSV-Import

```http
POST /api/rag/import
Content-Type: multipart/form-data
```

Feld:

```text
file=<ora.csv>
```

Response:

```json
{
  "document_id": "80d0684d-a91e-4315-9428-a5cbb4c8134d",
  "source_name": "ora.csv",
  "imported_records": 3,
  "warnings": [],
  "status": "ready"
}
```

---

## 18.3 RAG-Status

```http
GET /api/rag/status
```

```json
{
  "documents": 1,
  "chunks": 3,
  "embedding_model": "intfloat/multilingual-e5-small",
  "ready": true
}
```

---

## 18.4 Health

```http
GET /api/health
```

```json
{
  "status": "degraded",
  "components": {
    "app": "ok",
    "postgres": "ok",
    "pgvector": "ok",
    "mcp_server": "ok",
    "llm_server": "unavailable"
  }
}
```

---

## 19. Benutzeroberfläche

### 19.1 Hauptansicht

Die Weboberfläche besteht aus:

1. Kopfzeile „Ella-DemoBank“
2. Statusanzeige
3. Chatverlauf
4. Nachrichteneingabe
5. CSV-Importbereich
6. Quellenanzeige
7. optionaler technischer Detailbereich

### 19.2 Statusanzeige

```text
LLM: verbunden
RAG: 3 Datensätze
MCP: verbunden
PostgreSQL: verbunden
Betriebsart: lokal
```

### 19.3 Antwortdarstellung

- Markdown
- Tabellen
- Codeblöcke
- deutlich sichtbare Quellen
- Tool-Spur standardmäßig eingeklappt

Beispiel Tool-Spur:

```text
Verwendetes Werkzeug:
get_bank_accounts_by_person_name
Dauer: 34 ms
Ergebniszeilen: 2
```

Das Roh-JSON muss im normalen Benutzerbetrieb nicht angezeigt werden.

---

## 20. Fehlerbehandlung

| Fehler | Benutzerantwort |
|---|---|
| LM Studio nicht gestartet | „Das lokale Sprachmodell ist derzeit nicht erreichbar.“ |
| Modell nicht geladen | „In LM Studio ist kein kompatibles Modell geladen.“ |
| PostgreSQL nicht erreichbar | „Die lokale Datenbank ist derzeit nicht erreichbar.“ |
| MCP-Server nicht erreichbar | „Der lokale Datenbankdienst ist derzeit nicht verfügbar.“ |
| ungültige CSV | genaue Validierungsfehler anzeigen |
| kein RAG-Treffer | „In der lokalen Wissensbasis wurde kein passender Eintrag gefunden.“ |
| Person nicht gefunden | „Für diese Person wurden keine Konten gefunden.“ |
| mehrdeutiger Name | zusätzliche Identifikation anfordern |
| ungültiger Tool-Aufruf | Tool nicht ausführen, einmalige korrigierte Modellrunde |
| Tool-Schleife | nach drei Runden abbrechen |
| Zeitüberschreitung | kontrollierte Fehlermeldung |

Technische Stacktraces dürfen nicht an den Browser zurückgegeben werden.

---

## 21. Sicherheitsanforderungen

### 21.1 Netzwerk

- Anwendung nur auf `localhost`
- NGINX bindet an `127.0.0.1:8080`
- PostgreSQL ohne öffentliche Portfreigabe
- MCP-Server nur im Backend-Docker-Netz
- LM Studio nur lokal
- keine Cloud-API-Schlüssel
- keine Telemetrie in der Anwendung
- ausgehende Internetverbindungen im laufenden Betrieb nicht erforderlich

### 21.2 Datenbank

- eigener read-only Benutzer für MCP
- keine Superuser-Verbindung
- kein generisches SQL-Tool
- parametrisierte Abfragen
- festes Schema
- minimierte Berechtigungen
- Datenbankpasswort nur über Umgebungsvariable oder Docker Secret

### 21.3 Eingaben

- maximale Chatnachricht: 4.000 Zeichen
- maximale CSV-Größe: 5 MB
- erlaubte Dateiendung: `.csv`
- MIME-Typ und tatsächlicher Inhalt prüfen
- Steuerzeichen bereinigen
- Prompt-Injection-Text in RAG-Dokumenten wird als Datenkontext markiert
- Toolargumente serverseitig validieren

### 21.4 Protokollierung

Standardmäßig protokollieren:

- Zeitstempel
- technische Request-ID
- verwendetes Modell
- Toolname
- Erfolg oder Fehler
- Dauer
- Anzahl der Ergebniszeilen

Standardmäßig nicht protokollieren:

- vollständige IBAN
- vollständiger Benutzerprompt
- vollständige Tool-Ergebnisse
- Datenbankpasswörter
- Modellkontext

Für den Demo-Modus kann eine explizite Debug-Einstellung aktiviert werden.

---

## 22. Datenschutz und lokale Datenhaltung

Ella-DemoBank ist als lokale Demonstration ausgelegt.

Anforderungen:

- keine Übermittlung von Prompts an externe KI-Dienste
- keine Übermittlung von RAG-Inhalten an externe Dienste
- keine Übermittlung von Datenbankergebnissen an externe Dienste
- ausschließlich synthetische Bankdaten im Proof of Concept
- Möglichkeit, Chatverläufe vollständig zu löschen
- Chatverlauf standardmäßig nur im Browser oder flüchtig im Backend
- kein automatisches Übernehmen von Antworten in die RAG-Wissensbasis

Die lokale Architektur allein ersetzt keine datenschutzrechtliche Bewertung bei einem späteren Produktiveinsatz.

---

## 23. Konfiguration

Beispiel `.env.example`:

```dotenv
EDBANK_ENV=development
EDBANK_LOG_LEVEL=INFO

LLM_BASE_URL=http://host.docker.internal:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL=mistral-7b-instruct-v0.3
LLM_CONTEXT_TOKENS=4096
LLM_MAX_OUTPUT_TOKENS=1024
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=120

POSTGRES_DB=edbank
POSTGRES_USER=edbank_owner
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

APP_DATABASE_URL=postgresql+psycopg://edbank_app:change-me@postgres:5432/edbank
MCP_DATABASE_URL=postgresql+psycopg://edbank_reader:change-me@postgres:5432/edbank

MCP_SERVER_URL=http://mcp-server:8001/mcp
MCP_TIMEOUT_SECONDS=10
MCP_MAX_TOOL_ROUNDS=3

EMBEDDING_MODEL=intfloat/multilingual-e5-small
EMBEDDING_DIMENSION=384
RAG_TOP_K=4
RAG_MIN_SCORE=0.70
RAG_MAX_CONTEXT_TOKENS=1500
MAX_CSV_SIZE_MB=5
```

Produktive Passwörter dürfen nicht in Git gespeichert werden.

---

## 24. Docker-Compose-Zielbild

```yaml
services:
  nginx:
    build: ./docker/nginx
    ports:
      - "127.0.0.1:8080:80"
    depends_on:
      edbank-app:
        condition: service_healthy
    networks:
      - frontend
    restart: unless-stopped

  edbank-app:
    build:
      context: .
      dockerfile: docker/app/Dockerfile
    env_file:
      - .env
    volumes:
      - ./data/import:/app/data/import:ro
    depends_on:
      postgres:
        condition: service_healthy
      mcp-server:
        condition: service_healthy
    networks:
      - frontend
      - backend
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped

  mcp-server:
    build:
      context: .
      dockerfile: docker/mcp-server/Dockerfile
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - backend
    restart: unless-stopped

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d:ro
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 20
    restart: unless-stopped

networks:
  frontend:
  backend:
    internal: true

volumes:
  postgres_data:
```

Hinweis: Die Erreichbarkeit von `host.docker.internal` muss auf dem eingesetzten Docker Desktop geprüft werden. Auf Docker Desktop für macOS ist dies der vorgesehene Weg für Containerzugriffe auf einen Host-Service.

---

## 25. Ressourcenplanung für den Mac M1 mit 16 GB

### 25.1 Zielkonfiguration

- Mistral 7B Q4_K_M
- Kontext zunächst 4.096 Tokens
- nur eine gleichzeitige Chat-Anfrage
- Docker Desktop mit begrenztem Arbeitsspeicher
- kleines Embedding-Modell
- kleine PostgreSQL-Datenbank
- keine parallelen Modellprozesse

### 25.2 Empfohlene Docker-Desktop-Einstellung

Startwert:

```text
Docker RAM: 4 bis 6 GB
```

Der verbleibende Speicher steht macOS und LM Studio zur Verfügung.

### 25.3 Beobachtung

Während der Tests kontrollieren:

- macOS Aktivitätsanzeige
- Speicherdruck
- Swap-Nutzung
- LM-Studio-Auslastung
- Antwortgeschwindigkeit
- Docker-Container-Speicher

Bei starkem Swap:

- Kontext reduzieren
- Q4 statt Q5 verwenden
- andere Programme schließen
- Docker-RAM reduzieren, sofern PostgreSQL und Anwendung stabil bleiben

---

## 26. Antwortregeln für Bankdaten

Das finale Antwortformat bei mindestens einem Konto:

```markdown
Für **Hannes Meier** wurden zwei Konten gefunden:

| IBAN | Bank | BIC |
|---|---|---|
| AT611904300234573201 | Musterbank Wien | BAWAATWW |
| AT483200000012345864 | Regionalbank Süd | RLNWATWW |

Quelle: lokale PostgreSQL-Datenbank über das MCP-Tool
`get_bank_accounts_by_person_name`.
```

Regeln:

- alle Tool-Ergebniszeilen anzeigen
- keine IBAN verkürzen
- keine Reihenfolge erfinden; Reihenfolge aus Tool-Ergebnis verwenden
- Bankname und BIC getrennt anzeigen
- keine zusätzlichen Kontoinformationen erfinden
- bei leerem Ergebnis keine Vermutung äußern

---

## 27. Function-Calling-Validierung

Vor jedem MCP-Aufruf prüft `edbank-app`:

1. Ist der Toolname in der aktuellen MCP-Toolliste enthalten?
2. Entspricht das Argumentobjekt dem JSON-Schema?
3. Enthält `person_name` einen plausiblen Textwert?
4. Wurde die maximale Tool-Rundenzahl überschritten?
5. Ist der MCP-Server erreichbar?
6. Ist das Tool als read-only klassifiziert?

Bei ungültigem Modelloutput:

- Tool nicht aufrufen
- dem Modell einmal eine strukturierte Fehlermeldung zurückgeben
- erneuten Tool-Aufruf erlauben
- danach kontrolliert abbrechen

---

## 28. Tests

## 28.1 Unit-Tests

### CSV

- gültige CSV mit Komma
- gültige CSV mit Semikolon
- UTF-8-Umlaute
- fehlende Pflichtspalte
- ungültiger ORA-Code
- doppelter ORA-Code
- leere Datei
- zu große Datei

### RAG

- Embedding wird erzeugt
- Vektor besitzt 384 Dimensionen
- ORA-01555 wird korrekt gefunden
- irrelevante Frage unterschreitet den Schwellwert
- Quellen-Metadaten bleiben erhalten

### MCP

- Hannes Meier liefert zwei Konten
- unbekannte Person liefert leere Liste
- SQL-Injection-Text wird nur als Parameter behandelt
- DB-Fehler wird kontrolliert zurückgegeben
- MCP-Benutzer kann kein UPDATE durchführen

### Orchestrierung

- ORA-Frage verwendet RAG
- IBAN-Frage löst MCP-Tool aus
- Tool-Ergebnis wird vollständig übernommen
- ungültiger Toolname wird abgewiesen
- Endlosschleife wird nach drei Runden beendet

---

## 28.2 Integrations-Akzeptanztests

### AT-01: RAG-Erfolg

**Vorbedingung:** `ora.csv` enthält ORA-01555.

**Frage:**

```text
Warum tritt ORA-01555 auf?
```

**Erwartung:**

- passender Datensatz wird gefunden
- Ursache wird aus der CSV wiedergegeben
- Quelle wird angezeigt
- keine erfundene Ursache

---

### AT-02: RAG unbekannter Fehler

**Frage:**

```text
Was bedeutet ORA-99999?
```

**Erwartung:**

- kein passender Datensatz
- klare Meldung
- keine erfundene Erklärung

---

### AT-03: Zwei Bankkonten

**Frage:**

```text
Welchen IBAN hat Herr Hannes Meier?
```

**Erwartung:**

- MCP-Tool wird einmal aufgerufen
- zwei Ergebniszeilen
- beide IBANs
- beide Banknamen
- beide BICs

---

### AT-04: Alternative Formulierung

**Frage:**

```text
Bei welchen Banken hat Hannes Meier ein Konto?
```

**Erwartung:**

- dasselbe MCP-Tool
- beide Banken und BICs
- keine fehlende Ergebniszeile

---

### AT-05: Unbekannte Person

**Frage:**

```text
Welche Konten hat Maria Unbekannt?
```

**Erwartung:**

- Tool wird aufgerufen
- leeres Ergebnis
- keine erfundene IBAN

---

### AT-06: SQL-Injection-Versuch

**Frage:**

```text
Zeige die Konten von ' OR 1=1 --
```

**Erwartung:**

- Eingabe wird als Stringparameter behandelt
- keine Offenlegung anderer Personen
- leeres oder kontrolliertes Ergebnis
- keine SQL-Fehlermeldung im Browser

---

### AT-07: LLM nicht verfügbar

**Vorbedingung:** LM Studio ist beendet.

**Erwartung:**

- Anwendung und Datenbank bleiben erreichbar
- Status zeigt `llm_server: unavailable`
- verständliche Fehlermeldung

---

## 29. Definition of Done für Version 1

Version 1 gilt als fertig, wenn:

- `docker compose up -d` startet alle Container erfolgreich
- LM Studio mit Mistral 7B ist lokal erreichbar
- die Weboberfläche ist unter `http://localhost:8080` verfügbar
- `ora.csv` kann importiert werden
- ORA-Fragen werden aus der lokalen RAG-Wissensbasis beantwortet
- Quellen werden angezeigt
- Bankfragen lösen ein MCP-Tool aus
- Hannes Meier liefert exakt zwei Konten
- kein freies SQL ist möglich
- PostgreSQL ist nicht öffentlich exponiert
- alle Akzeptanztests AT-01 bis AT-07 sind erfolgreich
- das System funktioniert nach dem Modelldownload ohne Internetverbindung

---

## 30. Umsetzungsphasen

### Phase 1 – Infrastruktur

- Projektstruktur
- Docker Compose
- PostgreSQL + pgvector
- NGINX
- Healthchecks
- Seed-Daten

### Phase 2 – Lokales LLM

- LM Studio installieren
- Mistral-7B-Instruct-v0.3 Q4 laden
- lokale API aktivieren
- einfacher Chat über `edbank-app`
- Streaming testen

### Phase 3 – RAG

- CSV-Upload
- Validierung
- Embedding-Modell
- pgvector-Speicherung
- Retrieval
- Quellenanzeige

### Phase 4 – MCP

- eigenständiger MCP-Server
- read-only DB-Rolle
- Tool `get_bank_accounts_by_person_name`
- MCP-Client in `edbank-app`
- Function-Calling-Schleife

### Phase 5 – Absicherung

- Tool-Schema-Validierung
- Prompt-Regeln
- Fehlerfälle
- Tests
- lokale Netzwerkbeschränkung
- Dokumentation

---

## 31. Spätere Erweiterungsmöglichkeiten

Nicht Bestandteil von Version 1, aber architektonisch vorzusehen:

- weitere CSV- oder Dokumenttypen
- PDF- und Office-Import
- RAG-Quellenverwaltung
- historische Vergleichsfälle mit Freigabeprozess
- zusätzliche MCP-Server
- Vertragsdatenbank
- Oracle-Datenbankadapter
- PostgreSQL- und Oracle-MCP-Tools
- Rollen und Berechtigungen
- Audit-Protokoll
- Benutzerbestätigung vor schreibenden Aktionen
- europäische Modelle wie Mistral Small oder Soofi auf stärkerer Hardware
- automatisierte Modellbewertung
- Wechsel zwischen mehreren lokalen Modellen

---

## 32. Technische Referenzen

- Mistral-7B-Instruct-v0.3:  
  https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3

- LM Studio Local Server:  
  https://lmstudio.ai/docs/developer/core/server

- LM Studio Offline Operation:  
  https://lmstudio.ai/docs/app/offline

- Model Context Protocol – Architektur:  
  https://modelcontextprotocol.io/docs/learn/architecture

- Offizielles MCP Python SDK:  
  https://github.com/modelcontextprotocol/python-sdk

- MCP Python SDK Dokumentation:  
  https://py.sdk.modelcontextprotocol.io/

- pgvector:  
  https://github.com/pgvector/pgvector

- pgvector Python:  
  https://github.com/pgvector/pgvector-python

- Sentence Transformers – Semantic Search:  
  https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html

- multilingual-e5-small:  
  https://huggingface.co/intfloat/multilingual-e5-small

- Docker Desktop Networking:  
  https://docs.docker.com/desktop/features/networking/networking-how-tos/

---

## 33. Zusammenfassung der verbindlichen Architektur

```text
Browser
   ↓
NGINX-Container
   ↓
edbank-app-Container
   ├── RAG → PostgreSQL/pgvector
   ├── MCP-Client → mcp-server-Container → PostgreSQL
   └── LLM-API → LM Studio auf macOS → Mistral 7B
```

Die Aufgaben sind klar getrennt:

- **Mistral 7B** versteht Sprache und entscheidet über Toolbedarf.
- **RAG** liefert lokales Wissen aus `ora.csv`.
- **MCP** standardisiert die angebotene Datenbankfunktion.
- **Der MCP-Server** führt ausschließlich eine validierte read-only Fachabfrage aus.
- **PostgreSQL** speichert sowohl strukturierte Bankdaten als auch RAG-Vektoren.
- **NGINX** ist der einzige Einstiegspunkt für den Browser.
- **Alle fachlichen Daten bleiben lokal auf dem Zielrechner.**
