# Умный скрипт перезапуска с проверкой порта
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "🏥 CLINIC MANAGEMENT SYSTEM - УМНЫЙ ПЕРЕЗАПУСК" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Шаг 1: Остановка процессов
Write-Host "Шаг 1: Остановка процессов Python..." -ForegroundColor Yellow
& "$PSScriptRoot\stop_all_python.ps1"

# Шаг 2: Проверка порта
Write-Host ""
Write-Host "Шаг 2: Проверка доступности порта 8000..." -ForegroundColor Yellow

$maxAttempts = 5
$attempt = 0
$portFree = $false

while ($attempt -lt $maxAttempts -and -not $portFree) {
    $attempt++
    $check = netstat -ano | Select-String ":8000.*LISTENING"
    
    if (-not $check) {
        $portFree = $true
        Write-Host "✅ Порт 8000 свободен!" -ForegroundColor Green
    }
    else {
        Write-Host "⏳ Попытка $attempt/$maxAttempts - порт все еще занят, ожидание..." -ForegroundColor Yellow
        
        # Пытаемся убить процесс еще раз
        $check | ForEach-Object {
            $line = $_.Line
            $processId = ($line -split '\s+')[-1]
            Write-Host "   Останавливаем процесс PID: $processId"
            taskkill /PID $processId /F 2>$null
        }
        
        Start-Sleep -Seconds 2
    }
}

# Шаг 3: Выбор порта и запуск
Write-Host ""
if ($portFree) {
    Write-Host "Шаг 3: Запуск сервера на порту 8000..." -ForegroundColor Yellow
    Write-Host ""
    & "c:\final\.venv\Scripts\python.exe" "$PSScriptRoot\start_server.py"
}
else {
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host "⚠️ ВНИМАНИЕ: Не удалось освободить порт 8000!" -ForegroundColor Red
    Write-Host "=" * 80 -ForegroundColor Red
    Write-Host ""
    Write-Host "Варианты решения:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Запустить на альтернативном порту 8001:" -ForegroundColor Cyan
    Write-Host "   python start_server_port8001.py" -ForegroundColor White
    Write-Host ""
    Write-Host "2. Закрыть процессы вручную через Диспетчер задач:" -ForegroundColor Cyan
    Write-Host "   - Нажмите Ctrl+Shift+Esc" -ForegroundColor White
    Write-Host "   - Найдите процессы python.exe" -ForegroundColor White
    Write-Host "   - Завершите их" -ForegroundColor White
    Write-Host ""
    Write-Host "3. Перезагрузить компьютер" -ForegroundColor Cyan
    Write-Host ""
    
    $response = Read-Host "Запустить на порту 8001? (y/n)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host ""
        Write-Host "Запуск на порту 8001..." -ForegroundColor Green
        & "c:\final\.venv\Scripts\python.exe" "$PSScriptRoot\start_server_port8001.py"
    }
}
