# Settings Contract Restoration Plan

Scope:
- restore the live `GET/PUT /settings` contract for the active Admin settings
  page
- remove only proven orphan residue directly tied to the stale settings
  surface

Evidence:
- `frontend/src/pages/Settings.jsx` still uses `/settings`
- `backend/app/api/v1/endpoints/settings.py` existed but was not mounted
- `backend/openapi.json` did not publish `/api/v1/settings`
- middleware already treated `/api/v1/settings` as an Admin/settings-permission
  surface
- detached plural `settings_*` backend files and stale frontend settings client
  helpers had no live imports

Why this is safe:
- the runtime change restores an already intended live route rather than
  opening a new protected domain
- the route surface stays narrow: category read plus single key/value upsert
- orphan cleanup is limited to files and blocks with explicit no-import proof

Out of scope:
- activation cleanup or activation contract repair
- clinic-management branch-scope review
- any auth, payment, queue, or EMR mutation beyond existing settings access
