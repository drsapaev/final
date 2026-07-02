# ================================================
# 🏥 КЛИНИЧЕСКАЯ СИСТЕМА - АВТОМАТИЧЕСКИЙ ЗАПУСК
# ================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🏥 КЛИНИЧЕСКАЯ СИСТЕМА - АВТОМАТИЧЕСКИЙ ЗАПУСК" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Перейти в папку проекта
Set-Location "C:\final\backend"

Write-Host "🔧 Активируем виртуальное окружение..." -ForegroundColor Yellow
& ".\\.venv\\Scripts\\Activate.ps1"

# Установить переменные окружения
$env:WS_DEV_ALLOW = "1"
if (-not $env:CORS_DISABLE) { $env:CORS_DISABLE = "0" }
$env:REQUIRE_LICENSE = "0"

Write-Host "🚀 Запускаем сервер с автоматической проверкой..." -ForegroundColor Green
python run_server_auto.py

Write-Host ""
Write-Host "✅ Работа завершена. Нажмите любую клавишу для выхода..." -ForegroundColor Green
Read-Host
