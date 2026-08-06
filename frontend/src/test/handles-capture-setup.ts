/**
 * v10.1 — Active handles capture setup file.
 *
 * Per Codex P1 #5: Include the test path in each handle capture.
 * Per Codex P2 #9: Register the beforeExit probe only once.
 *
 * This file is registered as a setupFile in vitest.config.ts.
 * In singleFork mode, setupFiles execute before EACH test file,
 * and afterAll runs after each file's tests.
 *
 * To get the current test file path, we use vitest's internal
 * __vitest_worker__ global state (available in worker context).
 * If not available, we fall back to import.meta.url.
 *
 * Output format (one line per afterAll invocation):
 *   HANDLES_TRACE:{"file":"<test-file>","handles_count":N,...}
 */

import { afterAll } from 'vitest';

// Per Codex P2 #9: Guard beforeExit listener with process-global sentinel
// to prevent accumulating 159 listeners in singleFork mode.
declare global {
  // eslint-disable-next-line no-var
  var __handles_capture_registered: boolean | undefined;
}

function getCurrentTestFile(): string {
  // Try vitest's internal worker state
  try {
    const worker = (globalThis as Record<string, unknown>).__vitest_worker__;
    if (worker && typeof worker === 'object') {
      const filepath = (worker as Record<string, unknown>).filepath;
      if (typeof filepath === 'string') return filepath;
    }
  } catch {}
  // Try environment variable (vitest may set this)
  try {
    const envFile = process.env.VITEST_TEST_FILE;
    if (envFile) return envFile;
  } catch {}
  return '(unknown)';
}

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
afterAll(() => {
  const file = getCurrentTestFile();
  const capture = captureHandles();
  const line = JSON.stringify({
    ts: Date.now(),
    pid: process.pid,
    file,
    ...capture,
  });
  // Per Codex P2 #12: use fs.writeSync for reliability under pipe backpressure
  try {
    const fs = require('fs');
    fs.writeSync(2, 'HANDLES_TRACE:' + line + '\n');
  } catch {
    process.stderr.write('HANDLES_TRACE:' + line + '\n');
  }
});

// Per Codex P2 #9: Register beforeExit probe only ONCE
// In singleFork mode, this setup file executes before each test file,
// but the worker process is reused. Without this guard, we'd accumulate
// 159 listeners.
if (!globalThis.__handles_capture_registered) {
  globalThis.__handles_capture_registered = true;
  process.on('beforeExit', (code) => {
    const file = getCurrentTestFile();
    const capture = captureHandles();
    const line = JSON.stringify({
      ts: Date.now(),
      pid: process.pid,
      file: file + ' (beforeExit)',
      code,
      ...capture,
    });
    try {
      const fs = require('fs');
      fs.writeSync(2, 'HANDLES_TRACE:' + line + '\n');
    } catch {
      process.stderr.write('HANDLES_TRACE:' + line + '\n');
    }
  });
}
