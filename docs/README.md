# 📚 Documentation Index

## 🚨 MANDATORY READING (Before ANY Changes)

> **AI Agents and Developers MUST read these FIRST!**

| Document | Purpose | Priority |
|----------|---------|----------|
| [AUTHENTICATION_LAWS_FOR_AI.md](./AUTHENTICATION_LAWS_FOR_AI.md) | Auth system rules | 🔴 CRITICAL |
| [DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md](./DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md) | Autocomplete rules | 🔴 CRITICAL |
| [ROLE_SYSTEM_PROTECTION.md](./ROLE_SYSTEM_PROTECTION.md) | Role protection | 🔴 CRITICAL |
| [AUTHENTICATION_SYSTEM_FINAL_GUIDE.md](./AUTHENTICATION_SYSTEM_FINAL_GUIDE.md) | Auth full guide | 🟡 Important |

---

## 🏗️ Architecture & Systems

### Core Systems
| Document | Description |
|----------|-------------|
| [ROLES_AND_ROUTING.md](./ROLES_AND_ROUTING.md) | Role-based access control |
| [QUEUE_SYSTEM_ARCHITECTURE.md](./QUEUE_SYSTEM_ARCHITECTURE.md) | Current queue SSOT aligned to current `main` |
| [runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md](./runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md) | Current staging contour and role acceptance flow |
| [runbooks/CLINIC_HOST_INSTALL_RUNBOOK.md](./runbooks/CLINIC_HOST_INSTALL_RUNBOOK.md) | Clinic-host/on-prem install skeleton and fresh-run smoke pack |
| [runbooks/CLINIC_WINDOWS_PILOT_HOST_RUNBOOK.md](./runbooks/CLINIC_WINDOWS_PILOT_HOST_RUNBOOK.md) | Windows-native pilot host lifecycle and safe update flow |
| [runbooks/CLINIC_WINDOWS_OPERATOR_CARD.md](./runbooks/CLINIC_WINDOWS_OPERATOR_CARD.md) | Short operator card for day-1 Windows clinic opening |
| [runbooks/CLINIC_RELEASE_ARTIFACT_POLICY.md](./runbooks/CLINIC_RELEASE_ARTIFACT_POLICY.md) | Approved release artifact format, import, and online/offline delivery policy |
| [runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md](./runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md) | Final pre-release gate for approved artifacts, backups, smoke, and rollback readiness |
| [runbooks/CLINIC_PRE_RELEASE_EVIDENCE_PACK.md](./runbooks/CLINIC_PRE_RELEASE_EVIDENCE_PACK.md) | Pre-release proof for the real Windows pilot host artifact import, update, and post-update smoke |
| [runbooks/CLINIC_RELEASE_CANDIDATE_SUMMARY.md](./runbooks/CLINIC_RELEASE_CANDIDATE_SUMMARY.md) | Release candidate pinned to the tested artifact `clinic-release-923010c00bf3.zip` |
| [runbooks/CLINIC_ROUTING_PROOF_PHASE.md](./runbooks/CLINIC_ROUTING_PROOF_PHASE.md) | Live-router proof for canonical routes, legacy redirects, role-home behavior, and visible navigation parity |
| [runbooks/CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md](./runbooks/CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md) | Named limited-pilot contour for the real Windows clinic host |
| [runbooks/LOCAL_ONLY_EXTERNAL_SERVICES_POLICY.md](./runbooks/LOCAL_ONLY_EXTERNAL_SERVICES_POLICY.md) | Local-only policy for optional external integrations and configure-later behavior |
| [runbooks/LOCAL_ONLY_CLINIC_MASTER_CHECKLIST.md](./runbooks/LOCAL_ONLY_CLINIC_MASTER_CHECKLIST.md) | Single execution checklist for local-only clinic package, pilot, and safe updates |
| [runbooks/CLINIC_UPDATE_REHEARSAL_RUNBOOK.md](./runbooks/CLINIC_UPDATE_REHEARSAL_RUNBOOK.md) | Safe update rehearsal for initialized clinic deployments |
| [runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md](./runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md) | Backup and restore proof for a clinic deployment |
| [runbooks/CLINIC_STATE_SEPARATION_AUDIT.md](./runbooks/CLINIC_STATE_SEPARATION_AUDIT.md) | Separation checklist for release, DB, files, logs, and backups |
| [runbooks/CLINIC_OPERATOR_CHECKLIST.md](./runbooks/CLINIC_OPERATOR_CHECKLIST.md) | One-page operator checklist for fresh install, update, backup, restore, and rollback |
| [runbooks/CLINIC_EVIDENCE_PACK_TEMPLATE.md](./runbooks/CLINIC_EVIDENCE_PACK_TEMPLATE.md) | Evidence pack template for rehearsal and rollout logs |
| [runbooks/CONTROLLED_PILOT_GATE_CHECKLIST.md](./runbooks/CONTROLLED_PILOT_GATE_CHECKLIST.md) | One-screen gate checklist for the last three proofs before controlled pilot |
| [runbooks/CONTROLLED_PILOT_GATE_QUICK.md](./runbooks/CONTROLLED_PILOT_GATE_QUICK.md) | Compact copy-paste gate checklist for operators |
| [runbooks/CONTROLLED_PILOT_GATE_RESULT.md](./runbooks/CONTROLLED_PILOT_GATE_RESULT.md) | Final controlled pilot gate result and evidence summary |
| [runbooks/PILOT_LAUNCH_PACK.md](./runbooks/PILOT_LAUNCH_PACK.md) | One-page pilot scope, incident, and go/no-go pack for the first clinic live cycle |
| [runbooks/PILOT_START_CHECKLIST.md](./runbooks/PILOT_START_CHECKLIST.md) | First-day pilot start checklist for opening the clinic to real users |
| [runbooks/PILOT_DAY1_GO_NO_GO_WINDOWS_HOST.md](./runbooks/PILOT_DAY1_GO_NO_GO_WINDOWS_HOST.md) | Filled day-1 go/no-go result for the real Windows pilot host |
| [runbooks/PILOT_INCIDENT_NOTE_TEMPLATE.md](./runbooks/PILOT_INCIDENT_NOTE_TEMPLATE.md) | One-screen template for recording pilot incidents and stop conditions |
| [runbooks/PILOT_7_DAY_EVIDENCE_PACK.md](./runbooks/PILOT_7_DAY_EVIDENCE_PACK.md) | Seven-day live pilot evidence pack |
| [runbooks/OPERATIONAL_PROOF_PACKET.md](./runbooks/OPERATIONAL_PROOF_PACKET.md) | Minimal execution packet for the Linux/VPS, release delta, and clinic-like data proofs |
| [runbooks/CLINIC_PILOT_CONTOUR_TEMPLATE.md](./runbooks/CLINIC_PILOT_CONTOUR_TEMPLATE.md) | Template for naming one real clinic pilot contour before the first live cycle |
| [ONLINE_QUEUE_SYSTEM_GUIDE.md](./ONLINE_QUEUE_SYSTEM_GUIDE.md) | Historical online queue guide (deprecated; keep for reference only) |
| [BATCH_UPDATE_ARCHITECTURE.md](./BATCH_UPDATE_ARCHITECTURE.md) | Batch operations |

