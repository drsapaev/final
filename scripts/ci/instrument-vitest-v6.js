#!/usr/bin/env node
/*
 * Instrumentation patcher for vitest 3.2.7.
 *
 * Patches node_modules/vitest/dist/chunks/cli-api.DVe0nWUx.js to add
 * structured "beacon" trace points that divide the vitest lifecycle
 * into phases. Per maintainer v6 plan, only 6 strategic beacons are
 * added — NOT exhaustive instrumentation. The goal is to localize
 * WHICH phase the process is stuck in, not to trace every line.
 *
 * Beacon points (per maintainer spec):
 *   B1. After runFiles() finishes (pool.runTests + coverage + report)
 *   B2. Before ctx.close() in startVitest()
 *   B3. After ctx.close() in startVitest()
 *   B4. Before return from startVitest()
 *   B5. process.on('beforeExit') — registered at module load
 *   B6. process.on('exit') — registered at module load
 *
 * Plus: getActiveResourcesInfo() called before ctx.close() to see
 * what's keeping the event loop alive.
 *
 * Each beacon writes VITEST_TRACE:{json} to process.stderr with:
 *   - wall-clock timestamp (Date.now)
 *   - monotonic ms since first beacon (process.hrtime.bigint)
 *   - pid
 *   - beacon_id (B1-B6)
 *   - context (phase name + relevant data)
 *
 * Decision tree (per maintainer):
 *   No B2 (before ctx.close) → hang is in main runner, before close
 *   B2 yes, no B3 → hang is inside ctx.close()
 *   B3 yes, no B5 (beforeExit) → hang is in active Node resources
 *   B5 yes, no B6 (exit) → hang is in exit handlers
 *
 * Approach: regex-based patching of specific method bodies.
 * Idempotent: checks for sentinel, skips if already patched.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const VITEST_CLI_API = path.join(
  process.cwd(),
  'node_modules/vitest/dist/chunks/cli-api.DVe0nWUx.js'
);
const TRACE_FILE = '/tmp/vitest-trace.jsonl';
const SENTINEL = '__vitest_trace';

// ESM-safe trace helper (same pattern as tinypool instrument)
const TRACE_HELPER = `
var __vitest_trace_start = null;
function __vitest_trace(beacon_id, context) {
  try {
    var now = Date.now();
    var hr = process.hrtime.bigint();
    if (__vitest_trace_start === null) __vitest_trace_start = hr;
    var mono_ns = Number(hr - __vitest_trace_start);
    var line = JSON.stringify({
      ts: now,
      mono_ms: Math.round(mono_ns / 1000000),
      pid: process.pid,
      beacon: beacon_id,
      context: context || {}
    });
    process.stderr.write('VITEST_TRACE:' + line + '\\n');
  } catch (e) { /* never break vitest */ }
}
// Register process exit handlers ONCE at module load (B5, B6)
process.on('beforeExit', function(code) {
  __vitest_trace('B5_beforeExit', { code: code });
});
process.on('exit', function(code) {
  __vitest_trace('B6_exit', { code: code });
});
`;

function patcherLog(event, payload = {}) {
  const line = JSON.stringify({
    ts: Date.now(),
    pid: process.pid,
    ppid: process.ppid,
    event,
    ...payload,
  });
  try {
    fs.appendFileSync(TRACE_FILE, line + '\n');
  } catch (e) {
    process.stderr.write(`[vitest-instrument] failed to log: ${e.message}\n`);
  }
}

function patch() {
  if (process.env.VITEST_INSTRUMENT === '0') {
    console.log('[vitest-instrument] disabled by env, skipping');
    return;
  }

  if (!fs.existsSync(VITEST_CLI_API)) {
    console.error(`[vitest-instrument] not found: ${VITEST_CLI_API}`);
    console.error('  Run this script from frontend/ after `npm ci`');
    process.exit(1);
  }

  try {
    fs.writeFileSync(TRACE_FILE, '');
    patcherLog('vitest_instrument_start', {
      file: VITEST_CLI_API,
      node: process.version,
    });
  } catch (e) {
    console.error(`[vitest-instrument] cannot write ${TRACE_FILE}: ${e.message}`);
    process.exit(1);
  }

  let src = fs.readFileSync(VITEST_CLI_API, 'utf8');

  if (src.includes(SENTINEL)) {
    console.log('[vitest-instrument] already patched, skipping');
    return;
  }

  // Backup original
  fs.writeFileSync(VITEST_CLI_API + '.bak', src);
  console.log(`[vitest-instrument] backup saved to ${VITEST_CLI_API}.bak`);

  // === Patch 0: Inject trace helper at top of file ===
  // This registers process.on('beforeExit') and process.on('exit') handlers
  // immediately when the module loads, so they fire even if vitest hangs.
  src = TRACE_HELPER + src;

  // === Patch 1 (B1): After runFiles() finishes ===
  // The runFiles method (line ~9631) has a `finally` block that does
  // coverage generation + reportCoverage + _testRun.end(). After that
  // finally block, the inner async IIFE returns, then .finally() runs,
  // then `return await this.runningPromise` returns.
  //
  // We inject B1 right before `return await this.runningPromise;` at the
  // end of runFiles. This fires AFTER all tests + coverage + reporters.
  //
  // Original code at end of runFiles:
  //   })().finally(() => {
  //       this.runningPromise = void 0;
  //       this.isFirstRun = false;
  //       this.config.changed = false;
  //       this.config.related = void 0;
  //   });
  //   return await this.runningPromise;
  // }
  //
  // We add B1 before `return await this.runningPromise;`
  const runFilesReturnRegex = /(\t\treturn await this\.runningPromise;\n\t\}\n\t\/\*\*\n\t\* Collect tests in specified modules)/;
  if (!runFilesReturnRegex.test(src)) {
    console.error('[vitest-instrument] cannot find runFiles return point');
    console.error('  Expected: \\t\\treturn await this.runningPromise; followed by collectTests comment');
    process.exit(1);
  }
  src = src.replace(
    runFilesReturnRegex,
    '\t\t__vitest_trace("B1_after_runFiles", { phase: "tests+coverage+reporters complete, runFiles returning" });\n$1'
  );

  // === Patch 2 + 3 + 4 (B2, B3, B4): Around ctx.close() in startVitest ===
  // Original (line ~10539-10542):
  //   if (ctx.shouldKeepServer()) return ctx;
  //   stdinCleanup?.();
  //   await ctx.close();
  //   return ctx;
  // }
  //
  // We inject:
  //   B2 before await ctx.close()  (with getActiveResourcesInfo)
  //   B3 after await ctx.close()
  //   B4 before return ctx
  const startVitestCloseRegex = /(\tif \(ctx\.shouldKeepServer\(\)\) return ctx;\n\tstdinCleanup\?\.\(\);\n\t)await ctx\.close\(\);(\n\treturn ctx;\n\})/;
  if (!startVitestCloseRegex.test(src)) {
    console.error('[vitest-instrument] cannot find startVitest ctx.close() block');
    console.error('  Expected: if (ctx.shouldKeepServer()) return ctx; stdinCleanup?.(); await ctx.close(); return ctx;');
    process.exit(1);
  }
  src = src.replace(
    startVitestCloseRegex,
    `$1__vitest_trace("B2_before_ctx_close", { phase: "about to call ctx.close()", active_resources: (typeof process.getActiveResourcesInfo === "function" ? process.getActiveResourcesInfo() : "getActiveResourcesInfo not available") });\n\tawait ctx.close();\n\t__vitest_trace("B3_after_ctx_close", { phase: "ctx.close() returned" });\n\t__vitest_trace("B4_before_return", { phase: "startVitest returning" });$2`
  );

  // === Patch 5: Inside ctx.close() — instrument pool.close() call ===
  // This complements tinypool instrumentation. If B2 fires but tinypool_destroy_enter
  // doesn't, the hang is BETWEEN ctx.close() entry and pool.close() call
  // (i.e. in teardownProjects or project.close()).
  //
  // Original (line ~9911-9931):
  //   async close() {
  //     if (!this.closingPromise) this.closingPromise = (async () => {
  //       const teardownProjects = [...this.projects];
  //       ...
  //       for (const project of teardownProjects.reverse()) await project._teardownGlobalSetup();
  //       const closePromises = this.projects.map((w) => w.close());
  //       ...
  //       if (this.pool) closePromises.push((async () => {
  //         await this.pool?.close?.();
  //         this.pool = void 0;
  //       })());
  //
  // We add a trace right at close() entry.
  const ctxCloseRegex = /(\tasync close\(\) \{\n\t\tif \(!this\.closingPromise\) this\.closingPromise = \(async \(\) => \{)/;
  if (!ctxCloseRegex.test(src)) {
    console.error('[vitest-instrument] cannot find ctx.close() method');
    process.exit(1);
  }
  src = src.replace(
    ctxCloseRegex,
    `$1\n\t\t\t__vitest_trace("B2a_ctx_close_entered", { phase: "ctx.close() called, beginning teardown" });`
  );

  // Write patched file
  fs.writeFileSync(VITEST_CLI_API, src);
  console.log(`[vitest-instrument] patched ${VITEST_CLI_API}`);
  console.log(`[vitest-instrument] beacons added:`);
  console.log(`  B1  — after runFiles() returns`);
  console.log(`  B2  — before ctx.close() (with getActiveResourcesInfo)`);
  console.log(`  B2a — inside ctx.close() entry`);
  console.log(`  B3  — after ctx.close() returns`);
  console.log(`  B4  — before startVitest returns`);
  console.log(`  B5  — process.on('beforeExit')`);
  console.log(`  B6  — process.on('exit')`);
  console.log(`[vitest-instrument] trace lines: VITEST_TRACE:{json} on stderr`);
  patcherLog('vitest_instrument_applied', {
    beacons: ['B1', 'B2', 'B2a', 'B3', 'B4', 'B5', 'B6'],
  });
}

try {
  patch();
} catch (e) {
  console.error(`[vitest-instrument] fatal: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}
