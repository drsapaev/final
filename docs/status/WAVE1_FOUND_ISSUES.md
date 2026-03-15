# Wave 1 Found Issues

Date: 2026-03-06

## Issues

| ID | Severity | Area | Evidence | Current state |
|---|---|---|---|---|
| W1-F001 | high | CI stability | unified run `22748643145`, job `🎨 Frontend тесты` | open |
| W1-F002 | high | Frontend tests | local repro: `TwoFactorManager` mock missing `tokenManager` export | open |
| W1-F003 | medium | Docs truth | `46` optimistic claim matches across `docs/**` | open |
| W1-F004 | medium | Contract visibility | parity gate passes but total coverage low (`coverage_pct=11.51`) | open |
| W1-F005 | medium | RBAC audit reproducibility | `test_role_routing.py` failed (`401/429`) while matrix tests pass | pending human review |
| W1-F006 | high | Backend static security | `bandit` high findings (`18`), dominated by `B701` and `B324` | open |
| W1-F007 | high | Backend dependencies | `pip-audit`: `33` vulns in `15` packages | open |
| W1-F008 | high | Frontend dependencies | `npm audit`: `16` vulns (`2 critical`, `7 high`) | open |

## Notes

- W1-F001 and W1-F002 are immediate stabilization blockers.
- W1-F005 requires a human decision because it touches auth audit policy quality and protected-domain confidence.
- W1-F006/W1-F007/W1-F008 were intentionally not auto-remediated in Wave 1 per hard rule.
