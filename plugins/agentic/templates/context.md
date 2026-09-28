## Project: {{PROJECT_NAME}} — {{PROJECT_ABOUT}}

<!-- Цей файл отримує кожен агент (planner, implementer, validator) у промпті.
     Пишіть коротко й конкретно: що читати, як запускати, які правила перевіряти.
     {{PROJECT_BIN}} замінюється на шлях до .claude/agentic/bin. Коментарі можна видалити. -->

### Read before planning or judging a task

- `CLAUDE.md` (loaded automatically).
{{DOCS}}

### Tools for this worktree

<!-- Як агенту запускати тести, збірку, застосунок САМЕ у worktree (не у вашому
     робочому checkout). Якщо потрібні обгортки — покладіть скрипти в .claude/agentic/bin/
     і дозвольте їх в AGENT_BASH у config.sh. Опишіть тут кожну: що робить, аргументи,
     середовище (що монтує, які змінні) — прочитати скрипт агенти можуть, але це зайві кроки. -->
- Full quality gate: the `checks` script from the pipeline rules below.

### Project rules agents must follow and check

<!-- Правила, які агент має дотримуватися і які validator має перевірити:
     стиль коду, мова інтерфейсу, заборонені підходи, обов'язкові тести… -->
- User-facing text is {{LANGUAGE}}.
