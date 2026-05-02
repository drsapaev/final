# Решение проблемы "Port 18000 already in use"

## Проблема
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 18000):
обычно разрешается только одно использование адреса сокета (протокол/сетевой адрес/порт)
```

**Причина:** Backend пытается запуститься на порту 18000, но порт уже занят зомби-процессом.

## ✅ АВТОМАТИЧЕСКОЕ РЕШЕНИЕ

### Используйте start_server.py (рекомендуется)

Backend сервер **автоматически** останавливает процессы на порту 18000:

```bash
cd backend
python start_server.py
```

**Что делает скрипт:**
1. Находит все процессы на порту 18000
2. Останавливает их через PowerShell + taskkill
3. Ждет 3 секунды для освобождения порта
4. Проверяет что порт свободен
5. Запускает Uvicorn на http://0.0.0.0:18000

## 🛠️ РУЧНОЕ РЕШЕНИЕ

### Метод 1: PowerShell - Остановить все Python

```powershell
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force"
```

### Метод 2: PowerShell скрипт

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File kill_port_18000.ps1
```

### Метод 3: Найти PID и остановить вручную

```bash
# 1. Найти процесс на порту 18000
netstat -ano | findstr :18000

# Вывод: TCP  0.0.0.0:18000  0.0.0.0:0  LISTENING  12345
# PID = 12345

# 2. Остановить процесс
taskkill /F /PID 12345
```

## ✅ Проверка что порт свободен

```bash
netstat -ano | findstr :18000
```

Если команда **ничего не вернула** - порт свободен ✅

## 📝 Конфигурация портов

**Backend запускается на порту 18000** ([start_server.py](start_server.py#L140))
```python
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=18000,  # ← Backend порт
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

- **Backend ВСЕГДА на порту 18000**
- **Frontend ВСЕГДА на порту 5173**
- **Vite автоматически проксирует /api и /ws на backend**
- При остановке используйте Ctrl+C (процессы автоматически остановятся)

## 🔧 Если проблема сохраняется

