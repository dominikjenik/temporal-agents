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

### 7a. Content v conversations — čo tam patrí - OPEN

**Q:** Čo má byť v stĺpci `content`?
