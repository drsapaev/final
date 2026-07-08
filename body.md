refactor: deduplicate IndependentQueueEntry creation (406→210 LOC) (#2032)

_full_update_create_independent_entries had ~120 lines of near-identical
code duplicated between the first_fill_qr branch (additional services)
and the editing branch (new services). Both branches:

  1. Resolve target_queue_id (by queue_tag, or auto-create DailyQueue)
  2. Compute next_number via SQL
  3. Compute item_price with discounts (repeat/benefit/all_free)
  4. Create OnlineQueueEntry with services/service_codes JSON

Extracted 2 shared helpers:

1. _full_update_resolve_target_queue_id (48 LOC) — resolves the target
   DailyQueue ID for a service based on its queue_tag. Finds existing
   queue by day+tag+active, or auto-creates via queue_service.

2. _full_update_create_single_independent_entry (89 LOC) — creates one
   IndependentQueueEntry for a service: resolves target queue, computes
   next_number, computes price with discounts, creates the entry with
   services/service_codes JSON.

Both branches now call _full_update_create_single_independent_entry in
a simple loop, reducing the function from 406 to 210 LOC.

Test results (SQLite local): 14 pass / 8 fail (unchanged from PR #2031).
No regressions. Remaining 8 failures are pre-existing environmental
(SQLite vs Postgres).

Function sizes after this PR:
  _full_update_create_independent_entries:   210 lines (was 406)
  _full_update_resolve_target_queue_id:       48 lines (new)
  _full_update_create_single_independent_entry: 89 lines (new)

All full_update_* functions are now ≤210 LOC except:
  _full_update_handle_all_free_visit:        349 lines (future work)
  _full_update_collect_existing_services:    320 lines (future work)

Co-authored-by: Z User <z@container>
