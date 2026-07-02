# Wave 2C Registrar Wizard Design Intent

Date: 2026-03-08
Mode: contract review, docs-only

## Evidence Used

- `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
- `docs/architecture/W2C_REGISTRAR_WIZARD_SUBFLOWS.md`
- `docs/architecture/W2C_REGISTRAR_WIZARD_POLICY_COUPLING.md`
- `docs/status/W2C_REGISTRAR_WIZARD_CLASSIFICATION.md`
- `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`
- `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md`
- `docs/architecture/W2C_QUEUE_NUMBERING_CONTRACT.md`

## Design Signals From ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md

The design document consistently points to queue ownership by queue claim rather
than by “one specialist only”:

- “one patient may have multiple queue entries”
- “new services create new queue entries with the current edit time”
- morning assignment creates one row for each `queue_tag`
- `queue_tag` determines which queue the patient enters

At the same time, the document is not reliable for runtime details such as
`specialist_id` foreign-key semantics. Those details stay runtime-grounded.

## Answer 1: Should wizard cart flow have specialist-level claim ownership?

No, not as the primary local model.

That would conflict with the design signals above:

- wizard cart can fan out one visit into multiple queue claims
- morning-assignment-style allocation is already queue-tag driven
- “new services later in the same day” is described as creating new queue entries
  when the new service introduces a new queue claim

Specialist identity still matters as queue metadata and for initial queue
bootstrap, but it is not the primary claim key for this family.

## Answer 2: Should wizard claim ownership be queue_tag-level?

Yes.

More precisely, wizard-family claim ownership should be based on the resolved
queue claim represented by `queue_tag` for that day, with runtime queue owner
details resolved underneath.

That matches both:

- design intent: `queue_tag` determines queue placement
- runtime behavior: same-day cart allocation expands by unique `queue_tag`

## Answer 3: Are multiple active rows allowed for the same specialist on the same day if `queue_tag` differs?

Yes, in wizard-family scope.

If the same specialist-day visit expands into different `queue_tag` claims,
those are different queue claims and may legitimately produce multiple active
rows.

What is **not** allowed by the target contract:

- a second active row for the same patient in the same resolved queue claim on
  the same day

## Divergence From Registrar Batch Family

This divergence is justified and local:

- registrar batch-only flow models “add services to an existing specialist-day
  registrar claim”
- registrar wizard cart flow models “initial or expanded queue placement by
  queue claim”

So the batch-family specialist-level contract should not be imported into the
wizard family by default.

## Design Intent Verdict

For the registrar wizard family, the correct local design intent is:

- queue-tag-driven claim ownership
- multiple active rows allowed across different queue claims
- no duplicate active row inside the same resolved queue claim/day
