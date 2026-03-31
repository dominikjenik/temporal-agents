# Temporal Replacement — Research Threads

*Dátum: 2026-03-30*

---

## Thread 1: Existujúce Temporal + AI agent projekty

**Otázka:** Existuje už niečo podobné môjmu cieľu (multi-agent orchestrácia + HITL + Temporal)?

### Kľúčové nájdené projekty

| Projekt | Hviezdy | Zrelosť | Jazyk |
|---|---|---|---|
| [temporal-community/temporal-ai-agent](https://github.com/temporal-community/temporal-ai-agent) | 657 | Produkčný základ | Python |
| [pydantic/pydantic-ai-temporal-example](https://github.com/pydantic/pydantic-ai-temporal-example) | — | Officiálny, type-safe, HITL | Python |
| [domainio/temporal-langgraph-poc](https://github.com/domainio/temporal-langgraph-poc) | 7 | POC: Temporal + LangGraph | Python |
| OpenAI Agents SDK + Temporal | — | Public Preview (sep 2025) | Python |
| [Vercel AI SDK + Temporal](https://temporal.io/blog/building-durable-agents-with-temporal-and-ai-sdk-by-vercel) | — | Officiálny | TypeScript |

### Záver

**Žiadny projekt neimplementuje všetky štyri veci naraz:**
- manager → feature → developer → tester → auditor hierarchia
- HITL s approval gates
- Temporal ako orchestračný backend
- Claude CLI subprocess (nie API)

`temporal-ai-agent` je len durable chatbot (loop: čakaj signal → LLM → tool → repeat). **Nie je tam IntentParsing ani hierarchia agentov.**

---

## Thread 2: temporal-ai-agent — čo reálne robí?

**Otázka:** Je tam IntentParsing? Prečo ma sklamalo?

### Skutočná architektúra temporal-ai-agent

```
Temporal Workflow loop:
  1. čakaj na ľudský vstup (Signal)
  2. pošli LLM-u správu + dostupné nástroje
  3. LLM rozhodne (nedeterministicky) ktorý nástroj zavolať
  4. vykonaj nástroj (Activity)
  5. späť na 1.
```

### Čo chýba

| Feature | Prítomné? |
|---|---|
| IntentParser (deterministické routing) | ❌ |
| Manager agent delegujúci na feature/dev/tester | ❌ |
| Hierarchia agentov | ❌ |
| Paralelné workflow pre rôzne features | ❌ |
| Temporal durable execution (crash recovery, retry) | ✅ |
| HITL cez Temporal Signals | ✅ |
| Nástroje ako Activities | ✅ |

### Záver

`temporal-ai-agent` dáva len kostru (Temporal loop + HITL signály). IntentParsing, hierarchia agentov a Claude CLI subprocess sú veci, ktoré musíš postaviť sám — to je reálna hodnota `temporal-agentic-workflow` projektu.

**Temporal nie je podmienka** — kľúčové je čiastočná deterministickosť orchestrácie medzi agentmi.

---

## Thread 3: Cline Kanban + Claude CLI

**Otázka:** Dá sa Cline Kanban rozšíriť tak, aby používal Claude CLI namiesto API?

### 3a. Cline — Claude Code provider obmedzenia

| Obmedzenie | Fundamentálne? | Poznámka |
|---|---|---|
| Streaming po tokene | ❌ | ~50 riadkov zmeny — pre agentov irelevantné |
| Prompt caching | ❌ | Pridať `--resume <session_id>` flag |
| Obrázky | čiastočne | Workaround cez temp súbory (zapísať na disk, poslať cestu) |

**Riziko:** Anthropic v januári 2026 obmedzil OAuth token usage v third-party nástrojoch — celý Claude Code provider v Cline môže byť problematický.

### 3b. LiteLLM — čo je to?

Python knižnica — jednotné rozhranie pre volanie rôznych LLM API (OpenAI, Anthropic, Gemini...) rovnakým kódom. Adapter vrstva: `litellm.completion(model="claude-3-5-sonnet")` → správne API volanie. Použité v `temporal-ai-agent`.

### 3c. claude-code-gateway — integrácia s existujúcimi nástrojmi

GitHub: [enescingoz/claude-code-gateway](https://github.com/enescingoz/claude-code-gateway)

FastAPI server, spúšťa `claude` CLI ako subprocess, exponuje `/v1/chat/completions` v OpenAI formáte.

**Podporuje 30+ nástrojov:**
- Cline, Aider, OpenHands, SWE-agent
- CrewAI, AutoGen, LangChain, Pydantic AI, OpenAI Agents SDK
- n8n, Flowise, Langflow, Continue.dev

Pre `temporal-ai-agent` (LiteLLM): stačí nastaviť base URL na gateway → Temporal workflow používa Claude subscription bez API bilingu.

**Riziko:** Môže byť mimo Anthropic ToS.

### 3d. Cline Kanban — vyžaduje CLI alebo môže API?

Kanban podporuje oboje:
- **Cline agent** → akýkoľvek API provider (Anthropic API key, OpenAI...)
- **Claude Code CLI agent** → subprocess volania

Kanban nevyžaduje CLI, ale **používateľ vyžaduje CLI** ako podmienku.

---

### 4. Zhrnutie — čo budovať

| Komponent | Riešenie |
|---|---|
| Orchestrácia (deterministická) | Vlastný IntentParser + agent hierarchia |
| Durable execution | Temporal (alebo alternatíva) |
| HITL | Temporal Signals alebo vlastné |
| Claude CLI as backend | `claude-code-gateway` alebo natívny subprocess |
| Kanban UI pre paralelné agenty | Cline Kanban (s Claude CLI agentom) |

**Základ na fork:** `temporal-community/temporal-ai-agent` (Temporal + HITL kostra) + doplniť IntentParsing + hierarchiu agentov + Claude CLI cez gateway.
