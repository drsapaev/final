[<- Previous Page](AI_MODULE.md) | [Back to README](../README.md) | [Next Page ->](DEPLOYMENT.md)

# Testing

## Vitest: Fake Timers Rule

**Any test file that calls `vi.useFakeTimers()` MUST call `vi.useRealTimers()` in `afterEach` or `afterAll`.**

This project uses `pool: 'forks'` with `singleFork: true` in `vitest.config.ts`. In this mode, all test files share a single Node.js process. If a test file enables fake timers but does not restore real timers in cleanup, fake timers **leak into subsequent files** and can cause the vitest process to **hang indefinitely** during shutdown.

This was the root cause of a CI process hang that was investigated and fixed in August 2026 (see commit `9706ecda` and worklog `v5`–`v10` investigation).

### Correct pattern

```ts
describe('myFeature', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers(); // ← REQUIRED
  });

  it('does something with timers', () => { ... });
});
```

### Enforcement

- A global safety net in `src/test/setup.ts` calls `vi.useRealTimers()` in `afterEach`.
- An ESLint custom rule (`custom/no-fake-timers-without-cleanup`) enforces this at lint time. Files with `vi.useFakeTimers()` but no `vi.useRealTimers()` in `afterEach`/`afterAll` will fail the lint check.

## Local Windows Python Launchers

- General Python: `C:\final\scripts\run_python.ps1 <python args>`
- Backend pytest: `C:\final\scripts\run_backend_pytest.ps1 <tests...>`

Use these instead of bare `python`, `py`, or pgAdmin Python in local Windows shells. The backend pytest launcher selects a Python 3.11+ interpreter that has `pytest`, runs from `backend/`, and sets `PYTHONPATH` to the backend root.

## Targeted Checks Run During Recovery

| Area | Representative checks |
|---|---|
| Routing | `npm.cmd run test:run -- src/routing/__tests__/routeContract.test.js` |
| Frontend build | `npm.cmd run build` |
| AI component | `npm.cmd run test:run -- src/components/ai/__tests__/AIAssistant.test.jsx` |
| Backend syntax | `python -m py_compile ...` on changed endpoint files |
| AI services | `python -m pytest backend\tests\unit\test_ai_tracking_api_service.py backend\tests\unit\test_admin_ai_service.py -q` |
| Telegram | `pytest backend\tests\unit\test_telegram_webhook_security.py -q` |
| Visits | `pytest backend\tests\unit\test_visits_router_service_wiring.py -q` |
| Alembic | `python -m alembic heads --verbose`, `branches --verbose`, `history -r base:head` |

## Known Testing Gaps

- Full backend suite was not proven in this recovery session.
- `backend/tests/unit/test_ai_chat_api_service.py` is blocked by `@pytest.mark.asyncio` while `backend/pytest.ini` uses `--strict-markers` without declaring `asyncio`.
- Clean online `alembic upgrade head` remains blocked locally until an explicitly disposable PostgreSQL target is available. Task 25 verified a single linear Alembic head (`0022_service_audit_log`) and attempted to create a throwaway database on the reachable local PostgreSQL server, but the configured role does not have `CREATEDB`; staging `55432`, Docker/Compose, and `psql` were unavailable.
- Browser role-flow smoke still needs real safe credentials and a controlled test database.

## Minimum Critical Flow Tests

- Registrar creates patient and visit.
- Patient enters queue.
- Doctor calls patient and saves EMR.
- Payment is created and callback is processed idempotently.
- Reports update.
- Role access and cross-patient denial paths are enforced.
- Telegram notification path is mocked.
- AI suggestion stays draft-only and requires approval.

## See Also

- [Recovery Plan](RECOVERY_PLAN.md)
- [API](API.md)
- [Deployment](DEPLOYMENT.md)
