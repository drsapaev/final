# AI Execution Budget

> **Правило**: Верхний слой ВСЕГДА имеет больший таймаут, чем нижний.  
> `Provider ≤ MCP < Frontend`

---

## 📊 Таймауты по слоям

| Слой | Компонент | Timeout | Retry | Переменная |
|------|-----------|---------|-------|------------|
| **Frontend** | axios / mcpClient.js | 120s | 0 | hardcoded |
| **MCP Orchestrator** | mcp_manager.py | 180s | 1 | `MCP_REQUEST_TIMEOUT` |
| **AI Provider** | deepseek/openai/gemini | 160s | 0 | `AI_PROVIDER_TIMEOUT` |

---

## ⚠️ Критические правила

### 1. Иерархия таймаутов
```
Provider (160s) < MCP (180s) < Frontend (120s)
         ↑              ↑              ↑
    HTTP timeout   asyncio.wait_for   UX timeout
```

**Почему Frontend < MCP?**  
Frontend показывает пользователю ошибку раньше, чем backend завершит попытку.
Это **ОК** — лучше показать "попробуйте позже" чем зависнуть.

### 2. Retry только на одном уровне
- ❌ Frontend: **НЕТ retry**
- ✅ MCP: **1 retry** при timeout
- ❌ Provider: **НЕТ retry**

**Почему?** Retry на нескольких уровнях = экспоненциальное умножение попыток.

### 3. Circuit Breaker
После **3 consecutive failures** от провайдера:
- Провайдер отключается на **5 минут**
- Логируется `CIRCUIT_BREAKER` событие
- Fallback на другого провайдера (если есть)

---

## 🔧 Конфигурация

### Backend (.env)
```env
MCP_REQUEST_TIMEOUT=180
AI_PROVIDER_TIMEOUT=160
```

### Frontend (mcpClient.js)
```javascript
const mcpClient = axios.create({
    timeout: 120000,  // 120 секунд
});
```

---

## 📈 Мониторинг

### Логи для отслеживания
```
MCP_WAIT_START: server=icd10, timeout=180s
MCP_TIMEOUT: server=icd10, elapsed=180.12s, layer=mcp_manager
CIRCUIT_BREAKER: provider=deepseek, disabled_until=...
```

### Метрики
- `/api/v1/mcp/metrics` — статистика по серверам
- `avg_response_time` — среднее время ответа
- `errors` — количество ошибок

---

## 🚨 Что делать при таймаутах

1. **Проверить логи**: искать `MCP_TIMEOUT`
2. **Проверить провайдера**: API статус, rate limits
3. **Проверить circuit breaker**: `/mcp/metrics`
4. **Временно снизить таймауты** для тестирования

---

## 📝 История изменений

| Дата | Изменение |
|------|-----------|
| 2026-01-17 | Начальная версия. MCP timeout: 30→180s |
