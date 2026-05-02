# SSOT QA Checklist v2

Единый bounded-runbook для ручного прогона клинических панелей по живому бизнес-потоку:

`регистратура -> касса -> специалисты -> лаборатория -> админка`

Документ задаёт один язык маршрутов, вкладок, кнопок, статусов и cross-panel handoff-проверок. Это не полный тест-план на всё приложение, а компактный operational standard для `smoke`, `regression` и `destructive/admin-only` прогона.

---

## 1. Цель и правила использования

- Один файл является SSOT для ручной проверки панелей.
- Целевой бюджет: `47` кейсов.
- Целевой `Smoke/P0`: `15` кейсов за `45-60 минут` при подготовленных тестовых данных.
- `Smoke` выполняется только production-safe действиями.
- `Regression` покрывает P0 + P1 и повторно проверяет критичные handoff-переходы.
- `Destructive/Admin-only` выполняется только в `staging` или на `test data`.
- Для каждого кейса обязательны:
  - `Case ID`
  - `Tier`
  - `Priority`
  - `Role`
  - `Canonical route/tab`
  - `Preconditions`
  - `Steps`
  - `Buttons / actions`
  - `Expected status transition`
  - `Primary source of truth`
  - `Secondary source of truth`
  - `Downstream effect`
  - `Evidence to attach`
  - `Cleanup / reset` для destructive

---

## 2. Канонические маршруты

Использовать только эти маршруты для ручного QA.

| Area | Canonical route | Notes |
|---|---|---|
| Регистратура | `/registrar-panel` | Вкладки через `?tab=` |
| Касса | `/cashier-panel` | Вкладки через локальный tab-state |
| Общий врач | `/doctor-panel` | Вкладки `dashboard / patients / appointments / queue / ai / reports` |
| Кардиолог | `/cardiologist` | Вкладки через `?tab=` |
| Дерматолог | `/dermatologist` | Вкладки через `?tab=` |
| Стоматолог | `/dentist` | Вкладки через `?tab=` |
| Лаборатория | `/lab-panel` | Вкладки `queue / templates / reports` |
| Админка | `/admin` | Подразделы через path и query params |

### Legacy aliases

- Старые e2e могут использовать `/registrar`, `/cashier`, `/doctor`.
- В ручном прогоне эти пути считаются legacy-алиасами и не используются как канонический entry point.

---

## 3. Единый словарь статусов

Не использовать в баг-репортах вольные синонимы.

### Visits

| Domain | Canonical statuses |
|---|---|
| Visit | `pending_confirmation`, `confirmed`, `open`, `in_progress`, `completed` |

### Queue

| Domain | Canonical statuses |
|---|---|
| Queue entry | `waiting`, `called`, `diagnostics`, `no_show`, `incomplete`, `served` |

### Payments

| Domain | Canonical statuses |
|---|---|
| Payment | `pending`, `completed`, `cancelled`, `refunded` |

### Laboratory

| Domain | Canonical statuses |
|---|---|
| Lab report instance | `DRAFT`, `IN_PROGRESS`, `READY`, `FINALIZED`, `PRINTED` |

---

## 4. Run modes и приоритеты

### Run modes

| Tier | Scope | Rules |
|---|---|---|
| `Smoke` | Только P0 | Production-safe, без тяжёлых мутаций, без удаления сущностей |
| `Regression` | P0 + P1 | Разрешены редактирование, отмены, повторная печать, повторные входы |
| `Destructive` | Risky/admin-only | Только `staging/test data`; включает удаления, смену прав, возвраты, ревизии, provider/settings changes |

### Priorities

| Priority | Meaning |
|---|---|
| `P0` | Ломает рабочий поток клиники |
| `P1` | Поток завершается, но с обходом или сильным трением |
| `P2` | Не блокирует поток, но даёт UX/данные/локализационный долг |

### Source-of-truth rules

- Каждый state-changing кейс обязан иметь `Primary` и `Secondary` source of truth.
- `Primary` по умолчанию: UI текущей панели.
- `Secondary` по умолчанию: downstream UI или известное API/network family.
- Прямая проверка БД не входит в обычный ручной прогон.

---

## 5. Execution discipline: не терять план во время прогона

Эти правила обязательны для человека и для агента, который выполняет runbook.

### Core rule

- До завершения прогона план считается активным артефактом, а не “контекстом в голове”.
- После каждого завершённого шага нужно явно обновить статус выполнения.
- Нельзя переходить к следующему кейсу или следующей панели, пока текущий кейс не получил один из статусов:
  - `[x] Done`
  - `[!] Failed`
  - `[-] Blocked`
  - `[~] Partial`

### Minimum execution protocol

Перед началом прогона зафиксировать:

