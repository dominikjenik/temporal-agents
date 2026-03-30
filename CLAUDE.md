# temporal-ai-agent — Projektová dokumentácia

> Aktualizuj tento súbor s novými poznatkami počas práce.

---

## Architektúra

**Základný princíp:** Claude je stateless — stav drží Temporal. Temporal orchestruje workflows, nie Claude.

**Flow:**
1. API dostane request posunie na Intent Resolvera
2. Intent resolver - IntentResolver a Validation layer - zavola LLM agenta, ocakava format vstupu. V pripade chat posuva konverzaciu naspat k pouzivatelovi, v pripade ak to nie je chat posuva to na CommandDispatchera
3. Command dispatcher - exekuje workflow, riesi signaly.
4. workflow pozostava s aktivit

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

