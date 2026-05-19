# Report Templates

Use these templates to keep audits and implementation reports consistent.

## Audit Report

```markdown
**Scope**
Mode:
Routes:
Roles:
Files inspected:
Browser evidence:

**UI Layer Inventory**
Canonical components:
Inline styles:
Legacy classes:
MUI imports:
Hardcoded tokens:
Relevant tests:

**Findings**
P0:
P1:
P2:
P3:

**Phased Plan**
Phase 1:
Phase 2:
Phase 3:

**Validation Plan**
Static:
Automated:
Browser:

**Stop Conditions**
```

## Shape Brief

```markdown
**Shape Brief**
Role:
Workflow:
Primary action:
Risk level:
Current UI layer:
Drift sources:
Design direction:
Out of scope:
Validation:
```

## Implementation Report

```markdown
**Changed**

**Why Safe**

**Validation**

**Not Changed**

**Remaining Risks**

**Next Smallest Slice**
```

## Visual QA Report

```markdown
**Visual QA**
Route:
Role:
Viewport(s):
Before:
After:
Console/network:
Keyboard/focus:
Result:
Residual risk:
```

## Finding Format

```markdown
- `P1` <short title> - <route/file>. Evidence: <line/screenshot/static search>. Impact: <workflow risk>. Fix: <smallest safe change>.
```

## Source Evidence Format

Use file links with exact paths and line numbers when available. Prefer one high-signal reference over many vague references.

Good:

```markdown
[AdminPanel.jsx](/abs/path/frontend/src/pages/AdminPanel.jsx:1234) repeats local grid and card layout styles.
```

Weak:

```markdown
The admin UI has too much styling.
```

