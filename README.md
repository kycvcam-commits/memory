<div align="center">

<img src="https://images.blackroad.io/pixel-art/road-logo.png" alt="BlackRoad OS" width="80" />

# BlackRoad Memory

**Persistent agent memory system — journal, codex, TILs, FTS5 search, cross-session collaboration, and 30K agent orchestration.**

[![BlackRoad OS](https://img.shields.io/badge/BlackRoad_OS-Pave_Tomorrow-FF2255?style=for-the-badge&labelColor=000000)](https://blackroad.io)
[![License](https://img.shields.io/badge/License-Proprietary-FF6B2B?style=for-the-badge&labelColor=000000)](./LICENSE)
[![Agents](https://img.shields.io/badge/Agents-30%2C000-00D4FF?style=for-the-badge&labelColor=000000)](https://github.com/BlackRoad-OS-Inc)

</div>

---

## Overview

BlackRoad Memory is the knowledge persistence layer for BlackRoad OS. Every AI agent session reads from and writes to this shared memory, enabling cross-session collaboration, institutional knowledge, and continuous improvement.

**We don't ride the BlackRoad alone.** Every session is a group effort.

## Components

### Memory Scripts (`scripts/`)

| Script | Purpose | Key Commands |
|--------|---------|-------------|
| `memory-system.sh` | Core journal + hash chain | `status`, `summary`, `log <action> <entity> "<details>"` |
| `memory-codex.sh` | Solutions & patterns DB | `search <query>`, `stats`, `add-solution`, `add-pattern` |
| `memory-infinite-todos.sh` | Long-running projects | `list`, `show <id>`, `add-todo`, `complete-todo` |
| `memory-task-marketplace.sh` | Claimable task pool | `list`, `claim <id>`, `complete <id>`, `search` |
| `memory-til-broadcast.sh` | Cross-session learnings | `broadcast <category> "<learning>"`, `list`, `search` |
| `memory-indexer.sh` | FTS5 search + knowledge graph | `search <query>`, `rebuild`, `patterns` |
| `memory-security.sh` | Agent identity + audit | `status`, `identity <name>`, `sign`, `audit` |

### Agent Orchestrator (`orchestrator/`)

30,000 agent system across 3 Raspberry Pi nodes:

- **Spawn Scheduler** — lazy-activates agents from SQLite pools
- **NATS Protocol** — pub/sub with queue groups for load balancing
- **Task Router** — routes to best node by capacity + archetype
- **Agent Worker** — async coroutines running Ollama inference
- **Node Supervisor** — manages local agent pool per Pi
- **Controller** — FastAPI on :8100, REST API, pipelines, jobs
- **Pipelines** — chain agents: research-report, code-review, fleet-audit, content-create, bug-fix
- **Jobs** — recurring: fleet-health (10min), security-scan (1hr), code-index (30min), analytics (1hr)

## Session Workflow

```bash
# 1. Read the briefing — check what other sessions have done
memory-system.sh summary

# 2. Search codex BEFORE solving anything
memory-codex.sh search "<your problem>"

# 3. Pick up pending work
memory-infinite-todos.sh list

# 4. Do work, then log it
memory-system.sh log <action> <entity> "<details>"

# 5. Broadcast what you learned
memory-til-broadcast.sh broadcast <category> "<learning>"

# 6. Add solutions for future sessions
memory-codex.sh add-solution "<name>" "<category>" "<problem>" "<solution>"

# 7. Mark todos complete
memory-infinite-todos.sh complete-todo <project-id> <todo-id>
```

## Current Stats

| Metric | Count |
|--------|-------|
| Journal entries | 413+ |
| Codex solutions | 94 |
| Codex patterns | 40 |
| Best practices | 30 |
| Anti-patterns | 22 |
| TILs broadcast | 230+ |
| Agents registered | 30,000 |
| Agent pools | 24 |
| Archetypes | 8 |
| Pipelines | 5 |
| Recurring jobs | 5 |

## Collaboration Rules

1. **Check [MEMORY]** — read briefing, search codex before starting
2. **Don't rebuild what's solved** — `memory-codex.sh search` first
3. **Log your work** — every action gets a journal entry
4. **Broadcast learnings** — TILs help ALL future sessions
5. **Mark todos complete** — so others don't redo work
6. **We don't ride the BlackRoad alone** — every session is a group effort

## License

**Proprietary** — Copyright (c) 2024-2026 [BlackRoad OS, Inc.](https://blackroad.io) All rights reserved.

---

<div align="center">

**BlackRoad OS — Pave Tomorrow.**

[blackroad.io](https://blackroad.io) · [Brand](https://brand.blackroad.io) · [GitHub](https://github.com/BlackRoad-OS-Inc)

</div>
