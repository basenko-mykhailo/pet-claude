---
name: tasks
description: Turn a project spec (ТЗ, технічне завдання, PRD, requirements, feature list) into epics and task spec files for the agentic pipeline — the Markdown specs with id/status/depends_on front-matter that `agentic run` executes. Use whenever the user wants to break a spec or a large feature into tasks/tickets/epics for the pipeline ("розбий ТЗ на задачі", "підготуй таски для agentic", "зроби епіки з цього документа"), or to add, split or rewrite task specs in <repo>/.claude/agentic's TASKS_GLOB — even if they don't name the pipeline.
---

# Spec → task files for the agentic pipeline

The pipeline runs each task unattended: a planner, an implementer and a validator, each a fresh
`claude -p` that knows only the task file, what it points to, the standing criteria and
`.claude/agentic/context.md`. Nobody answers their questions. So a task file is the whole
brief — anything vague in it becomes a guess, a `needs-human` stop, or a validator `fail`.
Running the pipeline is the `pipeline` skill; this one prepares its input.

## 1. Gather context

- `.claude/agentic/config.sh` must exist; without it, set the project up first (`agentic init`,
  see the `pipeline` skill). From it take `TASKS_GLOB`, `PROGRESS_FILE`, `STANDING_CRITERIA`,
  `LANGUAGE`, `BASE_BRANCH`, `CHECKS`, `project_setup`, the Bash allowlists and `AGENT_TIMEOUT`.
- Read `context.md`, `CLAUDE.md`, the existing task specs of all epics and the progress log —
  continue the numbering, don't duplicate work. `git branch --list 'auto/epic-*'` shows epics that
  have already started (see "Changing tasks later").
- Read the whole spec, then the code: what already exists shapes what the tasks must add.
- The agents work in a worktree cut from `BASE_BRANCH` and see only what is committed there. If
  the spec lives outside the repo or isn't Markdown, propose a path (e.g. `docs/spec.md`) and put
  a faithful Markdown copy there — convert, don't rewrite.

## 2. Close the gaps before splitting

The planner gives up on contradictions, product decisions with no reasonable default, and
anything needing credentials, accounts or paid services. Find these now, while the user is here:

- **Open questions** → ask the user (AskUserQuestion when the options are clear). Record the
  answers in a decisions file (e.g. `docs/decisions.md`) and list it under "Read before planning"
  in `context.md`, so every agent sees them.
- **Business values the spec leaves open** (a rate, a limit, a price, a deadline) → if the user
  can't give the real one yet, mark the placeholder in the decisions file as an assumption to
  confirm, and name it in the hand-over as "confirm before running epic N". A placeholder that
  works passes every check, so nothing else will catch it before it ships.
- **Human-only work** (accounts, API keys, DNS, store publishing, purchases) → a list of human
  prerequisites, not tasks.
- **Commands the agents can't run.** Agents may run read-only commands, `checks`, and what
  `AGENT_BASH` / `IMPLEMENTER_EXTRA_BASH` allow; `project_setup` runs once per run. A task that
  needs anything else (installing a new package, a migration against a real DB, docker) stalls —
  propose a config change or move that step to the human.
- **Prep changes.** If the fix is a change you make now — a dependency in the manifest, a vendored
  asset, an edit to `config.sh` — show it to the user separately from the task files, commit it
  on its own, and run the preflight (step 6) on that commit before the task files go in; fix or
  revert it if the preflight fails. An unverified manifest change breaks `project_setup`, and with
  it the whole run.

## 3. Propose the breakdown — no files yet

Show per epic a table: id, title, depends_on, one line of scope, what proves it done. Add the
decisions, the human prerequisites and the proposed standing criteria. Write files only after
the user agrees; reshuffling a table is cheap, reshuffling twenty files is not.

**Epics.** An epic is one branch `auto/epic-N` cut from `BASE_BRANCH` and one PR. Epic N+1 sees
epic N's code only after that PR is merged, and `depends_on` across epics is ignored by the queue
(ids outside the epic count as done). So order epics so each builds only on earlier ones, and make
each a useful increment a human can review as one PR — typically 3–10 tasks.

**Tasks.**
- One task = one coherent commit that a single agent can plan, implement and prove within
  `AGENT_TIMEOUT` (default 60 min), leaving `CHECKS` green. Every task pays for three agents, so
  don't slice too thin: a field, its migration and its test are one task, not three. Too thick
  shows too: more than about six acceptance criteria, or several subsystems in one task (a
  scheduler, an email template and the delivery), usually means two tasks.
