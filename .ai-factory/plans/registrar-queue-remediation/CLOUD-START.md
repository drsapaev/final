# Старт и продолжение работы ИИ-агента

Этот файл рассчитан на новый локальный или облачный агент без доступа к предыдущему чату и Windows-диску автора.

- [Основной план](../codex-registrar-queue-remediation-plan.md) — что исправлять.
- [PROGRESS](PROGRESS.md) — что сделано и откуда продолжать.
- [ACCEPTANCE](ACCEPTANCE.md) — как доказать результат.
- Пути внутри инструкций заданы относительно корня репозитория `drsapaev/final`. Локальные абсолютные пути автора не нужны.

## Готовый стартовый запрос

Скопировать целиком в новую задачу агента:

> Работай в репозитории drsapaev/final по .ai-factory/plans/codex-registrar-queue-remediation-plan.md. Сначала прочитай AGENTS.md, .ai-factory/plans/registrar-queue-remediation/CLOUD-START.md и PROGRESS.md, затем определения следующей задачи и ее ACCEPTANCE-сценарии. Не полагайся на историю чата. Сверь статусы с актуальными GitHub PR и origin/main; продолжи активную работу либо возьми минимальную незаблокированную RQ-задачу. План подготовки находится в ветке codex/registrar-queue-remediation-plan, если еще не merged. До его merge разрешено прочитать план, уточнить решения и подготовить handoff; runtime-работу начинай с fresh origin/main, содержащего план, если я отдельно не указал другую базу. Используй отдельный checkout/worktree и правила gate из AGENTS. Не исправляй весь план одним PR. Для каждого среза сначала укажи владельца, first-touch, проверки и stop conditions; затем исправь, проверь и сохрани checkpoint в PROGRESS с PR/commit, командами, результатами и точным следующим шагом. Открытые D-решения не считай согласованными. Если обязательного инструмента/БД/доступа нет, запиши конкретный blocker и готовую передачу; не обходи gate и не называй пропущенные проверки успешными. Не меняй production, реальные данные, токены, глобальные настройки и чужие изменения. Не останавливайся только на составлении нового плана, когда есть доступная авторизованная задача на исправление. Merge/публикацию выполняй в пределах предоставленных полномочий; отсутствие merge не обходи следующим PR.

Для продолжения конкретного среза добавить: «Продолжи RQ-NN / PR #…; сначала сверяй журнал и фактический HEAD».

## B0 — проверить исходное состояние

Команды ниже выполняются из собственного checkout. Они не переключают main tree:

```sh
git status --short --branch
git rev-parse --show-toplevel
git remote -v
git fetch origin
git log -1 --format="%H %s" origin/main
git worktree list
```

При наличии GitHub CLI:

```sh
gh pr list --state open --limit 100 --json number,title,headRefName,headRefOid,url
gh pr view 3114 --json number,state,headRefName,headRefOid,mergedAt,url
gh pr view 3142 --json number,state,mergeCommit,mergedAt,url
```

Не выводить gh token, env, .env и содержимое auth-файлов. Если GitHub CLI отсутствует, использовать доступный штатный GitHub connector/API для read-only проверки PR; не угадывать merge по имени ветки.

Если план еще не в main:

```sh
git show origin/codex/registrar-queue-remediation-plan:.ai-factory/plans/registrar-queue-remediation/PROGRESS.md
```

Для чтения всего комплекта открыть рабочую ветку плана отдельным checkout/worktree через среду облачного агента. Не переносить незавершенные runtime-изменения из этой или чужих веток. Docs PR должен быть merged до обычного выполнения из fresh main; иначе оставить точный handoff или получить явное указание базы.

## Изоляция

На Windows production живет в C:\final. Там запрещены switch/rebase и запуск production с feature-ветки. Создать собственный worktree по актуальному AGENTS. Пример для первой задачи, только после проверки отсутствия такой ветки/каталога:

```powershell
git worktree add C:\final\_wt_rq02 -b codex/rq-02-registrar-search origin/main
```

В облаке использовать уже предоставленный изолированный checkout, если платформа подготовила ветку; проверить его договоренности, не создавать второй checkout автоматически. Для новой задачи после fetch проверить `git rev-parse HEAD` и `git rev-parse origin/main`: до собственных изменений HEAD должен быть свежей согласованной базой. Если платформа дала устаревшую/другую базу без явного указания пользователя, создать отдельный worktree от fresh main, сохраняя исходную ветку. Для продолжения существующего PR сохранять его ветку/изменения и применять правила обновления своего PR, а не создавать заново. Когда требуется отдельный worktree и платформа его не подготовила:

```sh
git worktree add ../final-rq02 -b codex/rq-02-registrar-search origin/main
```

