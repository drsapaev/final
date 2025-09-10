# 🚀 Руководство по настройке переменных окружения

## 📋 Когда настраивать переменные окружения

### 1. **СЕЙЧАС (Разработка)**
- ✅ **Базовые настройки** - для корректной работы системы
- ✅ **Безопасность** - установить SECRET_KEY
- ✅ **CORS** - для работы frontend с backend

### 2. **ПОЗЖЕ (По мере необходимости)**
- 🔄 **Firebase** - когда понадобятся push-уведомления
- 🔄 **Telegram** - для уведомлений в Telegram
- 🔄 **Платежи** - для интеграции с Payme/другими системами
- 🔄 **Принтер** - для печати чеков

## 🛠️ Как настроить

### Шаг 1: Создать файл .env
```bash
cd C:\final\backend
copy NUL .env
```

### Шаг 2: Добавить базовые настройки
```env
# ===========================================
# КЛИНИКА - ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ===========================================

# --- ОСНОВНЫЕ НАСТРОЙКИ ---
ENV=dev
APP_NAME=Clinic Manager
APP_VERSION=0.9.0

# --- БАЗА ДАННЫХ ---
DATABASE_URL=sqlite:///./clinic.db

# --- АУТЕНТИФИКАЦИЯ ---
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# --- CORS ---
CORS_ALLOW_ALL=0
CORS_ORIGINS=http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173

# --- ВРЕМЯ И ОЧЕРЕДЬ ---
TIMEZONE=Asia/Tashkent
QUEUE_START_HOUR=7
ONLINE_MAX_PER_DAY=15

# --- PDF И ПЕЧАТЬ ---
PDF_FOOTER_ENABLED=1
CLINIC_LOGO_PATH=

# --- ПРИНТЕР ---
PRINTER_TYPE=none

# --- ЛИЦЕНЗИРОВАНИЕ ---
REQUIRE_LICENSE=0
LICENSE_ALLOW_HEALTH=1
```

## 🎯 Приоритеты настройки

### 🔴 КРИТИЧНО (сейчас)
1. **SECRET_KEY** - для безопасности JWT токенов
2. **CORS_ORIGINS** - для работы frontend
3. **DATABASE_URL** - для подключения к БД

### 🟡 ВАЖНО (в ближайшее время)
4. **TIMEZONE** - для корректного времени
5. **QUEUE_START_HOUR** - для работы очереди
6. **PDF_FOOTER_ENABLED** - для печати

### 🟢 ОПЦИОНАЛЬНО (по необходимости)
7. **FIREBASE_*** - для push-уведомлений
8. **TELEGRAM_*** - для Telegram уведомлений
9. **PAYME_*** - для платежей
10. **PRINTER_*** - для печати чеков

## ⚡ Быстрый старт

```bash
# 1. Создать .env файл
cd C:\final\backend
echo. > .env

# 2. Открыть в редакторе и добавить настройки выше

# 3. Перезапустить backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 🔒 Безопасность

- **НИКОГДА** не коммитьте .env в git
- **СМЕНИТЕ** SECRET_KEY в продакшене
- **ИСПОЛЬЗУЙТЕ** разные настройки для dev/stage/prod
