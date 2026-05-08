# 🚀 AI/MCP Quick Start Guide

## ⚡ Быстрый старт (5 минут)

### 1. Запуск системы

```bash
# Backend
cd C:\final\backend
python run_server.py

# Frontend (в новом терминале)
cd C:\final
npm run dev
```

### 2. Проверка MCP

```bash
# Открыть в браузере
http://localhost:18000/docs

# Или curl
curl http://localhost:18000/api/v1/mcp/health
```

✅ Должно вернуть: `{"status": "healthy", "servers": [...]}`

### 3. Тестирование в UI

1. **Открыть:** http://localhost:5173
2. **Логин:** используйте локально созданного врача и пароль
3. **Создать запись** → **Оплатить** → **Открыть EMR**
4. **Ввести жалобу:** "Головная боль в течение 2 дней"
5. **Нажать AI кнопку** → Должен показаться анализ ✅
6. **Ввести диагноз:** "мигрень" → Автоподсказки МКБ-10 ✅

---

## 🎯 Основные фичи

### В EMR System:

| Поле | AI кнопка | Функция |
|------|-----------|---------|
| **Жалобы** | ✅ | Анализ жалоб с планом обследования |
| **Анамнез** | ✅ | Помощь в составлении анамнеза |
| **Осмотр** | ✅ | Рекомендации по плану осмотра |
| **Диагноз** | ✅ | Автоподсказки МКБ-10 (debounce 800ms) |
| **Рекомендации** | ✅ | Генерация рекомендаций по лечению |
| **Изображения** | ✅ | Анализ медицинских снимков |

### AI Провайдеры:

- 🟢 **DeepSeek** (по умолчанию) - не блокирует медицинский контент
- 🔵 **Gemini** (fallback)
- 🟡 **OpenAI** (опционально)

---

## 📊 Что изменилось?

### ДО (v1.0):
- ❌ Прямой API без MCP
- ❌ Только Gemini (блокировки)
- ❌ Простые списки кодов МКБ-10
- ❌ AI только для жалоб и диагноза

### ПОСЛЕ (v2.0):
- ✅ Model Context Protocol (MCP)
- ✅ DeepSeek как основной (без блокировок)
- ✅ Клинические рекомендации МКБ-10
- ✅ AI во всех полях EMR
- ✅ Анализ изображений
- ✅ Автоподсказки с debounce
- ✅ Fallback механизм
- ✅ Provider selector

---

## 🛠️ Troubleshooting

### ❌ "Request timeout"

**Решение:**
```python
# backend/app/core/mcp_config.py
MCP_REQUEST_TIMEOUT: int = 120  # Уже исправлено
```

### ❌ "Mock provider fallback"

**Проверить:**
```bash
# backend/.env
DEEPSEEK_API_KEY=sk-...  # Должен быть установлен
```

### ❌ Подсказки МКБ-10 не появляются

**Проверить:**
1. `useMCP=true` в `useEMRAI`
2. Есть текст в диагнозе
3. `canSaveEMR=true` (статус визита = "IN_VISIT")

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| `docs/AI_MCP_FRONTEND_INTEGRATION_GUIDE.md` | Полное руководство (50+ страниц) |
| `docs/AI_MCP_QA_CHECKLIST.md` | QA чеклист (200+ пунктов) |
| `docs/AI_MCP_IMPLEMENTATION_SUMMARY.md` | Итоговое резюме |
| `frontend/src/api/__tests__/mcpClient.test.js` | Unit тесты MCP |
| `frontend/src/components/ai/__tests__/AIAssistant.test.jsx` | Unit тесты UI |

---

## 🧪 Быстрый тест

```javascript
// В консоли браузера
import { mcpAPI } from './api/mcpClient';

// Проверка здоровья
await mcpAPI.getStatus()

// Тест анализа жалоб
await mcpAPI.analyzeComplaint({
  complaint: 'Головная боль',
  patientAge: 30,
  patientGender: 'female',
  provider: 'deepseek'
})

// Тест МКБ-10
await mcpAPI.suggestICD10({
  symptoms: ['головная боль'],
  diagnosis: 'мигрень',
  provider: 'deepseek'
})
```

---

## 💡 Best Practices

### ✅ DO:
```javascript
// Используйте MCP
const ai = useEMRAI(true, 'deepseek');

// Обрабатывайте ошибки
try {
  const result = await analyzeComplaints(data);
} catch (err) {
  showError(err.message);
}

// Используйте debounce
const debounced = useDebounce(callback, 800);
```

### ❌ DON'T:
```javascript
// Не используйте старый API
const ai = useEMRAI(false);  // ❌

// Не игнорируйте ошибки
await analyzeComplaints(data);  // ❌ Нет error handling

// Не запрашивайте на каждую букву
onChange={async (e) => await suggest(e.target.value)}  // ❌
```

---

## 🎓 Примеры кода

### Использование в компоненте:

```jsx
import { useEMRAI } from '../../hooks/useEMRAI';
import { AIButton } from '../ai';

function MyComponent() {
  const {
    loading,
    icd10Suggestions,
    clinicalRecommendations,
    getICD10Suggestions
  } = useEMRAI(true, 'deepseek');

  return (
    <div>
      <input 
        onChange={(e) => debouncedSuggest(e.target.value)}
        placeholder="Диагноз (автоподсказки)"
      />
      
      {(icd10Suggestions.length > 0 || clinicalRecommendations) && (
        <AISuggestions
          suggestions={icd10Suggestions}
          clinicalRecommendations={clinicalRecommendations}
          onSelect={handleSelect}
        />
      )}
    </div>
  );
}
```

---

## 🚀 Готово к использованию!

**Все функции интегрированы и работают.**

- ✅ 14/14 TODO задач выполнено
- ✅ Тесты написаны
- ✅ Документация создана
- ✅ QA чеклист подготовлен

### Следующие шаги:

1. Запустите систему (см. выше)
2. Протестируйте основные функции
3. Используйте QA чеклист для полного тестирования
4. Читайте полную документацию при необходимости

---

**Вопросы?** Смотрите полную документацию в `docs/`

🎉 **Happy coding!**

