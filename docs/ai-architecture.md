# AI Architecture

> Документ описывает архитектуру AI подсистемы в EMR V2

---

## 📐 Слои

```
┌──────────────────────────────────────────────────────────────┐
│                        UI Layer                               │
│                                                               │
│  EMRSmartFieldV2.jsx  ──────▶  mcpClient.js                  │
│  ICD10Autocomplete.jsx        (axios, timeout=120s)          │
│                                                               │
└───────────────────────────────┬──────────────────────────────┘
                                │ HTTP POST /api/v1/mcp/*
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                  AI Orchestration Layer                       │
│                                                               │
│  mcp.py (endpoints)  ──────▶  mcp_manager.py                 │
│                               - asyncio.wait_for (180s)       │
│                               - Circuit breaker               │
│                               - Metrics                       │
│                               - debug_meta (dev)              │
│                                                               │
│                      ──────▶  mcp_client.py                  │
│                               - Server routing                │
│                                                               │
│                      ──────▶  *_server.py                    │
│                               - complaint_server.py           │
│                               - icd10_server.py               │
│                               - lab_server.py                 │
│                               - imaging_server.py             │
│                                                               │
└───────────────────────────────┬──────────────────────────────┘
                                │ async call
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                    AI Provider Layer                          │
│                                                               │
│  ai_manager.py  ──────▶  deepseek_provider.py (primary)      │
│                          openai_provider.py (fallback)        │
│                          gemini_provider.py (fallback)        │
│                          mock_provider.py (testing)           │
│                                                               │
│  Timeout: AI_PROVIDER_TIMEOUT (160s)                          │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Конфигурация

| Параметр | Default | Описание |
|----------|---------|----------|
| `MCP_ENABLED` | true | Включить MCP подсистему |
| `MCP_REQUEST_TIMEOUT` | 180s | Таймаут orchestrator |
| `AI_PROVIDER_TIMEOUT` | 160s | Таймаут HTTP к AI |
| `MCP_LOG_REQUESTS` | true | Логировать запросы |

---

## 🚦 Circuit Breaker

### Параметры
- **Threshold**: 3 consecutive failures
- **Cooldown**: 5 minutes

### Логика
```
failure → increment counter
if counter >= 3:
    disable server for 5 min
    log CIRCUIT_BREAKER_TRIPPED

success → reset counter

after cooldown:
    re-enable server
    log CIRCUIT_BREAKER_RESET
```

### Мониторинг
```
GET /api/v1/mcp/circuit-breaker
```

---

## 📋 Правила

### 1. UI НЕ вызывает провайдеров напрямую
```
❌ EMRSmartFieldV2 → deepseek_provider
✅ EMRSmartFieldV2 → mcpClient → mcp.py → mcp_manager → provider
```

### 2. Таймауты: Provider ≤ MCP < Frontend
```
✅ 160s ≤ 180s < 120s (wait is aborted)
❌ 200s ≤ 100s (orchestrator kills before provider finishes)
```

### 3. Retry только на уровне MCP
```
❌ UI retry
❌ Provider retry
✅ mcp_manager: 1 retry on timeout
```

### 4. Все AI ответы содержат провенанс
```json
{
  "status": "success",
  "data": {...},
  "debug_meta": {
    "layer": "mcp_manager",
    "elapsed_ms": 42000,
    "server": "icd10"
  }
}
```

---

## 🔍 Отладка

### Логи для поиска
```
MCP_WAIT_START    - начало запроса
MCP_TIMEOUT       - таймаут (с elapsed и timeout)
CIRCUIT_BREAKER_* - события circuit breaker
AI_CALL           - вызовы провайдеров
```

### Dev консоль
```javascript
// Автоматически логируется в dev mode
[AI Debug] { layer: "mcp_manager", elapsed_ms: 42000, ... }
```

---

## 📁 Файлы

### Backend
```
backend/app/
├── api/v1/endpoints/mcp.py      # HTTP endpoints
├── services/mcp/
│   ├── mcp_manager.py           # Orchestrator
│   ├── mcp_client.py            # Server router
│   ├── complaint_server.py      # Complaint analysis
│   ├── icd10_server.py          # ICD-10 suggestions
│   ├── lab_server.py            # Lab interpretation
│   └── imaging_server.py        # Image analysis
├── services/ai/
│   ├── ai_manager.py            # Provider selection
│   ├── deepseek_provider.py     # DeepSeek API
│   ├── openai_provider.py       # OpenAI API
│   ├── gemini_provider.py       # Gemini API
│   └── base_provider.py         # Abstract base
└── core/config.py               # Settings
```

### Frontend
```
frontend/src/
├── api/mcpClient.js             # API client
└── components/emr-v2/
    ├── EMRContainerV2.jsx       # AI integration
    └── sections/
        └── EMRSmartFieldV2.jsx  # AI-enabled field
```

---

## 📝 См. также

- [ai-execution-budget.md](./ai-execution-budget.md) — таймауты
- [ai-smoke-tests.md](./ai-smoke-tests.md) — тестирование
