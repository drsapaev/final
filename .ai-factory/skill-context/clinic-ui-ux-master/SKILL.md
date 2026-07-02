# `clinic-ui-ux-master` Context

Read `../common/SKILL.md` first.

This is an AI Factory bridge, not the source of truth.

## Source Of Truth

Use the repo Codex skill as the canonical UI/UX rule set:

- `.agents/skills/clinic-ui-ux-master/SKILL.md`
- `.agents/skills/clinic-ui-ux-master/references/*.md`

Do not duplicate or reinterpret those rules inside `.ai-factory`. If an AI Factory workflow needs clinic UI/UX guidance, load the Codex skill first and then use this file only to preserve AI Factory context conventions.

## When To Use

Use this bridge for:

- substantial clinic frontend UI/UX audits
- design-system convergence
- mixed inline-style, legacy-class, or MUI cleanup
- role workflow polish for Admin, Doctor, Registrar, Cashier, Lab, Patient
- visual QA planning and evidence capture

## Rules

- Clinic usability, accessibility, role clarity, and current project architecture win over generic design advice.
- Keep implementation slices small and validation-backed.
- Do not change runtime behavior, route semantics, API contracts, RBAC, queue, payment, EMR, lab, or backend logic as part of visual cleanup.
- For AI Factory plans, include the active `clinic-ui-ux-master` reference files used.
