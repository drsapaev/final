# 📱 Руководство по системе QR очередей

## Обзор системы

Система онлайн-очереди позволяет пациентам записываться к врачу через QR код с соблюдением временных ограничений и правил бизнес-логики клиники.

## Архитектура

### Backend Endpoints

1. **Генерация QR токена** (для регистратора/администратора)
   ```
   POST /api/v1/queue/qrcode?day=YYYY-MM-DD&specialist_id={id}
   Authorization: Bearer {token}
   ```
   
   Ответ:
   ```json
   {
     "token": "uuid-token",
     "qr_url": "/queue/join?token=...",
     "expires_at": "2025-10-05T23:59:59",
     "specialist_name": "Доктор Иванов",
     "day": "2025-10-05"
   }
   ```

2. **Вступление в очередь** (публичный endpoint)
   ```
   POST /api/v1/queue/join
   {
     "token": "uuid-token",
     "phone": "+998901234567",
     "patient_name": "Иван Иванов"
   }
   ```

3. **Статус очереди** (для регистратора/врача)
   ```
   GET /api/v1/queue/status/{specialist_id}?target_date=YYYY-MM-DD
   Authorization: Bearer {token}
   ```

### Frontend Components

1. **ModernQueueManager** (`frontend/src/components/queue/ModernQueueManager.jsx`)
   - Генерация QR кодов
   - Просмотр текущей очереди
   - Управление приёмом
   - Вызов пациентов

2. **OnlineQueueManager** (`frontend/src/components/queue/OnlineQueueManager.jsx`)
   - Полнофункциональный UI с Material-UI
   - Использует хук `useQueueManager`

3. **QRTokenManager** (`frontend/src/components/admin/QRTokenManager.jsx`)
   - Управление активными QR токенами
   - Деактивация токенов
   - Статистика использования

## Бизнес-правила

### Временные ограничения

1. **Окно онлайн-записи**: 07:00 - 09:00
   - Пациенты могут записаться в очередь только в это время
   - После 09:00 или открытия приёма регистратором запись закрывается

2. **Срок действия токена**: До конца дня
   - QR токен генерируется на конкретную дату
   - Действует до 23:59:59 этой даты

3. **Закрытие онлайн-записи**:
   - Автоматически при открытии приёма в регистратуре
   - После окончания времени онлайн-записи (09:00)

### Логика работы

```
┌─────────────────────────────────────────────────────────┐
│  1. РЕГИСТРАТОР генерирует QR код                       │
│     - Выбирает специалиста                              │
│     - Выбирает дату (сегодня или будущая)               │
│     - Система создает токен                             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2. ПАЦИЕНТ сканирует QR код                            │
│     - Открывается страница /queue/join?token=...        │
│     - Проверяется временное окно (07:00-09:00)          │
│     - Проверяется что приём не открыт                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  3. ПАЦИЕНТ получает номер в очереди                    │
│     - Номер зависит от специальности                    │
│     - Кардиология: 100+                                 │
│     - Дерматология: 200+                                │
│     - Стоматология: 300+                                │
│     - Общие: 1+                                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  4. РЕГИСТРАТОР открывает приём                         │
│     - Онлайн-запись автоматически закрывается           │
│     - Пациенты вызываются по порядку                    │
│     - Врач видит очередь в своём интерфейсе             │
└─────────────────────────────────────────────────────────┘
```

## Проверки и ограничения

### При генерации QR

```javascript
// backend/app/api/v1/endpoints/queue.py
1. Проверка прав (Admin или Registrar)
2. Проверка существования специалиста
3. Проверка даты (не в прошлом)
4. Создание/получение DailyQueue
5. Генерация уникального токена
```

### При вступлении в очередь

```javascript
// backend/app/crud/online_queue.py
1. Проверка токена (существует и активен)
2. Проверка срока действия токена
3. Проверка что очередь не открыта (opened_at == None)
4. Проверка временного окна (07:00-09:00)
5. Проверка лимита записей на день
6. Предотвращение дубликатов по телефону
```

## Интеграция в RegistrarPanel

```jsx
import ModernQueueManager from './components/queue/ModernQueueManager';

// В RegistrarPanel.jsx
<ModernQueueManager
  selectedDate={selectedDate}
  selectedDoctor={selectedDoctor}
  doctors={doctors}
  onQueueUpdate={() => loadAppointments()}
/>
```

