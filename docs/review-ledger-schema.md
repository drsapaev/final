# Review Resolution Ledger — Schema & Methodology

**Status:** Living document — updated incrementally as new reviews arrive.
**Last full audit:** 2026-08-01 (1157 comments classified)

---

## Schema

The ledger (`docs/review-resolution-ledger.csv`) contains one row per GitHub review comment with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `comment_id` | int | GitHub comment ID (unique identifier) |
| `pr` | int | Pull request number |
| `date` | string | Comment creation date (YYYY-MM-DD) |
| `severity` | string | P0 (critical) / P1 (high) / P2 (medium) |
| `file` | string | File path at time of review |
| `line` | int | Line number at time of review |
| `status` | string | 8-status classification (see below) |
| `owner` | string | Domain owner: Frontend / Backend / DevOps / Documentation / AI Tooling |
| `review_agent` | string | Which specialized agent verified this comment |
| `confidence` | float | Confidence score 0.00–1.00 (0 = unverified, 1 = certain) |
| `evidence_type` | string | How the verdict was reached: Commit/PR, ADR, Static analysis, Manual, Test, N/A |
| `verification_date` | string | When the comment was last verified (YYYY-MM-DD) |
| `evidence` | string | Specific proof: commit SHA, PR number, ADR reference, identifiers searched, explanation |
| `issue` | string | Extracted issue title from review comment |

---

## 8-Status Model

| Status | Meaning | Confidence | Action |
|--------|---------|-----------|--------|
| **FIXED** | Issue confirmed and fixed by a specific PR | 1.00 | None — closed |
| **SUPERSEDED** | Code rewritten; issue eliminated by different implementation | 0.85 | None — closed |
| **OBSOLETE** | File deleted, renamed, or .jsx→.tsx migration | 1.00 | None — closed |
| **WONT_FIX** | Architectural decision, intentional design, or historical document | 0.80–0.95 | None — closed with justification |
| **UNVERIFIED** | Not yet verified — requires domain-specific check | 0.00 | **Action required** |
| **OUT_OF_SCOPE** | Requires domain expert not available in current audit | 0.50 | **Assign to owner** |
| **DUPLICATE** | Same issue as another comment | 1.00 | None — closed |
| **OPEN** | Confirmed open issue requiring fix | 1.00 | **Fix required** |

---

## Specialized Review Agents

Each comment is assigned to the most appropriate specialized agent:

### 1. Mechanical Verification Agent (Level 1)
- **Scope:** Automated checks — file existence, identifier search, pattern matching
- **Confidence:** 0.85–1.00
- **Used for:** SUPERSEDED (code rewritten), OBSOLETE (file deleted), bot comments
- **Can do:** grep, file existence check, identifier search, line range check

### 2. Frontend Review Agent (Level 2–3)
- **Scope:** React, TypeScript, hooks, rendering, memoization, accessibility
- **Knowledge:** React 18, TypeScript strict:true, AsyncState, ChatSessionState, Zod, Playwright
- **Confidence:** 0.80–0.95
- **Used for:** Frontend P1/P2 issues requiring semantic verification

### 3. Backend Review Agent (Level 3)
- **Scope:** FastAPI, SQLAlchemy 2, Alembic, asyncio, PostgreSQL, Pydantic, transactions
- **Knowledge:** Transaction isolation, JWT, RBAC, session lifecycle, async safety
- **Confidence:** 0.80–0.95
- **Used for:** Backend Python review comments (currently OUT_OF_SCOPE — pending assignment)

### 4. CI Agent (Level 2)
- **Scope:** GitHub Actions, matrix, cache, CodeQL, Playwright, k6
- **Knowledge:** Workflow YAML, permissions, path filters, runner types
- **Confidence:** 0.85–0.95
- **Used for:** CI/CD workflow comments

### 5. Security Agent (Level 3)
- **Scope:** JWT, RBAC, XSS, CSRF, SSRF, secrets, crypto
- **Knowledge:** OWASP, auth flows, token management
- **Confidence:** 0.85–0.95
- **Used for:** Security-tagged review comments

### 6. Architecture Agent (Level 4)
- **Scope:** ADR compliance, SSOT, ownership, boundaries, dependency direction
- **Knowledge:** ADR-0001 through ADR-0018, project architecture
- **Confidence:** 0.95
- **Used for:** Architectural decision comments, route mocking, state pattern disputes

---

## Evidence Types

| Type | Description | Example |
|------|-------------|---------|
| **Commit/PR** | Specific PR that fixed the issue | "PR #2638: PII replaced with synthetic data" |
| **ADR** | Architectural Decision Record reference | "ADR-0018: mapper-layer validation replaces live backend" |
| **Static analysis** | Automated code analysis | "Identifiers ['functionName'] not found in current file" |
| **Test** | Test coverage evidence | "Test at src/types/__tests__/chat-session-state.test.ts covers this transition" |
| **Manual** | Manual code review | "Verified by reading code at line X — pattern matches" |
| **Automated classification** | Bot comment classification | "github-actions[bot] lifecycle recommendation" |
| **N/A** | Not yet verified | "Pending verification" |

---

## Incremental Update Process

When new review comments arrive:

1. **Fetch** new comments via GitHub API (`pulls/comments` endpoint)
2. **Classify** using Mechanical Verification Agent first (file existence, pattern matching)
3. **Route** remaining UNVERIFIED to specialized agent based on `owner` field
4. **Verify** each comment with evidence (call graph, test, ADR, commit)
5. **Update** ledger row with: status, review_agent, confidence, evidence_type, verification_date
6. **Fix** any confirmed OPEN issues in small thematic PRs

This ensures the ledger is a **living registry**, not a one-time report. Subsequent audits can skip already-verified comments (confidence > 0.80) and focus only on new or changed code.

---

## Current State (2026-08-01)

| Status | Count | Owner breakdown |
|--------|-------|-----------------|
| FIXED | 15 | Frontend: 10, DevOps: 5 |
| SUPERSEDED | 357 | Frontend: 180, Backend: 120, DevOps: 40, Docs: 17 |
| OBSOLETE | 467 | Frontend: 250, Backend: 150, DevOps: 40, Docs: 27 |
| WONT_FIX | 143 | Frontend: 30, Backend: 50, DevOps: 40, Docs: 23 |
| UNVERIFIED | 21 | Frontend: 6, AI Tooling: 15 |
| OUT_OF_SCOPE | 154 | Backend: 150, AI Tooling: 4 |
| OPEN | 0 | — |
| **Total** | **1157** | |
