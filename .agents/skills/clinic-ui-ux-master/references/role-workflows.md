# Role Workflows

Use this reference when auditing or changing role-specific clinical screens.

## Admin

Primary jobs:

- monitor clinic operations
- manage users, roles, settings, departments, services, pricing, activation, integrations
- review audit and operational signals

UI risks:

- too many equal-weight cards
- mixed admin sections without clear ownership
- dangerous settings near routine actions
- inconsistent table actions
- unclear role or permission changes

Audit focus:

- dashboard hierarchy
- action grouping
- settings state clarity
- auditability and confirmation states
- tables and filters

Validation:

- admin route smoke
- keyboard path through tables and dialogs
- dark/light theme if touched

## Registrar

Primary jobs:

- register patients
- create and manage appointments
- route patients to departments
- handle queue and schedule changes
- coordinate with cashier and doctors

UI risks:

- patient identity ambiguity
- phone/date/time normalization confusion
- repeated appointments unclear
- queue status mismatch
- overloaded toolbar on small screens

Audit focus:

- patient search and selection
- appointment wizard
- queue actions
- schedule/reschedule flow
- error and duplicate handling

Validation:

- create/search/reschedule smoke where available
- mobile/tablet toolbar wrapping
- empty and error states

## Doctor

Primary jobs:

- review queue and appointments
- open patient context
- record visit data
- view history, reports, AI assistance, and next appointment actions

UI risks:

- unclear current patient
- AI content visually competing with clinical data
- actions that imply diagnosis or treatment without confirmation
- dense tabs with weak active state
- history/report sections hard to scan

Audit focus:

- current patient identity
- queue-to-visit transition
- EMR and report hierarchy
- AI disclaimer and status
- loading/partial data behavior

Validation:

- route with and without patient id
- tab keyboard/focus behavior
- no hidden critical action on mobile/tablet

## Cashier

Primary jobs:

- review pending payments
- accept payment
- handle refunds/discounts/benefits where allowed
- reconcile payment status

UI risks:

- amount/status ambiguity
- success/pending/cancel/error states too similar
- action buttons not clearly separated
- old payment state shown after status update
- weak confirmation for sensitive actions

Audit focus:

- amount formatting
- payment status color and text
- action hierarchy
- receipt and audit feedback
- retry/error states

Validation:

- payment status screens
- no raw network errors
- disabled/loading states during submit

## Lab

Primary jobs:

- process lab queue
- create or edit report templates
- generate reports
- communicate result readiness

UI risks:

- patient/sample/result mismatch
- template selection ambiguity
- report preview not matching final output
- missing partial/error state
- dense forms without grouping

Audit focus:

- queue table scan order
- sample/result identity
- template workflow
- report generation state
- print/export controls

Validation:

- lab queue smoke
- report preview/export where available
- empty/error state checks

## Patient

Primary jobs:

- view appointments
- view lab results and payment state
- manage profile or family context
- join queue where public/mobile flows apply

UI risks:

- medical result visibility without context
- confusing payment or queue state
- mobile overflow
- unclear next action after success/failure

Audit focus:

- mobile-first layout
- plain language states
- privacy and role clarity
- payment/queue result clarity

Validation:

- 375px and 768px viewport
- focus and tap target checks
- localized text does not overflow

## Queue

Primary jobs:

- public join
- staff monitoring
- display boards
- department/specialist routing

UI risks:

- queue number, date, specialist, or department ambiguity
- stale live state
- mobile input friction
- display-board text clipping
- status mismatch between public and staff screens

Audit focus:

- current queue state
- next action
- live update messaging
- mobile form ergonomics
- display-board legibility at distance

Validation:

- mobile public join
- display-board wide screen
- live update or refresh behavior if touched

## Payment

Primary jobs:

- user sees success/cancel/pending/error
- cashier reconciles and acts
- staff can recover from provider failure

UI risks:

- pending treated as success
- canceled treated as error without recovery action
- amount/currency/provider unclear
- Telegram/contact action overemphasized or underexplained

Audit focus:

- status semantics
- receipt details
- recovery actions
- support path
- accessible alerts

Validation:

- success, cancel, pending, not found, and error variants if fixtures allow

## EMR And Reports

Primary jobs:

- clinical note capture
- report review
- diagnosis/procedure history
- print/export

UI risks:

- legacy EMR folder usage
- unclear patient context
- large forms without save state
- print/export differs from visible state
- AI suggestions mixed with confirmed clinical facts

Audit focus:

- patient identity header
- save/pending/error state
- section grouping
- print/report preview
- AI provenance and disclaimer

Validation:

- route smoke
- no use of retired EMR runtime layer
- print/export smoke where available