- `Run mode`: `Smoke` / `Regression` / `Destructive`
- `Environment`
- `Operator`
- `Test data set`
- `Start time`
- `Target case list`

Во время прогона вести:

- `Current case`
- `Last completed case`
- `Next case`
- `Open blockers`
- `Evidence status`

### Active run checklist template

Скопировать этот блок в рабочую заметку, ticket, comment или task description перед стартом:

```text
Run mode:
Environment:
Operator:
Test data:
Start time:

Current case:
Last completed case:
Next case:
Open blockers:

[ ] Phase 1 - Регистратура
[ ] Phase 2 - Касса
[ ] Phase 3 - Специалисты
[ ] Phase 4 - Лаборатория
[ ] Phase 5 - Админка

[ ] Evidence attached for completed cases
[ ] Blockers recorded with Case ID
[ ] Final summary prepared
```

### Per-case progress markers

Использовать только эти маркеры:

| Marker | Meaning |
|---|---|
| `[ ]` | Не начато |
| `[~]` | В работе / частично пройдено |
| `[x]` | Завершено успешно |
| `[!]` | Завершено с дефектом |
| `[-]` | Заблокировано внешней причиной |

### Step completion rule

- После каждого кейса записывать не только результат, но и `что именно завершено`.
- Формат короткой отметки:

```text
[x] REG-03 - запись добавлена в очередь, visit виден в downstream lab queue
[!] CASH-02 - payment modal открыт, submit дал ошибку, evidence attached
[-] ADM-09 - blocked, нет test provider credentials для staging
```

### Resume rule

- Если прогон прерван, возобновление идёт не “по памяти”, а от `Last completed case`.
- Следующий старт всегда начинается с:
  - проверки `Current case`
  - чтения последней completed/failed записи
  - подтверждения, что evidence по предыдущему кейсу уже приложены

---

## 6. Шаблон тест-кейса

Использовать этот формат при расширении runbook:

```text
Case ID:
Tier:
Priority:
Role:
Canonical route/tab:
Preconditions:
Steps:
Buttons / actions:
Expected status transition:
Primary source of truth:
Secondary source of truth:
Downstream effect:
Evidence to attach:
Cleanup / reset:
```

В таблицах ниже каждая колонка соответствует обязательному полю шаблона.

---

## 7. Case Budget

| Panel | Smoke | Regression | Destructive | Total |
|---|---:|---:|---:|---:|
| Регистратура | 3 | 4 | 1 | 8 |
| Касса | 2 | 3 | 1 | 6 |
| Специалисты: общий врач | 2 | 3 | 1 | 6 |
| Кардиолог: delta | 1 | 2 | 0 | 3 |
| Дерматолог: delta | 1 | 2 | 0 | 3 |
| Стоматолог: delta | 1 | 2 | 0 | 3 |
| Лаборатория | 3 | 4 | 1 | 8 |
| Админка | 2 | 4 | 4 | 10 |
| **Total** | **15** | **24** | **8** | **47** |

---

## 8. Панельные разделы

## 8.1 Регистратура

### Scope