Примеры RQ-02 — шаблон; не брать эту задачу в обход RQ-01. Имя нового пути/ветки не должно совпадать с чужой работой. Не использовать reset --hard/checkout для очистки неизвестных изменений.

## Cloud prerequisites и gate

Требуется Git, Node/npm из актуальных CI/manifest, Python >=3.11 и PowerShell Core `pwsh`. На базисе плана CI использует Node 20, Python 3.11.10, PostgreSQL 16, Redis 7; при исполнении сверить актуальные файлы CI, не менять lockfile ради этих подсказок.

`scripts/run_python.ps1` поддерживает Linux .venv/bin/python и PATH python3. `ai/langgraph/scripts/agent_gate.py` использует стандартную библиотеку и находит корень по своему расположению. Поэтому Windows-path сервера не нужен.

Из корня **своего** checkout:

```sh
pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-NN: конкретная задача и узкая граница"
```

При действительно подтвержденном root cause:

```sh
pwsh -NoProfile -File ./ai/langgraph/scripts/run_agent_gate.ps1 "RQ-NN: конкретная задача" --known-root-cause "backend/app/подтвержденный_файл.py"
```

Путь выше — placeholder, заменить существующим canonical file. Прочитать возвращенный Ready-to-send execution prompt до правок. Сохранить точную команду, вывод/путь handoff и first-touch в evidence без секретов.

Если нет pwsh, сначала проверить разрешенный setup среды; его отсутствие — prerequisite, а не повод вызвать bare agent_gate.py вопреки AGENTS. Если обеспечить pwsh/валидный gate нельзя, остановить risky edits и сохранить BLOCKED. Анализ и независимая действительно direct_execute задача возможны лишь при соблюдении общего PR-цикла. Не переименовывать risky задачу в direct_execute, чтобы обойти проверку.

При misroute: один retry с --known-root-cause; narrow_override только при основании, которое допускает актуальный AGENTS, в узких границах и с записью gate_misroute/override_used. Этот план сам по себе не выдает blanket override.

## F0 — frontend

Из `frontend/`, зависимости ставить в своей рабочей копии по текущим manifest/lockfile:

```sh
npm ci --legacy-peer-deps
npm run test:run -- src/pages/registrar/__tests__/registrarWorklistRows.test.ts
```

Для исходной группы аудита:

```sh
node node_modules/vitest/vitest.mjs run src/pages/registrar/__tests__/registrarWorklistRows.test.ts src/components/navigation/__tests__/Tabs.a11y.test.tsx src/components/wizard/__tests__/AppointmentWizardV2.contract.test.tsx src/components/admin/__tests__/UserModal.onboarding.test.tsx --no-cache --reporter=dot
```

Сначала выбрать затронутые tests из задачи. До merge каждого UI PR обязателен полный Tier 1 из `docs/AGENTS_UI.md` §13 (проверять актуальную редакцию):

```sh
npm run test:run
npm run type-check
npm run lint:check
npm run check-theme
npm run audit:icon-controls
npm run build
```

Tier 1 также включает self-contained Playwright suite из W0 ниже. `test:run` запускает Vitest без watch. `npm run lint` применяет --fix; не запускать его как read-only verification. Узкий ESLint/Stylelint полезен первым шагом, но не заменяет полный обязательный gate. Не править lockfile и зависимости в UI fix без обоснования/нового среза.

## P0 — backend, только выбранные тесты

Работать с интерпретатором, где установлены зависимости проекта. **До любого backend import/test** настроить через безопасную тестовую среду `DATABASE_URL` одноразового PostgreSQL, `ENV=dev`, `TESTING=1` и необходимые тестовые secrets по актуальному CI/config. Не наследовать production .env, не печатать DSN/секреты. Даже SQLite fixture не отменяет обязательный DATABASE_URL при импорте app.db.session. Если тестового URL/сервиса нет, backend-проверку пометить BLOCKED.

Пример Linux bootstrap (если среда еще не подготовлена и безопасный DATABASE_URL уже предоставлен), из корня собственного checkout:

```sh
python3 -m venv .venv
export REPO_PYTHON="$PWD/.venv/bin/python"
export ENV=dev
export TESTING=1
"$REPO_PYTHON" -m pip install -r backend/requirements.txt
"$REPO_PYTHON" -m pip install pytest pytest-cov pytest-asyncio pytest-deadfixtures httpx
pwsh -NoProfile -File ./scripts/run_backend_pytest.ps1 tests/integration/test_registrar_services_grouping.py
```

При наличии актуального проектного test-manifest использовать его, сверив CI. Не изменять dependency-файлы только ради локальной установки и не отправлять в Git venv.

Windows может переиспользовать установленный интерпретатор через REPO_PYTHON, но wrapper всегда брать из своей рабочей копии:

