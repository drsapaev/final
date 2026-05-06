# Wave 2C Registrar Batch Design Intent

Date: 2026-05-05
Mode: docs-only replacement for stale PR #78

## Intent

The registrar batch queue path should stay a narrow batch allocator boundary. It should explain the current mounted behavior before any future redesign tries to broaden it.

The intended current-main contract is:

- frontend/request `specialist_id` identifies the doctor profile (`doctors.id`)
- backend groups submitted services by resolved doctor
- same-doctor services collapse into one queue entry for the batch
- first service `queue_tag` selects the queue bucket for that entry
- duplicate checks operate within that resolved queue bucket

## Why This Shape Exists

This shape matches the behavior carried forward and corrected in replacement PR #264. It avoids mixing three different identities:

- user account id (`users.id`)
- doctor profile id (`doctors.id`)
- service queue bucket (`queue_tag`)

The old #78 text blurred those identities by using `specialist_user_id`. That is useful as a historical warning, but not as a current contract.

## Decisions Held Stable

Keep these stable until a dedicated runtime PR changes them with tests:

- doctor profile id is the owner identity for batch grouping
- service queue tag is a queue bucket selector, not the grouping owner
- same-doctor batch services should not create multiple active rows by default
- docs must call out whether they describe current runtime or proposed target behavior

## Open Product Question

A future redesign can still decide that same-doctor services with different queue tags should become separate queue claims. That is not a docs-only decision. It requires runtime changes, migration-aware tests, and compatibility proof for queue numbering and duplicate behavior.
