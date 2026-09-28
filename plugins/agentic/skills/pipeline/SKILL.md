---
name: pipeline
description: Drive the agentic pipeline — the autonomous task-queue runner (planner → implementer → checks → validator → commit) configured in <repo>/.claude/agentic/. Use when the user asks to run an epic, check the queue or a run's progress, retry a needs-human task, or set the pipeline up in a new project.
---

# Agentic pipeline

`agentic` is on PATH (the plugin's `bin/`). Run it from the project repository; the project config is
`<git root>/.claude/agentic/config.sh`. Full docs: `${CLAUDE_PLUGIN_ROOT}/README.md`.

| Goal | Command |
|---|---|
| Queue: statuses, dependencies, what's next | `agentic status --epic N` |
| Run everything ready in the epic | `agentic run --epic N` |
| Try a single task / a specific one | `agentic run --epic N --max-tasks 1 --no-pr` / `--only N.M` |
| Put a needs-human task back to todo | `agentic retry --epic N --only N.M` |
| Live view of the current run | `agentic watch --epic N` |
| Set up a new project | `agentic init` (interactive) |

- **`run` takes hours** and spawns its own `claude -p` agents. Start it detached — Bash with
  `run_in_background`, or `nohup agentic run --epic N >/dev/null 2>&1 &` — and don't wait on it. Progress:
  `agentic status`, the run log `.claude/agentic/runs/<run>/pipeline.log`, `summary.txt` at the end.
- **`watch` never exits** — it's for the user's terminal; tell them to run it there instead of calling it.
- **`init` is an interview** that reads answers from the terminal: ask the user to type `! agentic init`,
  or run `agentic init --yes` (all defaults) and then adjust `.claude/agentic/config.sh` and `context.md`
  with them. It never overwrites an existing config.
- Before `run`, confirm the task specs (front-matter `id`, `status: todo`, `depends_on`) are committed to
  `BASE_BRANCH` — the worktree is created from it, uncommitted specs are invisible to the run.
