"""Background job spawning for periodic schedulers.

Jobs run on **daemon** threads so that a stalled job (sync DB call without a
socket timeout, long pg_dump) can never block application shutdown past the
scheduler grace period: past the grace the job is abandoned and the thread
dies with the process.

The result is bridged back to the caller as an ``asyncio.Future`` resolved on
the calling (application) loop via ``call_soon_threadsafe``, so callers can
``await``/``shield`` jobs exactly like executor futures.

Origin: P0 origin freeze 2026-08-28 (sync I/O on the event loop) and the
codex review follow-up on #2874 ("make the shutdown grace actually bounded").
"""

from __future__ import annotations

import asyncio
import threading


def spawn_daemon_job(fn, /, *args) -> asyncio.Future:
    """Run ``fn(*args)`` on a daemon thread; resolve the returned future on
    the calling loop when the thread finishes.

    Exceptions propagate to the awaiting task. If the awaiting task was
    cancelled (shutdown), the future is cancelled as well and the result is
    discarded — the daemon thread keeps running until process exit.
    """
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    def _runner() -> None:
        try:
            result = fn(*args)
            error = None
        except BaseException as exc:  # noqa: BLE001 - propagated to awaiter
            result, error = None, exc

        def _set() -> None:
            if fut.done():
                return
            if error is not None:
                fut.set_exception(error)
            else:
                fut.set_result(result)

        try:
            loop.call_soon_threadsafe(_set)
        except RuntimeError:
            # Event loop already closed during shutdown — the awaiting task
            # is gone; nothing to resolve.
            pass

    threading.Thread(target=_runner, name="clinic-bg-job", daemon=True).start()
    return fut
