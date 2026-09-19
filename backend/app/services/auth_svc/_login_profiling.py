"""Login phase profiler (read-only diagnostics, no behavior change).

Production login against the remote Supabase pooler measured 8.8s wall /
3.2s DB across 11 sequential statements (P2 inventory, 2026-09-19). The
per-query RTT (~300ms us-east-1 <-> UZ) dominates, but ~5.6s of the login
wall time was unaccounted. This timer produces ONE INFO line per login
with the per-phase breakdown (user lookup, password verify, lockout,
audit writes, 2FA check, session revocation, token issuance) so the next
round-trip-reduction PR is data-driven.

Phase timers are best-effort diagnostics: they never alter control flow,
and failures inside a phase are reported through the existing error
paths. Remove the timer hooks once the login latency incident resolves.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class LoginPhaseTimer:
    """Accumulates wall time per named phase of a login attempt."""

    __slots__ = ("_total_start", "_phase_start", "phases")

    def __init__(self) -> None:
        self._total_start = time.perf_counter()
        self._phase_start = self._total_start
        self.phases: dict[str, float] = {}

    def mark(self, phase: str) -> None:
        """Close the current phase and open the next one."""
        now = time.perf_counter()
        self.phases[phase] = self.phases.get(phase, 0.0) + (now - self._phase_start)
        self._phase_start = now

    def report(self, masked_username: str) -> None:
        """Emit one INFO line with the per-phase breakdown (ms)."""
        total = time.perf_counter() - self._total_start
        breakdown = " ".join(
            f"{name}={ms * 1000:.0f}ms" for name, ms in self.phases.items()
        )
        logger.info(
            "login_phase_profile: user=%s total_ms=%d %s",
            masked_username,
            round(total * 1000),
            breakdown,
        )
