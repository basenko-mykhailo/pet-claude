## Pipeline rules

- Write everything meant for humans (summaries, user-facing text) in {{LANGUAGE}}.
- Full quality gate: `{{BIN}}/checks` — run it before you finish.
- Scratch files never go in the worktree (everything in it gets committed). Get a dir with
  `{{BIN}}/scratch new <name>` (prints `/tmp/agentic-<name>-XXXXXX`) and create files in it with the
  **Write tool** (implementer). Don't clean up — the pipeline removes /tmp/agentic-* dirs and
  agentic-* docker images after every task.

### Bash permissions

Nobody approves commands: what the pipeline's permission settings don't allow is refused. A refusal
is deliberate — don't retry variations of the same command; rewrite it to fit these rules or use
another tool.

- `|`, `&&` and `;` split a command into parts, and every part must be allowed on its own. Several
  simple calls beat one compound call. Long inline scripts (multi-line quoted code, escaped quotes
  or braces) can be refused as too complex to check — put such a script in a scratch file.
- The exit code and stderr come back with every result: don't append `; echo $?` or
  `echo "exit=$?"` — `echo` isn't allowed, so the whole command is refused.
- Quote arguments that contain `|`, `*`, `?`, `(`, `;`, `&` or spaces: `--filter='A|B'`,
  `-k 'a or b'`. Unquoted, `A|B` is a pipe into a command `B` — refused, and broken anyway.
- `$(…)`, backticks and `git -C` are refused. Don't `cd`: you start in the worktree, a `cd` sticks
  for the following calls, and relative paths stop working.
- Shell commands (`cat`, `grep`, `ls`, `head`, `sed -n`…) read the worktree, the project tools in
  `{{PROJECT_BIN}}` and `/tmp/agentic-*`. Open anything else outside the worktree with the Read tool.
- Change files with the Edit/Write tools, not `sed -i`, `>` or `tee` (implementer; the planner and
  the validator change nothing). Edit/Write work only in the worktree and `/tmp/agentic-*`.