- Основной маршрут: `/registrar-panel`
- Критичные вкладки: `welcome`, `appointments`, профильные направления, `queue`
- Обязательный handoff: `регистратура -> касса`, `регистратура -> врач`, `регистратура -> лаборатория`

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `REG-01` | Smoke | P0 | Registrar | `/registrar-panel?tab=appointments` | Валидный логин регистратора | Открыть панель; проверить, что список записей и табы загрузились без ошибок | Вход, табы панели | `auth ok`; список отображается | `SOT-AUTH-01` | `SOT-REG-UI-01` | Можно стартовать поток пациента | Скрин header + список | `-` |
| `REG-02` | Smoke | P0 | Registrar | `/registrar-panel?tab=appointments` | Есть свободный тестовый слот и тестовая услуга | Создать нового пациента и новую запись; сохранить через мастер | `Новая запись`, `Далее`, `Сохранить` | Новая запись появляется как `scheduled`/`confirmed` по реализации среды | `SOT-REG-UI-01` | `SOT-REG-API-01` | Появляется канонический patient/appointment объект | Скрин summary мастера + строка записи | `-` |
| `REG-03` | Smoke | P0 | Registrar | `/registrar-panel?tab=appointments` | Запись из `REG-02` создана с лабораторной или врачебной услугой | Добавить запись в очередь и проверить downstream | `Добавить в очередь`, профильный таб, `Онлайн-очередь` | Строка получает queue indicator / `queued` по среде | `SOT-REG-UI-01` | `SOT-LAB-UI-01` или `SOT-DOC-UI-01` | Визит виден в целевой очереди по `visit_id` | Скрин registrar row + downstream row | `-` |
| `REG-04` | Regression | P1 | Registrar | `/registrar-panel?tab=appointments` | Уже существует пациент с уникальным телефоном/ФИО | Найти пациента, открыть карточку, создать повторную запись без дубля пациента | Поиск, открыть найденного пациента, `Новая запись` | Новый визит создаётся без нового patient record | `SOT-REG-UI-02` | `SOT-REG-API-01` | История пациента продолжается в одной сущности | Скрин поиска + patient summary | `-` |
| `REG-05` | Regression | P1 | Registrar | `/registrar-panel?tab=appointments` | Есть запись с непогашенной оплатой | Передать запись в кассовый поток и проверить, что она попала в pending payments | `Оплата` или переход в payment flow | Статус оплаты остаётся `pending`, запись видна кассиру | `SOT-REG-UI-01` | `SOT-CASH-UI-01` | Кассир видит тот же визит/пациента | Скрин registrar row + cashier pending row | `-` |
| `REG-06` | Regression | P1 | Registrar | `/registrar-panel?tab=appointments` | Есть сохранённая запись | Напечатать талон и убедиться в понятном feedback | `Печать талона` | Данные записи не меняются; печать завершается без ошибки | `SOT-REG-UI-01` | `SOT-REG-API-01` | Пациент может идти дальше по потоку с корректным ticket output | Скрин success feedback / preview / opened doc | `-` |
| `REG-07` | Regression | P1 | Registrar | `/registrar-panel?tab=appointments` | Есть активная будущая запись | Перенести запись на другой слот и проверить, что downstream не сломан | `Редактировать`, reschedule actions, `Сохранить` | Дата/время меняются, запись остаётся валидной | `SOT-REG-UI-01` | `SOT-REG-API-01` | У врача/лаба отражается новое время, не создаётся дубль | Скрин before/after row | `-` |
| `REG-08` | Destructive | P1 | Registrar | `/registrar-panel?tab=appointments` | Только staging/test data; есть тестовая запись | Отменить запись или отметить `Неявка`; проверить, что запись уходит из рабочего happy path | `Отменить`, `Подтвердить`, `Неявка` | Статус меняется на `cancelled` или `no_show` по среде и перестаёт участвовать в обычном потоке | `SOT-REG-UI-01` | `SOT-DOC-UI-01` или `SOT-CASH-UI-01` | Downstream-панели не продолжают вести отменённый визит как активный | Скрин reason dialog + итоговая строка | Вернуть запись только вручную при наличии штатного restore path |

---

## 8.2 Касса

### Scope

