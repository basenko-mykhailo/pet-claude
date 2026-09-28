# Agentic pipeline

Автономне виконання задач з черги: **planner → implementer → checks → validator → committer**.
Кожен агент — окремий `claude -p` з чистим контекстом; спілкуються лише через файли й JSON.
Git і стан черги веде скрипт, не агенти.

Плагін `agentic` — **загальний інструмент**: однаковий у всіх проєктах, нічого не знає про
конкретний проєкт. Усе проєктне лежить у проєкті, в `.claude/agentic/`.

```
plugins/agentic/                  ← інструмент (Claude Code plugin, маркетплейс pet-claude)
  bin/agentic                     ← єдина команда в PATH: agentic <init|run|status|watch|retry|telegram>
  libexec/pipeline                ← оркестратор: run / status / watch / retry
  libexec/checks                  ← детермінований gate: CHECKS з конфігу проєкту
  libexec/init                    ← agentic init: інтерв'ю → .claude/agentic/
  libexec/scratch                 ← тимчасові теки /tmp/agentic-* для агентів
  libexec/notify-telegram         ← сповіщення в Telegram (NOTIFY_CMD)
  lib/project.sh                  ← знаходить і вантажить конфіг проєкту
  lib/taskq.py                    ← черга: front-matter у специфікаціях + рядок у progress-лозі
  lib/watch.py                    ← live-перегляд прогону
  prompts/*.md, schemas/*.json    ← ролі й структуровані відповіді
  prompts/rules.md                ← правила пайплайна для всіх ролей (дозволи Bash тощо)
  templates/                      ← шаблони config.sh і context.md для init
  skills/pipeline/SKILL.md        ← /agentic:pipeline — щоб Claude вмів керувати конвеєром
  skills/tasks/SKILL.md           ← /agentic:tasks — ТЗ → епіки й специфікації задач

<repo>/.claude/agentic/           ← проєкт
  config.sh                       ← черга, гілки, CHECKS, project_setup, дозволи, мова, тексти
  context.md                      ← що агентам знати про проєкт: доки, правила, інструменти
  bin/                            ← проєктні інструменти для агентів (runtime-обгортки, рендер…)
  runs/                           ← логи прогонів (gitignored)
```

Проєкт знаходиться через `$AGENTIC_PROJECT` або `<git root>/.claude/agentic` — запускати з репозиторію.

## Встановлення (у кожен проєкт окремо)

Плагін живе в маркетплейсі `pet-claude` (цей репозиторій) і ставиться **на рівні проєкту** —
не для користувача. З кореня проєкту:

```bash
claude plugin marketplace add ~/pets/pet-claude --scope project
claude plugin install agentic@pet-claude --scope project
```

