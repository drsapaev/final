# Windows Pilot Host Wrapper

Use `clinic_host.ps1` when the real pilot host is a Windows machine.

It keeps the clinic host lifecycle Windows-native:

- starts backend with `backend/run_server.py`
- starts frontend with `npm run dev -- --host 0.0.0.0 --port 18080`
- runs backup, import, migration, smoke, and rollback helpers from `ops/vps/scripts`
- avoids the Linux-only `bash`, `systemctl`, and `nginx` chain

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 status
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 start
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 backup
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 import-release -ArtifactFile C:\path\to\clinic-release.zip
powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 update -ArtifactFile C:\path\to\clinic-release.zip
```

## Telegram polling scheduled task

Before a public HTTPS domain is available, the patient Telegram bot runs through
polling:

```powershell
cd C:\final\backend
python -m app.scripts.telegram_polling_worker
```

On a Windows pilot host, register polling as a startup task so it comes back
after a PC or server restart. Run PowerShell as Administrator and adjust
`$RepoRoot` if the checkout lives somewhere else:

```powershell
$TaskName = "KosmedTelegramPollingWorker"
$RepoRoot = "C:\final"
$BackendDir = Join-Path $RepoRoot "backend"
$PythonExe = (Get-Command python).Source

$Action = New-ScheduledTaskAction `
  -Execute $PythonExe `
  -Argument "-m app.scripts.telegram_polling_worker" `
  -WorkingDirectory $BackendDir

$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -MultipleInstances IgnoreNew `
  -RestartCount 999 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description "Runs the Kosmed Clinic Telegram bot in polling mode." `
  -RunLevel Highest `
  -Force
```

Useful operator commands:

```powershell
Start-ScheduledTask -TaskName "KosmedTelegramPollingWorker"
Get-ScheduledTaskInfo -TaskName "KosmedTelegramPollingWorker"
Stop-ScheduledTask -TaskName "KosmedTelegramPollingWorker"
Unregister-ScheduledTask -TaskName "KosmedTelegramPollingWorker" -Confirm:$false
```

Safe smoke check before registering the task:

```powershell
cd C:\final\backend
python -m app.scripts.telegram_polling_worker --once --max-updates 1 --keep-webhook --log-file none --pid-file none
```

Do not put the Telegram bot token in the scheduled task command. The worker reads
the token from the application configuration/database. When a public HTTPS domain
and server are ready, stop this task before switching the bot to webhook mode.