- Основной маршрут: `/cashier-panel`
- Критичные зоны: `Ожидающие оплаты`, `История платежей`, `Возвраты`
- Обязательный handoff: `касса -> регистратура/врач` через payment status

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CASH-01` | Smoke | P0 | Cashier | `/cashier-panel` | Валидный логин кассира; есть минимум одна pending запись | Открыть кассу, проверить pending list, totals и базовый поиск | Поиск, фильтр статуса | Pending row корректно отображается как `pending` | `SOT-AUTH-01` | `SOT-CASH-UI-01` | Кассир видит именно ожидающие оплаты записи | Скрин pending list + totals | `-` |
| `CASH-02` | Smoke | P0 | Cashier | `/cashier-panel` | Есть тестовый визит с `pending` оплатой | Провести оплату для одной записи | `Онлайн-оплата` / payment modal / submit | `pending -> completed` | `SOT-CASH-UI-01` | `SOT-CASH-API-01` | У визита исчезает pending badge в downstream UI | Скрин modal + completed row | `-` |
| `CASH-03` | Regression | P1 | Cashier | `/cashier-panel` | `CASH-02` завершён | Проверить, что обновлённый payment status виден вне кассы | История/refresh/переход в связанный поток | Статус остаётся `completed` и не откатывается | `SOT-CASH-UI-01` | `SOT-REG-UI-01` или `SOT-DOC-UI-02` | Регистратура/врач видят оплаченный визит | Скрин cashier row + downstream badge | `-` |
| `CASH-04` | Regression | P1 | Cashier | `/cashier-panel` | Есть completed payment | Напечатать чек или открыть receipt download | `Чек` | Печать/receipt открывается без потери статуса | `SOT-CASH-UI-01` | `SOT-CASH-API-01` | Чек можно отдать пациенту без ручной правки | Скрин opened receipt / success feedback | `-` |
| `CASH-05` | Regression | P1 | Cashier | `/cashier-panel` | Есть минимум один completed payment | Открыть `История платежей`, проверить сумму, провайдера, статус и дату | Переключение вкладки, поиск | Историческая запись остаётся консистентной | `SOT-CASH-UI-01` | `SOT-CASH-API-01` | История пригодна для повторной сверки и поддержки | Скрин history row | `-` |
| `CASH-06` | Destructive | P1 | Cashier | `/cashier-panel` | Только staging/test data; есть completed payment | Выполнить отмену pending-платежа или возврат completed-платежа с причиной | `Отмена`, `Возврат`, submit reason | `pending -> cancelled` или `completed -> refunded` | `SOT-CASH-UI-01` | `SOT-CASH-API-01` | Downstream-визит больше не считается полностью оплаченным | Скрин reason modal + итоговый row state | Вернуть тестовую запись к исходному состоянию через отдельный test payment при необходимости |

## 8.3 Специалисты: общий врачебный поток

### Scope

- Основной маршрут: `/doctor-panel`
- Критичные вкладки: `patients`, `appointments`, `queue`
- Обязательный handoff: `очередь врача -> статус визита -> следующий визит`

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `DOC-01` | Smoke | P0 | Doctor | `/doctor-panel?tab=queue` | Валидный логин врача; есть waiting entry | Открыть вкладку очереди; убедиться, что видны только релевантные врачу записи | `Queue` tab | Очередь загружена без лишних чужих записей | `SOT-AUTH-01` | `SOT-DOC-UI-01` | Врач работает со своей queue slice | Скрин queue table | `-` |
| `DOC-02` | Smoke | P0 | Doctor | `/doctor-panel?tab=queue` | Есть минимум одна `waiting` запись | Вызвать следующего пациента и открыть рабочий контекст | `Вызвать следующего`, открыть пациента/визит | `waiting -> called` | `SOT-DOC-UI-01` | `SOT-DOC-API-01` | Пациент переходит в активный клинический шаг | Скрин before/after queue row | `-` |
| `DOC-03` | Regression | P1 | Doctor | `/doctor-panel?tab=queue` | Есть `called` запись | Отправить пациента на диагностику, затем вернуть его по штатному пути | `На обследование`, `Вернуть с диагностики (Push)` | `called -> diagnostics -> called/active` по среде | `SOT-DOC-UI-01` | `SOT-DOC-API-01` | Очередь и визит не теряют пациента между этапами | Скрин diagnostics row + return action | `-` |
| `DOC-04` | Regression | P1 | Doctor | `/doctor-panel?tab=queue` | Есть вызванный или вернувшийся пациент | Завершить приём и убедиться, что рабочая запись покидает активную очередь | `Завершить приём` | `called/diagnostics -> served` и связанный визит уходит из активной очереди | `SOT-DOC-UI-01` | `SOT-REG-UI-01` | Регистратура/очередь не считают визит активным | Скрин final queue row state | `-` |
| `DOC-05` | Regression | P1 | Doctor | `/doctor-panel?tab=appointments` | Есть пациент, которому нужен follow-up | Назначить следующий визит через штатный модал | `Назначить следующий визит` | Создаётся новый follow-up visit со своим временем | `SOT-DOC-UI-02` | `SOT-REG-UI-01` | Новый визит виден в регистрационном/appointment потоке | Скрин schedule modal + created appointment row | `-` |
| `DOC-06` | Destructive | P1 | Doctor | `/doctor-panel?tab=queue` | Только staging/test data; есть active queue entry | Пометить `Не явился`, затем проверить path `Восстановить следующим` или `Не вернулся`/`incomplete` | `Не явился`, `Восстановить следующим`, `Не вернулся` | `called/waiting -> no_show` или `diagnostics -> incomplete` | `SOT-DOC-UI-01` | `SOT-DOC-API-01` | Очередь не зависает на проблемном пациенте и поддерживает штатное восстановление | Скрин destructive state + restore path | После прогона восстановить запись или создать новую тестовую |

## 8.4 Кардиолог: delta к общему врачу

### Tabs

- Mandatory tabs for happy path: `Queue`, `Appointments`, `Visit`, плюс `ECG` или `Blood Tests` по услуге
- Supporting tabs: `Services`, `History`, `AI`
- Required downstream check: профильные данные видны в истории пациента и не ломают статус визита

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `CARD-01` | Smoke | P1 | Cardiologist | `/cardiologist?tab=appointments` | Есть кардиологический визит с релевантной услугой | Открыть `Appointments`, перейти в `Visit`, заполнить один профильный блок (`ECG` или `Blood Tests`) и сохранить | Таб-переходы, профильная форма, save action среды | Визит остаётся рабочим; профильные данные сохраняются без потери контекста | `SOT-CARD-UI-01` | `SOT-DOC-UI-02` | Кардиологический визит продолжает общий клинический поток | Скрин form + saved state | `-` |
| `CARD-02` | Regression | P1 | Cardiologist | `/cardiologist?tab=history` | Есть ранее сохранённые профильные данные | Проверить историю и повторное открытие сохранённого исследования | `History`, открыть сохранённый элемент | Данные открываются без дубля и без потери visit linkage | `SOT-CARD-UI-01` | `SOT-DOC-API-01` | История пригодна для повторной клинической интерпретации | Скрин history item + reopened data | `-` |
| `CARD-03` | Regression | P2 | Cardiologist | `/cardiologist?tab=services` | Есть активный визит | Пройти supporting tabs и убедиться, что нет broken navigation | `Services`, `AI`, `History` | Навигация и контекст пациента не ломаются | `SOT-CARD-UI-01` | `SOT-DOC-UI-02` | Supporting tabs не разрывают happy path | Скрин tabs sequence | `-` |

## 8.5 Дерматолог: delta к общему врачу

### Tabs

- Mandatory tabs for happy path: `Queue`, `Appointments`, `Visit`, плюс `Skin Examination` или `Cosmetic`
- Supporting tabs: `Patients`, `Photos`, `Services`, `History`, `AI`
- Required downstream check: осмотр/процедура сохраняются и отражаются в истории пациента

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `DERM-01` | Smoke | P1 | Dermatologist | `/dermatologist?tab=appointments` | Есть дерматологический визит | Открыть обязательные табы и сохранить один `Skin Examination` или `Cosmetic` кейс | Таб-переходы, профильная форма, save action среды | Осмотр/процедура сохраняется без потери visit context | `SOT-DERM-UI-01` | `SOT-DOC-UI-02` | В истории пациента появляется профильный след | Скрин saved profile block | `-` |
| `DERM-02` | Regression | P1 | Dermatologist | `/dermatologist?tab=history` | Есть ранее сохранённый дерматологический артефакт | Проверить открытие history и повторное чтение данных | `History`, открыть элемент | История и карточка пациента согласованы | `SOT-DERM-UI-01` | `SOT-DOC-API-01` | История осмотров/процедур доступна без дублей | Скрин history + reopened item | `-` |
| `DERM-03` | Regression | P2 | Dermatologist | `/dermatologist?tab=photos` | Есть активный дерматологический визит | Пройти supporting tabs и проверить, что они не теряют пациента/визит | `Photos`, `Services`, `AI`, `Patients` | Навигация целостна, контекст пациента не пропадает | `SOT-DERM-UI-01` | `SOT-DOC-UI-02` | Supporting workflow не ломает основной осмотр | Скрин tabs sequence | `-` |

## 8.6 Стоматолог: delta к общему врачу

### Tabs

- Mandatory tabs for happy path: `Appointments`, `Examinations` или `Diagnoses`, `Visit Protocols`
- Supporting tabs: `Photo Archive`, `Templates`, `Reports`, `Dental Chart`, `Treatment Plans`, `Prosthetics`, `AI`
- Required downstream check: протокол визита и клинические записи открываются повторно и связаны с пациентом

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `DENT-01` | Smoke | P1 | Dentist | `/dentist?tab=appointments` | Есть стоматологический визит | Открыть mandatory tabs и сохранить один диагноз/осмотр или протокол визита | `Appointments`, `Examinations/Diagnoses`, `Visit Protocols`, save action | Стоматологическая запись сохраняется и остаётся связанной с визитом | `SOT-DENT-UI-01` | `SOT-DOC-UI-02` | Клинический документ доступен повторно | Скрин saved protocol/diagnosis | `-` |
| `DENT-02` | Regression | P1 | Dentist | `/dentist?tab=reports` | Есть сохранённый dental visit protocol | Открыть документ/историю повторно и убедиться, что данные не пропали | `Reports`, `Templates` или history-equivalent среды | Документ доступен без перезаписи и рассинхрона | `SOT-DENT-UI-01` | `SOT-DOC-API-01` | История пациента остаётся консистентной | Скрин reopened document | `-` |
| `DENT-03` | Regression | P2 | Dentist | `/dentist?tab=dental-chart` | Есть активный визит | Пройти supporting tabs и проверить отсутствие broken navigation | `Dental Chart`, `Treatment Plans`, `Photo Archive`, `AI` | Контекст пациента сохраняется во всех поддерживающих табах | `SOT-DENT-UI-01` | `SOT-DOC-UI-02` | Supporting tabs не ломают основной visit flow | Скрин tabs sequence | `-` |

## 8.7 Лаборатория

### Tabs

- Mandatory tabs for happy path: `Очередь`, `Шаблоны`, `Бланки`
- Обязательный сквозной контур: `queue -> template resolution -> create/open report -> save draft -> READY -> FINALIZED -> print/reprint -> REVISE -> history`
- Required downstream check: queue status обновляется по визиту, а finalized report остаётся immutable

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `LAB-01` | Smoke | P0 | Lab | `/lab-panel?tab=queue` | Есть визит, созданный в регистратуре, с lab service | Открыть лабораторную очередь и проверить canonical `visit_id`, patient context и template resolution | `Очередь`, открыть запись | В queue row есть валидный visit context; доступен только разрешённый template set | `SOT-LAB-UI-01` | `SOT-LAB-API-01` | Лаборатория работает от `visit`, а не от абстрактного списка анализов | Скрин queue row + resolution hint | `-` |
| `LAB-02` | Smoke | P0 | Lab | `/lab-panel?tab=reports` | Есть запись из `LAB-01`; для визита есть один допустимый шаблон | Создать или auto-open бланк и сохранить значения | `Создать бланк`, `Сохранить черновик` | `DRAFT -> IN_PROGRESS` | `SOT-LAB-UI-02` | `SOT-LAB-API-01` | Бланк создаётся без ручного обхода и сохраняет values batch-wise | Скрин header + saved fields | `-` |
| `LAB-03` | Smoke | P0 | Lab | `/lab-panel?tab=reports` | Есть `IN_PROGRESS` бланк | Провести цепочку готовности до печати | `Отметить готовым`, `Финализировать`, `Печать PDF` | `IN_PROGRESS -> READY -> FINALIZED -> PRINTED` | `SOT-LAB-UI-02` | `SOT-LAB-UI-01` | Очередь и история получают финальный статус по тому же визиту | Скрин status chain + queue update | `-` |
| `LAB-04` | Regression | P1 | Lab | `/lab-panel?tab=reports` | Есть `PRINTED` или `FINALIZED` бланк | Повторно напечатать PDF и убедиться, что reprint не ломает сущность | `Печать PDF` | Статус остаётся `PRINTED` или переходит в `PRINTED` повторно без новой мутации данных | `SOT-LAB-UI-02` | `SOT-LAB-API-01` | Reprint пригоден для выдачи результата без ручной правки | Скрин repeat print feedback | `-` |
| `LAB-05` | Regression | P1 | Lab | `/lab-panel?tab=reports` | Есть finalized/printed бланк | Создать ревизию и проверить неизменяемость старой версии | `Создать ревизию` | Старая версия остаётся `FINALIZED/PRINTED`; новая ревизия открывается отдельно | `SOT-LAB-UI-02` | `SOT-LAB-API-01` | История показывает независимые версии, а не перезапись финала | Скрин old vs revised instances | `-` |
| `LAB-06` | Regression | P1 | Lab | `/lab-panel?tab=queue` или `/lab-panel?tab=reports` | Есть минимум две версии одного lab visit | Проверить историю пациента и фильтрацию по visit | `История бланков пациента`, открыть историю | Версии отображаются в правильном порядке и с правильными статусами | `SOT-LAB-UI-02` | `SOT-LAB-API-01` | Пациентская история пригодна для повторной клинической проверки | Скрин history list | `-` |
| `LAB-07` | Regression | P1 | Lab | `/lab-panel?tab=reports` | Есть визит с настроенным mapping service_code -> template | Попробовать открыть/создать недопустимый шаблон для визита | template picker, create/open | Неверный template choice блокируется; wrong report instance не создаётся | `SOT-LAB-UI-02` | `SOT-LAB-API-01` | Система не допускает ошибочный бланк в клиническом потоке | Скрин error message / blocked create | `-` |
| `LAB-08` | Destructive | P1 | Lab | `/lab-panel?tab=templates` | Только staging/test data; есть template draft/published version | Создать/обновить draft version, опубликовать или клонировать шаблон, затем проверить, что существующие finalized reports не изменились | `Создать шаблон`, `Сохранить черновик`, `Опубликовать`, `Копировать` | Draft/published badges обновляются; старые finalized report instances остаются неизменными | `SOT-LAB-UI-03` | `SOT-LAB-UI-02` | Template versioning не ломает исторические документы | Скрин template badges + unaffected finalized report | Вернуть template changes или использовать isolated test template |

## 8.8 Админка

### Scope

- Основной маршрут: `/admin`
- Проверяем только рабочее ядро:
  - `Пользователи`
  - `Врачи`
  - `Услуги`
  - `queue profiles`
  - `Пациенты`
  - `Записи`
  - `Финансы`
  - `Настройки`
- Обязательный handoff: `админка -> маршрутизация/доступ`, `админка -> registrar/lab/cashier behavior`
- Для короткого smoke только по guardrail каталога услуг используйте [ADM-06_BROWSER_SMOKE.md](ADM-06_BROWSER_SMOKE.md).

| Case ID | Tier | Pri | Role | Canonical route/tab | Preconditions | Steps | Buttons / actions | Expected status transition | Primary SoT | Secondary SoT | Downstream effect | Evidence to attach | Cleanup / reset |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ADM-01` | Smoke | P0 | Admin | `/admin` | Валидный admin login | Открыть dashboard и пройти core navigation | Навигация: `Пользователи`, `Врачи`, `Услуги`, `Пациенты`, `Записи`, `Финансы`, `Настройки` | Admin routes доступны без 403/пустых экранов | `SOT-AUTH-01` | `SOT-ADM-UI-01` | Админ может войти в рабочие разделы ядра | Скрин dashboard + 2-3 core sections | `-` |
| `ADM-02` | Smoke | P0 | Admin | `/admin/users` | Есть несколько пользователей разных ролей | Проверить users list, поиск и фильтр ролей | Поиск, role filter | Таблица корректно фильтруется; role labels консистентны | `SOT-ADM-UI-01` | `SOT-ADM-API-01` | Админ быстро находит объект для RBAC-операций | Скрин search/filter result | `-` |
| `ADM-03` | Regression | P1 | Admin | `/admin/users` | Есть test user | Создать или отредактировать пользователя с ролью и проверить сохранение | `Добавить пользователя`, `Сохранить изменения` | User row обновляется и роль сохраняется | `SOT-ADM-UI-01` | `SOT-AUTH-01` | Маршрутизация и доступ пользователя соответствуют новой роли | Скрин modal + resulting row | `-` |
| `ADM-04` | Regression | P1 | Admin | `/admin/doctors` | Есть test doctor slot | Создать или отредактировать врача и проверить downstream selectors | `Добавить врача`, `Сохранить изменения` | Doctor row сохраняется без потери отделения/специализации | `SOT-ADM-UI-01` | `SOT-REG-UI-02` | Новый/обновлённый врач виден в записи/назначении | Скрин doctor modal + selector downstream | `-` |
| `ADM-05` | Regression | P1 | Admin | `/admin/patients` и `/admin/appointments` | Есть test patient/appointment | Проверить поиск и безопасное редактирование пациента/записи | Search, edit actions, save | Изменения отображаются без дублей и broken row state | `SOT-ADM-UI-01` | `SOT-REG-UI-01` | Регистратура видит те же обновлённые данные | Скрин before/after row | `-` |
| `ADM-06` | Regression | P1 | Admin | `/admin/services?servicesTab=queue-profiles` | Есть тестовая услуга и queue profile | Изменить service catalog или queue profile и проверить handoff в registrar/lab | `Услуги`, `queue profiles`, save action среды | Справочник сохраняется и становится активным | `SOT-ADM-UI-01` | `SOT-REG-UI-01` или `SOT-LAB-UI-01` | Регистратура/лаборатория видят актуальный каталог и маршрутизацию | Скрин save feedback + downstream availability | `-` |
| `ADM-07` | Destructive | P1 | Admin | `/admin/finance` | Только staging/test data | Создать, отредактировать и удалить тестовую финансовую транзакцию | create/edit/delete actions | Финансовая запись проходит полный CRUD-cycle без ghost rows | `SOT-ADM-UI-01` | `SOT-ADM-API-01` | Финансовый раздел не копит мусор и поддерживает консистентность | Скрин full CRUD path | Удалить созданную тестовую запись |
| `ADM-08` | Destructive | P1 | Admin | `/admin/settings?section=settings` | Только staging/test data | Изменить clinic settings и проверить persistence | `Настройки`, `Сохранить`, optional logo upload | Настройки сохраняются и повторно загружаются после refresh | `SOT-ADM-UI-02` | `SOT-ADM-API-01` | Брендинг/контакты/таймзона доступны downstream, включая print context по среде | Скрин save banner + refreshed values | Вернуть исходные значения после прогона |
| `ADM-09` | Destructive | P1 | Admin | `/admin/settings?section=payment-providers` | Только staging/test data | Изменить provider settings, выполнить тест соединения и проверить, что касса видит ожидаемое состояние | `Сохранить`, `Тест`, provider toggles | Provider config persists; test result возвращает success/error без краша | `SOT-ADM-UI-02` | `SOT-CASH-UI-01` | Кассир получает корректный список/доступность провайдеров | Скрин provider settings + cashier confirmation | Вернуть provider settings к baseline |
| `ADM-10` | Destructive | P1 | Admin | `/admin/settings?section=security` и protected routes | Только staging/test data; есть non-admin test user | Изменить доступ или деактивировать user и проверить прямой доступ к admin routes под этой ролью | user deactivate, role change, direct URL open | Доступ отзывается; прямой URL не даёт скрытый admin access | `SOT-ADM-UI-01` | `SOT-AUTH-01` | RBAC реально работает, а не только скрывает кнопку | Скрин role change + forbidden/redirect result | Вернуть test user в исходную роль/active state |

