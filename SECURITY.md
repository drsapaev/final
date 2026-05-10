# Security Policy

This repository contains a clinic EMR and operations platform. Security reports
must be handled with extra care because the product can involve patient data,
medical workflows, billing, Telegram integration, and audit logs.

## Supported Branch

Security fixes are accepted for the default branch:

- `main`

## Reporting a Vulnerability

Use GitHub private vulnerability reporting:

https://github.com/drsapaev/final/security/advisories/new

Do not open a public issue for a vulnerability.

## Do Not Include Sensitive Data

Reports must not include:

- real patient data or medical records
- clinic production credentials
- payment tokens or callback secrets
- Telegram bot tokens or webhook secrets
- database dumps, access tokens, cookies, or session IDs

Use synthetic examples, redacted logs, and minimal reproduction steps.

## High Priority Areas

Please mark reports as high impact when they affect:

- authentication, session handling, or password reset flows
- authorization, RBAC, or cross-role data access
- EMR, lab, queue, appointment, or patient data exposure
- payment callback signature validation or idempotency
- audit log integrity or critical action traceability
- Telegram bot/webhook authorization or token handling
- secret leakage, dependency compromise, or CI/CD credential exposure

## Expected Response

Best effort response targets:

- acknowledge receipt within 3 business days
- triage severity within 10 business days
- coordinate a fix, mitigation, or disclosure timeline based on impact

The project may request additional reproduction detail, but never real patient
data or production secrets.

## AI and Medical Safety

AI-assisted features must remain draft or suggestion workflows. A vulnerability
that allows AI output to become an autonomous medical decision, bypass clinical
approval, leak patient data, or execute unsafe tools should be reported as a
security issue.
