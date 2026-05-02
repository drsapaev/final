# EMR Smart Autocomplete UX v4.0

## Обзор

EMRSmartField v4 — интеллектуальная система автодополнения для медицинских записей с:
- **Doctor History-Based Autocomplete** — подсказки из реальной истории врача (поиск, не генерация)
- **Automatic Readiness System** — автоматическая активация при достаточном объёме данных
- **Ghost text** как в IDE
- **Hybrid Control** — возможность паузы для каждого поля
- **Telemetry** для аналитики эффективности
- **Переключатель режимов** для разных стилей работы

---

## 🔥 Doctor History-Based Autocomplete (NEW in v4.0)

### Принципы
- ✅ **Поиск и ранжирование** — НЕ генерация
- ✅ **Только история конкретного врача** — приватность данных
- ✅ **Автоматическая активация** — нет ручных переключателей
- ✅ **Prefix search** — подсказки после 3 символов
- ✅ **Частотное ранжирование** — сначала часто используемые фразы

### Критерии активации (Readiness)

Система **автоматически активируется** когда врач:
1. Завершил ≥**10 EMR записей**
2. Накопил ≥**30 уникальных фраз**
3. Имеет ≥**5 повторяющихся фраз**

До достижения критериев — подсказок из истории нет.

### UI индикатор

```
┌─────────────────────────────────────────────────────────────┐
│ ЖАЛОБЫ                                📝 ⏸️                  │
├─────────────────────────────────────────────────────────────┤
│ Головная боль|, давящего характера...           [Tab ↹]    │
└─────────────────────────────────────────────────────────────┘
                    ↑
            история активна
```

- **📝** — подсказки из истории активны
- **⏸️** — кнопка паузы (Hybrid Control)

### Пример работы

```
Врач вводит: "Голов"
                ↓
Система ищет в его истории:
  ✓ "Головная боль, давящего характера" (×23)
  ✓ "Головокружение при вставании" (×12)
  ✓ "Головная боль, пульсирующая" (×8)
                ↓
Ghost text: "ная боль, давящего характера..."
                ↓
[Tab] → вставлено в поле
```

### Индексируемые поля EMR

- `complaints` — жалобы
- `anamnesis` — анамнез
- `examination` — объективный осмотр
- `diagnosis` — диагноз
- `recommendations` — рекомендации

---

## 🎯 Automatic Readiness System

### Backend API

```http
GET /api/v1/emr/readiness/{doctor_id}
```

**Response:**
```json
{
  "ready": true,
  "progress": {
    "completed_emrs": 15,
    "unique_phrases": 45,
    "repeated_phrases": 12
  },
  "missing": [],
  "message": "Autocomplete ready!"
}
```

### Frontend Integration

```javascript
// useDoctorPhrases hook автоматически проверяет readiness
const { ready, readinessProgress } = useDoctorPhrases({
  doctorId: 123,
  field: 'complaints',
  currentText: value
});

// ready=true → включается автодополнение
// ready=false → подсказок нет
```

### Кэширование

- **TTL**: 1 минута
- **Инвалидация**: при новой индексации (`indexPhrases()`)

---

## 📊 Indexing System

### Batch Indexing (Migration)

Запускается один раз при деплое для индексации всех существующих EMR:

```bash
# Через скрипт
python c:\final\backend\migrate_phrases.py

# Или через API (ADMIN ONLY)
POST /api/v1/emr/batch-index
{
  "limit": 100,
  "offset": 0
}
```

**Response:**
```json
{
  "totalDoctors": 50,
  "totalEmrs": 523,
  "totalPhrases": 2150,
  "doctorsNowReady": 35,
  "durationMs": 12500,
  "errors": []
}
```

### Incremental Indexing (Automatic)

Срабатывает автоматически при сохранении EMR:

```python
# в appointment_flow.py -> save_emr()
indexer.index_single_emr(
    emr_id=emr.id,
    doctor_id=current_user.id,
    specialty=specialty
)
```

### Single Doctor Indexing

```http
POST /api/v1/emr/index-doctor
{
  "doctorId": 123,
  "specialty": "cardiology"
}
```

---

## 📈 Telemetry

### Doctor History Telemetry

Система собирает статистику использования:

```http
POST /api/v1/emr/telemetry
{
  "doctorId": 123,
  "field": "complaints",
  "phraseId": "abc-123",
  "event": "shown" | "accepted"
}
```

### Telemetry Dashboard

```http
GET /api/v1/emr/telemetry-stats/{doctor_id}
```

**Response:**
```json
{
  "doctorId": 123,
  "totalShown": 150,
  "totalAccepted": 120,
  "acceptanceRate": 80.0,
  "avgTimeToAcceptMs": null,
  "topAcceptedPhrases": [
    {
      "phrase": "Головная боль, давящего характера...",
      "field": "complaints",
      "timesAccepted": 23
    }
  ]
}
```

---

## 🔀 Hybrid Control (Per-Field Pause)

Врач может **приостановить** подсказки для конкретного поля:

