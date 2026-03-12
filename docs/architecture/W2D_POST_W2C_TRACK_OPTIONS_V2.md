# Wave 2D Post-W2C Track Options V2

Date: 2026-03-10

## Option 1: Postgres-aligned test infrastructure follow-up

Why realistic now:

- production/dev already runs on Postgres
- pytest still provisions SQLite
- queue and legacy-island behavior are sensitive to DB semantics
- no product/ops decision is required to start an inventory/prep pass

First execution unit:

- inventory and prep pass for SQLite-vs-Postgres drift in queue-sensitive test
  paths

What it would unblock later:

- safer OnlineDay deprecation slices
- stronger confidence for any operational-route fixes
- more reliable parity validation for future legacy retirement

Why it may still not be chosen:

- it is infrastructure-facing, not user-facing
- it may require staged prep before any real infra switch

## Option 2: Docs / architecture consolidation

Why realistic now:

- the repo now contains a large amount of W2C/W2D intermediate docs
- many decisions are already settled

First execution unit:

- top-level docs normalization and superseded-status cleanup plan

What it would unblock later:

- faster onboarding and lower doc drift
- simpler navigation through legacy-tail decisions

Why it may still not be chosen:

- lower leverage than improving runtime-verification confidence

## Option 3: Support/test-only residue cleanup

Why realistic now:

- dead and support-only cleanup already started successfully
- remaining residue is narrower and better understood

First execution unit:

- inventory + safe-cleanup prep for retained support/test-only artifacts

What it would unblock later:

- smaller legacy surface
- less accidental confusion between runtime owners and architecture artifacts

Why it may still not be chosen:

- does not address the highest-value repo-wide confidence gap

## Option 4: Formalize a pause point

Why realistic now:

- major architecture work is already done
- blocked tails are known

First execution unit:

- blocked-tail register and project pause summary

What it would unblock later:

- a clean handoff to future work

Why it may still not be chosen:

- useful only if we intentionally stop, not if a strong deterministic next
  track still exists

## Option 5: Continue OnlineDay deprecation directly

Why it is not realistic now:

- the remaining high-value pieces are no longer purely engineering tasks
- route semantics and external/manual usage risks are still unresolved

## Option 6: force_majeure follow-up

Why it is not the best immediate choice:

- it is intentionally isolated
- some candidate changes still depend on local business-policy clarification
- it offers less broad architectural leverage than test-infra alignment