---

## Appendix A. Source of Truth

Использовать эти идентификаторы в кейсах и баг-репортах.

| ID | Primary check | Where / how to verify |
|---|---|---|
| `SOT-AUTH-01` | Роль и landing route после логина | UI landing panel + URL после входа |
| `SOT-REG-UI-01` | Строка записи, статус, queue badges в регистратуре | `/registrar-panel`, appointments/queue-related tabs |
| `SOT-REG-UI-02` | Поисковая выдача и patient summary в мастере/карточке | `/registrar-panel`, search + wizard summary |
| `SOT-REG-API-01` | Patient/appointment/queue network families | Browser network: `patients`, `appointments`, `queue` |
| `SOT-CASH-UI-01` | Pending/history/refund rows, totals, badges | `/cashier-panel`, pending/history/refunds |
| `SOT-CASH-API-01` | Payment network families | Browser network: `pending-payments`, `payments`, `receipt` |
| `SOT-DOC-UI-01` | Queue row, action buttons, queue status | `/doctor-panel?tab=queue` |
| `SOT-DOC-UI-02` | Patient/appointment rows and schedule-next flow | `/doctor-panel?tab=patients` and `/doctor-panel?tab=appointments` |
| `SOT-DOC-API-01` | Doctor queue and follow-up API families | Browser network: `queue/*`, `doctor/visits/schedule-next` |
| `SOT-CARD-UI-01` | Cardio-specific forms and history | `/cardiologist`, tabs `ecg`, `blood`, `history` |
| `SOT-DERM-UI-01` | Derm-specific forms and history | `/dermatologist`, tabs `skin`, `cosmetic`, `history`, `photos` |
| `SOT-DENT-UI-01` | Dental protocol, diagnosis, document/history blocks | `/dentist`, visit/report-oriented tabs |
| `SOT-LAB-UI-01` | Queue workbench row with visit/template/status context | `/lab-panel?tab=queue` |
| `SOT-LAB-UI-02` | Report workbench header, field state, version/history list | `/lab-panel?tab=reports` |
| `SOT-LAB-UI-03` | Template draft/published/version badges | `/lab-panel?tab=templates` |
| `SOT-LAB-API-01` | Lab network families | Browser network: `lab/report-instances`, `lab/template-resolutions`, `lab/templates`, `lab/catalog` |
| `SOT-ADM-UI-01` | Admin tables/forms for core sections | `/admin/*`, tables, filters, CRUD modals |
| `SOT-ADM-UI-02` | Settings persistence and success/error feedback | `/admin/settings` |
| `SOT-ADM-API-01` | Admin network families | Browser network: `users`, `doctors`, `patients`, `appointments`, `finance`, admin settings |