### EMR & Autocomplete
| Document | Description |
|----------|-------------|
| [EMR_SMART_AUTOCOMPLETE_UX.md](./EMR_SMART_AUTOCOMPLETE_UX.md) | Smart autocomplete UX |
| [DOCTOR_AUTOCOMPLETE_README.md](./DOCTOR_AUTOCOMPLETE_README.md) | Doctor history autocomplete |
| [COMPLAINTS_FIELD_SPEC.md](./COMPLAINTS_FIELD_SPEC.md) | Complaints field specification |

### AI Integration
| Document | Description |
|----------|-------------|
| [AI_ARCHITECTURE_RULE.md](./AI_ARCHITECTURE_RULE.md) | AI architecture rules |
| [AI_INTEGRATION_GUIDE.md](./AI_INTEGRATION_GUIDE.md) | AI integration |
| [architecture/AI_LANDING_FACTORY_ARCHITECTURE.md](./architecture/AI_LANDING_FACTORY_ARCHITECTURE.md) | AI-first landing page factory blueprint |
| [runbooks/AI_LANDING_FACTORY_RUNBOOK.md](./runbooks/AI_LANDING_FACTORY_RUNBOOK.md) | Operational flow for landing runs |
| [AI_MCP_FRONTEND_INTEGRATION_GUIDE.md](./AI_MCP_FRONTEND_INTEGRATION_GUIDE.md) | MCP frontend |
| [MCP_INTEGRATION_GUIDE.md](./MCP_INTEGRATION_GUIDE.md) | MCP backend |

