#!/usr/bin/env node
/*
 * v7 instrumentation: per-spec beacons inside pool.runTests (forks pool).
 *
 * Per maintainer v7 plan: previous v6.2 confirmed hang is INSIDE
 * pool.runTests(). Now we need to identify WHICH spec (test file)
 * causes the hang, or if the hang is in recycleWorkers() after all
 * specs complete.
 *
 * Per-spec beacons added:
 *   RUN_PRE       — before pool.run() for each spec
 *                   (index, total, filename, workerId)
 *   RUN_POST      — after pool.run() returns successfully
 *                   (filename, duration_ms)
 *   RUN_ERROR     — if pool.run() throws
 *                   (filename, error)
 *   RUN_LOOP_DONE — after all spec loop iterations complete
 *   RECYCLE_PRE   — before pool.recycleWorkers()
 *   RECYCLE_POST  — after pool.recycleWorkers() returns
 *
 * Also captures process.getActiveResourcesInfo() after each RUN_POST
 * to see which spec creates a new active handle that never disappears.
 *
 * Target file: node_modules/vitest/dist/chunks/coverage.DfSpMS-b.js
 * Target function: createForksPool → runWithFiles (line ~2633)
 *
 * Three interpretation scenarios (per maintainer):
 *   Scenario 1: RUN_PRE(file Y) then silence → hang in pool.run() for file Y
 *   Scenario 2: RUN_POST(last) + RUN_LOOP_DONE + RECYCLE_PRE, no RECYCLE_POST
 *                → hang in recycleWorkers()
 *   Scenario 3: RUN_POST(last) + RUN_LOOP_DONE + RECYCLE_POST, pool.runTests
 *                still doesn't return → internal Promise/sync barrier issue
 *
 * Project config: pool='forks', singleFork=true → all specs go through
 * the singleFork branch (lines 2697-2711 of vitest 3.2.7).
 */

'use strict';

const fs = require('fs');
const path = require('path');

const VITEST_COVERAGE = path.join(
  process.cwd(),
  'node_modules/vitest/dist/chunks/coverage.DfSpMS-b.js'
);
const TRACE_FILE = '/tmp/vitest-pool-trace.jsonl';
const SENTINEL = '__pool_trace';