```
┌─────────────────────────────────────────────────────────────┐
│ ЖАЛОБЫ                                📝 [⏸️]                │  ← клик
├─────────────────────────────────────────────────────────────┤
│ Головная боль|                                              │
└─────────────────────────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────────────────┐
│ ЖАЛОБЫ                                ⏸️ [▶️]                │
├─────────────────────────────────────────────────────────────┤
│ Головная боль|                                              │
└─────────────────────────────────────────────────────────────┘
```

### API (Preferences)

```http
GET /api/v1/emr/preferences/{doctor_id}
```

```http
POST /api/v1/emr/preferences
{
  "doctorId": 123,
  "preferences": [
    { "field": "complaints", "paused": false },
    { "field": "diagnosis", "paused": true }
  ]
}
```

---

## Режимы работы

### Переключатель в UI
```
┌─────────────────────────────────────────────────────────────┐
│ ЖАЛОБЫ                                   [✨ Ghost ▾]  📝   │
├─────────────────────────────────────────────────────────────┤
│ Головная боль|, давящего характера...           [Tab ↹]    │
└─────────────────────────────────────────────────────────────┘
                                             ↓ клик
                                      ┌────────────────┐
                                      │ ✨ Ghost   ✓   │
                                      │ 📋 MVP        │
                                      │ ⚡ Word       │
                                      │ 🔀 Hybrid     │
                                      └────────────────┘
```

### 1. Ghost Mode (✨) — default
```
Головная боль|, давящего характера, усиливается к вечеру [Tab ↹]
             ↑          серый ghost text (полупрозрачный)
          курсор

[Alt+1] давящего характера, усиливается к вечеру...     ⭐
[Alt+2] пульсирующая, в области висков...               ×15
[Alt+3] диффузная, умеренной интенсивности...
```

### 2. MVP Mode (📋) — dropdown
```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Варианты из шаблонов:                                ✕  │
├─────────────────────────────────────────────────────────────┤
│ [1] давящего характера, усиливается к вечеру    ⭐ ×23     │ ← selected
│ [2] пульсирующая, в области висков              ×15        │
│ [3] диффузная, умеренной интенсивности                     │
├─────────────────────────────────────────────────────────────┤
│ ↑↓  Alt+Enter  Alt+1/2/3                                    │
└─────────────────────────────────────────────────────────────┘
```

### 3. Word Mode (⚡) — power users
```
Ввод: "Голов"
           ↓
Dropdown: ["Головная", "Головокружение"]
           ↓
[Enter] → вставить слово → курсор на следующее слово
```

### 4. Hybrid Mode (🔀)
- Ghost text по умолчанию
- Word-by-Word при длинных фразах
- Автопереключение по контексту

---

## Горячие клавиши (унифицированные)

| Клавиша | Ghost | MVP | Word | Описание |
|---------|-------|-----|------|----------|
| **Tab** | ✅ | — | — | Принять ghost text |
| **Alt+Enter** | ✅ | ✅ | ✅ | Принять выбранный |
| **Alt+1/2/3** | ✅ | ✅ | ✅ | Выбрать конкретный |
| **↑↓** | ✅ | ✅ | ✅ | Навигация |
| **Enter** | — | — | ✅ | Принять слово |
| **Escape** | ✅ | ✅ | ✅ | Скрыть подсказки |
| **Ctrl+Alt+Enter** | ✅ | ✅ | ✅ | Inline correction |

---

## Сортировка подсказок

Приоритет:
1. **⭐ Недавно использованные** — в начале списка
2. **×N Частота** — по количеству использований
3. **Специальность** — подсказки для текущей специальности выше

```
┌─────────────────────────────────────────────────────────────┐
│ [1] давящего характера, усиливается      ⭐ ×23  Кардиолог  │
│ [2] пульсирующая, связана с АД           ×15   [history]    │
│ [3] диффузная, умеренной интенсивности   ×8                │
└─────────────────────────────────────────────────────────────┘
```

---

## Использование

```jsx
import EMRSmartField from './EMRSmartField';

<EMRSmartField
  // Data
  value={text}
  onChange={setText}
  
  // State
  isEditable={true}
  
  // 🔥 Doctor History (NEW in v4.0)
  useDoctorHistory={true}
  doctorId={currentUser.id}
  specialty="cardiology"
  
  // AI (fallback when history not ready)
  aiEnabled={true}
  onRequestAI={fetchTemplates}
  
  // Config
  defaultMode="ghost"
  showModeSwitcher={true}
  debounceMs={500}
  
  // Validation
  error={formErrors.field}
  
  // UX
  autoFocus={true}
  onFieldTouch={trackField}
  onBlur={handleBlur}
  onTelemetry={sendAnalytics}
  
  // Labels
  fieldName="complaints"
  label="Жалобы"
  placeholder="Начните ввод..."
  multiline={true}
  rows={3}
/>
```

---

## API Endpoints (v4.0)

### History-Based Suggestions

