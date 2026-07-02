# Project Tree — after Step C (part 1)

backend/
app/
api/
v1/
api.py # ← обновлён (подключены недостающие роутеры безопасно)
endpoints/
... # существующие эндпоинты
ws/
queue_ws.py # ← обновлён (алиас ?date= для WS)
core/
config.py
scripts/
init.py
audit_data.py
out/
alembic/
env.py
versions/
20250814_0003_queue.py
20250814_0012_online_queue.py
20250817_0001_perf_indexes.py
20250817_0002_backfill_nullable_defaults.py
20250817_0003_fk_set_null.py
20250818_0004_not_null_hardening.py
20250818_0005_not_null_alignment.py
.env
.env.example
pyproject.toml

frontend/
.env
.env.example
src/
... # вызовы API/WS используют VITE_API_BASE/VITE_WS_BASE

docs/
passport.md
detail.md
README_env.md
Tree_F.md

ops/
backend.Dockerfile
frontend.Dockerfile
docker-compose.yml

MIGRATIONS.md
CHANGELOG.md