```powershell
$env:REPO_PYTHON = 'C:\final\backend\.venv\Scripts\python.exe'
.\scripts\run_backend_pytest.ps1 tests/integration/test_registrar_services_grouping.py
```

Сначала проверить существование/валидность интерпретатора; это пример, не обязательный путь облака. **Вызов C:\final\scripts\run_backend_pytest.ps1 из чужого worktree все равно тестирует main tree**, потому что wrapper вычисляет root по своему файлу.

### Что эти тесты НЕ доказывают

На исходном базисе `backend/tests/conftest.py:test_db` создает временную SQLite через metadata.create_all, даже если DATABASE_URL указывает PostgreSQL. Обычный PASS integration/allocator concurrency не доказывает Postgres locks, уникальность, RLS или Alembic upgrade.

Для RQ-04/14/15/25 и любого schema change:

- Найти/добавить в своем разрешенном test-срезе fixture **одноразового PostgreSQL**, явно проверяющий dialect, безопасный тестовый адрес и Alembic-created schema. Ориентир структуры: `backend/tests/integration/test_reminder_pipeline_pg.py`; это reference-only, не тест очередей.
- Не копировать production/staging данные или .env. Использовать canonical synthetic_seed/dev_seed по AGENTS.
- Проверить актуальный `backend/pytest.ini`: gate_d исключен по умолчанию. Для соответствующих тестов нужен явный `-m gate_d`; --noconftest допустим только если suite специально самостоятельный.
- Доказательство включает конкретный тест, PG dialect/version, Alembic head и результат; никаких полных DSN/паролей в evidence.
- Нет безопасного PG — PostgreSQL acceptance остается BLOCKED/NOT_RUN; не подменять его SQLite.

## W0 — браузер и полный поток

Из `frontend/`, браузер устанавливать версией Playwright текущего lockfile:

```sh
npx playwright install --with-deps chromium
CI=1 npm run test:e2e -- e2e/registrar-ux-audit.spec.ts --project=chromium
```

Это пример узкого запуска. До merge UI PR дополнительно выполнить весь обязательный self-contained набор (актуальность состава сверить с docs/AGENTS_UI.md и CI):

```sh
CI=1 npm run test:e2e -- e2e/registrar-time.spec.ts e2e/registrar-ux-audit.spec.ts e2e/cashier-ux-audit.spec.ts e2e/visual-regression.spec.ts e2e/frontend-10-route-smoke.spec.ts e2e/frontend-10-visual-a11y.spec.ts --project=chromium
```

CI=1 в Linux не позволяет случайно переиспользовать посторонний dev server по текущему config. В PowerShell задавать `$env:CI='1'` отдельно. Сначала прочитать `frontend/playwright.config.ts` и выбранный spec. Intentional snapshot update требует A/B или pixel-diff доказательства по §13; не обновлять все baseline ради зеленого результата.

При недоступном backend Tier 2 можно оформить как DEFERRED по правилам review: original requirement, reason, evidence, owner, resume condition, impact on completion. Это не закрывает обязательный REAL_API-сценарий плана. Нужное подтверждение reviewer учитывать в PR.

registrar-workflow, registrar-ux-audit, registrar-time в исходном коде подменяют API. Это полезная UI-проверка, но **не** доказательство сохранения пациента/очереди в настоящем backend. В evidence маркировать MOCK или REAL_API.

Для REAL_API: явный disposable backend + PostgreSQL/Redis, локальная синтетическая авторизация/данные, подтвержденные адреса, выбранный сценарий без route mocks. Существующий localhost:18000 на production-хосте автоматически тестовой средой не становится. Не перезапускать production для браузерных проверок.

Снимки/trace хранить в текущих установленных artifact-путях тестового запуска или CI; не перезаписывать чужой output/test-results/storage. Использовать исключительно SYNTHETIC/DEV-DEMO, без PHI. В PROGRESS — относительные пути/CI-ссылки, viewport, роль и S-ID.

## Закрытие среза и передача

1. Сверить diff с first-touch, `git diff --check`, выбранные тесты и сценарии.
2. Обновить свою строку PROGRESS и E-NNN: tested HEAD, команды/результат, не проверенное, PR, следующий шаг.
3. Сохранить changes в своей ветке. Создать/обновить один PR по авторизации; после финального commit проверить required checks на фактическом HEAD.
4. В PR прямо указать scope, влияние, доказательства, ограничения, rollback. Не объявлять проверенной систему по unit/CI.
5. Если merge еще не разрешен/доступен, оставить PR_OPEN и точный handoff. Не запускать следующий PR-цикл вопреки AGENTS.
6. Завершение сессии не завершает весь план. Следующий агент начинает с PROGRESS.

Минимальный итог агенту/владельцу: «RQ-NN: статус; измененное поведение; проверки PASS/FAIL/NOT_RUN; PR/commit; blocker или следующий конкретный шаг».