---

## 🔌 API Reference

| Document | Description |
|----------|-------------|
| [API_REFERENCE.md](./API_REFERENCE.md) | General API reference |
| [QUEUE_API_REFERENCE.md](./QUEUE_API_REFERENCE.md) | Queue API endpoints |
| [QUEUE_BATCH_API_USAGE_GUIDE.md](./QUEUE_BATCH_API_USAGE_GUIDE.md) | Batch API guide |
| [DOCTOR_AUTOCOMPLETE_API.md](./DOCTOR_AUTOCOMPLETE_API.md) | Autocomplete API |

---

## 🚀 Deployment & Operations

| Document | Description |
|----------|-------------|
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | Full deployment guide |
| [BACKUP_RESTORE_PROCEDURES.md](./BACKUP_RESTORE_PROCEDURES.md) | Backup & restore |
| [PRODUCTION_SECURITY.md](./PRODUCTION_SECURITY.md) | Security in production |
| [README_env.md](./README_env.md) | Environment variables |
| [runbooks/LOCAL_DEV_ONBOARDING.md](./runbooks/LOCAL_DEV_ONBOARDING.md) | Local setup (Postgres-first) |

---

## 📖 User Guides

| Document | Audience |
|----------|----------|
| [ADMIN_QUICK_GUIDE.md](./ADMIN_QUICK_GUIDE.md) | Admins |
| [QR_QUEUE_USER_MANUAL.md](./QR_QUEUE_USER_MANUAL.md) | Registrars |
| [QR_EDITING_RULES.md](./QR_EDITING_RULES.md) | QR operations |
| [TELEGRAM_PWA_GUIDE.md](./TELEGRAM_PWA_GUIDE.md) | Telegram users |

---

## 🧪 Testing & QA

| Document | Description |
|----------|-------------|
| [AI_MCP_QA_CHECKLIST.md](./AI_MCP_QA_CHECKLIST.md) | AI/MCP QA checklist |
| [DOCTOR_AUTOCOMPLETE_CHECKLIST.md](./DOCTOR_AUTOCOMPLETE_CHECKLIST.md) | Autocomplete checklist |
| [runbooks/PR_REVIEW_QUALITY_GATES.md](./runbooks/PR_REVIEW_QUALITY_GATES.md) | PR review gates for contract, RBAC, realtime, resilience, scope, and release readiness |
| [runbooks/PR_REVIEW_PRACTICE_TRACK.md](./runbooks/PR_REVIEW_PRACTICE_TRACK.md) | 12-week practical track for applying PR review quality gates |
| [reports/PRINT_PANEL_AUDIT_REPORT.md](./reports/PRINT_PANEL_AUDIT_REPORT.md) | Unified print audit across registrar, specialists, lab, and admin panels |
| [runbooks/MESSAGING_CONTRACT.md](./runbooks/MESSAGING_CONTRACT.md) | Historical messaging contract and rollout evidence |
| [runbooks/MESSAGING_QA_CHECKLIST.md](./runbooks/MESSAGING_QA_CHECKLIST.md) | Historical messaging QA evidence |
| [PANEL_QA_CHECKLIST.md](./PANEL_QA_CHECKLIST.md) | SSOT runbook for panel verification with step-by-step progress tracking |
| [ADM-06_BROWSER_SMOKE.md](./ADM-06_BROWSER_SMOKE.md) | Compact manual smoke for the service-catalog prefix guardrail |