```http
POST /api/v1/emr/phrase-suggest
{
  "field": "complaints",
  "currentText": "Голов",
  "cursorPosition": 5,
  "doctorId": 123,
  "specialty": "cardiology",
  "maxSuggestions": 5
}
```

**Response:**
```json
{
  "suggestions": [
    {
      "text": "ная боль, давящего характера",
      "source": "history",
      "usageCount": 23,
      "lastUsed": "2026-01-05T10:30:00Z"
    }
  ],
  "field": "complaints",
  "doctorId": 123
}
```

### Readiness Check

```http
GET /api/v1/emr/readiness/{doctor_id}
```

### Telemetry

```http
POST /api/v1/emr/telemetry
```

### Indexing

```http
POST /api/v1/emr/batch-index  # ADMIN ONLY
POST /api/v1/emr/index-doctor
```

---

## Профиль врача

```javascript
// Настройки в профиле пользователя
userPreferences = {
  emr: {
    autocompleteMode: 'ghost',     // default режим
    debounceMs: 500,
    showModeSwitcher: true,
    showRecentFirst: true,
    enableInlineCorrections: true,
    // v4.0: per-field pause
    pausedFields: {
      complaints: false,
      diagnosis: true  // paused
    }
  }
}
```

---

## Файлы

```
c:\final\backend\
├── app\services\
│   ├── doctor_phrase_service.py         # Prefix search & ranking
│   ├── emr_phrase_indexer.py            # Batch/incremental indexing
│   └── doctor_autocomplete_readiness.py # Readiness evaluation
├── app\api\v1\endpoints\
│   └── phrase_suggest.py                # API endpoints
├── app\models\
│   └── doctor_phrase_history.py         # DB model
└── alembic\versions\
    └── 20260105_0002_doctor_phrases.py  # Migration

c:\final\frontend\src\
├── components\emr-v2\sections\
│   ├── EMRSmartFieldV2.jsx              # v4.0 - Doctor History integration
│   └── EMRSmartFieldV2.css
└── hooks\
    └── useDoctorPhrases.js              # Hook with readiness check
```

---

## База данных

### doctor_phrase_history

```sql
CREATE TABLE doctor_phrase_history (
  id INTEGER PRIMARY KEY,
  doctor_id INTEGER NOT NULL,
  field VARCHAR(100) NOT NULL,
  phrase TEXT NOT NULL,
  prefix_3 VARCHAR(3),
  prefix_5 VARCHAR(5),
  usage_count INTEGER DEFAULT 1,
  last_used TIMESTAMP,
  first_used TIMESTAMP,
  specialty VARCHAR(100),
  -- v4.0: telemetry
  suggestions_shown INTEGER DEFAULT 0,
  suggestions_accepted INTEGER DEFAULT 0,
  
  UNIQUE(doctor_id, field, phrase)
);

CREATE INDEX ix_doctor_phrase_prefix_3 ON doctor_phrase_history (doctor_id, field, prefix_3);
CREATE INDEX ix_doctor_phrase_prefix_5 ON doctor_phrase_history (doctor_id, field, prefix_5);
```

---

## Карта переходов (v4.0)

```
                      ┌─────────────┐
                      │   EMPTY     │
                      │  (focus)    │
                      └──────┬──────┘
                             │
                       check readiness
                             │
                ┌────────────┴────────────┐
                │                         │
         ready=false                 ready=true
                │                         │
                ▼                         ▼
       ┌─────────────────┐      ┌──────────────────┐
       │  AI TEMPLATES   │      │ DOCTOR HISTORY   │
       │   (fallback)    │      │  (primary source)│
       └─────────────────┘      └─────────┬────────┘
                                          │
                                   3+ chars typed
                                          │
                                          ▼
                                ┌─────────────────┐
                                │  SEARCH PREFIX  │
                                │  in history DB  │
                                └────────┬────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                           ┌────┤  GHOST TEXT    ├───┐
                           │    │  SHOWN          │   │
                           │    └────────┬────────┘   │
                           │             │            │
                  paused=true          Tab/Alt+1    Escape
                           │             │            │
                           ▼             ▼            ▼
                    ┌───────────┐  ┌──────────┐ ┌────────┐
                    │ HIDE      │  │ ACCEPT   │ │ DISMISS│
                    │ SUGGESTIONS│  │ + telemtr│ └────────┘
                    └───────────┘  └──────────┘
```

---

## Безопасность и приватность

1. **Изоляция данных**: каждый врач видит только СВОЮ историю
2. **Никакого AI**: чистый поиск, нет генерации текста
3. **Локальное хранение**: фразы в `DoctorPhraseHistory`, не отправляются третьим лицам
4. **Телеметрия**: только статистика использования (shown/accepted), не содержимое

---

## Migration Roadmap

1. ✅ Phase 1: Readiness System
2. ✅ Phase 2: Frontend Integration
3. ✅ Phase 3: Batch/Incremental Indexing
4. ✅ Phase 4: Telemetry & Dashboard
5. ✅ Phase 5: Hybrid Control (per-field pause)

---

*v4.0 | 2026-01-06 | Doctor History-Based Autocomplete*
