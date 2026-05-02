# AI Integration Guide for Developers

> Техническое руководство по работе с AI подсистемой

---

## 📐 Архитектура

См. [ai-architecture.md](./ai-architecture.md)

**Ключевые файлы**:
- `backend/app/schemas/ai_contract.py` — Pydantic модели
- `backend/app/services/mcp/mcp_manager.py` — Orchestrator
- `backend/app/services/ai/*_provider.py` — AI провайдеры
- `frontend/src/api/mcpClient.js` — API клиент

---

## 🔧 Добавление новой AI функции

### 1. Определите контракт

```python
# backend/app/schemas/ai_contract.py
class MyNewResponse(BaseModel):
    suggestions: List[MySuggestion]
    provider: Optional[str] = None
    latency_ms: Optional[int] = None
```

### 2. Реализуйте в провайдере

```python
# backend/app/services/ai/deepseek_provider.py
async def my_new_function(self, ...) -> List[Dict]:
    prompt = "..."
    response = await self.generate(AIRequest(prompt=prompt))
    return self._parse_response(response)
```

### 3. Добавьте в MCP сервер

```python
# backend/app/services/mcp/my_server.py
@MCPTool(name="my_tool", description="Description")
async def my_tool(self, ...) -> Dict[str, Any]:
    result = await self.ai_manager.my_new_function(...)
    return {"status": "success", "data": result}
```

### 4. Добавьте endpoint

```python
# backend/app/api/v1/endpoints/mcp.py
@router.post("/my-endpoint")
async def my_endpoint(...):
    return await mcp_manager.execute_request(
        server="my_server", method="tool/my_tool", params=...
    )
```

### 5. Вызовите из frontend

```javascript
// frontend/src/api/mcpClient.js
myFunction: async (params) => {
    const response = await mcpClient.post('/mcp/my-endpoint', params);
    return response.data;
}
```

---

## ⏱️ Таймауты

См. [ai-execution-budget.md](./ai-execution-budget.md)

**Правило**: `Provider ≤ MCP < Frontend`

```
AI_PROVIDER_TIMEOUT=160  # HTTP к AI API
MCP_REQUEST_TIMEOUT=180  # asyncio.wait_for
Frontend axios=120       # UX timeout
```

---

## 🚦 Circuit Breaker

После 3 consecutive failures сервер отключается на 5 минут.

**Мониторинг**:
```bash
GET /api/v1/mcp/circuit-breaker
```

**Логи**:
```
CIRCUIT_BREAKER_TRIPPED  - сработал
CIRCUIT_BREAKER_BLOCKED  - запрос заблокирован
CIRCUIT_BREAKER_RESET    - восстановлен
```

---

## 🔍 Отладка

### Backend логи

```
MCP_WAIT_START: server=icd10, timeout=180s
MCP_TIMEOUT: server=icd10, elapsed=180.12s, layer=mcp_manager
```

### Frontend (dev mode)

```javascript
// Автоматически в консоли
[AI Debug] { layer: "mcp_manager", elapsed_ms: 42000, ... }
```

### Debug meta

В dev режиме ответы содержат `debug_meta`:
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

## 🚫 Чего НЕ делать

| ❌ Плохо | ✅ Хорошо |
|----------|-----------|
| UI вызывает провайдеров напрямую | UI → mcpClient → mcp.py → provider |
| Retry в UI | Retry только в mcp_manager |
| Retry в провайдере | Retry только в mcp_manager |
| Hardcoded timeout | Из settings: `AI_PROVIDER_TIMEOUT` |
| Regex парсинг AI ответов | Structured JSON от провайдера |
| PHI в телеметрии | Только агрегированные метрики |

---

## ✅ Чеклист перед мержем

- [ ] Используется `AIResponse` контракт
- [ ] Нет прямых вызовов провайдеров из UI
- [ ] Таймауты из config, не hardcoded
- [ ] Добавлены логи для отладки
- [ ] Обработка ошибок и timeouts
- [ ] Undo/Redo работает
- [ ] Smoke tests пройдены

---

## 📚 Связанные документы

- [ai-architecture.md](./ai-architecture.md) — архитектура
- [ai-execution-budget.md](./ai-execution-budget.md) — таймауты
- [ai-smoke-tests.md](./ai-smoke-tests.md) — тестирование
- [AI-for-Doctors.md](./AI-for-Doctors.md) — руководство для врачей
