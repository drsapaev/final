---
description: SSOT правила для QueueProfiles и управления вкладками/специальностями
---

# SSOT: QueueProfiles Architecture

## Принцип Single Source of Truth (SSOT)

**QueueProfile** — единственный источник истины для:
- Вкладок в Registrar Panel
- Специальностей на QR-странице
- Dropdown "Врач" в онлайн-очереди

## Ключевые поля QueueProfile

| Поле | Описание |
|------|----------|
| `key` | Уникальный ключ (cardiology, ecg, dermatology...) |
| `is_active` | Показывать в Registrar Panel (вкладки) |
| `show_on_qr_page` | Показывать на QR-странице и в dropdown очереди |

## API Endpoints

### Приватный (требует авторизации)
```
GET /api/v1/queues/profiles?active_only=true
```
- Используется: Registrar Panel (ModernTabs), Admin Panel
- Возвращает: Все профили с is_active=true

### Публичный (без авторизации)  
```
GET /api/v1/queues/profiles/public
```
- Используется: QueueJoin.jsx, ModernQueueManager.jsx (dropdown "Врач")
- Возвращает: Только профили с is_active=true AND show_on_qr_page=true

## Управление

**Admin Panel → Услуги → Вкладки регистратуры**
- Чекбокс "Активна" → контролирует `is_active`
- Чекбокс "Показывать на QR-странице" → контролирует `show_on_qr_page`

## Файлы

### Backend
- `backend/app/models/queue_profile.py` — модель с полем show_on_qr_page
- `backend/app/api/v1/endpoints/registrar_integration.py` — endpoints

### Frontend  
- `frontend/src/pages/QueueJoin.jsx` — QR страница (uses /public)
- `frontend/src/components/queue/ModernQueueManager.jsx` — dropdown "Врач" (uses /public)
- `frontend/src/components/navigation/ModernTabs.jsx` — вкладки (uses /queues/profiles)
- `frontend/src/components/admin/QueueProfilesManager.jsx` — админка

## Важно!
- НЕ хардкодить списки специальностей в frontend
- Всегда использовать API для получения списков
- Изменения в админке сразу отражаются на QR-странице
