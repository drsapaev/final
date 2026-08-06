/**
 * v10 — Active handles capture setup file.
 *
 * Per maintainer v10 directive: stop instrumenting vitest internals.
 * Instead, capture active handles AFTER each test file completes
 * to identify which test leaves handles that prevent worker exit.
 *
 * This file is registered as a setupFile in vitest.config.ts.
 * It registers an afterAll hook that:
 *   1. Captures process._getActiveHandles() — internal handle objects
 *   2. Captures process.getActiveResourcesInfo() — readable names
 *   3. Captures process._getActiveRequests() — pending async ops
 *   4. Writes them to stderr as HANDLES_TRACE:{json}
 *
 * The afterAll hook runs AFTER all tests in a file complete but
 * BEFORE runTests() returns. If a test file leaves handles, they
 * will appear in the capture for that file.
 *
 * By comparing captures across files, we can identify WHICH file
 * first introduces a persistent handle.
 *
 * Output format (one line per afterAll invocation):
 *   HANDLES_TRACE:{"file":"<test-file>","handles_count":N,"requests_count":M,
 *                   "resources":["PipeWrap","Socket","MessagePort",...],
 *                   "handle_details":[{"type":"Socket","fd":1,"destroyed":false},...]}
 *
 * The handle_details array projects each handle to safe fields only
 * (per maintainer v4 feedback — never JSON.stringify handles directly
 * due to circular references).
 */

import { afterAll } from 'vitest';

function captureHandles() {
  try {
    const handles = typeof process._getActiveHandles === 'function'
      ? process._getActiveHandles()
      : [];
    const requests = typeof process._getActiveRequests === 'function'
      ? process._getActiveRequests()
      : [];
    const resources = typeof process.getActiveResourcesInfo === 'function'
      ? process.getActiveResourcesInfo()
      : [];

    // Project handles to safe fields only (avoid circular refs)
    const handleDetails = handles.map((h) => {
      try {
        return {
          type: h && h.constructor ? h.constructor.name : String(h),
          hasRef: typeof h.hasRef === 'function' ? h.hasRef() : undefined,
          destroyed: h.destroyed,
          readable: h.readable,
          writable: h.writable,
          fd: typeof h.fd === 'number' ? h.fd : undefined,
        };
      } catch {
        return { type: 'unknown (projection failed)' };
      }
    });

    const requestDetails = requests.map((r) => {
      try {
        return r && r.constructor ? r.constructor.name : String(r);
      } catch {
        return 'unknown';
      }
    });

    return {
      handles_count: handles.length,
      requests_count: requests.length,
      resources: resources,
      handle_details: handleDetails,
      request_details: requestDetails,
    };
  } catch (e) {
    return { error: String(e && e.message || e) };
  }
}

// afterAll runs after all tests in the current file complete.
// We capture handles at this point to see what's left.
afterAll(() => {
  // Get current test file path from vitest's global state
  // In setupFiles, we don't have direct access to the file path,
  // but we can use a stack trace or environment variable.
  // Vitest sets VITEST_POOL_ID and workerId, but not current file.
  // We'll use a counter and timestamp instead.
  const capture = captureHandles();
  const line = JSON.stringify({
    ts: Date.now(),
    mono_ms: 0, // Can't easily get monotonic time here without setup
    pid: process.pid,
    file: '(afterAll — see preceding test output for file name)',
    ...capture,
  });
  process.stderr.write('HANDLES_TRACE:' + line + '\n');
});

// Also capture on process.beforeExit — this fires when event loop
// has no more work. If it never fires, something is keeping it alive.
process.on('beforeExit', (code) => {
  const capture = captureHandles();
  const line = JSON.stringify({
    ts: Date.now(),
    pid: process.pid,
    file: '(beforeExit)',
    code: code,
    ...capture,
  });
  process.stderr.write('HANDLES_TRACE:' + line + '\n');
});
