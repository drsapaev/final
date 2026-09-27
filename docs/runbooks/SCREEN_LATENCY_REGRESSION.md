# First-Screen Latency Regression Check

Use this when changing Registrar, Admin, Doctor/Cardiology, shared data
loading, or queue WebSocket behavior. The symptom to protect is the wait from
opening a screen until its real rows or queue content appear. FastAPI process
startup is a separate measurement.

## Comparable baseline

On 2026-09-24, after the local PostgreSQL move and the queue WebSocket fix,
the operator observed Registrar and Admin rows in under 1 second and the
Cardiology queue in 1–2 seconds in Edge. These are observations on one host,
not universal latency promises. Compare the same role, browser, network, data
volume, and cold/warm state before and after a change; record the conditions.

## Check the path to visible content

1. Measure a cold first opening and a return to the same section. Record when
   rows or queue content appear, not merely the first paint or a spinner.
2. In browser Network/Performance tools, inspect initial JavaScript chunks,
   request start/end times, and repeated requests. Distinguish asset download,
   serialized or duplicate API calls, backend work, database work, and
   WebSocket activity before choosing a fix.
3. Keep independent prerequisites parallel where their contracts allow it.
   Do not alter queue identity, ordering, or other backend-owned decisions to
   make a request waterfall look shorter. In the Cardiology panel, inactive
   Appointments, Visit, ECG, and edit-patient code is loaded on demand from
   `frontend/src/pages/CardiologistPanelUnified.tsx`; confirm these chunks do
   not join the initial static route load without a measured reason.
4. For `/ws/queue`, a disconnect or receive error must end the receive loop,
   cancel the heartbeat, and release the room. Run
   `backend/tests/unit/test_queue_ws_disconnect.py`. A closed socket that
   repeatedly logs receive errors can consume a CPU core and slow unrelated
   screens. Do not log a raw URL query, token, receive-error body, or queue
   broadcast payload.
5. Recheck with synthetic data in the isolated Linux staging environment
   described in `docs/runbooks/AGENT_SESSION_WORKTREES.md`. Verify the
   deployed commit and collect before/after timings and API/asset evidence.
   If a user measures production, ask only for timings; never request login
   credentials or patient details.

For a PR touching these paths, report the first-content timing for the
affected role, whether the delay is asset/API/backend/DB/WebSocket-related,
the targeted regression check, and anything not measured. A pass on the
disconnect unit test does not replace the full staging validation checklist
required before a whole-system or deployment claim.