## API Endpoints Reference

### Основные endpoints

| Метод | Endpoint | Описание | Роль |
|-------|----------|----------|------|
| POST | `/api/v1/queue/qrcode` | Генерация QR токена | Admin, Registrar |
| POST | `/api/v1/queue/join` | Вступление в очередь | Публичный |
| GET | `/api/v1/queue/status/{id}` | Статус очереди | Admin, Registrar, Doctor |
| POST | `/api/v1/queue/open` | Открытие приёма | Admin, Registrar |
| POST | `/api/v1/queue/{id}/call-next` | Вызвать следующего | Admin, Registrar, Doctor |

### Legacy endpoints (для совместимости)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/online-queue/qrcode` | Legacy генерация QR |
| POST | `/api/v1/registrar/generate-qr` | Генерация из регистратуры |

## Модели данных

### DailyQueue
```python
day: date                    # Дата приёма
specialist_id: int           # ID врача
active: bool                 # Активна ли очередь
opened_at: datetime          # Когда открыт приём (None = онлайн-запись)
online_start_time: str       # Начало онлайн-записи (07:00)
online_end_time: str         # Конец онлайн-записи (09:00)
max_online_entries: int      # Лимит записей
```

### QueueToken
```python
token: str (UUID)            # Уникальный токен
day: date                    # Дата действия
specialist_id: int           # ID специалиста
generated_by_user_id: int    # Кто сгенерировал
expires_at: datetime         # Срок действия (23:59:59)
active: bool                 # Активен ли токен
```

### OnlineQueueEntry
```python
id: int
queue_id: int                # Связь с DailyQueue
number: int                  # Номер в очереди
patient_name: str            # Имя пациента
phone: str                   # Телефон
telegram_id: int             # ID в Telegram (опционально)
status: str                  # waiting, called, completed, cancelled
source: str                  # online, registrar, telegram
created_at: datetime
```

## Настройка

### Изменение времени онлайн-записи

В `backend/app/services/queue_service.py`:
```python
ONLINE_QUEUE_START_TIME = time(7, 0)   # 07:00
ONLINE_QUEUE_END_TIME = time(9, 0)     # 09:00 (опционально)
```

В `backend/app/crud/online_queue.py`:
```python
queue_settings = get_queue_settings(db)
queue_start_hour = queue_settings.get("queue_start_hour", 7)
```

### Настройка лимитов

```python
# В настройках клиники
max_per_day = {
    "cardio": 15,
    "derma": 20,
    "dental": 12,
    "general": 30
}
```

## Тестирование

```bash
# Backend тесты
cd backend
python -m pytest backend/test_online_queue_system.py -v

# Основные тестовые сценарии
1. test_qr_token_generation          - Генерация QR
2. test_join_queue_with_valid_token  - Вступление в очередь
3. test_time_restrictions            - Временные ограничения
4. test_queue_opening_closes_online  - Закрытие при открытии
```

## Troubleshooting

### Проблема: 401 Unauthorized при генерации QR

**Решение:**
1. Проверьте что `localStorage.auth_token` существует
2. Проверьте роль пользователя (Admin/Registrar)
3. Проверьте срок действия токена

### Проблема: "Онлайн-запись закрыта"

**Причины:**
1. Текущее время не в окне 07:00-09:00
2. Приём уже открыт регистратором (opened_at != null)
3. Достигнут лимит записей на день

### Проблема: QR код не отображается

**Решение:**
1. Установить библиотеку: `npm install qrcode.react`
2. Импортировать: `import { QRCodeSVG } from 'qrcode.react';`
3. Использовать:
   ```jsx
   <QRCodeSVG
     value={`${window.location.origin}${qrData.qr_url}`}
     size={200}
   />
   ```

## Дальнейшие улучшения

- [ ] Интеграция реальной библиотеки QR кодов
- [ ] Telegram бот интеграция для уведомлений
- [ ] SMS уведомления о вызове
- [ ] Статистика и аналитика очередей
- [ ] Экспорт отчётов
- [ ] Мобильное приложение для пациентов
- [ ] Электронное табло очереди

## Полезные ссылки

- Документация API: `/docs` (Swagger)
- Модели данных: `backend/app/models/online_queue.py`
- CRUD операции: `backend/app/crud/online_queue.py`
- Бизнес-логика: `backend/app/services/queue_service.py`

