# Lessons — Self-Improvement Loop (REQ-015)

## Účel

Tento adresár implementuje **self-improvement slučku** definovanú v REQ-015.
Každý workflow, ktorý dokončí alebo zlyhá na úlohe, môže zachytiť lekciu —
poznatek o tom, čo sa osvedčilo alebo čo treba zlepšiť. Lekcie sa hromadia
v `pending.md` a po manuálnom review sa promujú do definícií agentov.

## Ako vznikne lekcia

1. Workflow zavolá Temporal aktivitu `capture_lesson` s parametrami:
   - `workflow_id` — ID aktuálneho Temporal workflowu
   - `agent_type` — typ agenta, ktorý lekciu generuje (napr. `developer`, `tester`)
   - `outcome` — výsledok: `success` alebo `failure`
   - `lesson_text` — voľný text popisujúci zistenie

2. Aktivita `capture_lesson` zapíše záznam na koniec súboru `lessons/pending.md`
   vo formáte Markdown (viď sekciu Format nižšie).

## Flow: pending.md → agent definície

```
Workflow execution
      │
      ▼
capture_lesson activity
      │  appends entry
      ▼
lessons/pending.md          ← staging area
      │
      │  (manual review — developer alebo tech lead)
      ▼
Hodnotné lekcie sa promujú do:
~/.claude/agents/<agent>.md  ← trvalá pamäť agenta
```

**Manuálny review** je zámerný — automatická propagácia by mohla zaviesť
chybné vzory do definícií agentov. Reviewer rozhodne, či je lekcia:
- **hodnotná** → pridá ju do príslušného `~/.claude/agents/*.md`
- **dočasná/špecifická** → ponechá v pending.md ako históriu
- **irelevantná** → zmaže

## Formát záznamu

```markdown
### 2026-01-15T10:30:00Z
- **workflow_id**: feature-ginidocs-auth-20260115
- **agent_type**: developer
- **outcome**: success
- **lesson_text**: Vždy overuj existenciu DB migrácie pred spustením testov.

---
```

## Súvisiace

- `src/temporal_agents/activities/lesson.py` — implementácia `capture_lesson` aktivity
- `src/temporal_agents/activities/options.py` — `CAPTURE_LESSON_OPTIONS`
- REQ-015 v projektovej dokumentácii
