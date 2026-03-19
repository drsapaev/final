# Решение проблемы "Port 8000 already in use"

## Проблема
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000):
обычно разрешается только одно использование адреса сокета (протокол/сетевой адрес/порт)
```

**Причина:** Backend пытается запуститься на порту 8000, но порт уже занят зомби-процессом.

## ✅ АВТОМАТИЧЕСКОЕ РЕШЕНИЕ

### Используйте start_server.py (рекомендуется)

Backend сервер **автоматически** останавливает процессы на порту 8000:

```bash
cd backend
python start_server.py
```

**Что делает скрипт:**
1. Находит все процессы на порту 8000
2. Останавливает их через PowerShell + taskkill
3. Ждет 3 секунды для освобождения порта
4. Проверяет что порт свободен
5. Запускает Uvicorn на http://0.0.0.0:8000

## 🛠️ РУЧНОЕ РЕШЕНИЕ

### Метод 1: PowerShell - Остановить все Python

```powershell
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"
```

### Метод 2: PowerShell скрипт

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File kill_port_8000.ps1
```

### Метод 3: Найти PID и остановить вручную

```bash
# 1. Найти процесс на порту 8000
netstat -ano | findstr :8000

# Вывод: TCP  0.0.0.0:8000  0.0.0.0:0  LISTENING  12345
# PID = 12345

# 2. Остановить процесс
taskkill /F /PID 12345
```

## ✅ Проверка что порт свободен

```bash
netstat -ano | findstr :8000
```

Если команда **ничего не вернула** - порт свободен ✅

## 📝 Конфигурация портов

**Backend запускается на порту 8000** ([start_server.py](start_server.py#L140))
```python
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8000,  # ← Backend порт
    reload=True
)
```

### Frontend

**Frontend запускается на порту 5173** ([vite.config.js](../frontend/vite.config.js#L13))
```javascript
server: {
    port: 5173,  // ← Frontend порт
    proxy: {
        "/api": {
            target: "http://localhost:18000",  // ← Proxy на backend
        },
        "/ws": {
            target: "ws://localhost:18000",  // ← WebSocket на backend
        }
    }
}
```

## 🚀 Быстрый старт (оба сервера)

**Терминал 1 - Backend:**
```bash
cd backend
python start_server.py
```

**Терминал 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Откройте браузер:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:18000/docs

## ⚠️ Важно

- **Backend ВСЕГДА на порту 8000**
- **Frontend ВСЕГДА на порту 5173**
- **Vite автоматически проксирует /api и /ws на backend**
- При остановке используйте Ctrl+C (процессы автоматически остановятся)

## 🔧 Если проблема сохраняется

1. Перезагрузите компьютер
2. Проверьте антивирус (может блокировать порты)
3. Используйте [kill_port_8000.ps1](kill_port_8000.ps1) вручную

---

**Последнее обновление:** Декабрь 2025
**Исправлена проблема с зомби-процессами на Windows**
