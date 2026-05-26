# Memory Probes

Protocol: `docs/devbrain/MEMORY_PROBE_PROTOCOL.md`

This ledger stores explicit memory canaries. Entries here are evidence records,
not project policy.

## Active Entries

### 2026-05-26 - Memory Probe Protocol Bootstrap

- Date/time: 2026-05-26, Asia/Tashkent.
- Source instruction: user asked to create a special "memory probe" protocol
  that records a control phrase/fact.
- Control fact: `Memory probe protocol was created after PR #1332 optimized the PR Lifecycle Recommendation workflow.`
- Origin: agent-generated because the user requested the protocol but did not
  provide a specific phrase/fact.
- Expected retrieval answer: `Memory probe protocol was created after PR #1332 optimized the PR Lifecycle Recommendation workflow.`
- Storage target: `.ai-factory/logs/memory-probes.md`.
- Validation run: `git diff --check`; `.\scripts\devbrain_refresh_memory.ps1`
  (fresh; 0 warnings, 0 failures).
- Status: active.
