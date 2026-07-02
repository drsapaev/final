# Backend SSOT Contract

> **Status**: Draft  
> **Created**: 2025-12-25  
> **Purpose**: Define required guarantees from backend to enable full SSOT frontend

---

## 🎯 Goal

This document defines the API contract that backend MUST fulfill for frontend to operate in pure SSOT mode (no heuristics, no fallbacks, no guessing).

---

## ✅ Required Guarantees

### 1. `department_key` — MUST be present

| Field | Requirement |
|-------|-------------|
| **Name** | `department_key` |
| **Always present** | ✅ Yes, never null/undefined |
| **Stable enum** | `cardiology`, `lab`, `dentistry`, `derma`, `echokg`, `procedures` |
| **Source** | Backend determines from queue/service mapping |

**Frontend impact**: When guaranteed, remove `specialty`/`queue_tag` fallback in `isInDepartment`.

---

### 2. `queue_tag` — MUST match `department_key`

| Field | Requirement |
|-------|-------------|
| **Name** | `queue_tag` |
| **Always present** | ✅ Yes |
| **Consistency** | Must equal `department_key` for same entry |

**Frontend impact**: Can simplify to single field check.

---

### 3. Stats Endpoint (Optional but Desired)

```json
GET /registrar/queues/stats

{
  "cardiology": 5,
  "lab": 12,
  "dentistry": 3,
  "all": 20
}
```

**Frontend impact**: Replace client-side `departmentStats` calculation.

---

### 4. Scoped Filtering (Future Improvement)

```
GET /registrar/queues/today?department=cardiology
```

**Frontend impact**: Reduce payload size, improve performance.

---

## 🚫 No Mixed Responsibilities

| Rule | Description |
|------|-------------|
| Frontend does NOT infer departments | Backend provides `department_key` |
| Frontend does NOT deduplicate | Backend returns unique entries |
| Frontend does NOT merge | Each API row = one UI row |

---

## 📋 Checklist for Backend Team

Before claiming SSOT compliance:

- [ ] `department_key` is always present in `/registrar/queues/today` response
- [ ] `department_key` uses stable enum values
- [ ] `queue_tag` matches `department_key`
- [ ] No duplicate entries returned for same patient+department+date
- [ ] Stats endpoint available (optional)

---

## 🔄 Migration Path

1. **Phase 1 (Current)**: Frontend uses fallback `queue_tag || specialty || department_key`
2. **Phase 2 (After backend fix)**: Frontend uses only `department_key`
3. **Phase 3 (Optional)**: Backend provides stats, frontend removes `departmentStats` calculation

---

*This contract must be reviewed and agreed upon by backend team before implementation.*
