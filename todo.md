# temporal-agents TODO

<!-- VSEOBECNA POZNAMKA K FORKU temporal-community/temporal-ai-agent:
  - repo obsahuje React frontend + FastAPI backend -- NEPOTREBUJEME
  - ich ulohu preberá Claude Code manažér (priame volanie agentov, CLI interakcia)
  - z repo preberáme: activity logiku, AgentWorkflow základ, worker setup, HITL confirm signal
-->

## Faza 0 -- Vyvojove prostredie
- [ ] Fork temporal-community/temporal-ai-agent  [BLOCKER: gh auth login]
- [ ] Vytvorit GitHub repo djenik/temporal-agents  [BLOCKER: gh auth login, remote nastaveny, push caka]
- [x] Docker Compose lokalny Temporal server (PostgreSQL + UI)  [Podman 4.9.3 + podman-compose 1.5.0, stack bezi, UI OK na localhost:8233]
- [x] Python projekt (uv, temporalio, pydantic)  [commit e2dbece]

## Faza 1 -- Activity vrstva
- [x] claude -p wrapper ako Temporal Activity (heartbeat, timeout, retry)  [commit 00b4fd9]
- [x] Retry politiky pre kazdy agent-typ (developer, tester, devops)  [DEVELOPER_OPTIONS, TESTER_OPTIONS, DEVELOPER_ZBORNIK_OPTIONS, DEVOPS_ZBORNIK_OPTIONS]
- [x] Unit testy activities  [8/8 zelene, pytest-asyncio]

## Faza 2 -- Workflow hierarchia
<!-- ANALYZA FORKU:
  - repo ma len 1 workflow (AgentWorkflow) -- FeatureWorkflow a ProjectWorkflow stavame od nuly
  - Workflow ID je hardcoded retazec "agent-workflow" -- treba refaktorovat na dynamicke ID
    (napr. f"feature-{project}-{feature_name}" / f"project-{project_name}")
-->
- [x] FeatureWorkflow (GiniDocs TDD, ZBORNIK bez testera)  [commit 847192b]
- [x] ProjectWorkflow (GiniDocs paralelne, ZBORNIK sekvencne)  [commit 9c22859, 10/10 zelene]
- [x] Unit testy WorkflowEnvironment (time-skipping)  [10/10 zelene v test_project_workflow.py]

## Faza 3 -- HITL signaly
<!-- ANALYZA FORKU:
  - repo ma HITL confirm signal (human_confirm) -- pouzit ako zaklad
  - treba doplnit cancel/reject signal (repo nema)
-->
- [x] FeatureWorkflow require_confirm flag  [commit 3d8add4]
- [x] ManagerWorkflow so signalmi (confirm, cancel)  [commit 4c0e129]
- [x] CLI gateway (request + confirm prikazy)  [commit a6054e7]
- [x] HITL unit testy  [6/6 zelene, commit 0c06ec5]

## Faza 4 -- Worker + integracne testy
<!-- ANALYZA FORKU:
  - repo ma worker setup (run_worker.py) -- pouzit ako zaklad, adaptovat na nasu strukturu
-->
- [x] Worker proces (max 5 paralelnych activities)  [worker.py: async with Worker, graceful shutdown, print pri starte]
- [x] Integracne testy s realnym Temporal serverom  [2/2 zelene + 1 skip (ManagerWorkflow); Podman localhost:7233]

## Faza 5 -- Self-improvement slucka
- [x] lessons/pending.md staging area  [lessons/pending.md + lessons/README.md (REQ-015 dokumentacia)]
- [x] Activity capture_lesson  [src/temporal_agents/activities/lesson.py, CAPTURE_LESSON_OPTIONS, 6/6 unit testov zelene]
- [x] REQ-015 + rozsirenia agent definicii  [lessons/README.md: flow pending.md -> manuálny review -> ~/.claude/agents/*.md]

## Faza 6 -- Pokrocile funkcie (napady)
<!-- Pridane 2026-03-27 -->
- [ ] HITL zaznamy v PostgreSQL s prioritizaciou
  - Kazdy HITL request sa uklada do DB (tabulka hitl_requests: id, workflow_id, description, priority, status, created_at)
  - Manager moze zobrazit prioritizovany zoznam cakajucich HITLov (napr. CLI: `temporal-agents hitl list`)
- [ ] Manager DB-query vrstva
  - Manager generuje strukturovany JSON dotaz (napr. {table: "hitl_requests", filter: {status: "pending"}, order: "priority"})
  - Temporal activity vykona SELECT nad tabulkou a vrati vysledok spat manazerovi
  - Nahradi pure-LLM lookup — deterministicke, auditovatelne
