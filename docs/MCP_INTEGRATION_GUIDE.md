# 🚀 MCP (Model Context Protocol) - Руководство по интеграции

## 📖 Оглавление
1. [Что такое MCP](#что-такое-mcp)
2. [Архитектура решения](#архитектура-решения)
3. [Установка и настройка](#установка-и-настройка)
4. [Использование](#использование)
5. [API Reference](#api-reference)
6. [Мониторинг](#мониторинг)
7. [Тестирование](#тестирование)
8. [Troubleshooting](#troubleshooting)

---

## 🤖 Что такое MCP

**MCP (Model Context Protocol)** - это открытый протокол для стандартизации интеграции между AI-моделями и внешними инструментами. В нашем проекте MCP обеспечивает:

- ✅ **Унифицированный интерфейс** для всех AI-провайдеров (OpenAI, Gemini, DeepSeek)
- ✅ **Стандартизированную обработку** медицинских данных
- ✅ **Централизованный мониторинг** и метрики
- ✅ **Fallback механизмы** для надежности
- ✅ **Пакетную обработку** запросов

## 🏗️ Архитектура решения

### Компоненты системы

```
┌─────────────────────────────────────────────────────┐
│                   Frontend                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐│
│  │ AIAssistant │  │  MCPMonitor  │  │ mcpClient  ││
│  └─────────────┘  └──────────────┘  └────────────┘│
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                   API Layer                         │
│  ┌──────────────────────────────────────────────┐  │
│  │         /api/v1/mcp/* endpoints              │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                  MCP Manager                        │
│  ┌──────────────────────────────────────────────┐  │
│  │   Routing, Metrics, Health Checks            │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                  MCP Servers                        │
│  ┌──────────┐  ┌────────┐  ┌─────┐  ┌─────────┐  │
│  │Complaint │  │ ICD-10 │  │ Lab │  │ Imaging │  │
│  └──────────┘  └────────┘  └─────┘  └─────────┘  │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                 AI Providers                        │
│  ┌─────────┐  ┌────────┐  ┌──────────┐           │
│  │ OpenAI  │  │ Gemini │  │ DeepSeek │           │
│  └─────────┘  └────────┘  └──────────┘           │
└─────────────────────────────────────────────────────┘
```

### MCP Серверы

1. **ComplaintServer** - Анализ жалоб пациентов
2. **ICD10Server** - Работа с кодами МКБ-10
3. **LabServer** - Интерпретация лабораторных анализов
4. **ImagingServer** - Анализ медицинских изображений

## 🛠️ Установка и настройка

### 1. Установка зависимостей

```bash
cd backend
pip install mcp httpx pydantic-settings
```

### 2. Конфигурация (.env файл)

```env
# MCP Settings
MCP_ENABLED=true
MCP_LOG_REQUESTS=true
MCP_FALLBACK_TO_DIRECT=true
MCP_REQUEST_TIMEOUT=30
MCP_HEALTH_CHECK_INTERVAL=60
MCP_MAX_BATCH_SIZE=10

# AI Providers (необходимо для работы MCP)
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key
DEEPSEEK_API_KEY=your-deepseek-key
```

### 3. Запуск системы

```bash
# Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm start
```

## 💻 Использование

### Backend - Python

```python
from app.services.mcp import get_mcp_manager

# Инициализация
mcp_manager = await get_mcp_manager()

# Анализ жалоб
result = await mcp_manager.execute_request(
    server="complaint",
    method="tool/analyze_complaint",
    params={
        "complaint": "Головная боль и тошнота",
        "patient_info": {"age": 35, "gender": "female"},
        "urgency_assessment": True
    }
)

# Подсказки МКБ-10
result = await mcp_manager.execute_request(
    server="icd10",
    method="tool/suggest_icd10",
    params={
        "symptoms": ["головная боль", "тошнота"],
        "diagnosis": "Мигрень"
    }
)
```

### Frontend - JavaScript/React

```javascript
import { mcpAPI } from './api/mcpClient';

// Анализ жалоб
const analyzeComplaint = async () => {
  const result = await mcpAPI.analyzeComplaint({
    complaint: "Головная боль и тошнота",
    patientAge: 35,
    patientGender: "female"
  });
  
  if (result.status === 'success') {
    console.log('Анализ:', result.data);
  }
};

// Проверка критических значений анализов
const checkLabValues = async () => {
  const results = [
    {test_name: "glucose", value: 8.5, unit: "ммоль/л"},
    {test_name: "hemoglobin", value: 95, unit: "г/л"}
  ];
  
  const critical = await mcpAPI.checkCriticalValues(results);
  if (critical.has_critical) {
    alert('Обнаружены критические значения!');
  }
};
```

### Использование в React компонентах

```jsx
import { AIAssistant } from './components/ai/AIAssistant';

function DoctorPanel() {
  return (
    <AIAssistant
      analysisType="complaint"
      data={{
        complaint: patientComplaint,
        patient_age: patientAge,
        patient_gender: patientGender
      }}
      useMCP={true}  // Включаем MCP
      onResult={(result) => {
        // Обработка результата
        console.log('Результат анализа:', result);
      }}
    />
  );
}
```

## 📚 API Reference

### MCP Endpoints

#### Управление
- `GET /api/v1/mcp/status` - Статус системы
- `GET /api/v1/mcp/health` - Проверка здоровья
- `GET /api/v1/mcp/metrics` - Метрики
- `GET /api/v1/mcp/capabilities` - Возможности серверов

#### Анализ жалоб
- `POST /api/v1/mcp/complaint/analyze` - Анализ жалоб
- `POST /api/v1/mcp/complaint/validate` - Валидация жалоб
- `GET /api/v1/mcp/complaint/templates` - Шаблоны жалоб

#### МКБ-10
- `POST /api/v1/mcp/icd10/suggest` - Подсказки кодов
- `POST /api/v1/mcp/icd10/validate` - Валидация кода
- `GET /api/v1/mcp/icd10/search` - Поиск кодов

#### Лабораторные анализы
- `POST /api/v1/mcp/lab/interpret` - Интерпретация результатов
- `POST /api/v1/mcp/lab/check-critical` - Проверка критических значений
- `GET /api/v1/mcp/lab/normal-ranges` - Нормальные диапазоны

#### Медицинские изображения
- `POST /api/v1/mcp/imaging/analyze` - Анализ изображения
- `POST /api/v1/mcp/imaging/skin-lesion` - Анализ кожных образований
- `GET /api/v1/mcp/imaging/types` - Типы изображений

#### Пакетная обработка
- `POST /api/v1/mcp/batch` - Пакетная обработка запросов

### Примеры запросов

#### Анализ жалоб с оценкой срочности

```bash
curl -X POST http://localhost:18000/api/v1/mcp/complaint/analyze \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "complaint": "Острая боль в груди, одышка",
    "patient_age": 55,
    "patient_gender": "male",
    "urgency_assessment": true
  }'
```

#### Пакетная обработка

```bash
curl -X POST http://localhost:18000/api/v1/mcp/batch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {
        "server": "complaint",
        "method": "tool/validate_complaint",
        "params": {"complaint": "Головная боль"}
      },
      {
        "server": "icd10",
        "method": "tool/suggest_icd10",
        "params": {"symptoms": ["головная боль"], "max_suggestions": 3}
      }
    ],
    "parallel": true
  }'
```

## 📊 Мониторинг

### MCPMonitor компонент

Встроенный компонент мониторинга показывает:
- ✅ Статус всех MCP серверов
- 📈 Метрики запросов (успешные/ошибки)
- ⏱️ Среднее время ответа
- 🔧 Конфигурацию системы

### Использование MCPMonitor

```jsx
import MCPMonitor from './components/ai/MCPMonitor';

function AdminPanel() {
  return (
    <div>
      <h1>MCP Мониторинг</h1>
      <MCPMonitor />
    </div>
  );
}
```

### Метрики

```python
# Получение метрик
mcp_manager = await get_mcp_manager()
metrics = mcp_manager.get_metrics()

print(f"Всего запросов: {metrics['requests_total']}")
print(f"Успешных: {metrics['requests_success']}")
print(f"Ошибок: {metrics['requests_failed']}")

# Метрики по серверам
for server, stats in metrics['server_stats'].items():
    print(f"{server}: {stats['requests']} запросов, {stats['errors']} ошибок")
```

## 🧪 Тестирование

### Запуск тестов

```bash
python test_mcp_integration.py
```

### Тестовые сценарии

1. **Проверка здоровья системы**
2. **Анализ жалоб**
3. **Подсказки МКБ-10**
4. **Интерпретация лабораторных анализов**
5. **Метрики системы**
6. **Пакетная обработка**

### Пример теста

```python
async def test_complaint_analysis():
    client = await get_mcp_client()
    
    result = await client.analyze_complaint(
        complaint="Головная боль",
        patient_info={"age": 30, "gender": "female"}
    )
    
    assert result['status'] == 'success'
    assert 'data' in result
```

## 🔧 Troubleshooting

### Проблема: MCP не инициализируется

**Решение:**
1. Проверьте наличие API ключей в .env файле
2. Убедитесь что MCP_ENABLED=true
3. Проверьте логи: `tail -f backend/logs/mcp.log`

### Проблема: Timeout при запросах

**Решение:**
1. Увеличьте MCP_REQUEST_TIMEOUT в конфигурации
2. Проверьте доступность AI провайдеров
3. Используйте fallback режим: MCP_FALLBACK_TO_DIRECT=true

### Проблема: Ошибки при анализе изображений

**Решение:**
1. Проверьте размер файла (макс. 25MB)
2. Проверьте формат (JPEG, PNG, HEIC)
3. Используйте провайдеры с поддержкой изображений (OpenAI, Gemini)

### Логирование

```python
# Включение детального логирования
import logging
logging.getLogger('app.services.mcp').setLevel(logging.DEBUG)
```

## 🚀 Расширение функциональности

### Добавление нового MCP сервера

1. Создайте новый сервер в `backend/app/services/mcp/`:

```python
from .base_server import BaseMCPServer, MCPTool

class MyCustomMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(name="custom-server", version="1.0.0")
    
    @MCPTool(name="my_tool", description="Мой инструмент")
    async def my_tool(self, param1: str) -> Dict[str, Any]:
        # Ваша логика
        return {"result": "success"}
```

2. Зарегистрируйте сервер в `mcp_client.py`:

```python
self.servers["custom"] = MyCustomMCPServer()
```

3. Добавьте API endpoint если нужно

### Добавление нового AI провайдера

1. Реализуйте провайдер наследуясь от `BaseAIProvider`
2. Добавьте в `AIProviderType` enum
3. Зарегистрируйте в `AIManager`

## 📝 Best Practices

1. **Всегда используйте MCP для новых AI функций**
2. **Включайте fallback для критических функций**
3. **Мониторьте метрики и здоровье системы**
4. **Используйте пакетную обработку для множественных запросов**
5. **Кешируйте результаты где возможно**
6. **Документируйте новые MCP инструменты**

## 🔒 Безопасность

- ✅ Все запросы требуют авторизацию
- ✅ Валидация входных данных на уровне MCP
- ✅ Ограничение размера файлов
- ✅ Rate limiting через API
- ✅ Логирование всех запросов

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `backend/logs/mcp.log`
2. Запустите тесты: `python test_mcp_integration.py`
3. Проверьте метрики через MCPMonitor
4. Обратитесь к документации API провайдеров

---

**Версия документа:** 1.0.0  
**Дата обновления:** 2024  
**Автор:** AI Assistant
