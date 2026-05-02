# Скрипт для запуска сервера с автоматическим освобождением порта
Write-Host "=" * 80
Write-Host "🏥 CLINIC MANAGEMENT SYSTEM - ЗАПУСК СЕРВЕРА" -ForegroundColor Cyan
Write-Host "=" * 80
Write-Host ""

# Шаг 1: Останавливаем все процессы Python
Write-Host "Шаг 1: Остановка процессов Python..." -ForegroundColor Yellow
& "$PSScriptRoot\stop_all_python.ps1"

Write-Host ""
Write-Host "Шаг 2: Запуск сервера..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
$env:BACKEND_HOST = "0.0.0.0"
$env:BACKEND_PORT = "18000"

# Шаг 2: Запускаем сервер
try {
    & "c:\final\.venv\Scripts\python.exe" "$PSScriptRoot\start_server.py"
}
catch {
    Write-Host ""
    Write-Host "❌ Ошибка при запуске сервера: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Попробуйте запустить вручную:" -ForegroundColor Yellow
    Write-Host "  cd backend" -ForegroundColor Gray
    Write-Host "  python start_server.py" -ForegroundColor Gray
    exit 1
}
