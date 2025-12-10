# Простой и надежный скрипт для остановки всех процессов Python в проекте
Write-Host "=" * 60
Write-Host "🛑 Остановка всех процессов Python в проекте..." -ForegroundColor Yellow
Write-Host "=" * 60

$stopped = 0

# Метод 1: Через Get-Process
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like '*final*'
} | ForEach-Object {
    Write-Host "Останавливаем: $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Cyan
    Write-Host "  Путь: $($_.Path)"
    Stop-Process -Id $_.Id -Force
    $stopped++
}

if ($stopped -gt 0) {
    Write-Host ""
    Write-Host "✅ Остановлено процессов: $stopped" -ForegroundColor Green
    Start-Sleep -Seconds 2
}
else {
    Write-Host "ℹ️ Процессы Python не найдены" -ForegroundColor Gray
}

# Метод 2: Проверка порта 8000 через netstat
Write-Host ""
Write-Host "Проверка порта 8000..." -ForegroundColor Yellow
$netstat = netstat -ano | Select-String ":8000.*LISTENING"

if ($netstat) {
    Write-Host "⚠️ Порт 8000 все еще занят, принудительная очистка..." -ForegroundColor Yellow
    $netstat | ForEach-Object {
        $line = $_.Line
        $processId = ($line -split '\s+')[-1]
        Write-Host "Останавливаем процесс PID: $processId"
        taskkill /PID $processId /F 2>$null
    }
    
    # Даем время на освобождение порта
    Write-Host "Ожидание освобождения порта..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    
    # Повторная проверка и очистка
    $netstat2 = netstat -ano | Select-String ":8000.*LISTENING"
    if ($netstat2) {
        Write-Host "Повторная попытка очистки порта..." -ForegroundColor Yellow
        $netstat2 | ForEach-Object {
            $line = $_.Line
            $processId = ($line -split '\s+')[-1]
            taskkill /PID $processId /F 2>$null
        }
        Start-Sleep -Seconds 2
    }
}

# Финальная проверка
$finalCheck = netstat -ano | Select-String ":8000.*LISTENING"
if (-not $finalCheck) {
    Write-Host ""
    Write-Host "=" * 60
    Write-Host "✅ Порт 8000 свободен и готов к использованию!" -ForegroundColor Green
    Write-Host "=" * 60
}
else {
    Write-Host ""
    Write-Host "=" * 60
    Write-Host "⚠️ ВНИМАНИЕ: Порт 8000 все еще занят!" -ForegroundColor Red
    Write-Host "Попробуйте закрыть процессы вручную через Диспетчер задач" -ForegroundColor Yellow
    Write-Host "=" * 60
}