- Prefer vertical slices ("registration end to end: model, API, test") over layers ("all
  models", then "all endpoints"): each slice is testable alone, and a failure blocks less.
- Number tasks in execution order — the queue takes the lowest ready id. List in `depends_on`
  only real prerequisites: when a task fails, the pipeline skips its dependents and carries on
  with the rest, so honest deps keep an overnight run productive.
- Greenfield repo: `CHECKS` gate every attempt of every task, and `project_setup` must succeed at
  the start of each run. The first task — or setup by hand before the first run — has to produce
  the skeleton that makes both work (manifest, test runner, one passing test).

## 4. Write the task files

Path: `TASKS_GLOB` with `${EPIC}` = the epic number; any file name matching the glob — order comes
from `id`, not the name. Headings and text in the project `LANGUAGE`. Example (Ukrainian):

```markdown
---
id: 2.3
status: todo
depends_on: [2.1]
---
# 2.3 — Реєстрація користувача через email

## Контекст
ТЗ: `docs/spec.md`, розділ 4.2 «Реєстрація». Рішення: `docs/decisions.md`, п. 3.
Вже є: модель User і міграція (2.1). Ця задача додає ендпоінт і лист підтвердження.

## Що зробити
- POST /api/register: email + пароль, валідація, створення користувача.
- Лист підтвердження через наявний Mailer (`app/Mail`).

## Поза межами
- Логін і скидання пароля — задача 2.4.

## Критерії приймання
- [ ] Валідні дані → 201, користувач у БД; тест `tests/Feature/RegisterTest.php`.
- [ ] Повторний email → 422 з повідомленням українською; покрито тестом.
- [ ] Лист підтвердження ставиться в чергу; перевірено `Mail::fake()` у тесті.

## Ручна перевірка
- Вигляд листа в поштовому клієнті.
```

The queue parses the format strictly:
- Front-matter holds `id`, `status: todo` and, if needed, `depends_on` as an inline list
  `[2.1, 2.2]` — a multi-line YAML list isn't parsed. No comments on these lines: values are
  taken verbatim. The pipeline itself later sets `status` and `reason`.
- `id` is `N.M`, where N is the epic of the directory.
- The first heading is `# <id> — <Title>`; the title (after ` — `) goes into the progress log,
  commits and notifications.
- Every `depends_on` id must exist in the same epic — an unknown id is silently treated as done.

What makes a task file work:
- **Self-contained.** Point to spec sections by path and heading instead of pasting them, but
  restate the part this task hinges on, and say what earlier tasks already built.
- **Acceptance criteria are the definition of done.** The validator checks each one separately
  and wants evidence — a test, a command, a grep, a file. Write observable outcomes ("GET /health
  → 200, covered by a test"), not qualities ("the API is robust"). Criteria backed by tests are
  best: `CHECKS` keep guarding them in every later task.
- **Human-only checks** (look and feel, a real device, a real account) go under a manual-check
  heading: the task still completes, marked 🟡 with those items for the owner.
- **Out of scope** names the neighbouring tasks, so the implementer doesn't do their work early
  and the validator doesn't mistake it for scope creep.
- Rules that hold for every task don't belong in a task — they go to the standing criteria.

## 5. Supporting files

- **`STANDING_CRITERIA`** (if configured): cross-cutting rules as bullets — language of
  user-facing text, testing expectations, dependency policy, code style. Every agent gets them on
  every call, read from the main checkout.
- **`PROGRESS_FILE`** must exist on `BASE_BRANCH` — the pipeline edits it after every task and
  fails if it's missing. Create it if absent, with a row per epic and a line per task. The
  pipeline finds an epic's row by `| N |` at the start and the emoji in the last cell, and a
  task's line by `- <emoji> **<id> `:

  ```markdown
  | Епік | Назва | Стан |
  |---|---|---|
  | 2 | Акаунти користувачів | ⬜ |

  - ⬜ **2.3 Реєстрація користувача через email** — Специфікація: `tasks/epic-2/task-3-register.md`.
  ```
- **Decisions file** from step 2, referenced from `context.md`.

## 6. Check and hand over

- **Preflight on this machine.** If `project_setup` fails, the run stops before the first task; if
  a `CHECKS` command can't run, every attempt of every task fails. Try both in a throwaway
  worktree of `HEAD`, from the repo root (`${CLAUDE_PLUGIN_ROOT}` is the plugin root — the
  `agentic` on PATH is its `bin/agentic`):

  ```bash
  tmp=$(mktemp -d <scratch dir>/agentic-preflight-XXXXXX)
  git worktree add --detach "$tmp" HEAD
  bash -c 'source "$0/lib/project.sh"; project_setup "$1"' "${CLAUDE_PLUGIN_ROOT}" "$tmp"
  AGENTIC_WT="$tmp" "${CLAUDE_PLUGIN_ROOT}/libexec/checks"
  git worktree remove --force "$tmp"
  ```

  Greenfield: `CHECKS` can pass only after the first task, so check that the tools they call
  exist instead. On a failure, fix it with a prep change or tell the user what to install — don't
  hand over a run that can't start.
- `agentic status --epic N` for each epic: every task listed, deps as intended, `next:` is the
  task you expect.
- List the created files for the user and commit them to `BASE_BRANCH` once they approve —
  uncommitted specs are invisible to the run.
- In the hand-over, list what the user must do or confirm before the run: human prerequisites,
  placeholder values to confirm (with the epic that needs them), anything the preflight couldn't
  settle.
- Suggest trying one task first: `agentic run --epic N --max-tasks 1 --no-pr` (the `pipeline`
  skill covers running).

## Changing tasks later

- Epic not started (no `auto/epic-N` branch): edit on `BASE_BRANCH`.
- Epic started: its branch is never rebased, so the specs on `auto/epic-N` are what counts. Edit
  them in the worktree (`WORKTREE_DIR`) and commit there, never during a run — each run and task
  starts by wiping uncommitted changes in the worktree. Or put the new work into a new epic.
- Don't hand-edit `status` of finished tasks; `agentic retry --epic N --only N.M` returns a
  `needs-human` task to the queue.
