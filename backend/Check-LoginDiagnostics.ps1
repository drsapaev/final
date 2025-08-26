# === Конфигурация ===
$ApiRoot = "http://localhost:8000"
$DbFilePath = "C:\final\backend\clinic.db"  # путь к SQLite-файлу (если используется)
$EnvPath = "C:\final\backend\.env"
$AuthFile = "C:\final\backend\app\api\v1\endpoints\auth.py"
$DepsFile = "C:\final\backend\app\api\deps.py"
$SessionFile = "C:\final\backend\app\db\session.py"

Write-Host "▶️  Проверка состояния проекта FastAPI..." -ForegroundColor Cyan
Write-Host "--------------------------------------------------"

# 1. Проверка openapi.json
Write-Host "`n[1] Проверка openapi.json..." -ForegroundColor Yellow
try {
  $openapi = Invoke-RestMethod -Uri "$ApiRoot/openapi.json" -TimeoutSec 3
  if ($openapi.info.title) {
    Write-Host "✅ OpenAPI доступен: $($openapi.info.title)" -ForegroundColor Green
  }
} catch {
  Write-Host "❌ Ошибка при обращении к /openapi.json. Backend не запущен?" -ForegroundColor Red
}

# 2. Проверка файла .env
Write-Host "`n[2] Проверка .env (переменная DATABASE_URL)..." -ForegroundColor Yellow
if (Test-Path $EnvPath) {
  $dburl = Get-Content $EnvPath | Where-Object { $_ -match "^DATABASE_URL\s*=" }
  if ($dburl) {
    Write-Host "✅ Найдено: $dburl" -ForegroundColor Green
  } else {
    Write-Host "❌ В .env отсутствует DATABASE_URL" -ForegroundColor Red
  }
} else {
  Write-Host "❌ Файл .env не найден: $EnvPath" -ForegroundColor Red
}

# 3. Проверка файла базы данных
Write-Host "`n[3] Проверка файла БД (SQLite)..." -ForegroundColor Yellow
if (Test-Path $DbFilePath) {
  $size = (Get-Item $DbFilePath).Length
  Write-Host "✅ База данных существует ($([math]::Round($size / 1KB, 1)) KB)" -ForegroundColor Green
} else {
  Write-Host "❌ База данных отсутствует: $DbFilePath" -ForegroundColor Red
}

# 4. Проверка доступности /login с тест-данными
Write-Host "`n[4] Тест логина (admin/admin)..." -ForegroundColor Yellow
try {
  $body = "username=admin&password=admin&grant_type=password"
  Invoke-RestMethod -Method Post -Uri "$ApiRoot/api/v1/login" `
    -ContentType "application/x-www-form-urlencoded" `
    -Body $body -TimeoutSec 3
  Write-Host "✅ Логин прошёл успешно" -ForegroundColor Green
} catch {
  if ($_.Exception.Response.StatusCode.value__ -eq 401) {
    Write-Host "⚠️  Неверный логин/пароль (401 Unauthorized)" -ForegroundColor Yellow
  } elseif ($_.Exception.Response.StatusCode.value__ -eq 500) {
    Write-Host "❌ Ошибка 500 (Internal Server Error). Проверь трассировку в uvicorn." -ForegroundColor Red
  } else {
    Write-Host "❌ Запрос не выполнен: $($_.Exception.Message)" -ForegroundColor Red
  }
}

# 5. Проверка ключевых файлов
Write-Host "`n[5] Проверка ключевых файлов auth/deps/session..." -ForegroundColor Yellow
foreach ($file in @($AuthFile, $DepsFile, $SessionFile)) {
  if (Test-Path $file) {
    $line = Get-Content $file | Select-String -Pattern "def get_db|verify_password|sessionmaker"
    if ($line) {
      Write-Host "✅ $file содержит важные функции: $($line -join ', ')" -ForegroundColor Green
    } else {
      Write-Host "⚠️  $file найден, но без ключевых функций" -ForegroundColor Yellow
    }
  } else {
    Write-Host "❌ Отсутствует: $file" -ForegroundColor Red
  }
}

Write-Host "`n✅ Диагностика завершена. Если ошибка 500 осталась — покажи трассировку из uvicorn." -ForegroundColor Cyan
