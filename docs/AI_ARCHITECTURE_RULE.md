# 🔒 AI Architecture Rule - ОБЯЗАТЕЛЬНО для всех компонентов

## Главное правило

```
AI всегда вызывается через useEMRAI / mcpClient.
UI компоненты никогда не знают про провайдеров.
```

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    UI LAYER (UI-only)                       │
├─────────────────────────────────────────────────────────────┤
│  EMRSmartField  │  ICD10Autocomplete  │  AISuggestions      │
│       │                  │                    │             │
│  suggestions: []    suggestions: []     suggestions: []     │
│  loading: bool      loading: bool       onSelect: fn        │
│  onSearch: fn       onSearch: fn                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ props (suggestions, loading, callbacks)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    HOOK LAYER                               │
├─────────────────────────────────────────────────────────────┤
│                      useEMRAI                               │
│   - icd10Suggestions                                        │
│   - loading                                                 │
│   - getICD10Suggestions(symptoms, diagnosis, specialty)     │
│   - analyzeComplaints(...)                                  │
│   - interpretLabResults(...)                                │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ calls mcpAPI
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    API LAYER                                │
├─────────────────────────────────────────────────────────────┤
│                      mcpClient                              │
│   - suggestICD10({ symptoms, diagnosis, provider })         │
│   - analyzeComplaint({ complaint, patientAge, provider })   │
│   - interpretLabResults({ results, provider })              │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP POST /api/v1/mcp/*
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND MCP                              │
├─────────────────────────────────────────────────────────────┤
│  icd10_server  │  complaint_server  │  lab_server          │
│       │                  │                  │               │
│       └──────────────────┼──────────────────┘               │
│                          ▼                                  │
│               AI Manager (DeepSeek → Gemini → OpenAI)       │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Правильные примеры

### 1. ICD10Autocomplete (UI-only)

```jsx
// ICD10Autocomplete.jsx - UI-only component
const ICD10Autocomplete = ({
  suggestions = [],      // Получаем от родителя
  loading = false,       // Получаем от родителя  
  onSearch,              // Callback в родителя
  onChange
}) => {
  // ❌ НЕТ: const result = await api.post('/ai/icd-suggest')
  // ❌ НЕТ: const { searchICD } = useICDSuggestions()
  
  // ✅ ДА: Просто отображаем suggestions
  return (
    <Dropdown>
      {suggestions.map(s => <Item key={s.code} />)}
    </Dropdown>
  );
};
```

### 2. Parent Component (с useEMRAI)

```jsx
// EMRContainerV2.jsx
import { useEMRAI } from '../../hooks/useEMRAI';

const EMRContainerV2 = () => {
  // AI через hook
  const { icd10Suggestions, loading, getICD10Suggestions } = useEMRAI(true, 'deepseek');

  return (
    <ICD10Autocomplete
      suggestions={icd10Suggestions}
      loading={loading}
      onSearch={(query) => getICD10Suggestions(complaints, query)}
    />
  );
};
```

### 3. EMRSmartField (с внешними templates)

```jsx
// EMRSmartField - получает suggestions от родителя
<EMRSmartField
  onRequestAI={mockEMRTemplates}  // Callback, не прямой API
  // Внутри EMRSmartField вызывает onRequestAI, не api напрямую
/>
```

---

## ❌ ЗАПРЕЩЕНО

```jsx
// В UI компоненте
import { api } from '../../api/client';
import { mcpAPI } from '../../api/mcpClient';

// Прямой вызов API внутри UI компонента
const result = await api.post('/ai/icd-suggest', data);
const mcpResult = await mcpAPI.suggestICD10(data);
```

---

## 📁 Файлы

| Файл | Тип | Назначение |
|------|-----|------------|
| `useEMRAI.js` | Hook | Единственная точка вызова AI |
| `mcpClient.js` | API Client | HTTP вызовы к MCP backend |
| `ICD10Autocomplete.jsx` | UI-only | Отображение, клавиатура |
| `AISuggestions.jsx` | UI-only | Отображение подсказок |
| `EMRSmartFieldV2.jsx` | UI-only | Ghost text, modes |

---

## Преимущества

1. **Единая точка входа** — все AI через useEMRAI
2. **Легко тестировать** — mock useEMRAI в тестах
3. **Провайдеры скрыты** — UI не знает про DeepSeek/Gemini
4. **Fallback автоматический** — в useEMRAI
5. **Кеширование** — в hook, не в каждом компоненте

---

## Чеклист ревью

При code review проверяй:

- [ ] UI компонент НЕ импортирует `mcpClient` или `api`
- [ ] AI вызывается через `useEMRAI` в родительском компоненте
- [ ] Suggestions передаются через props
- [ ] Loading state передаётся через props
- [ ] onSearch callback вызывает функцию из useEMRAI

---

**Версия:** 1.0  
**Дата:** 2026-01-05  
