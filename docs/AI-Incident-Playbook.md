# AI Incident Playbook

> Руководство по устранению неполадок AI подсистемы

---

## 🚨 Симптомы и действия

### 1. "AI не отвечает" / Timeout

**Признаки**:
- Loading крутится больше 2 минут
- В консоли: `Request timeout`
- В логах: `MCP_TIMEOUT`

**Диагностика**:
```bash
# Проверить логи backend
grep "MCP_TIMEOUT" backend.log

# Проверить circuit breaker
curl /api/v1/mcp/circuit-breaker
```

**Действия**:
1. Проверить API ключи в `.env`
2. Проверить статус провайдера (DeepSeek, OpenAI)
3. Если circuit breaker сработал — подождать 5 минут
4. Временно увеличить `MCP_REQUEST_TIMEOUT`

---

### 2. Circuit Breaker сработал

**Признаки**:
- В логах: `CIRCUIT_BREAKER_TRIPPED`
- Быстрые ответы с ошибкой "Server temporarily unavailable"

**Диагностика**:
```bash
curl /api/v1/mcp/circuit-breaker
# Ответ покажет disabled серверы и оставшееся время
```

**Действия**:
1. Определить причину failures (таймауты? ошибки API?)
2. Подождать окончания cooldown (5 минут)
3. Проверить статус провайдера
4. При необходимости — перезапустить backend

---

### 3. Неправильные подсказки

**Признаки**:
- AI даёт нерелевантные коды МКБ-10
- Подсказки не соответствуют симптомам

**Диагностика**:
```javascript
// В консоли браузера (dev mode)
// Искать: [AI Debug] — покажет какой провайдер использовался
```

**Действия**:
1. Проверить `debug_meta.provider`
2. Попробовать другой провайдер через `.env`
3. Проверить prompt в `deepseek_provider.py`
4. Убедиться что симптомы передаются корректно

---

### 4. Пустые подсказки

**Признаки**:
- AI вызывается, но suggestions пустой массив
- В консоли: `[EMR AI] No ICD-10 suggestions returned`

**Диагностика**:
```bash
# Проверить ответ от провайдера
grep "DeepSeek ICD10" backend.log
```

**Действия**:
1. Проверить что symptoms не пустые
2. Проверить JSON parsing в провайдере
3. Смотреть на fallback regex в провайдере
4. Временно включить более детальное логирование

---

### 5. Frontend зависает

**Признаки**:
- UI не реагирует после нажатия AI
- Нет error в консоли

**Диагностика**:
```
Network tab → найти /mcp/* запрос → проверить статус
```

**Действия**:
1. Проверить network tab на pending запросы
2. Сравнить `MCP_REQUEST_TIMEOUT` и frontend timeout
3. Проверить что backend запущен
4. Перезагрузить страницу

---

## 🔧 Быстрые команды

### Проверить здоровье MCP
```bash
curl -H "Authorization: Bearer $TOKEN" /api/v1/mcp/health
```

### Проверить метрики
```bash
curl -H "Authorization: Bearer $TOKEN" /api/v1/mcp/metrics
```

### Проверить circuit breaker
```bash
curl -H "Authorization: Bearer $TOKEN" /api/v1/mcp/circuit-breaker
```

### Найти таймауты в логах
```bash
grep "MCP_TIMEOUT\|CIRCUIT_BREAKER" backend.log | tail -20
```

---

## 📊 Мониторинг

### Ключевые метрики
- `requests_failed` — общее количество ошибок
- `avg_response_time` — среднее время ответа
- Circuit breaker статус всех серверов

### Алерты (рекомендуется настроить)
- `requests_failed` > 10 за 5 минут
- `avg_response_time` > 60 секунд
- Circuit breaker срабатывает

---

## 📞 Эскалация

1. **L1**: Перезапуск backend
2. **L2**: Проверка API ключей, смена провайдера
3. **L3**: Анализ логов, debugging кода
4. **L4**: Контакт с провайдером API (DeepSeek, OpenAI)

---

## 📝 Шаблон инцидента

```
Время: [когда обнаружено]
Симптомы: [что наблюдается]
Затронуто: [какие функции]
Диагностика:
  - Circuit breaker: [ok/tripped]
  - Логи: [ключевые строки]
  - Provider: [какой использовался]
Причина: [если известна]
Решение: [что сделано]
Время восстановления: [когда заработало]
```