Обидві команди пишуть у `<repo>/.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) —
закомітити його.

Команда `agentic` у терміналі — через [direnv](https://direnv.net/), теж на рівні проєкту: `.envrc` у корені

```bash
# direnv: `agentic` (agentic plugin) on PATH inside this repo. The plugin path comes from
# the pet-claude marketplace declared in .claude/settings.json. Once: `direnv allow`.
PATH_add "$(jq -r '.extraKnownMarketplaces["pet-claude"].source.path' .claude/settings.json)/plugins/agentic/bin"
```

і один раз `direnv allow`. Поза проєктом команди немає. Далі — `agentic init` (див. нижче).

Claude бачить `agentic` у PATH свого Bash (усе з `bin/` плагіна) і skills `/agentic:pipeline`, `/agentic:tasks`.
Тому в `bin/` лише одна команда, а внутрішні скрипти — у `libexec/`.

Маркетплейс — локальна тека, тож сесії Claude беруть `bin/` і skills прямо з цього репозиторію:
правки діють з наступної сесії (або `/reload-plugins`), версію піднімати не треба.

## Запуск

```bash
agentic status --epic 6        # черга, залежності, що наступне
agentic watch  --epic 6        # що відбувається зараз (етапи + дії агента)
agentic run    --epic 6        # усе, що готове, по черзі; в кінці push + PR
agentic run    --epic 6 --max-tasks 1 --no-pr   # спробувати одну задачу
agentic run    --epic 6 --only 6.3              # конкретну (ігнорує depends_on)
agentic retry  --epic 6 --only 6.7              # needs-human → todo
```

На ніч: `nohup agentic run --epic 6 >/dev/null 2>&1 &`, потім `agentic watch`:
етапи + дії поточного агента (🔧 виклики, 💬 думки, ⚠ відмови в доступі й помилки).

## Сповіщення (Telegram)

Конвеєр сам пише про старт, кожну задачу (✅/🟡/🛑 + час і вартість), збої й кінець прогону
(підсумок + посилання на порівняння гілки на GitHub). Гілка пушиться після кожної задачі
(`PUSH_EACH_TASK=1`), тож прогрес видно і в застосунку GitHub.

Одноразово на машині (облікові дані спільні для всіх проєктів, поза git):
1. У Telegram: @BotFather → `/newbot` → отримати токен.
2. Відкрити свого бота → **Start**.
3. `agentic telegram --setup <токен>` — знайде chat id, збереже
   `~/.config/agentic/telegram.env` (права 600) і надішле тестове повідомлення.

У конфігу проєкту: `NOTIFY_CMD=("$AGENTIC_DIR/libexec/notify-telegram")`. Не налаштовано — тиша,
прогін не падає. Інший канал — будь-яка команда, що приймає текст першим аргументом.

## Підключити новий проєкт

```bash
cd <проєкт>
agentic init               # інтерв'ю українською з поясненнями
agentic init --yes         # або все за замовчуванням
```

`init` визначає що може з репозиторію (базова гілка, `npm test`/`composer test`/`pytest`/…,
доки в `README.md` і `docs/`), питає решту і створює `.claude/agentic/config.sh`, `context.md`,
`bin/`, файл постійних критеріїв і рядок у `.gitignore`. Наявний конфіг не перезаписує.
Шаблони — `templates/` плагіна.

Далі руками: `context.md` (як запускати тести/застосунок у worktree, правила проєкту),
`project_setup()` у `config.sh` (залежності у свіжому worktree), специфікації задач з front-matter:

```yaml
---
id: 6.2
status: todo
depends_on: [6.1]
---
# Будь-який префікс — Назва задачі
```

закомічені в `BASE_BRANCH` (worktree створюється з нього). Перевірка: `agentic status --epic N`.

Специфікації з ТЗ готує Claude: `/agentic:tasks docs/spec.md` (або просто «розбий ТЗ на задачі для
agentic»). Спершу питання й рішення, яких ТЗ не дає, потім розбивка на епіки й задачі на погодження,
і лише тоді файли задач, журнал прогресу й постійні критерії.

## Як проходить задача

1. **Вибір** — перша `status: todo`, у якої всі `depends_on` мають `done`.
2. **Planner** — `--permission-mode plan`, тільки читання → план (`plans/<spec>` поруч зі специфікацією).
3. **Implementer** — `acceptEdits` + allowlist → зміни у worktree `WORKTREE_DIR`.
4. **Checks** — `libexec/checks`; провал → вивід іде фідбеком наступній спробі.
5. **Validator** — чистий контекст, без Edit/Write, бачить `git diff --cached`, AC специфікації й
   постійні AC → `pass | fail | needs_human`. `fail` → фідбек implementer (до `MAX_ATTEMPTS`).
   Якщо валідатор щось змінив у дереві — зміни відкочуються.
6. **Committer** — скрипт: `status: done`, рядок ✅/🟡 у progress, коміт у `WORK_BRANCH`.

Будь-яка роль може повернути `needs_human` (або вичерпано спроби / таймаут / збій) → патч
останньої спроби в `runs/…/last-attempt.patch`, `status: needs-human` + `reason`, 🛑 у progress,
коміт — і далі наступна задача. Залежні від неї задачі пропускаються (⛔ у підсумку).
🟡 = зроблено й провалідовано, але є пункти для ручної перевірки.

Промпт кожного агента = роль (`prompts/`) + специфікація + постійні критерії (`STANDING_CRITERIA`)
+ контекст проєкту (`context.md`) + правила пайплайна (`prompts/rules.md`).

## Дозволи агентів

`write_settings` у `libexec/pipeline` на старті прогону пише `runs/<id>/settings-<роль>.json`. Підтверджувати
нікому, тож усе, що не дозволено, агент отримує як відмову (`permission_denials` у `*.result.json`, ⚠ у
`agentic watch`). Як працювати в цих рамках, агентам пояснює `prompts/rules.md` — правити його разом
із `write_settings`.

- **Читання** (усі ролі): інструмент Read — будь-де; shell (`cat`, `grep`, `sed -n`…) — worktree,
  `$PROJECT_BIN` і `/tmp/agentic-*`.
- **Запис** (лише implementer): Edit/Write — worktree (`acceptEdits`) і `/tmp/agentic-*`. Голих `Edit`/`Write`
  в allow немає навмисно: вони пускали б правки будь-куди поза worktree, зокрема в обгортки `$PROJECT_BIN`,
  які агенти запускають без підтвердження. З тієї ж причини `$PROJECT_BIN` відкрито правилом `Read(…)`, а не
  `--add-dir`: робочу теку `acceptEdits` відкрив би й для запису з shell (`sed -i`, `>`, `mkdir`).
- **Bash**: базовий набір (read-only shell і git, `checks`, `scratch`) + `AGENT_BASH` і `*_EXTRA_BASH` з конфігу,
  мінус `DENY_BASH`. Кожен такий шаблон виконується без підтвердження — додавайте лише те, що не пише за
  межі worktree.

## Відомі обмеження

- Послідовно, одна гілка на епік; гілка не ребейзиться на свіжий `BASE_BRANCH`.
- Конфіг і allowlist фіксуються на старті прогону; промпти ролей, `prompts/rules.md` і
  `STANDING_CRITERIA` читаються на кожен виклик агента. Правити `libexec/pipeline` посеред прогону — лише атомарно
  (новий файл + `mv`), bash дочитує скрипт з диска.

## Далі (v2)

Оркестратор на Agent SDK, паралельні незалежні задачі у власних worktree,
черга в GitHub Issues (замінити `taskq.py`), PR на задачу + auto-merge після CI.
