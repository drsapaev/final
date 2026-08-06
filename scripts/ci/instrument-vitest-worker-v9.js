#!/usr/bin/env node
/*
 * v9 instrumentation: vitest worker.js (execute function) beacons.
 *
 * Per maintainer v9 plan: v8 confirmed hang is INSIDE handler(task)
 * for the 170-file batch in Worker 2 (pid=2478). The handler is
 * vitest's execute() function in dist/worker.js. Now we instrument
 * execute() to find which await never returns.
 *
 * Target: node_modules/vitest/dist/worker.js
 * Target function: execute(method, ctx) — lines 69-113 of vitest 3.2.7
 *
 * Beacons (with elapsed_ms for each phase):
 *   VW_EXECUTE_ENTER    — execute() function entry
 *   VW_IMPORT_RUNNER    — after import(file) (test runner module loaded)
 *   VW_ENV_LOADED       — after loadEnvironment() (jsdom ready)
 *   VW_RUNTESTS_PRE     — before worker[methodName](state)
 *   VW_RUNTESTS_POST    — after worker[methodName](state) returns
 *   VW_FINALLY_ENTER    — finally block entered
 *   VW_RPCDONE_PRE      — before rpcDone()
 *   VW_RPCDONE_POST     — after rpcDone() returns
 *   VW_INSPECTOR_CLEANUP — after inspectorCleanup()
 *   VW_EXECUTE_RETURN   — before execute() returns
 *
 * Interpretation:
 *   VW_RUNTESTS_PRE yes, VW_RUNTESTS_POST no → hang INSIDE worker.runTests()
 *   VW_RUNTESTS_POST yes, VW_RPCDONE_POST no → hang in rpcDone()
 *   VW_RPCDONE_POST yes, VW_EXECUTE_RETURN no → hang in inspectorCleanup()
 *   VW_EXECUTE_RETURN yes → execute() completed, hang is elsewhere
 *
 * Each beacon includes elapsed_ms since previous beacon to distinguish
 * "await never returns" from "await is slow".
 */

'use strict';

const fs = require('fs');
const path = require('path');

const VITEST_WORKER = path.join(
  process.cwd(),
  'node_modules/vitest/dist/worker.js'
);
const TRACE_FILE = '/tmp/vitest-worker-trace.jsonl';
const SENTINEL = '__vitest_worker_trace';

