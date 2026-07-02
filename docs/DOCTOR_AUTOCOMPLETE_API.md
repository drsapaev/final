# Doctor History Autocomplete - API Reference

## Base URL
```
/api/v1/emr
```

---

## Endpoints

### 1. Get Phrase Suggestions

Получить подсказки из истории врача.

**Endpoint:**
```http
POST /phrase-suggest
```

**Request:**
```json
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

**Notes:**
- Минимальная длина текста: 3 символа
- Поиск по prefix (начало фразы)
- Сортировка по частоте использования

---

### 2. Index Phrases

Проиндексировать фразы из EMR.

**Endpoint:**
```http
POST /phrase-index
```

**Request:**
```json
{
  "doctorId": 123,
  "emrData": {
    "complaints": "Головная боль, давящего характера",
    "diagnosis": "Гипертоническая болезнь II ст."
  },
  "specialty": "cardiology"
}
```

**Response:**
```json
{
  "indexed": 12,
  "doctorId": 123
}
```

**Notes:**
- Автоматически вызывается при сохранении EMR
- Извлекает фразы из всех `INDEXABLE_FIELDS`

---

### 3. Check Readiness

Проверить готовность врача к автодополнению.

**Endpoint:**
```http
GET /readiness/{doctor_id}
```

**Response (ready):**
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

**Response (not ready):**
```json
{
  "ready": false,
  "progress": {
    "completed_emrs": 5,
    "unique_phrases": 12,
    "repeated_phrases": 2
  },
  "missing": [
    "Needs 5 more EMRs (10 required)",
    "Needs 18 more unique phrases (30 required)",
    "Needs 3 more repeated phrases (5 required)"
  ],
  "message": "Not ready yet"
}
```

**Readiness Criteria:**
- ≥10 completed EMRs
- ≥30 unique phrases
- ≥5 repeated phrases

---

### 4. Record Telemetry

Записать событие показа/принятия подсказки.

**Endpoint:**
```http
POST /telemetry
```

**Request:**
```json
{
  "doctorId": 123,
  "field": "complaints",
  "phraseId": "abc-123",
  "event": "shown"
}
```

**Event types:**
- `"shown"` - подсказка показана
- `"accepted"` - подсказка принята

**Response:**
```json
{
  "success": true,
  "message": "Recorded shown event"
}
```

---

### 5. Get Telemetry Stats

Получить статистику использования подсказок.

**Endpoint:**
```http
GET /telemetry-stats/{doctor_id}
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

### 6. Get Field Preferences

Получить настройки паузы для полей.

**Endpoint:**
```http
GET /preferences/{doctor_id}
```

**Response:**
```json
{
  "doctorId": 123,
  "preferences": {
    "complaints": false,
    "anamnesis": false,
    "examination": false,
    "diagnosis": true,
    "recommendations": false
  }
}
```

**Notes:**
- `true` = поле приостановлено (paused)
- `false` = подсказки активны

---

### 7. Update Field Preferences

Обновить настройки паузы.

**Endpoint:**
```http
POST /preferences
```

**Request:**
```json
{
  "doctorId": 123,
  "preferences": [
    { "field": "complaints", "paused": false },
    { "field": "diagnosis", "paused": true }
  ]
}
```

**Response:**
```json
{
  "doctorId": 123,
  "preferences": {
    "complaints": false,
    "diagnosis": true
  }
}
```

---

### 8. Batch Index All Doctors

Проиндексировать всех врачей (миграция).

**Endpoint:**
```http
POST /batch-index
```

**Auth:** ADMIN ONLY

**Request:**
```json
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

---

### 9. Index Single Doctor

Проиндексировать одного врача.

**Endpoint:**
```http
POST /index-doctor
```

**Request:**
```json
{
  "doctorId": 123,
  "specialty": "cardiology"
}
```

**Response:**
```json
{
  "totalEmrs": 15,
  "totalPhrases": 45,
  "durationMs": 850
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Field must be one of: complaints, anamnesis, examination, diagnosis, recommendations"
}
```

### 404 Not Found
```json
{
  "detail": "Doctor not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Database connection error"
}
```

---

## Rate Limits

- **Phrase suggestions**: 100 requests/minute per doctor
- **Readiness check**: Cached for 1 minute
- **Telemetry**: 1000 events/minute per doctor

---

## Data Models

### Suggestion
```typescript
{
  text: string;           // Continuation text (tail only)
  source: "history";      // Always "history"
  usageCount: number;     // Frequency
  lastUsed: string;       // ISO timestamp
  id?: string;           // Optional phrase ID
}
```

### ReadinessProgress
```typescript
{
  completed_emrs: number;
  unique_phrases: number;
  repeated_phrases: number;
}
```

### TelemetryStats
```typescript
{
  doctorId: number;
  totalShown: number;
  totalAccepted: number;
  acceptanceRate: number;  // 0-100
  avgTimeToAcceptMs: number | null;
  topAcceptedPhrases: Array<{
    phrase: string;
    field: string;
    timesAccepted: number;
  }>;
}
```

---

## Frontend Hook

### useDoctorPhrases

```typescript
const {
  // State
  suggestions,
  loading,
  error,
  
  // Readiness
  ready,
  readinessChecked,
  readinessProgress,
  readinessMessage,
  
  // Hybrid Control
  paused,
  togglePause,
  
  // Data
  topSuggestion,
  
  // Actions
  clearSuggestions,
  acceptSuggestion,
  indexPhrases,
  recordTelemetry,
  refetch,
  recheckReadiness
} = useDoctorPhrases({
  doctorId: 123,
  field: 'complaints',
  specialty: 'cardiology',
  currentText: 'Голов',
  cursorPosition: 5,
  config: {
    debounceMs: 500,
    minQueryLength: 3,
    maxSuggestions: 5
  }
});
```

---

*Version: 1.0*  
*Last Updated: 2026-01-06*
