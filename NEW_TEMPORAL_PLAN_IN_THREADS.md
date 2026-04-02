# Temporal Agentic Workflow — Plan

---

## 1. Git sandbox repo pre testy - DONE: Plan A — session-scoped bare origin + per-test klon

**Q:** Pre beh testov chcem git sandbox repo s jedným bash skriptom, initial commitom a jedným testom.
Operácie: clone, commit, branch. Query `"new feature sandbox echo hello world 2"` má ísť priamo
na ten folder/repo. Čo navrhuješ?

**A:** Dve varianty:
- **Plan A:** `sandbox_origin` (session-scoped bare repo) + `sandbox_repo` (per-test klon z originu)
- **Plan B:** Persistent path `/tmp/temporal_sandbox`

Nevýhody zdieľanej cesty: nemožná paralelizácia (race condition), reset po každom teste,
pri páde ostane repo "špinavé", testy závislé na poradí.

**Q:** Aká je nevýhoda zdieľanej cesty?

**A:** Paralelizácia + reset + dirty state pri páde.

---

## 2. Repos + .env - DONE: `repos JSONB` list + `env_file TEXT` raw obsah

### 2a. Repos — list format - DONE: `repos JSONB` — list objektov `{title, url}`

**Q:** Dictionary by mal byť nezávislý od názvu — skôr list `[{title, url}]`.

**A:**
```json
[
  {"title": "backend",  "url": "git@github.com:org/ginidocs-backend.git"},
  {"title": "frontend", "url": "git@github.com:org/ginidocs-frontend.git"}
]
```
`title` je len label — bez sémantickej väzby na kľúč.

### 2b. .env ako súbor - DONE: `env_file TEXT` — raw `.env` obsah v DB, aktivita ho zapíše na disk po clone

**Q:** .env preferujem ako súbor, projekty to tak zvyknú mať.

**A:** Kolumna `env_file TEXT` — raw obsah `.env` súboru. Aktivita po clone zapíše `.env` do working dir.

---

## 3. IntentParser — detekcia komponentu - DONE: API layer robí DB lookup pred IntentParserom, výsledok ide do system promptu

**Q:** Treba pridať identifikovanie intentu ktorého komponentu sa to týka/všetkých.
Čo znamená "lookup" — aktivita agenta? MCP tool?

**A:** IntentParser je front-facing agent, nie súčasť workflow.
API vrstva (FastAPI endpoint) pred volaním IntentParsera načíta všetky projekty z DB
a vloží `repos[].title` do system promptu ako kontext:

```
Projekt "ginidocs" má komponenty: backend, frontend.
```

IntentParser rozhodne `component: "frontend"` z textu. Žiadny tool, žiadna aktivita —
API layer to pripraví pred volaním.

`ParsedIntent` rozšíriť o pole:
```python
component: str | None  # "backend" | "frontend" | None = všetky
```

---

## 4. MCP code-index-mcp / central repo - DONE: cache by commit hash — index sa builduje raz per hash, reusuje sa medzi features aj branches na tom istom commite

**Q:** Feature agent by mohol využívať centrálne repo na statickú analýzu cez `code-index-mcp`.
Central repo = `~/projektove_repo`. Keď developer commituje, nič sa nedeje...
ale možno lepšie indexovať pre každú feature samostatne?

**A:** Možnosti:

| | Izolácia | Cena (výpočet) | Cena (tokeny) | Aktuálnosť |
|---|---|---|---|---|
| A. Fresh per feature | plná | vysoká — index build pri každom feature | nízka — presný index | vždy |
| B. Central, pull on-demand | žiadna | nízka — len git pull | stredná — agent číta viac | na požiadanie |
| C. Cached by commit hash | plná | stredná — build raz per commit, reuse pri opakovaní | nízka — presný index | per commit |
| D. Bez indexu (grep/MCP reads) | n/a | minimálna | vysoká — agent musí čítať súbory | vždy |

---

## 5. Secrets v DB - DONE: Secrets sa ukladajú do `env_file`, žiadna extra logika

**Q:** Mňa to netrápí že secrets idú do DB — ak to projekt nemá zaheslované, je to chyba
konfigurácie projektu, nie?

**A:** Áno. `env_file TEXT` bude obsahovať aj secrets. Zodpovednosť za šifrovanie je na DB infraštruktúre.

---

## 6. Konverzačný kontext across sessions - DONE: tabuľka conversations, user_id session, nullable task_id, trimming N správ

**Q:** Chcem aby front-facing agent udržiaval kontext konverzácie across sessions.

**A:** Nová tabuľka `conversations` s nullable `task_id`.

