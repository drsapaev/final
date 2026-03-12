# Wave 2C Force Majeure Design Intent

Date: 2026-03-09
Mode: contract-review

## Baseline

`ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md` defines the normal queue model:

- `queue_time` is the fairness timestamp
- duplicates in the same queue/day are not the intended default
- sources such as `online`, `desk`, and `morning_assignment` describe ordinary
  queue entry origins
- numbering is queue-local and day-scoped

The design document does not define a normal "force-majeure transfer" flow.
That means force majeure must be treated as an explicit exception domain, not as
an ordinary queue-create variation.

## Answers To The Core Questions

### 1. Should force majeure preserve the old ticket number?

No.

Target behavior should allocate a new queue-local number on the target
tomorrow-queue.

Why:

- transfer creates a new queue claim in a different day-scoped queue
- reusing the old number would not fit the target queue/day numbering contract
- the old row is cancelled, not migrated in place

### 2. Should force majeure preserve the old `queue_time`?

No.

Target behavior should assign a new transfer-time timestamp on the target row.

Why:

- force majeure is an operational requeue/transfer event, not a normal edit
- the normal immutability rule for `queue_time` applies to the same queue claim,
  not to a newly created tomorrow claim
- the transfer batch still needs deterministic internal ordering, but that can
  be defined within the transfer contract

### 3. Should force majeure override priority?

Yes.

This is the clearest intentional override in the current family. The service
and endpoint documentation both describe transferred patients as "first in
queue" on the next day.

### 4. Is a second active row on the tomorrow queue acceptable?

No.

Nothing in the general queue design justifies creating a duplicate active claim
for the same patient on the same target queue/day merely because the trigger is
force majeure.

Target contract should treat this as a conflict that must be handled explicitly,
not as a silent duplicate-creation allowance.

### 5. Should `source` be separate (`force_majeure_transfer`)?

Yes.

That source value is a useful intentional override because it records that the
row was created by an operational transfer rather than by the normal join/desk
flows.

## Resulting Intent

Force majeure is an exceptional queue-transfer domain with intentional
overrides for:

- new target-queue number
- new target `queue_time`
- explicit priority boost
- exceptional `source`

But it should still obey the broader queue-domain rule that one patient should
not silently receive multiple active claims in the same target queue/day.
