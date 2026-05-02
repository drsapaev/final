# Скрипт для остановки всех процессов на порту 5173
Write-Host "[*] Поиск процессов на порту 5173..." -ForegroundColor Cyan

$connections = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue

if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $pids) {
        try {
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "[!] Остановка процесса: $($process.ProcessName) (PID: $processId)" -ForegroundColor Yellow
                Stop-Process -Id $processId -Force
                Write-Host "[OK] Процесс PID $processId остановлен" -ForegroundColor Green
            }
        }
        catch {
            Write-Host "[ERROR] Не удалось остановить процесс PID $processId" -ForegroundColor Red
        }
    }

    Start-Sleep -Seconds 1
    Write-Host ""
    Write-Host "[OK] Порт 5173 освобожден!" -ForegroundColor Green
}
else {
    Write-Host "[OK] Порт 5173 свободен" -ForegroundColor Green
}
