# Next Execution Unit After Status Navigation Index Cleanup

Follow-up status:

- completed via `docs/architecture/W2D_HISTORICAL_REENTRY_DOC_NORMALIZATION.md`

Recommended next step:

- normalize older historical re-entry docs so they point to the current status
  landing page and canonical SSOT

Bounded candidate set:

- `docs/status/W2D_THREAD_HANDOFF.md`
- `docs/status/OPENHANDS_FIRST_10_TASKS.md`
- `docs/status/AI_FACTORY_OPENHANDS_PRECHECK.md`

Required entry conditions:

- preserve those files as historical records, not rewritten summaries
- add only short “historical / current SSOT” framing where needed
- keep `cashier_api_service.py` and other protected code paths out of scope

Why:

- the current status layer now has a landing page
- the next remaining navigation risk is older re-entry docs being mistaken for
  the live queue
- this is still lower risk and higher honesty than reopening completed
  protected residue slices
