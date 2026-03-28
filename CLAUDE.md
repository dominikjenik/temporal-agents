# temporal-ai-agent — Projektová dokumentácia

> Aktualizuj tento súbor s novými poznatkami počas práce.

---

## Architektúra

**Základný princíp:** Claude je stateless — stav drží Temporal. Temporal orchestruje workflows, nie Claude.

**Flow:**
1. Manažér dostane inštrukciu → LLM resolvne na štruktúrovaný JSON `{project, prompt}`
2. Temporal zavolá ProjectWorkflow pre daný projekt
3. ProjectWorkflow spustí FeatureWorkflow → `claude_agent_activity` (claude -p / LiteLLM)
4. Activity vráti štruktúrovaný JSON výstup (blockers, merge conflicts, výsledok)
5. Temporal if/else routing — ak merge conflict alebo blocker → HITL signal
6. HITL sa uloží do PostgreSQL pre prioritizáciu (tabuľka `hitl_requests`)
7. Manager môže queryovať DB cez štruktúrovaný JSON dotaz → Temporal activity → SELECT → výsledok späť

**Prečo nie pure-Claude:** deterministická orchestrácia, auditovateľnosť, HITL prioritizácia, paralelné/sekvenčné workflow podľa projektu.

**Workflow hierarchia:**
```
BaseWorkflow
  ↓
ProjectWorkflow (zbornik: sekvencia / ginidocs: paralelne)
  ↓
FeatureWorkflow (s HITL signálmi)
  ↓
claude_agent_activity (Claude cez LiteLLM)
```

---

## Tech Stack

- Python 3.11+, uv
- Temporal Python SDK (`temporalio`)
- FastAPI + uvicorn (API server port 8001)
- React + Vite (frontend port 5173)
- LiteLLM (abstrakcia pre LLM volania)
- PostgreSQL (`hitl_requests`, perzistentný stav)
- Podman / Docker Compose (Temporal server + PostgreSQL + UI)
- pytest-asyncio, Black, isort, mypy

---

## Štruktúra projektu

```
~/temporal-ai-agent/
├── workflows/          # BaseWorkflow, ProjectWorkflow, FeatureWorkflow, agent_goal
├── activities/         # claude_agent_activity.py + tool activities
├── goals/              # Definície projektov (zbornik.py, ginidocs.py)
├── api/                # FastAPI server
├── frontend/           # React UI
├── prompts/            # Generátory promptov pre agenty
├── shared/             # MCP server konfigurácia
├── models/             # Pydantic data types
├── tests/              # Temporal test suite (time-skipping)
├── start.sh            # Spustí Temporal (Podman) + worker + API + frontend
└── stop.sh             # Zastaví worker, API, frontend
```

---

## Kľúčové komponenty

**`claude_agent_activity`:** Volá `claude -p` (alebo LiteLLM) ako Temporal Activity s heartbeat, timeout, retry. Výstup je štruktúrovaný JSON.

**HITL signály:** `confirm` / `cancel` — workflow čaká na ľudský vstup pred pokračovaním.

**HITL v PostgreSQL:** Každý HITL request sa ukladá (`workflow_id`, `description`, `priority`, `status`). Manager môže zobraziť prioritizovaný zoznam.

**Manager DB-query vrstva:** Manager generuje `DBQuery(table, filter, order, limit)` → Temporal activity vykoná SELECT → výsledok späť. Whitelist ochrana (len povolené tabuľky).

**Self-improvement slučka:** Na konci workflow `capture_lesson` activity zapíše lekciu do `lessons/pending.md` → manuálny review → promovanie do agent definícií.

**Retry politiky (debugging):** `maximum_attempts=1` — pri debugovaní nechceme zacykliť na chybách a míňať tokeny.

---

## Goals — projekty

| Goal | Popis | Workflow typ |
|------|-------|-------------|
| zbornik | React Native PDF viewer (mobilná app) | Sekvenčný (zdieľané súbory) |
| ginidocs | FastAPI + React backend/frontend | Paralelný (backend vs frontend) |

---

## Príkazy

```bash
# Spustenie celého stacku
./start.sh

# Zastavenie
./stop.sh

# CLI request
uv run scripts/temporal_cli.py request {project} {prompt}

# Testy (unit — bez claude -p volaní)
uv run pytest tests/unit/

# Integračné testy (vyžaduje bežiaci Temporal server)
uv run pytest tests/integration/

# Temporal UI
# http://localhost:8233

# API
# http://localhost:8001

# Frontend
# http://localhost:5173

# Alembic migrácia (vyžaduje bežiaci PostgreSQL)
uv run alembic upgrade head
```

---

## Dizajnové rozhodnutia

- **Claude stateless:** Temporal drží všetok stav — workflow history, signály, timery
- **Štruktúrovaný JSON output:** Každá activity vracia JSON, nie plain text — Temporal môže robiť if/else routing
- **Retry threshold = 1:** V debug fáze — zabrání zacykleniu pri rate limit alebo chybe
- **Sekvenčné vs paralelné:** Zbornik má zdieľané súbory → musí byť sekvenčné. GiniDocs má separátny backend/frontend → môže bežať paralelne
- **HITL prioritizácia:** Nie všetky human-in-the-loop requesty sú rovnako dôležité — PostgreSQL umožňuje zoradiť podľa priority
