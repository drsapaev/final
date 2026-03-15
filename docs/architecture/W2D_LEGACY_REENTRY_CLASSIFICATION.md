# W2D Legacy Re-entry Classification

This pass splits the remaining post-W2C legacy work into actionable engineering
tails and tails that remain blocked by non-technical uncertainty.

## A) Actionable now

| Tail | Why it is actionable now |
| --- | --- |
| OnlineDay deprecation continuation for bounded read-only surfaces | The main allocator architecture is guarded by CI, and not every remaining OnlineDay surface is blocked. Read-only or retirement-prep work can move safely. |
| `appointments.stats()` retirement / replacement-prep | It is read-only, mounted, and has no confirmed live frontend runtime consumer in current repo usage. That makes it a good low-blast-radius deprecation candidate. |
| `queues.stats()` compatibility tail review | Strict counters are already partially migrated. Remaining work is compatibility-oriented, not product-blocked. |
| Support/test-only residue cleanup | The remaining residue is small and low-risk, though not the highest-value next move. |
| Docs / architecture consolidation | Always actionable, but lower leverage than reducing still-live legacy runtime surfaces. |
| Pause-point/status formalization | Actionable, but mostly already accomplished by the Postgres alignment review and CI guardrail docs. |

## B) Blocked now

| Tail | Why it is blocked now |
| --- | --- |
| `is_paused` / `is_closed` | The blocker is semantic ownership and product meaning, not engineering implementation. |
| Further legacy reduction of `/board/state` for those flags | The board page is mostly migrated already; remaining reduction depends on the blocked semantics above. |
| `open_day` / `close_day` behavior changes or replacement | Characterization showed real drift, but usage confirmation still says manual/ops usage is plausible. |
| `next_ticket` code change or retirement | The route has a deprecate-later direction, but external/manual usage is not disproven, so active code change remains risky. |
| Full OnlineDay runtime owner removal (`online_queue.py`, `OnlineDay`, legacy counter sidecar) | These owners are downstream of the blocked operational endpoints above. |
| Legacy websocket `queue.update` cleanup | This is tied to the remaining operational OnlineDay surfaces and possible external compatibility. |

## Why this split matters

The project no longer needs to keep the whole legacy/deprecation track on hold.
The right move is to resume only the parts that:

- have clear engineering ownership
- do not require inventing semantics
- do not risk changing possibly live operational workflows

That makes OnlineDay read-only reduction and retirement-prep work the best
re-entry zone, while product/ops tails stay intentionally frozen.
