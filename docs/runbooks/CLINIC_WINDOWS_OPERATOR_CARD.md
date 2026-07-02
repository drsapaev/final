# Clinic Windows Operator Card

[Back to README](../README.md)

1. Open the clinic URL: `http://192.168.1.5:18080`
2. Check host status:
   `powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 status`
3. Expected signal: `PASS: health_check completed successfully`
4. Before any change, take a backup:
   `powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 backup`
5. Approved artifact for this pilot: `clinic-release-923010c00bf3.zip`
6. Safe update:
   `powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 update -ArtifactFile C:\path\to\clinic-release-923010c00bf3.zip`
7. Restore proof:
   `powershell -ExecutionPolicy Bypass -File ops/windows/clinic_host.ps1 restore-rehearsal`
8. Stop signal: any `FAIL:` output
9. Stop signal: `/setup` appears on an initialized host
10. Stop signal: origin mismatch or login failure
11. If anything is red, pause pilot and write an incident note
12. Record day-1 evidence in [PILOT_7_DAY_EVIDENCE_PACK.md](PILOT_7_DAY_EVIDENCE_PACK.md)
