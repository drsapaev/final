# Wave 2C Next Execution Unit After Wizard Create Branch

Date: 2026-05-06

## Recommended Next Step

After this create-branch extraction, the next smallest runtime step is a focused compatibility test for the mounted registrar cart path.

The test should prove:

- same-day confirmed visits are assigned through `RegistrarWizardQueueAssignmentService`
- existing active queue entries are reused
- create handoff preserves `queue_time`, services, service codes, and `source`
- ambiguous active queue claims still raise through shared resolution logic

Do not combine this with queue numbering redesign or frontend workflow changes.
