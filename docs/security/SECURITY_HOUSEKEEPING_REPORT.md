# Security Housekeeping Report

Date: 2026-03-06  
Task: W1-T4  
Contract: `.ai-factory/contracts/w1-security-housekeeping.contract.json`  
Status: `done`

## Scope and Hard Rule

- Scope: analysis + remediation planning only.
- Hard rule enforced: **no dependency upgrades in W1-T4**.
- No package version changes were made.

## Mandatory Commands and Outcomes

### Backend dependency audit

- Command: `pip-audit --format json`
- Exit: `1` (expected when vulnerabilities found)
- Summary:
  - `15` packages with vulnerabilities
  - `33` vulnerability records
  - highest-volume packages:
    - `aiohttp` (`8`)
    - `setuptools` (`5`)
    - `cryptography` (`3`)
    - `urllib3` (`3`)

### Backend static security scan

- Command: `bandit -r . -f json`
- Exit: `1` (issues found)
- Note: initial run with shorter timeout was insufficient; re-run completed.

- Actionable summary command:
  - `bandit -r app -lll`
  - high findings summary:
    - `18` high
    - `16` medium
    - `127` low
  - high categories:
    - `B701` (`jinja2_autoescape_false`) = `11`
    - `B324` (`md5 usage`) = `7`

### Frontend dependency audit

- Command: `npm audit --json`
- Exit: `1` (expected when vulnerabilities found)
- Summary:
  - total `16`
  - critical `2`
  - high `7`
  - moderate `7`
  - direct high/critical examples:
    - `jspdf`, `jspdf-autotable`, `axios`, `react-router-dom`, `rollup`

## Prioritized Remediation Plan (No Upgrades Executed Here)

1. **P0**: isolate and remediate direct critical/high frontend packages in bounded PR slices.
2. **P1**: address backend high findings:
   - Jinja environment hardening (`autoescape` decisions by rendering context).
   - MD5 usage review in caching vs security-sensitive signing paths.
3. **P1**: dependency triage by exploitability in runtime context (not by count only).
4. **P2**: medium/low housekeeping with explicit max-diff limits per task.
5. **P2**: separate remediations for protected domains (payment/auth) with mandatory human review.

## Constraints Compliance

- Dependency upgrades: not performed.
- Code refactors: not performed.
- Output produced: analysis + actionable remediation queue.

## Commands Executed

- `pip-audit --format json`
- `bandit -r . -f json`
- `bandit -r app -lll`
- `npm audit --json`