### 6a. Relácia na task - DONE: `task_id UUID REFERENCES tasks(id)` — nullable

**Q:** Reláciu na task treba či nie?

**A:** Nullable FK — HITL konverzácia sa viaže na konkrétny task, bežný chat nie.

### 6b. Session per user - DONE: `user_id TEXT` — session = user account

**Q:** User účet má jednu session?

**A:** Áno — jeden user = jedna kontinuálna session (`user_id`). Všetka história pod jedným ID.

### 6c. Trimming + content - DONE: posledných N správ do kontextu (N konfigurovať pri implementácii), non-chat logging neriešime

**Q:** Treba niečo s trimmingom? Čo by bol content v conversations?

**A:**
- **content:** raw TEXT správy — to čo vidí používateľ a čo odpovie agent. Tool cally patria do Temporal history.
- **trimming:** načítavame posledných N správ do LLM contextu (napr. 50), všetko ostáva v DB.

---

## 7. DB schéma — migrácia r002 - OPEN

**Aktuálny stav (r001):**
```sql
project (id, name, priority, created_at, modified_at)
tasks (id, project_id, title, priority, status, type, workflow_id, created_at, modified_at)
project_requirements (id, project_id, description, status, workflow_id, created_at)
tasks_xref_project_requirements (task_id, project_requirement_id)
```

**Navrhovaná migrácia r002:**
```sql
ALTER TABLE project
    ADD COLUMN repos     JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN env_file  TEXT  NOT NULL DEFAULT '';

CREATE TABLE conversations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    task_id    UUID REFERENCES tasks(id),
    role       VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON conversations (user_id, created_at);
```

### 7a. Content v conversations — čo tam patrí - DONE

**Q:** Čo má byť v stĺpci `content`?

**A:**
- Raw text správy — to čo vidí používateľ a čo odpovie agent.
- Tool calls NEPATRIA do `content` — tie sú v Temporal workflow history.
- Príklad: `"user": "Ahoj, chcem nový button"`, `"assistant": "Rozumiem, vytvorím ho."`

---

## 8. Implementačný plán r003

### 8.1. DB migrácia r003

```python
# alembic/versions/YYYYMMDD_r003_conversations_and_repos.py

def upgrade() -> None:
    # Pridanie stĺpcov do project
    op.execute("""
        ALTER TABLE project
            ADD COLUMN repos    JSONB NOT NULL DEFAULT '[]',
            ADD COLUMN env_file TEXT  NOT NULL DEFAULT ''
    """)

    # conversations tabuľka
    op.execute("""
        CREATE TABLE conversations (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    TEXT NOT NULL,
            task_id    UUID REFERENCES tasks(id),
            role       VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
            content    TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ON conversations (user_id, created_at)")
```

### 8.2. API vrstva

| Súbor | Zmena |
|-------|-------|
| `api/main.py` | Nové endpointy `/conversations`, `/conversations/{user_id}` |
| `api/models.py` | `Conversation` Pydantic model |
| `api/service.py` | CRUD pre conversations |

### 8.3. IntentParser rozšírenie

```python
# src/temporal_agents/intent_config.py
@dataclass
class ParsedIntent:
    intent: Intent
    project: str | None
    component: str | None  # nové: "backend" | "frontend" | None
    planning: Planning | None
```

### 8.4. Konverzačný trimming

- Načítavame posledných **50 správ** do LLM contextu (konfigurovateľné).
- Všetko ostáva v DB — žiadny hard delete.

### 8.5. Súborová štruktúra (nové súbory)

```
src/temporal_agents/
├── models/
│   ├── conversation.py    # Conversation SQLAlchemy model
│   └── project_ext.py     # Repos, env_file na project
├── services/
│   └── conversation.py    # CRUD + trimming
api/
├── endpoints/
│   └── conversations.py   # FastAPI router
```

### 8.6. Testy

```bash
# Unit testy (bez Temporal servera)
uv run pytest tests/unit/test_conversation.py -v
uv run pytest tests/unit/test_intent_parser.py -v
```

### 8.7. Poradie implementácie

1. **DB migrácia r003** — základ
2. **Conversation CRUD** — service + endpoints
3. **API layer** — pass repos context + component extraction
4. **IntentParser** — component field
5. **Trimming logic** — posledných N správ
6. **FeatureWorkflow** — conversation_id nullable FK
7. **Testy**

---

## 9. Konfiguračné konštanty

```python
# src/temporal_agents/config.py
CONVERSATION_TRIM_MESSAGES: int = 50  # posledných N správ do contextu
```