### Secondary source-of-truth defaults

- Если кейс меняет запись или визит, secondary SoT должен быть downstream UI другого участника потока.
- Если downstream UI недоступен в текущем прогоне, использовать соответствующую network family из Appendix A.
- DB-check допускается только как отладочный fallback вне обычного runbook.

---

## Appendix B. Bug Capture / Severity

### Bug capture template

```text
Title:
Panel / route:
Case ID:
Role:
Environment:
Test data:
Preconditions:
Steps performed:
Expected result:
Actual result:
Primary source of truth:
Secondary source of truth:
Status values observed:
Evidence:
Severity:
Regression risk:
```

### Minimum evidence

- Скрин активного экрана до действия, если баг связан со state transition.
- Скрин или screen-record после действия.
- URL и tab/state на момент ошибки.
- Идентификаторы сущностей, если доступны:
  - `patient_id`
  - `visit_id`
  - `appointment_id`
  - `payment_id`
  - `report_instance_id`
- Для сетевых проблем: endpoint family, HTTP code, короткий excerpt response.

### Severity

| Severity | Meaning |
|---|---|
| `Critical` | Полностью блокирует поток и не даёт обхода |
| `Major` | Мешает реальной работе, но обход существует |
| `Minor` | Не блокирует поток, но тормозит или путает пользователя |
| `Nice to have` | Косметика и низкоприоритетные улучшения после стабилизации ядра |

### Common failure categories

- Кнопка не реагирует.
- Кнопка реагирует, но ничего не сохраняется.
- Статус меняется в UI, но не меняется в downstream.
- Статус меняется в downstream, но не обновляется в UI.
- Визит/пациент пропадает между панелями.
- Печать открывает пустой документ или даёт сломанный PDF.
- Финализированный лабораторный документ изменился задним числом.
- Direct URL обходит ограничения роли.
- Пустое состояние выглядит как поломка, а не как отсутствие данных.

---

## Appendix C. Dry-run acceptance before using this runbook

- Прогнать только `Smoke/P0` по одной тестовой цепочке пациента.
- Убедиться, что кейсы не дублируются и читаются быстро.
- Если `Smoke` стабильно выходит за `60` минут:
  - сначала объединять соседние кейсы;
  - не удалять handoff-проверки между ролями;
  - не удалять source-of-truth requirements.

---

*Last Updated: 2026-03-26*
