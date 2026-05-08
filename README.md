# 🏥 Система управления клиникой

Современная система управления медицинской клиникой с полным функционалом для записи пациентов, управления очередями, обработки платежей и ведения медицинских карт.

## ⚠️ ВАЖНО ДЛЯ РАЗРАБОТЧИКОВ И ИИ-АГЕНТОВ

**ПЕРЕД РАБОТОЙ С СИСТЕМОЙ АУТЕНТИФИКАЦИИ ОБЯЗАТЕЛЬНО ПРОЧИТАТЬ:**
- 📖 `docs/AUTHENTICATION_LAWS_FOR_AI.md` - **ЗАКОНЫ для ИИ-агентов (КРИТИЧЕСКИ ВАЖНО!)**
- 📖 `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md` - Полное руководство по системе
- 📖 `docs/ROLE_SYSTEM_PROTECTION.md` - Правила защиты системы

**СИСТЕМА ЗАЩИЩЕНА СТРОГИМИ ПРАВИЛАМИ - СОБЛЮДАЙТЕ ИХ!** 🛡️

## 🚀 Основные возможности

- **👥 Управление пациентами** - регистрация, поиск, ведение карт
- **📅 Система записи** - онлайн и офлайн запись к врачам
- **🎯 Управление очередями** - реальное время, уведомления
- **💳 Платежная система** - интеграция с PayMe, обработка платежей
- **📋 Медицинские карты** - EMR, рецепты, история лечения
- **📊 Аналитика и отчеты** - статистика, аналитика доходов
- **🔐 Система ролей** - Admin, Doctor, Registrar, Lab, Cashier
- **📱 Адаптивный интерфейс** - работает на всех устройствах

## 🏗️ Архитектура

### Backend (FastAPI + SQLAlchemy)
- **API**: RESTful API с автоматической документацией
- **База данных**: PostgreSQL + миграции Alembic (single source of truth)
- **Аутентификация**: JWT токены с системой ролей
- **WebSocket**: Реальное время для очередей и уведомлений

### Frontend (React + Vite)
- **UI**: Современный интерфейс с темной/светлой темой
- **Роутинг**: React Router с защищенными маршрутами
- **Состояние**: Контекст API для управления состоянием
- **Тестирование**: Playwright для E2E тестов

## 🛠️ Технологический стек

### Backend
- **Python 3.11** - основной язык
- **FastAPI** - веб-фреймворк
- **SQLAlchemy** - ORM для работы с БД
- **Alembic** - миграции базы данных
- **Pydantic** - валидация данных
- **WebSocket** - реальное время

### Frontend
- **React 18** - UI библиотека
- **Vite** - сборщик и dev сервер
- **React Router** - маршрутизация
- **Axios** - HTTP клиент
- **Lucide React** - иконки

### DevOps
- **Docker** - контейнеризация
- **GitHub Actions** - CI/CD
- **Playwright** - E2E тестирование
- **Ruff/Black/Isort** - качество кода

## 📦 Установка и запуск

### Требования
- Python 3.11+
- Node.js 20+
- PostgreSQL 17+
- Docker (опционально)

### Локальная разработка

1. **Клонирование репозитория**
   ```bash
   git clone <repository-url>
   cd final
   ```

2. **Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   # PostgreSQL DSN example:
   # postgresql+psycopg://clinic:<password>@localhost:5432/clinicdb
   alembic upgrade head
   python run_server.py
   ```

3. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Docker

```bash
# Запуск всех сервисов
docker-compose -f ops/docker-compose.yml up

# Или отдельно
docker build -f ops/backend.Dockerfile -t clinic-backend .
docker build -f ops/frontend.Dockerfile -t clinic-frontend .
```

## 🔧 Конфигурация

### Переменные окружения

```bash
# Backend
DATABASE_URL=postgresql+psycopg://clinic:<db_password>@localhost:5432/clinicdb
CORS_DISABLE=0
WS_DEV_ALLOW=1

# Frontend
VITE_API_URL=http://localhost:18000
```

### База данных

Все изменения схемы БД выполняются только через Alembic:

```bash
cd backend
alembic upgrade head
alembic current
```

Ожидаемый результат: `0001_baseline (head)` или более новая head-ревизия.

## 🧪 Тестирование

### Backend тесты
```bash
cd backend
pytest tests/
pytest tests/test_openapi_contract.py -q
```

### Frontend тесты
```bash
cd frontend
npm run test
npx playwright test
```
В CI фронтенд gate дополнительно включает `frontend/e2e/registrar-time.spec.js` для проверки времени регистрации пациента в `Asia/Tashkent`.

### CI/CD
Система включает полный CI/CD пайплайн с:
- Проверкой качества кода (Ruff, Black, Isort)
- Unit тестами
- Сканированием безопасности
- Docker сборкой и тестированием
- E2E тестами
- Проверкой документации

### Branch protection для `main`

Require these GitHub-native checks:

- `🔍 Качество кода`
- `🐍 Backend тесты`
- `🎨 Frontend тесты`
- `🧱 Context Boundary Integrity`
- `🔄 Frontend-Backend Parity`
- `role-system-check`

Не делать обязательными:

- `Vercel` и `Vercel Preview Comments` — это внешний preview/deploy signal, а не repository-owned CI gate
- `🔒 Security сканирование` — выполняется на `push` в `main` и `workflow_dispatch`
- `🐳 Docker сборка` — выполняется на `push` в `main` и `workflow_dispatch`
- `🔗 Интеграционные тесты` — тяжелая проверка для `push` в `main` и ручных запусков

## 📚 Документация

- [Документация API](docs/README.md) - подробное описание API
- [Короткий smoke по ADM-06](docs/ADM-06_BROWSER_SMOKE.md) - компактная ручная проверка guardrail для каталога услуг
- [Система ролей](docs/ROLES_AND_ROUTING.md) - управление доступом
- [CI Guardrails](docs/CI_GUARDRAILS.md) - какие проверки реально блокируют merge в `main`
- [CI/CD](CI-CD-README.md) - настройка и использование
- [Специализированные панели](SPECIALIZED_PANELS_README.md) - панели врачей

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

Проект разработан для медицинских учреждений с соблюдением стандартов безопасности и конфиденциальности данных.

## 🆘 Поддержка

Для получения помощи:
- Создайте Issue в репозитории
- Обратитесь к документации в папке `docs/`
- Проверьте логи CI/CD для диагностики проблем

---

**Система управления клиникой** - современное решение для медицинских учреждений 🏥✨
