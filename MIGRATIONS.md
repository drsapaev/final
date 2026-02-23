# MIGRATIONS — стратегия без потери данных

## Baseline (2026-02-11)
- Clean baseline migration is `backend/alembic/versions/0001_baseline.py`.
- Legacy migrations moved to `archives/alembic_versions_legacy` for reference only.
- Fresh Postgres bootstrap: `alembic upgrade head`.
- Existing DB that already matches schema: verify, then `alembic stamp 0001_baseline`.

## B.1 (2025-08-17): Индексы производительности
...

## B.2 (2025-08-17): Аудит и подготовка к ограничениям
...

## B.3 (2025-08-17..18): Ужесточение ограничений
### B.3.1 (2025-08-17): FOREIGN KEY с `ON DELETE SET NULL`
...

### B.3.2 (2025-08-18): NOT NULL hardening
...

### B.3.2a (2025-08-18): Выравнивание целей
Цель: согласовать фактическую схему с целями B.3.2.
- `activations.active` → **актуально** `activations.status` (NOT NULL).
- `schedules.*` — таблицы нет, шаг пропущен.

Миграция: `backend/alembic/versions/20250818_0005_not_null_alignment.py`  
Команды:
```bash
cd backend
alembic upgrade head
Откат:
alembic downgrade 20250818_0004
