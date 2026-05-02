# Doctor History-Based Autocomplete

Интеллектуальная система автодополнения для EMR на основе реальной истории врача.

## 🎯 Основные принципы

✅ **Search & Rank, Not Generate** — мы НЕ генерируем текст, мы ищем в истории  
✅ **Privacy First** — каждый врач видит только свою историю  
✅ **Automatic Activation** — включается автоматически при накоплении данных  
✅ **Zero Configuration** — работает "из коробки", без настроек  
✅ **Non-Intrusive UX** — не мешает обычному вводу текста  

---

## 📚 Документация

- **[UX Guide](./EMR_SMART_AUTOCOMPLETE_UX.md)** — полное описание UX и режимов работы
- **[Deployment Guide](./DOCTOR_AUTOCOMPLETE_DEPLOYMENT.md)** — инструкция по деплою
- **[API Reference](./DOCTOR_AUTOCOMPLETE_API.md)** — справка по API endpoints

---

## 🚀 Quick Start

### 1. Применить миграцию

```bash
cd c:\final\backend
alembic upgrade head
```

### 2. Индексировать существующие EMR

```bash
python migrate_phrases.py
```

### 3. Проверить готовность врача

```bash
curl http://localhost:18000/api/v1/emr/readiness/123
```

### 4. Всё! 🎉

Врачи, у которых есть достаточно данных, сразу увидят подсказки при вводе текста.

---

## 🔧 Архитектура

### Backend

```
app/
├── models/
│   └── doctor_phrase_history.py      # DB model
├── services/
│   ├── doctor_phrase_service.py       # Prefix search & ranking
│   ├── emr_phrase_indexer.py          # Batch/incremental indexing
│   └── doctor_autocomplete_readiness.py # Readiness evaluation
└── api/v1/endpoints/
    └── phrase_suggest.py              # REST API
```

### Frontend

```
src/
├── components/emr-v2/sections/
│   ├── EMRSmartFieldV2.jsx            # Smart field with doctor history
│   └── EMRSmartFieldV2.css
└── hooks/
    └── useDoctorPhrases.js            # Hook with readiness check
```

### Database

```sql
doctor_phrase_history (
  id, doctor_id, field, phrase,
  prefix_3, prefix_5,
  usage_count, last_used, first_used,
  specialty,
  suggestions_shown, suggestions_accepted
)
```

---

## 🎨 UX Flow

```
Врач вводит: "Голов"
       ↓
Система проверяет readiness
       ↓
  ready=true?
       ↓
Ищет в истории врача по prefix
       ↓
Показывает ghost text: "ная боль, давящего характера..."
       ↓
Врач нажимает [Tab]
       ↓
Текст вставлен! 🎉
+ Telemetry записана
```

---

## 📊 Readiness Criteria

Автодополнение активируется когда:

| Критерий | Минимум |
|----------|---------|
| Завершённых EMR | ≥10 |
| Уникальных фраз | ≥30 |
| Повторяющихся фраз | ≥5 |

**Проверка:**
```http
GET /api/v1/emr/readiness/{doctor_id}
```

---

## 🔐 Security

- ✅ **Data Isolation**: `WHERE doctor_id = :current_user_id`
- ✅ **No AI Generation**: Pure search, no LLMs
- ✅ **Local Storage**: Phrases stored in app database
- ✅ **Admin-Only Batch**: `/batch-index` requires admin role
- ✅ **Telemetry Privacy**: Only IDs, no medical content

---

## 📈 Telemetry

Система собирает анонимную статистику:

```json
{
  "totalShown": 150,
  "totalAccepted": 120,
  "acceptanceRate": 80.0,
  "topAcceptedPhrases": [...]
}
```

**Dashboard:**
```http
GET /api/v1/emr/telemetry-stats/{doctor_id}
```

---

## 🎛️ Configuration

### Backend

```python
# app/services/emr_phrase_indexer.py
INDEXABLE_FIELDS = [
    'complaints',
    'anamnesis',
    'examination',
    'diagnosis',
    'recommendations'
]
```

### Frontend

```jsx
<EMRSmartField
  useDoctorHistory={true}
  doctorId={currentUser.id}
  specialty="cardiology"
  debounceMs={500}
/>
```

---

## 🧪 Testing

### Unit Tests

```bash
# Backend
pytest app/tests/test_doctor_phrase_service.py
pytest app/tests/test_emr_phrase_indexer.py
pytest app/tests/test_autocomplete_readiness.py

# Frontend
npm test -- useDoctorPhrases.test.js
```

### Integration Tests

```bash
# Test full flow
curl -X POST http://localhost:18000/api/v1/emr/phrase-suggest \
  -d '{"field":"complaints","currentText":"Голов","doctorId":123}'
```

---

## 🐛 Troubleshooting

### Подсказки не появляются

1. Проверить readiness:
   ```bash
   curl http://localhost:18000/api/v1/emr/readiness/123
   ```

2. Проверить количество фраз:
   ```sql
   SELECT COUNT(*) FROM doctor_phrase_history WHERE doctor_id = 123;
   ```

3. Проверить кэш (TTL 1 минута):
   ```javascript
   recheckReadiness(); // в DevTools Console
   ```

### База не индексируется

1. Проверить, что EMR не в черновике (`is_draft = False`)
2. Проверить логи при сохранении EMR
3. Запустить индексацию вручную:
   ```bash
   python migrate_phrases.py
   ```

---

## 📦 Dependencies

### Backend
- SQLAlchemy 2.0+
- FastAPI
- Pydantic

### Frontend
- React 18+
- Custom hooks (useDoctorPhrases)

---

## 🗺️ Roadmap

- [x] Phase 1: Readiness System
- [x] Phase 2: Frontend Integration
- [x] Phase 3: Batch/Incremental Indexing
- [x] Phase 4: Telemetry & Dashboard
- [x] Phase 5: Hybrid Control (per-field pause)
- [ ] Phase 6: Multi-language support
- [ ] Phase 7: Celery background tasks
- [ ] Phase 8: ML-based ranking

---

## 📝 Changelog

### v4.0 (2026-01-06)
- ✨ Doctor History-Based Autocomplete
- ✨ Automatic Readiness System
- ✨ Batch/Incremental Indexing
- ✨ Telemetry Dashboard
- ✨ Hybrid Control (per-field pause)

### v3.0 (2026-01-05)
- Mode switcher in UI
- Inline corrections
- General telemetry

---

## 🤝 Contributing

При доработке системы соблюдайте принципы:

1. **No Text Generation** — только поиск в истории
2. **Privacy First** — изоляция данных врачей
3. **Performance** — prefix indexes, caching
4. **UX** — не мешать обычному вводу

---

## 📄 License

Internal use only. Confidential medical data.

---

*Maintained by: Development Team*  
*Last Updated: 2026-01-06*
