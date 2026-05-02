# Changelog

## 2026-03-26 — Follow-up backlog triage → ADM-06 browser smoke
- **docs/ADM-06_BROWSER_SMOKE.md** — added a compact QA checklist extracted from the live service-catalog smoke so QA can verify the guardrail in a few steps instead of running the full panel runbook.
- **docs/README.md** — updated the Testing & QA index and linked the new smoke checklist alongside the SSOT panel runbook.
- **docs/PANEL_QA_CHECKLIST.md** — added a direct pointer from the full runbook to the short smoke checklist and refreshed the document timestamp.
- **.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md** — final cycle tracking now reflects `ADM-06-BROWSER-SMOKE` as the last completed case and keeps the follow-up backlog closed.
- Verified live on the temp admin stack `http://127.0.0.1:4194` -> `http://127.0.0.1:18008`:
  - invalid `Лабораторные анализы + P77` blocked with the inline warning `Код P77 не подходит для группы "Лаборатория"`
  - valid `Прочие услуги + O77` saved successfully
  - new row `QA Mismatch Smoke` appeared in the catalog table with canonical code `O77`

## 2025-08-17 — Step A: Архитектура, конфиги, ENV, секреты
- **backend/app/core/config.py** — *kept + extended*: единый центр настроек; добавлены `API_V1_STR`, `DEBUG`, нормализация `CORS_ORIGINS` (CSV), сохранены прежние имена полей (`REQUIRE_LICENSE`, `LICENSE_ALLOW_HEALTH`, `DATABASE_URL`, `AUTH_*` и пр.).
- **backend/.env.example** — добавлен шаблон переменных окружения.
- **frontend/.env.example** — добавлен шаблон переменных для Vite.
- **backend/pyproject.toml** — закреплены верхние границы версий зависимостей для более предсказуемых сборок.
- **docs/README_env.md** — краткая памятка по переменным окружения.

## 2025-08-17 — Step B.1: Схема БД и миграции (безопасные индексы)
- Добавлен Alembic-скрипт `backend/alembic/versions/20250817_0001_perf_indexes.py` (создаёт индексы, только если таблицы/колонки существуют; идемпотентно).

## 2025-08-17 — Step B.2: Аудит данных и backfill NULL
- Добавлен `backend/app/scripts/audit_data.py` (отчёт по «висячим» ссылкам в CSV).
- Добавлен Alembic-скрипт `backend/alembic/versions/20250817_0002_backfill_nullable_defaults.py` (только безопасные обновления данных).

## 2025-08-17 — Fix: Alembic env.py (импорт пакета app)
- **backend/alembic/env.py** — добавлен блок `sys.path.insert(0, backend_root)`; теперь `alembic upgrade head` работает без PYTHONPATH.

## 2025-08-18 — Step B.3.2: NOT NULL hardening
- `backend/alembic/versions/20250818_0004_not_null_hardening.py` — условная установка `NOT NULL` на заранее заполненных полях (SQLite через batch).

## 2025-08-18 — Step B.3.2a: NOT NULL alignment
- `backend/alembic/versions/20250818_0005_not_null_alignment.py` — выравнивание целей (activations.status, исключение schedules).

## 2025-08-18 — **Step C (часть 1): Согласование API и WS**
- **backend/app/api/v1/api.py** — *kept + extended*: безопасное подключение недостающих роутеров (`queues`, `appointments`, `online_queue`) через `_safe_include`.
- **backend/app/ws/queue_ws.py** — *kept + extended*: добавлен алиас параметра `?date=` к `date_str` для совместимости с фронтендом; защищённый импорт реальной реализации стрима.
