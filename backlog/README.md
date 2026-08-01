# Backlog

The plan of record. Every unit of work is a markdown file with YAML frontmatter, committed to git.

**The repository is the state.** There is no external database, no server, no session memory. An
agent run can be killed at any moment, and the next run recovers everything it needs by reading
these files and `git log`. That is the entire durability strategy.

## Hierarchy

```
backlog/
├── EP-01-foundation/
│   ├── epic.md                     # goal, story list, epic-level acceptance criteria
│   ├── US-01-01-<slug>/
│   │   ├── story.md                # user story, acceptance criteria
│   │   ├── T-01-01-01-....md       # task: the unit an agent session executes
│   │   └── T-01-01-02-....md
│   └── US-01-02-<slug>/
│       └── ...
└── EP-02-<slug>/
    └── ...
```

| ID form | Meaning |
| --- | --- |
| `EP-nn` | Epic. Runs on its own branch, closes with a review. |
| `US-nn-nn` | Story. `<epic>-<story>`. A vertical slice a human would recognize as a feature. |
| `T-nn-nn-nn` | Task. `<epic>-<story>-<task>`. One agent session. One commit. |

IDs are globally unique and never reused. A task's file name may change; its ID may not.

## Status

**Only tasks carry mutable status.** Story and epic status is *derived* from their children, so
there is nothing to keep in sync and nothing to drift.

| Status | Meaning |
| --- | --- |
| `todo` | Not started. Runnable once its `deps` are all `done`. |
| `in_progress` | A session is working on it. Reset to `todo` on the next run if a session died. |
| `done` | Gate passed, committed. |
| `blocked` | Escalated to the user. Nothing downstream of it runs. |
| `reopened` | The epic review sent it back. Runnable again, with review notes appended. |

Epics carry two flags of their own: `planning` (`pending` or `done`) and `review` (`pending`,
`changes-requested`, or `passed`).

## Lifecycle

```
  epic: planning pending
        │
        ├─> planning session decomposes stories into task files ─> commit ─> planning: done
        │
  ┌─────▼───────────────────────────────────────────────────┐
  │  next runnable task (deps done)                          │
  │        │                                                 │
  │        ├─> checkout task/<task-id>, off the epic branch  │
  │        │                                                 │
  │        ├─> task session ──> writes result.json           │
  │        │                                                 │
  │        ├─> gate (run by the orchestrator, never trusted  │
  │        │        from the agent)                          │
  │        │                                                 │
  │        ├─ fail ─> retry once with the failure output     │
  │        │          ─> fail again ─> ESCALATE              │
  │        │                                                 │
  │        └─ pass ─> status: done ─> squash onto epic branch│
  │                    as one commit, task branch deleted    │
  └─────────────────────┬───────────────────────────────────┘
                        │ all tasks done
                        ▼
              epic review (diff vs the specification, doc currency)
                        │
        ┌───────────────┴────────────────┐
        │                                │
   changes-requested                   passed
   (tasks -> reopened,                   │
    loop back)                           ▼
                        land the epic branch: git.epic_landing
                    manual (halt, merge by hand) | auto (merge now) | pr
```

## Escalation

An agent that hits a question the docs do not answer **must not guess.** It writes
`.orchestrator/escalation.json` and exits:

```json
{
  "task_id": "T-01-02-01",
  "question": "<the specific decision it cannot make>",
  "why_uncovered": "<which docs it checked and what they fail to say>",
  "proposals": [
    { "summary": "<option>", "tradeoff": "<what it costs>" },
    { "summary": "<option>", "tradeoff": "<what it costs>" }
  ],
  "recommendation": "<what it would do and why>"
}
```

The orchestrator halts the queue, marks the task `blocked`, and opens an **interactive** Claude
session seeded with that payload to interview you. The outcome of that interview is an edit to a
specification document, because the docs are the specification. Once they answer the question,
clear the block and resume:

```bash
orchestrator resume
```

> [!IMPORTANT]
> An escalation is a documentation bug, not a coding failure. Resolving it always means changing a
> document. If you find yourself answering the question only in the chat, the next session will hit
> the same wall.

## Frontmatter schema

Epic, story, and task frontmatter share one `schema_version` and one migration chain: they are
versioned and documented together here, so a maintainer only has to learn the mechanism once.
`backlog.py` migrates any file whose `schema_version` is older than current (or absent, treated as
the oldest known version rather than already current) through the chain before the rest of the
backlog loads, then writes the migrated file back to disk uncommitted, the same way `Config.load`
migrates `.orchestrator.yaml`. A `schema_version` newer than this package's chain understands
surfaces the same "this environment is behind" prompt config uses, naming the specific file.

Task:

```yaml
---
id: T-01-02-01
type: task
schema_version: 1
title: A short imperative title
epic: EP-01
story: US-01-02
status: todo
deps: [T-01-01-02]
commit:
  type: feat # Conventional Commit type
  scope: core
---
```

Body sections, in order: **Objective**, **Acceptance criteria** (a checklist the agent must
self-report against), **Constraints** (pointers into the specification), and **Out of scope**.

Epic:

```yaml
---
id: EP-01
type: epic
schema_version: 1
title: Foundation
branch: feat/EP-01-foundation
depends_on: []
planning: pending
review: pending
---
```

Epics carry no `status` field. It is derived from their tasks, so storing it would only create
something to drift.

Story:

```yaml
---
id: US-01-02
type: story
schema_version: 1
title: A short user-facing title
epic: EP-01
---
```

## Running it

```bash
orchestrator status          # usage, plus what is done, running, blocked
orchestrator plan EP-02      # decompose the epic's stories into tasks
orchestrator run             # execute until blocked, escalated, or finished
orchestrator run --epic EP-02 --dry-run
orchestrator resume          # clear a resolved block and continue
```

Killing the process at any point is safe. `run` again picks up where it left off.
