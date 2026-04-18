# temporal-ai-agent — Projektová dokumentácia

> Aktualizuj tento súbor s novými poznatkami počas práce.

---

## Architektúra

**Základný princíp:** Claude je stateless — stav drží Temporal. Temporal orchestruje workflows, nie Claude.

**Flow:**
1. API routes dostane request posunie na Intent Resolvera
2. Intent resolver - IntentResolver a Validation layer - zavola LLM agenta, ocakava format vstupu. V pripade chat posuva konverzaciu naspat k pouzivatelovi, v pripade ak to nie je chat posuva to na CommandDispatchera
3. Command dispatcher - exekuje workflow, riesi signaly.
4. workflow pozostava s aktivit
5. servisna vrstva sa stara o ukladanie entit v transakciach
priklad: 1-2-3-4 alebo 1-2-3-5 

### Services (activities/)

| Súbor | Zodpovednosť |
|-------|--------------|
| `tasks.py` | Task management — `store_task`, `list_tasks`, `update_task_status`, `create_task`, `complete_task`, `execute_db_query` |
| `tickets.py` | Ticket management — `store_ticket`, `create_ticket`, `list_tickets` |
| `conversations.py` | Konverzačný kontext — `store_message`, `get_conversation_history`, `add_user_message`, `add_assistant_message` |
| `projects.py` | Project config — `store_project`, `get_project`, `list_projects`, `get_project_repos`, `get_project_env_file` |

### DB Tabuľky (SQLite)

| Tabuľka | Účel |
|---------|------|
| `tasks` | Work items s workflow_id (HITL tasky, bežné tasky) |
| `tickets` | Zadania uložené pre budúcu implementáciu (`planning=todo`) |
| `conversations` | Konverzačná história — `user_id`, `task_id` (nullable), `role`, `content` |
| `projects` | Projekty — `name`, `priority`, `repos` (JSONB), `env_file` |

## Tech Stack

- Python 3.11+, uv
- Temporal Python SDK (`temporalio`)
- FastAPI + uvicorn (API server port 8001)
- React + Vite (frontend port 8003)
- LiteLLM (abstrakcia pre LLM volania)
- PostgreSQL (`hitl_requests`, perzistentný stav)
- Podman / Docker Compose (Temporal server + PostgreSQL + UI)
- pytest-asyncio, Black, isort, mypy

---

**`claude_agent_activity`:** Volá LLM agenta ako Temporal Activity s heartbeat, timeout, retry. Výstup je štruktúrovaný JSON.

**HITL signály:** `confirm` / `cancel` — workflow čaká na ľudský vstup pred pokračovaním.

**HITL v SQLite:** Každý HITL task a ticket sa ukladá do SQLite (`/tmp/hitl.db`). Manager môže zobraziť prioritizovaný zoznam cez `/tasks` endpoint.

**Manager DB-query vrstva:** Manager generuje `DBQuery(table, filter, order, limit)` → Temporal activity vykoná SELECT → výsledok späť. Whitelist ochrana (len `tasks` a `tickets` tabuľky).

**Self-improvement slučka:** Na konci workflow `capture_lesson` activity zapíše lekciu do `lessons/pending.md` → manuálny review → promovanie do agent definícií.

**Retry politiky (debugging):** `maximum_attempts=1` — pri debugovaní nechceme zacykliť na chybách a míňať tokeny.

---

**`/hitl/{workflow_id}/state` endpoint:** Volá `CommandDispatcher.get_hitl_state()` priamo, vracia:
- `signal_type`: intent z workflow result (napr. "duplicate_suggested", "duplicate_resolved")
- `response`: payload správy
- `result`, `comments`, `status`, `log`

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
# http://localhost:8003

# Alembic migrácia (vyžaduje bežiaci PostgreSQL)
uv run alembic upgrade head
```

---

## Dizajnové rozhodnutia

- **Claude stateless:** Temporal drží všetok stav — workflow history, signály, timery
- **Štruktúrovaný JSON output:** Každá activity vracia JSON, nie plain text — Temporal môže robiť if/else routing
- **Retry threshold = 1:** V debug fáze — zabrání zacykleniu pri rate limit alebo chybe

---

## TODO — IntentResolver session kontext

IntentResolver je momentálne stateless (každé volanie = 1 LLM call, žiadna história).

Pre chat a clarification scenáre treba udržiavať kontext konverzácie — keď LLM potrebuje doplňujúcu otázku, druhé volanie nemá kontext prvého.

**Implementácia:** Pridať `session_id` parameter do `intent_parser_resolve`, in-memory store `{session_id: [messages]}`, posielať históriu do LLM promptu pri každom volaní.

---

## Referencia — pôvodná session

Session ID: `09215f3f-384b-4001-948d-9ce59e902fb6` (slug: `functional-mixing-oasis`, 2026-03-23/24)

Diskusia o porovnaní AI agent orchestračných frameworkov: LangGraph, CrewAI, AutoGen, Claude Agent SDK, Swarm, Temporal. Temporal zahrnutý ako "durable workflow engine" — infraštrukturálna vrstva pod agentmi. Riešila sa kombinácia Temporal + LangGraph, izolácia agentov cez Temporal aktivity.

# Spravanie Claude v tomto projekte

@~/.claude/skills/projektak/SKILL.md