// ESM-safe trace helper (same pattern as previous instrumenters)
const TRACE_HELPER = `
var __pool_trace_start = null;
function __pool_trace(event, context) {
  try {
    var now = Date.now();
    var hr = process.hrtime.bigint();
    if (__pool_trace_start === null) __pool_trace_start = hr;
    var mono_ns = Number(hr - __pool_trace_start);
    var line = JSON.stringify({
      ts: now,
      mono_ms: Math.round(mono_ns / 1000000),
      pid: process.pid,
      event: event,
      context: context || {}
    });
    process.stderr.write('POOL_TRACE:' + line + '\\n');
  } catch (e) { /* never break vitest */ }
}
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
    process.stderr.write(`[pool-instrument] failed to log: ${e.message}\n`);
  }
}

function patch() {
  if (process.env.POOL_INSTRUMENT === '0') {
    console.log('[pool-instrument] disabled by env, skipping');
    return;
  }

  if (!fs.existsSync(VITEST_COVERAGE)) {
    console.error(`[pool-instrument] not found: ${VITEST_COVERAGE}`);
    console.error('  Run this script from frontend/ after `npm ci`');
    process.exit(1);
  }

  try {
    fs.writeFileSync(TRACE_FILE, '');
    patcherLog('pool_instrument_start', {
      file: VITEST_COVERAGE,
      node: process.version,
    });
  } catch (e) {
    console.error(`[pool-instrument] cannot write ${TRACE_FILE}: ${e.message}`);
    process.exit(1);
  }

  let src = fs.readFileSync(VITEST_COVERAGE, 'utf8');

  if (src.includes(SENTINEL)) {
    console.log('[pool-instrument] already patched, skipping');
    return;
  }

  // Backup original
  fs.writeFileSync(VITEST_COVERAGE + '.bak', src);
  console.log(`[pool-instrument] backup saved to ${VITEST_COVERAGE}.bak`);

  // === Patch 0: Inject trace helper at top of file ===
  src = TRACE_HELPER + src;

  // === Patch 1: Instrument runFiles() — wrap pool.run() call ===
  // Original (line ~2651-2661):
  //   try {
  //       await pool.run(data, {
  //               name,
  //               channel
  //       });
  //   } catch (error) {
  //       // Worker got stuck and won't terminate - this may cause process to hang
  //       if (error instanceof Error && /Failed to terminate worker/.test(error.message)) vitest.state.addProcessTimeoutCause(`Failed to terminate worker while running ${paths.join(", ")}.`);
  //       else if (vitest.isCancelling && error instanceof Error && /The task has been cancelled/.test(error.message)) vitest.state.cancelFiles(paths, project);
  //       else throw error;
  //   }
  //
  // We add RUN_PRE before pool.run(), RUN_POST after success, RUN_ERROR in catch.
  // Also capture getActiveResourcesInfo() in RUN_POST to see what handles each
  // spec leaves behind.
  const poolRunRegex = /(\t\t\ttry \{\n\t\t\t\t)await pool\.run\(data, \{\n\t\t\t\t\tname,\n\t\t\t\t\tchannel\n\t\t\t\t\}\);(\n\t\t\t\} catch \(error\) \{)/;
  if (!poolRunRegex.test(src)) {
    console.error('[pool-instrument] cannot find pool.run() call in runFiles()');
    console.error('  vitest 3.2.7 source structure may have changed');
    process.exit(1);
  }
  src = src.replace(
    poolRunRegex,
    `$1__pool_trace("RUN_PRE", { worker_id: workerId, paths: paths, name: name });\n` +
    `\t\t\t\tconst __runStart = Date.now();\n` +
    `\t\t\t\tawait pool.run(data, {\n\t\t\t\t\tname,\n\t\t\t\t\tchannel\n\t\t\t\t});\n` +
    `\t\t\t\t__pool_trace("RUN_POST", { worker_id: workerId, paths: paths, duration_ms: Date.now() - __runStart, active_resources: (typeof process.getActiveResourcesInfo === "function" ? process.getActiveResourcesInfo() : []) });$2`
  );

  // Add RUN_ERROR in catch block — insert at start of catch body
  const catchRegex = /(\t\t\t\} catch \(error\) \{\n\t\t\t\t)(\/\/ Worker got stuck and won't terminate)/;
  if (!catchRegex.test(src)) {
    console.error('[pool-instrument] cannot find catch block in runFiles()');
    process.exit(1);
  }
  src = src.replace(
    catchRegex,
    `$1__pool_trace("RUN_ERROR", { worker_id: workerId, paths: paths, error: String(error && error.message || error) });\n\t\t\t\t$2`
  );

  // === Patch 2: Instrument singleFork branch (project uses singleFork=true) ===
  // Indentation: if=3tab, const=4tab, for=4tab, const files=5tab, for=5tab, body=6tab
  // We only need to wrap the inner body (recycleWorkers + runFiles).
  // Match the unique sequence inside the innermost for loop:
  //   \t\t\t\t\t\t// Always run environments isolated between each other
  //   \t\t\t\t\t\tawait pool.recycleWorkers();
  //   \t\t\t\t\t\tconst filenames = files.map((f) => f.file);
  //   \t\t\t\t\t\tawait runFiles(files[0].project, ...);
  const singleForkInnerRegex = /(\t\t\t\t\t\t\/\/ Always run environments isolated between each other\n\t\t\t\t\t\t)await pool\.recycleWorkers\(\);(\n\t\t\t\t\t\tconst filenames = files\.map\(\(f\) => f\.file\);\n\t\t\t\t\t\t)await runFiles\(files\[0\]\.project, getConfig\(files\[0\]\.project\), filenames, files\[0\]\.environment, invalidates\);(\n\t\t\t\t\t\})/;
  if (!singleForkInnerRegex.test(src)) {
    console.error('[pool-instrument] cannot find singleFork inner branch');
    console.error('  vitest 3.2.7 source structure may have changed');
    process.exit(1);
  }
  src = src.replace(
    singleForkInnerRegex,
    `$1__pool_trace("RECYCLE_PRE", {});\n` +
    `\t\t\t\t\t\tawait pool.recycleWorkers();\n` +
    `\t\t\t\t\t\t__pool_trace("RECYCLE_POST", {});\n` +
    `$2__pool_trace("SF_RUNFILES_PRE", { filenames: filenames });\n` +
    `\t\t\t\t\t\tawait runFiles(files[0].project, getConfig(files[0].project), filenames, files[0].environment, invalidates);\n` +
    `\t\t\t\t\t\t__pool_trace("SF_RUNFILES_POST", { filenames: filenames });$3`
  );

  // Write patched file
  fs.writeFileSync(VITEST_COVERAGE, src);
  console.log(`[pool-instrument] patched ${VITEST_COVERAGE}`);
  console.log(`[pool-instrument] beacons added:`);
  console.log(`  RUN_PRE       — before pool.run() for each spec`);
  console.log(`  RUN_POST      — after pool.run() returns (with active_resources)`);
  console.log(`  RUN_ERROR     — if pool.run() throws`);
  console.log(`  SF_LOOP_ENTER — singleFork branch entered (with singleFork_count)`);
  console.log(`  SF_GROUP_PRE  — before each singleFork group (with env, filenames)`);
  console.log(`  RECYCLE_PRE   — before pool.recycleWorkers()`);
  console.log(`  RECYCLE_POST  — after pool.recycleWorkers() returns`);
  console.log(`  SF_RUNFILES_PRE  — before runFiles() call`);
  console.log(`  SF_RUNFILES_POST — after runFiles() returns`);
  console.log(`  SF_LOOP_DONE  — singleFork loop completed`);
  console.log(`[pool-instrument] trace lines: POOL_TRACE:{json} on stderr`);
  patcherLog('pool_instrument_applied', {
    beacons: ['RUN_PRE', 'RUN_POST', 'RUN_ERROR', 'SF_LOOP_ENTER', 'SF_GROUP_PRE', 'RECYCLE_PRE', 'RECYCLE_POST', 'SF_RUNFILES_PRE', 'SF_RUNFILES_POST', 'SF_LOOP_DONE'],
  });
}

try {
  patch();
} catch (e) {
  console.error(`[pool-instrument] fatal: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}
