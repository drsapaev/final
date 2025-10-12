# 🤖 AI/MCP Frontend Integration Guide

## 📋 Содержание

1. [Обзор](#обзор)
2. [Архитектура](#архитектура)
3. [Компоненты](#компоненты)
4. [Использование](#использование)
5. [API Reference](#api-reference)
6. [Тестирование](#тестирование)
7. [Best Practices](#best-practices)

---

## 🎯 Обзор

Система AI/MCP интеграции предоставляет фронтенд-компоненты и хуки для взаимодействия с медицинским AI через Model Context Protocol (MCP).

### Основные возможности:

✅ **Анализ жалоб** - AI анализирует жалобы пациента и формирует план обследования  
✅ **Подсказки МКБ-10** - Автоматические и ручные подсказки кодов МКБ-10 с клиническими рекомендациями  
✅ **Интерпретация анализов** - AI интерпретирует лабораторные результаты  
✅ **Анализ изображений** - Анализ кожных образований и медицинских снимков  
✅ **Выбор AI провайдера** - DeepSeek, Gemini, OpenAI  
✅ **Fallback механизм** - Автоматическое переключение при сбоях

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend Layer                        │
├─────────────────────────────────────────────────────────┤
│  EMR System │ Lab Panel │ Cardio Panel │ Derma Panel    │
│      │            │            │              │          │
│      └────────────┴────────────┴──────────────┘          │
│                         │                                │
│              ┌──────────▼──────────┐                     │
│              │   useEMRAI Hook     │                     │
│              └──────────┬──────────┘                     │
│                         │                                │
│         ┌───────────────┼───────────────┐                │
│         │               │               │                │
│   ┌─────▼─────┐  ┌─────▼──────┐  ┌────▼──────┐         │
│   │AIAssistant│  │AISuggestions│  │AIClinical │         │
│   │           │  │             │  │   Text    │         │
│   └─────┬─────┘  └─────┬──────┘  └────┬──────┘         │
│         │              │              │                  │
│         └──────────────┼──────────────┘                  │
│                        │                                 │
│              ┌─────────▼─────────┐                       │
│              │   MCP API Client  │                       │
│              └─────────┬─────────┘                       │
└────────────────────────┼─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                    Backend MCP Layer                      │
├───────────────────────────────────────────────────────────┤
│  Complaint Server │ ICD10 Server │ Lab Server │ Imaging  │
│         │                │              │           │     │
│         └────────────────┴──────────────┴───────────┘     │
│                         │                                 │
│              ┌──────────▼──────────┐                      │
│              │    AI Manager       │                      │
│              └──────────┬──────────┘                      │
│                         │                                 │
│         ┌───────────────┼───────────────┐                 │
│   ┌─────▼─────┐  ┌─────▼──────┐  ┌────▼──────┐          │
│   │ DeepSeek  │  │   Gemini   │  │  OpenAI   │          │
│   │ Provider  │  │  Provider  │  │  Provider │          │
│   └───────────┘  └────────────┘  └───────────┘          │
└───────────────────────────────────────────────────────────┘
```

---

## 🧩 Компоненты

### 1. **MCP API Client** (`frontend/src/api/mcpClient.js`)

Основной клиент для взаимодействия с MCP серверами.

```javascript
import { mcpAPI } from '../api/mcpClient';

// Анализ жалоб
const result = await mcpAPI.analyzeComplaint({
  complaint: 'Головная боль в течение 2 дней',
  patientAge: 35,
  patientGender: 'female',
  provider: 'deepseek'
});

// Подсказки МКБ-10
const icd10 = await mcpAPI.suggestICD10({
  symptoms: ['головная боль', 'тошнота'],
  diagnosis: 'мигрень',
  provider: 'deepseek',
  maxSuggestions: 5
});

// Интерпретация анализов
const labResult = await mcpAPI.interpretLabResults({
  results: [
    { parameter: 'Гемоглобин', value: 120, unit: 'г/л' }
  ],
  patientAge: 30,
  patientGender: 'female',
  provider: 'deepseek'
});
```

### 2. **useEMRAI Hook** (`frontend/src/hooks/useEMRAI.js`)

React хук для AI функций в EMR.

```javascript
import { useEMRAI } from '../hooks/useEMRAI';

function MyComponent() {
  const {
    loading,
    error,
    icd10Suggestions,
    clinicalRecommendations,
    getICD10Suggestions,
    analyzeComplaints,
    interpretLabResults,
    analyzeSkinLesion,
    analyzeImage
  } = useEMRAI(true, 'deepseek'); // useMCP=true, provider='deepseek'

  // Использование
  const handleAnalyze = async () => {
    const result = await analyzeComplaints({
      complaint: 'Головная боль',
      patient_age: 30,
      patient_gender: 'female'
    });
  };
}
```

**Параметры:**
- `useMCP` (boolean, default: `true`) - Использовать MCP или прямой API
- `provider` (string, default: `'deepseek'`) - AI провайдер

**Возвращаемые значения:**
- `loading` - Идет ли загрузка
- `error` - Текст ошибки
- `icd10Suggestions` - Массив подсказок МКБ-10
- `clinicalRecommendations` - Клинические рекомендации (новый формат)

### 3. **AIAssistant Component** (`frontend/src/components/ai/AIAssistant.jsx`)

Универсальный компонент AI ассистента.

```jsx
<AIAssistant
  analysisType="complaint" // complaint | icd10 | lab | skin | imaging
  data={{
    complaint: 'Головная боль',
    patient_age: 30,
    patient_gender: 'female'
  }}
  onResult={(result) => console.log(result)}
  title="AI Анализ жалоб"
  useMCP={true}
  providerOptions={['deepseek', 'gemini', 'openai']}
/>
```

**Props:**
- `analysisType` - Тип анализа
- `data` - Данные для анализа
- `onResult` - Callback с результатом
- `title` - Заголовок
- `useMCP` - Использовать MCP
- `providerOptions` - Доступные провайдеры

**Фичи:**
- ✅ Выбор AI провайдера
- ✅ Retry механизм
- ✅ Отображение прогресса
- ✅ Копирование результатов
- ✅ Поддержка всех типов анализов

### 4. **AISuggestions Component** (`frontend/src/components/ai/AISuggestions.jsx`)

Компонент для отображения AI подсказок.

```jsx
<AISuggestions
  suggestions={icd10Suggestions}
  clinicalRecommendations={clinicalRecommendations}
  type="icd10"
  onSelect={(item) => handleSelect(item)}
  title="AI подсказки МКБ-10"
  fallbackProvider="deepseek"
/>
```

**Props:**
- `suggestions` - Массив подсказок
- `clinicalRecommendations` - Клинические рекомендации (новый формат)
- `type` - Тип подсказок (icd10 | generic)
- `onSelect` - Callback при выборе
- `fallbackProvider` - Провайдер fallback

### 5. **AIClinicalText Component** (`frontend/src/components/ai/AIClinicalText.jsx`)

Компонент для красивого отображения клинических рекомендаций.

```jsx
<AIClinicalText
  content={clinicalRecommendations}
  variant="info" // info | success | warning | error
/>
```

Автоматически парсит форматированный текст и отображает:
- Заголовки (###)
- Диагнозы (>)
- Списки (- или 1.)
- Эмодзи заголовки
- Выделенный текст (**)

---

## 💡 Использование

### В EMR System

```jsx
import { useEMRAI } from '../../hooks/useEMRAI';
import { AIButton, AISuggestions } from '../ai';

function EMRSystem({ appointment }) {
  const {
    loading,
    icd10Suggestions,
    clinicalRecommendations,
    getICD10Suggestions,
    analyzeComplaints
  } = useEMRAI(true, 'deepseek');

  // Автоподсказки МКБ-10 с debounce
  const debouncedICD10 = useDebounce(
    useCallback(async (complaints, diagnosis) => {
      await getICD10Suggestions(complaints, diagnosis, specialty);
    }, [getICD10Suggestions]),
    800
  );

  return (
    <div>
      {/* AI кнопка в жалобах */}
      <AIButton
        onClick={() => handleAnalyzeComplaints()}
        loading={loading}
        tooltip="AI анализ жалоб"
      />

      {/* Автоподсказки МКБ-10 */}
      {(icd10Suggestions.length > 0 || clinicalRecommendations) && (
        <AISuggestions
          suggestions={icd10Suggestions}
          clinicalRecommendations={clinicalRecommendations}
          type="icd10"
          onSelect={(item) => {
            setDiagnosis(item.name);
            setICD10Code(item.code);
          }}
        />
      )}
    </div>
  );
}
```

### В Lab Results Manager

```jsx
const {
  interpretLabResults
} = useEMRAI(true, 'deepseek');

const handleInterpret = async () => {
  const result = await interpretLabResults(
    labResults,
    patient.age,
    patient.gender
  );

  if (result) {
    setInterpretation(result.summary);
    setRecommendations(result.recommendations);
  }
};
```

### Анализ изображений

```jsx
const {
  analyzeSkinLesion,
  analyzeImage
} = useEMRAI(true, 'deepseek');

// Анализ кожного образования
const handleSkinAnalysis = async (imageFile) => {
  const result = await analyzeSkinLesion(
    imageFile,
    { location: 'рука', size: '2см' },
    { complaints: 'зуд, покраснение' }
  );
};

// Общий анализ изображения
const handleImageAnalysis = async (imageFile) => {
  const result = await analyzeImage(
    imageFile,
    'xray',
    { clinicalContext: 'боль в грудной клетке' }
  );
};
```

---

## 📚 API Reference

### mcpAPI Methods

| Метод | Описание | Параметры | Возвращает |
|-------|----------|-----------|------------|
| `analyzeComplaint()` | Анализ жалоб | complaint, patientAge, patientGender, provider | Promise<MCPResult> |
| `suggestICD10()` | Подсказки МКБ-10 | symptoms, diagnosis, specialty, provider | Promise<MCPResult> |
| `interpretLabResults()` | Интерпретация анализов | results, patientAge, patientGender, provider | Promise<MCPResult> |
| `analyzeSkinLesion()` | Анализ кожных образований | image, lesionInfo, patientHistory, provider | Promise<MCPResult> |
| `analyzeImage()` | Анализ изображения | image, imageType, options | Promise<MCPResult> |
| `getStatus()` | Статус MCP | - | Promise<StatusResult> |
| `getMetrics()` | Метрики MCP | server | Promise<MetricsResult> |

### MCPResult Format

```typescript
interface MCPResult {
  status: 'success' | 'error';
  data?: any;
  error?: string;
  metadata?: {
    provider_used: string;
    timestamp: string;
    [key: string]: any;
  };
}
```

---

## 🧪 Тестирование

### Запуск тестов

```bash
cd frontend
npm test -- --testPathPattern=ai
```

### Примеры тестов

```javascript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AIAssistant from '../AIAssistant';
import { mcpAPI } from '../../../api/mcpClient';

jest.mock('../../../api/mcpClient');

test('should analyze complaint via MCP', async () => {
  mcpAPI.analyzeComplaint.mockResolvedValue({
    status: 'success',
    data: { preliminary_diagnosis: ['Мигрень'] }
  });

  render(<AIAssistant analysisType="complaint" data={{...}} />);

  fireEvent.click(screen.getByRole('button', { name: /анализ/i }));

  await waitFor(() => {
    expect(screen.getByText('Мигрень')).toBeInTheDocument();
  });
});
```

---

## ✨ Best Practices

### 1. **Используйте MCP по умолчанию**

```javascript
// ✅ Хорошо
const ai = useEMRAI(true, 'deepseek');

// ❌ Плохо (старый API)
const ai = useEMRAI(false);
```

### 2. **Всегда обрабатывайте ошибки**

```javascript
const handleAnalyze = async () => {
  try {
    const result = await analyzeComplaints(data);
    if (result && !result.error) {
      // Обработка успешного результата
    } else {
      // Обработка ошибки из AI
      showError(result.error || 'AI analysis failed');
    }
  } catch (err) {
    // Обработка сетевых ошибок
    showError('Network error');
  }
};
```

### 3. **Используйте debounce для автоподсказок**

```javascript
const debouncedSuggest = useDebounce(
  useCallback(async (text) => {
    await getICD10Suggestions(text);
  }, [getICD10Suggestions]),
  800 // 800ms задержка
);

onChange={(e) => debouncedSuggest(e.target.value)}
```

### 4. **Показывайте статус провайдера**

```javascript
{fallbackProvider && (
  <Alert severity="warning">
    Используется резервный провайдер: {fallbackProvider}
  </Alert>
)}
```

### 5. **Добавляйте AI кнопки рядом с полями**

```jsx
<div className="flex justify-between">
  <label>Диагноз</label>
  <AIButton
    onClick={handleAI}
    loading={loading}
    tooltip="AI подсказки"
    disabled={!hasData}
  />
</div>
```

### 6. **Используйте специализированные компоненты**

```jsx
// ✅ Для клинических рекомендаций
<AIClinicalText content={recommendations} variant="info" />

// ✅ Для списка подсказок
<AISuggestions 
  suggestions={items} 
  clinicalRecommendations={recommendations}
  onSelect={handleSelect} 
/>

// ❌ Не используйте просто JSON
<pre>{JSON.stringify(result, null, 2)}</pre>
```

---

## 🔧 Конфигурация

### Выбор провайдера по умолчанию

В `useEMRAI`:
```javascript
const ai = useEMRAI(true, 'deepseek'); // DeepSeek по умолчанию
```

В `AIAssistant`:
```jsx
<AIAssistant
  providerOptions={['deepseek', 'gemini', 'openai']}
  // Первый в списке - по умолчанию
/>
```

### Timeout настройки

В `backend/app/core/mcp_config.py`:
```python
MCP_REQUEST_TIMEOUT: int = 120  # секунды
```

---

## 📊 Мониторинг

### Получение метрик MCP

```javascript
const metrics = await mcpAPI.getMetrics('complaint');

console.log(metrics);
// {
//   total_requests: 1523,
//   successful_requests: 1498,
//   failed_requests: 25,
//   average_response_time: 2.3
// }
```

### Проверка здоровья системы

```javascript
const health = await mcpAPI.healthCheck();

console.log(health);
// {
//   status: 'healthy',
//   servers: {
//     complaint: 'healthy',
//     icd10: 'healthy',
//     lab: 'healthy',
//     imaging: 'healthy'
//   }
// }
```

---

## 🐛 Troubleshooting

### Проблема: "Request timeout"

**Решение:**
1. Увеличьте timeout в `mcp_config.py`
2. Смените AI провайдер
3. Проверьте интернет-соединение

### Проблема: "Mock provider fallback"

**Решение:**
1. Проверьте API ключи в `.env`
2. Перезапустите backend
3. Убедитесь что баланс AI провайдера > 0

### Проблема: Подсказки МКБ-10 не появляются

**Решение:**
1. Проверьте что `useMCP=true`
2. Убедитесь что `canSaveEMR=true`
3. Проверьте что есть текст в диагнозе/жалобах

---

## 📝 Changelog

### v2.0.0 (Current)
- ✅ Полная интеграция MCP API
- ✅ DeepSeek как основной провайдер
- ✅ Поддержка клинических рекомендаций
- ✅ Автоподсказки МКБ-10 с debounce
- ✅ AI кнопки во всех полях EMR
- ✅ Анализ медицинских изображений
- ✅ Fallback механизм
- ✅ Unit тесты

### v1.0.0
- Базовая AI интеграция через прямой API
- Gemini провайдер
- Простые подсказки МКБ-10

---

## 🤝 Contributing

При добавлении новых AI функций:

1. Добавьте метод в `mcpClient.js`
2. Добавьте функцию в `useEMRAI.js`
3. Создайте UI компонент если нужно
4. Напишите unit тесты
5. Обновите документацию

---

## 📞 Support

При возникновении проблем:

1. Проверьте backend логи: `docker logs medical-backend`
2. Проверьте MCP метрики: `mcpAPI.getMetrics()`
3. Запустите тесты: `npm test`
4. Смотрите `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md`

---

**Версия:** 2.0.0  
**Дата обновления:** 2025-10-12  
**Автор:** Medical AI Team