// ESM-safe trace helper
const TRACE_HELPER = `
var __vw_trace_start = null;
var __vw_last_time = null;
function __vw_trace(event, phase) {
  try {
    var now = Date.now();
    var hr = process.hrtime.bigint();
    if (__vw_trace_start === null) {
      __vw_trace_start = hr;
      __vw_last_time = hr;
    }
    var mono_ns = Number(hr - __vw_trace_start);
    var elapsed_ns = Number(hr - __vw_last_time);
    __vw_last_time = hr;
    var line = JSON.stringify({
      ts: now,
      mono_ms: Math.round(mono_ns / 1000000),
      elapsed_ms: Math.round(elapsed_ns / 1000000),
      pid: process.pid,
      ppid: process.ppid,
      event: event,
      phase: phase || {}
    });
    process.stderr.write('VW_TRACE:' + line + '\\n');
  } catch (e) { /* never break worker */ }
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
    process.stderr.write(`[vitest-worker-instrument] failed to log: ${e.message}\n`);
  }
}

function patch() {
  if (process.env.VITEST_WORKER_INSTRUMENT === '0') {
    console.log('[vitest-worker-instrument] disabled by env, skipping');
    return;
  }

  if (!fs.existsSync(VITEST_WORKER)) {
    console.error(`[vitest-worker-instrument] not found: ${VITEST_WORKER}`);
    console.error('  Run this script from frontend/ after `npm ci`');
    process.exit(1);
  }

  try {
    fs.writeFileSync(TRACE_FILE, '');
    patcherLog('vitest_worker_instrument_start', {
      file: VITEST_WORKER,
      node: process.version,
    });
  } catch (e) {
    console.error(`[vitest-worker-instrument] cannot write ${TRACE_FILE}: ${e.message}`);
    process.exit(1);
  }

  let src = fs.readFileSync(VITEST_WORKER, 'utf8');

  if (src.includes(SENTINEL)) {
    console.log('[vitest-worker-instrument] already patched, skipping');
    return;
  }

  // Backup original
  fs.writeFileSync(VITEST_WORKER + '.bak', src);
  console.log(`[vitest-worker-instrument] backup saved to ${VITEST_WORKER}.bak`);

  // === Patch 0: Inject trace helper at top of file ===
  src = TRACE_HELPER + src;

  // === Patch execute() function ===
  // Original (lines 69-113 of vitest 3.2.7):
  //   async function execute(method, ctx) {
  //           disposeInternalListeners();
  //           const prepareStart = performance.now();
  //           const inspectorCleanup = setupInspect(ctx);
  //           process.env.VITEST_WORKER_ID = String(ctx.workerId);
  //           process.env.VITEST_POOL_ID = String(workerId);
  //           try {
  //                   if (ctx.worker[0] === ".") throw new Error(...);
  //                   const file = ctx.worker.startsWith("file:") ? ctx.worker : pathToFileURL(ctx.worker).toString();
  //                   const testRunnerModule = await import(file);
  //                   if (!testRunnerModule.default || ...) throw new TypeError(...);
  //                   const worker = testRunnerModule.default;
  //                   if (!worker.getRpcOptions || ...) throw new TypeError(...);
  //                   const { rpc, onCancel } = createRuntimeRpc(worker.getRpcOptions(ctx));
  //                   const beforeEnvironmentTime = performance.now();
  //                   const environment = await loadEnvironment(ctx, rpc);
  //                   if (ctx.environment.transformMode) environment.transformMode = ctx.environment.transformMode;
  //                   const state = { ... };
  //                   const methodName = method === "collect" ? "collectTests" : "runTests";
  //                   if (!worker[methodName] || ...) throw new TypeError(...);
  //                   await worker[methodName](state);
  //           } finally {
  //                   await rpcDone().catch(() => {});
  //                   inspectorCleanup();
  //           }
  //   }

  // Patch 1: VW_EXECUTE_ENTER at function entry (after disposeInternalListeners)
  // Indentation: top-level function, 1 tab for body
  const entryRegex = /(async function execute\(method, ctx\) \{\n\tdisposeInternalListeners\(\);)/;
  if (!entryRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find execute() entry');
    process.exit(1);
  }
  src = src.replace(
    entryRegex,
    `$1\n\t__vw_trace("VW_EXECUTE_ENTER", { method: method, worker_id: ctx.workerId });`
  );

  // Patch 2: VW_IMPORT_RUNNER after `const testRunnerModule = await import(file);`
  // Indentation: 2 tabs for try body
  const importRegex = /(\t\tconst testRunnerModule = await import\(file\);)/;
  if (!importRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find import(file)');
    process.exit(1);
  }
  src = src.replace(
    importRegex,
    `$1\n\t\t__vw_trace("VW_IMPORT_RUNNER", { file: file });`
  );

  // Patch 3: VW_ENV_LOADED after `const environment = await loadEnvironment(ctx, rpc);`
  // Indentation: 2 tabs for try body
  const envRegex = /(\t\tconst environment = await loadEnvironment\(ctx, rpc\);)/;
  if (!envRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find loadEnvironment');
    process.exit(1);
  }
  src = src.replace(
    envRegex,
    `$1\n\t\t__vw_trace("VW_ENV_LOADED", { environment_name: ctx.environment.name });`
  );

  // Patch 4 & 5: VW_RUNTESTS_PRE/POST around `await worker[methodName](state);`
  // Indentation: 2 tabs for try body
  const runTestsRegex = /(\t\tawait worker\[methodName\]\(state\);)/;
  if (!runTestsRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find worker[methodName](state)');
    process.exit(1);
  }
  src = src.replace(
    runTestsRegex,
    `\t\t__vw_trace("VW_RUNTESTS_PRE", { method: methodName });\n$1\n\t\t__vw_trace("VW_RUNTESTS_POST", { method: methodName });`
  );

  // Patch 6: VW_FINALLY_ENTER at finally block entry
  // Indentation: 1 tab for finally (it's at same level as try)
  const finallyRegex = /(\t\} finally \{)/;
  if (!finallyRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find finally block');
    process.exit(1);
  }
  src = src.replace(
    finallyRegex,
    `$1\n\t\t__vw_trace("VW_FINALLY_ENTER", {});`
  );

  // Patch 7 & 8: VW_RPCDONE_PRE/POST around `await rpcDone().catch(() => {});`
  // Indentation: 2 tabs for finally body
  const rpcDoneRegex = /(\t\tawait rpcDone\(\)\.catch\(\(\) => \{\}\);)/;
  if (!rpcDoneRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find rpcDone()');
    process.exit(1);
  }
  src = src.replace(
    rpcDoneRegex,
    `\t\t__vw_trace("VW_RPCDONE_PRE", {});\n$1\n\t\t__vw_trace("VW_RPCDONE_POST", {});`
  );

  // Patch 9: VW_INSPECTOR_CLEANUP after `inspectorCleanup();`
  // Indentation: 2 tabs for finally body
  const inspectorRegex = /(\t\tinspectorCleanup\(\);)/;
  if (!inspectorRegex.test(src)) {
    console.error('[vitest-worker-instrument] cannot find inspectorCleanup()');
    process.exit(1);
  }
  src = src.replace(
    inspectorRegex,
    `$1\n\t\t__vw_trace("VW_INSPECTOR_CLEANUP", {});`
  );

  // Write patched file
  fs.writeFileSync(VITEST_WORKER, src);
  console.log(`[vitest-worker-instrument] patched ${VITEST_WORKER}`);
  console.log(`[vitest-worker-instrument] beacons added:`);
  console.log(`  VW_EXECUTE_ENTER     — execute() function entry`);
  console.log(`  VW_IMPORT_RUNNER     — after import(file) (test runner loaded)`);
  console.log(`  VW_ENV_LOADED        — after loadEnvironment() (jsdom ready)`);
  console.log(`  VW_RUNTESTS_PRE      — before worker[methodName](state)`);
  console.log(`  VW_RUNTESTS_POST     — after worker[methodName](state) returns`);
  console.log(`  VW_FINALLY_ENTER     — finally block entered`);
  console.log(`  VW_RPCDONE_PRE       — before rpcDone()`);
  console.log(`  VW_RPCDONE_POST      — after rpcDone() returns`);
  console.log(`  VW_INSPECTOR_CLEANUP — after inspectorCleanup()`);
  console.log(`[vitest-worker-instrument] each beacon includes elapsed_ms since previous`);
  console.log(`[vitest-worker-instrument] trace lines: VW_TRACE:{json} on stderr`);
  patcherLog('vitest_worker_instrument_applied', {
    beacons: ['VW_EXECUTE_ENTER', 'VW_IMPORT_RUNNER', 'VW_ENV_LOADED', 'VW_RUNTESTS_PRE', 'VW_RUNTESTS_POST', 'VW_FINALLY_ENTER', 'VW_RPCDONE_PRE', 'VW_RPCDONE_POST', 'VW_INSPECTOR_CLEANUP'],
  });
}

try {
  patch();
} catch (e) {
  console.error(`[vitest-worker-instrument] fatal: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}
