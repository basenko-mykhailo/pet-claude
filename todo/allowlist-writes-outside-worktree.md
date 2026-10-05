# «Read-only» allowlist дає агентам писати файли поза worktree

Виявлено 2026-09-28 під час перевірки дозволів для коміту `ec84354` (Claude Code 2.1.284, `claude -p --model haiku`,
фейковий репо з worktree, settings від `write_settings()`).

## Що відбувається

Кожен шаблон в allow виконується без підтвердження. Кілька команд базового «read-only» набору
(`libexec/pipeline:112-121`, його отримують усі ролі, включно з валідатором) вміють писати файли, і Claude Code не
розпізнає це як запис. Валідатор (`--permission-mode manual`) без жодної відмови створив файли в теці поза worktree:

```
awk 'BEGIN { print "AWK" > "<dir>/awk-out" }'
sort -o <dir>/sorted src/a.txt
uniq src/a.txt <dir>/uniq-out
sed -n 'w <dir>/sed-out' src/a.txt
git diff --output=<dir>/diff-out HEAD
```

- Deny `Edit(//<dir>/**)` + `Write(//<dir>/**)` цього не зупиняє: з ними результат той самий. Такі deny ловлять
  лише команди, які Claude Code сам розбирає як запис (`sed -i`, `mkdir`, `>`).
- `awk` у implementer так само записав у `.claude/agentic/bin/`, хоча Edit/Write туди не пускає, бо `.claude/`
  Claude Code вважає «sensitive».
- Не перевіряли, але це той самий клас: `awk 'BEGIN { system("…") }'` (довільна команда), `git log/show --output=`.

Проєктні дозволи intita (`~/pets/intita/.claude/agentic/config.sh:92,99,106`):
- `unzip *` (implementer, validator): `unzip -o /tmp/agentic-…/evil.zip -d <PROJECT_BIN>` переписав обгортку
  (перевірено, теж у `.claude/`).
- `docker run --rm *` (implementer, validator): `-v <будь-який шлях>:/x` дає контейнеру запис у цей шлях (не
  перевіряли).

Наслідок: агент може переписати обгортки `$PROJECT_BIN`, `libexec/checks` плагіна або будь-який файл користувача.
Ці скрипти потім виконуються без підтвердження, тож обмеження можна обійти, а валідатор фактично не read-only.

## Варіанти

1. **Звузити базовий набір (плагін).** Прибрати `Bash(awk *)`, `Bash(sort *)`, `Bash(uniq *)`, `Bash(sed -n *)`.
   Для діапазонів рядків агентам лишається Read з offset/limit, для пошуку `grep`. `--output` у git заборонити deny
   на кшталт `Bash(git * --output*)`, але спершу перевірити, чи працює `*` посередині шаблону. Ціна: без свого
   правила `awk '{print $1}' src/a.txt` у валідатора отримав «This command requires approval», тож відмов
   побільшає. Перевірити, які з цих команд Claude Code дозволяє сам (без правила), а які ні.
2. **Точкові deny** замість видалення: `Bash(sort * -o *)`, `Bash(sed -n *w *)` тощо. Крихко, бо варіантів
   синтаксису багато (`-o`, `--output=`, `w` у скрипті sed), а `awk` так узагалі не обмежити.
3. **Проєктні обгортки замість сирих команд** (intita): замість `docker run --rm *` і `unzip *` дозволяти скрипти в
   `$PROJECT_BIN`, які самі перевіряють шляхи (монтування і `-d` лише в worktree та `/tmp/agentic-*`). Разом із цим
   правило в README/`templates/config.sh`: «нічого, що пише поза worktree», вже додане в `ec84354`.
4. **Sandbox Claude Code** для Bash (обмеження запису на рівні ОС робочими теками). Найнадійніше, але треба
   з'ясувати, чи уживається з docker (сокет, `excludedCommands` знову відкриє `-v`) і з `/tmp/agentic-*`.

Рекомендація: 1 для плагіна (з перевіркою відмов на реальному рані) + 3 для intita; 4 дослідити окремо.

## Як перевірити

Відтворити тест із `ec84354`:
- фейковий репо з `.claude/agentic/bin/tool` і worktree з нього;
- settings згенерувати функцією з пайплайна:
  `source <(sed -n '/^write_settings() {/,/^}/p' libexec/pipeline)` з потрібними `BIN`, `PROJECT_BIN`,
  `RUN_DIR`, `AGENT_BASH`…;
- з worktree запустити
  `claude -p --model haiku --max-budget-usd 0.4 --output-format stream-json --verbose --settings <file>`
  з `--permission-mode` і `--tools` ролі (див. `process_task`);
- промпт: виконати по одній команді зі списку вище, не повторювати після відмови.

Жодна з команд не має створити файл поза worktree, а в `permission_denials` результату мають бути всі п'ять. Тест
повторити з `$PROJECT_BIN` поза `.claude/`, бо в `.claude/` Edit/Write блокуються й без правил.
Потім прогін intita: чи не зросла кількість `permission_denials` порівняно з першим раном після `ec84354`.
