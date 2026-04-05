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
