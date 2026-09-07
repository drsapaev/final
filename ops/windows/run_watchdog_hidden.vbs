' ClinicRuntimeWatchdog hidden launcher.
'
' The scheduled task "ClinicRuntimeWatchdog" fires every minute; when its
' action runs powershell.exe directly, Task Scheduler flashes a console
' window on the operator's desktop each time. wscript.exe is a GUI-subsystem
' host: launching the powershell script from here with window style 0
' creates NO visible window.
'
' Scheduled task action (registered on the prod host):
'   wscript.exe "C:\final\ops\windows\run_watchdog_hidden.vbs"
'
' The script itself (watchdog_runtime.ps1) never deploys - runtime health
' checks only; see ops/windows/README.md.

Dim shell
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\final"
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\final\ops\windows\watchdog_runtime.ps1""", 0, False
