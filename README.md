# pet-claude

Claude Code plugin marketplace for personal pet projects.

| Plugin | What it does |
|---|---|
| [`agentic`](plugins/agentic/README.md) | Autonomous task-queue pipeline: planner → implementer → checks → validator → commit, in an isolated git worktree. |

Plugins are installed **per project**, not per user — from the project root:

```bash
claude plugin marketplace add ~/pets/pet-claude --scope project
claude plugin install agentic@pet-claude --scope project   # → <repo>/.claude/settings.json, commit it
claude plugin validate ~/pets/pet-claude                   # after editing manifests
```

A plugin lives in `plugins/<name>/` with `.claude-plugin/plugin.json` and is listed in
`.claude-plugin/marketplace.json`. Project-specific settings stay in each project
(for `agentic`: `<repo>/.claude/agentic/`).
