# Решение проблемы "Port 18000 already in use"

## Симптом

```text
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 18000)
```

Backend пытается стартовать на порту `18000`, но порт уже занят другим процессом.

## Рекомендуемый способ

Используйте guarded helper. По умолчанию он показывает владельца порта и не убивает чужой процесс без явного подтверждения:

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File kill_port_18000.ps1
```

Если вы проверили PID/процесс и точно хотите освободить порт:

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File kill_port_18000.ps1 -ForcePortOwner
```

Альтернатива через env-подтверждение:

```powershell
$env:CONFIRM_KILL_PORT_18000_OWNER = "1"
powershell -ExecutionPolicy Bypass -File kill_port_18000.ps1
Remove-Item Env:\CONFIRM_KILL_PORT_18000_OWNER
```

## Как проверить владельца порта вручную

```powershell
netstat -ano | findstr :18000
Get-Process -Id <PID>
```

Не используйте широкие команды вроде остановки всех `python.exe`. Сначала убедитесь, что PID принадлежит этому проекту или вашему dev-серверу.

## Проверка, что порт свободен

```powershell
netstat -ano | findstr :18000
```

Если команда ничего не вернула, порт свободен.

## Быстрый старт

Backend:

```powershell
cd backend
python start_server.py
```

Frontend:

```powershell
cd frontend
npm run dev
```

Ожидаемые адреса:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:18000/docs`

## Важно

- Backend по проектному контракту использует порт `18000`.
- Frontend использует порт `5173`.
- При обычной остановке используйте `Ctrl+C` в терминалах, которые вы сами запускали.