---

## 📁 Archives

Historical reports, completed fixes, and obsolete documentation are in [archives/](./archives/).

---

## 🎯 Quick Navigation

### "I need to understand the system"
1. Start with [ROLES_AND_ROUTING.md](./ROLES_AND_ROUTING.md)
2. Then [QUEUE_SYSTEM_ARCHITECTURE.md](./QUEUE_SYSTEM_ARCHITECTURE.md)
3. Then [runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md](./runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md)
4. Then [AUTHENTICATION_SYSTEM_FINAL_GUIDE.md](./AUTHENTICATION_SYSTEM_FINAL_GUIDE.md)

### "I'm an AI agent making changes"
1. **READ FIRST:** [AUTHENTICATION_LAWS_FOR_AI.md](./AUTHENTICATION_LAWS_FOR_AI.md)
2. **READ SECOND:** [DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md](./DOCTOR_AUTOCOMPLETE_LAWS_FOR_AI.md)
3. Then [runbooks/PR_REVIEW_QUALITY_GATES.md](./runbooks/PR_REVIEW_QUALITY_GATES.md)
4. Then specific area docs

### "I need to deploy"
1. [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
2. [DOCTOR_AUTOCOMPLETE_DEPLOYMENT.md](./DOCTOR_AUTOCOMPLETE_DEPLOYMENT.md)
3. [BACKUP_RESTORE_PROCEDURES.md](./BACKUP_RESTORE_PROCEDURES.md)
4. [runbooks/CLINIC_HOST_INSTALL_RUNBOOK.md](./runbooks/CLINIC_HOST_INSTALL_RUNBOOK.md)
5. [runbooks/CLINIC_WINDOWS_PILOT_HOST_RUNBOOK.md](./runbooks/CLINIC_WINDOWS_PILOT_HOST_RUNBOOK.md)
6. [runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md](./runbooks/CLINIC_PRE_RELEASE_CHECKLIST.md)
7. [runbooks/CLINIC_PRE_RELEASE_EVIDENCE_PACK.md](./runbooks/CLINIC_PRE_RELEASE_EVIDENCE_PACK.md)
8. [runbooks/CLINIC_RELEASE_CANDIDATE_SUMMARY.md](./runbooks/CLINIC_RELEASE_CANDIDATE_SUMMARY.md)
9. [runbooks/CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md](./runbooks/CLINIC_PILOT_CONTOUR_WINDOWS_HOST.md)
10. [runbooks/CLINIC_WINDOWS_OPERATOR_CARD.md](./runbooks/CLINIC_WINDOWS_OPERATOR_CARD.md)
11. [runbooks/PILOT_START_CHECKLIST.md](./runbooks/PILOT_START_CHECKLIST.md)
12. [runbooks/PILOT_DAY1_GO_NO_GO_WINDOWS_HOST.md](./runbooks/PILOT_DAY1_GO_NO_GO_WINDOWS_HOST.md)
13. [runbooks/CLINIC_UPDATE_REHEARSAL_RUNBOOK.md](./runbooks/CLINIC_UPDATE_REHEARSAL_RUNBOOK.md)
14. [runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md](./runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md)

### "I need local onboarding"
1. [runbooks/LOCAL_DEV_ONBOARDING.md](./runbooks/LOCAL_DEV_ONBOARDING.md)
2. [runbooks/POSTGRES_DR_RUNBOOK.md](./runbooks/POSTGRES_DR_RUNBOOK.md)
3. [README_env.md](./README_env.md)

### "I need to integrate with API"
1. [API_REFERENCE.md](./API_REFERENCE.md)
2. [QUEUE_API_REFERENCE.md](./QUEUE_API_REFERENCE.md)
3. [DOCTOR_AUTOCOMPLETE_API.md](./DOCTOR_AUTOCOMPLETE_API.md)

---

*Last Updated: 2026-04-07*
