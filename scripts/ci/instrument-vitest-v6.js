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

  // === Patch B0: Beacons around `await this.pool.runTests(specs, invalidates)` ===
  // Per maintainer v6.2 feedback: previous v6.1 run showed NO beacons fired
  // (only B6_exit). This could mean:
  //   (a) hang is before pool.runTests, OR
  //   (b) patch was applied to wrong file / wrong chunk version
  //
  // To distinguish, we add ONLY 2 beacons around pool.runTests (the most
  // likely culprit) AND verify the patch is in the executed file.
  //
  // Interpretation:
  //   B0_pre present, B0_post absent → hang INSIDE pool.runTests()
  //   B0_post present                → pool.runTests returns, look elsewhere
  //   B0_pre absent                  → hang BEFORE pool.runTests (earlier in
  //                                    runFiles try block) OR patch not applied
  //
  // Original (vitest 3.2.7, line 9648, 5-tab indent):
  //   \t\t\t\ttry {
  //   \t\t\t\t\tawait this.pool.runTests(specs, invalidates);
  //   \t\t\t\t} catch (err) {
  //
  // Patched:
  //   \t\t\t\ttry {
  //   \t\t\t\t\t__vitest_trace("B0_pre_runTests", {});
  //   \t\t\t\t\tawait this.pool.runTests(specs, invalidates);
  //   \t\t\t\t\t__vitest_trace("B0_post_runTests", {});
  //   \t\t\t\t} catch (err) {
  const poolRunTestsRegex = /(\t\t\t\ttry \{\n\t\t\t\t\t)await this\.pool\.runTests\(specs, invalidates\);(\n\t\t\t\t\} catch \(err\) \{)/;
  if (!poolRunTestsRegex.test(src)) {
    console.error('[vitest-instrument] cannot find pool.runTests call to patch');
    console.error('  Expected: \\t\\t\\t\\ttry { \\n\\t\\t\\t\\t\\tawait this.pool.runTests(specs, invalidates); \\n\\t\\t\\t\\t} catch (err) {');
    process.exit(1);
  }
  src = src.replace(
    poolRunTestsRegex,
    `$1__vitest_trace("B0_pre_runTests", { phase: "about to call pool.runTests" });\n\t\t\t\t\tawait this.pool.runTests(specs, invalidates);\n\t\t\t\t\t__vitest_trace("B0_post_runTests", { phase: "pool.runTests returned" });$2`
  );

  // === Patch 1: Granular beacons inside runFiles finally block ===
  // Per maintainer v6.1 feedback: B1 fired, but we don't know if runFiles
  // actually completed or if hang is in its finally{} block. The finally
  // block (lines 9661-9668) does:
  //   1. const coverage = await this.coverageProvider?.generateCoverage({ allTestsRun });
  //   2. const errors = this.state.getUnhandledErrors();
  //   3. this._checkUnhandledErrors(errors);
  //   4. await this._testRun.end(specs, errors, coverage);
  //   5. await this.reportCoverage(coverage, allTestsRun);
  //
  // We add beacons B1a-B1e around each step + B1f at the final return.
  // Also capture getActiveResourcesInfo() at B1f (last confirmed point).
  //
  // Original finally block:
  //   } finally {
  //       // TODO: wait for coverage only if `onFinished` is defined
  //       const coverage = await this.coverageProvider?.generateCoverage({ allTestsRun });
  //       const errors = this.state.getUnhandledErrors();
  //       this._checkUnhandledErrors(errors);
  //       await this._testRun.end(specs, errors, coverage);
  //       await this.reportCoverage(coverage, allTestsRun);
  //   }
  //
  // Patched:
  //   } finally {
  //       __vitest_trace("B1a_finally_entered", {});
  //       const coverage = await this.coverageProvider?.generateCoverage({ allTestsRun });
  //       __vitest_trace("B1b_after_generateCoverage", {});
  //       const errors = this.state.getUnhandledErrors();
  //       this._checkUnhandledErrors(errors);
  //       __vitest_trace("B1c_after_checkUnhandledErrors", {});
  //       await this._testRun.end(specs, errors, coverage);
  //       __vitest_trace("B1d_after_testRun_end", {});
  //       await this.reportCoverage(coverage, allTestsRun);
  //       __vitest_trace("B1e_after_reportCoverage", {});
  //   }
  const runFilesFinallyRegex = /(\t\t\t\} finally \{\n\t\t\t\t\/\/ TODO: wait for coverage only if `onFinished` is defined\n\t\t\t\t)const coverage = await this\.coverageProvider\?\.generateCoverage\(\{ allTestsRun \}\);\n\t\t\t\t(const errors = this\.state\.getUnhandledErrors\(\);\n\t\t\t\t)this\._checkUnhandledErrors\(errors\);\n\t\t\t\t(await this\._testRun\.end\(specs, errors, coverage\);\n\t\t\t\t)await this\.reportCoverage\(coverage, allTestsRun\);\n\t\t\t\}/;
  if (!runFilesFinallyRegex.test(src)) {
    console.error('[vitest-instrument] cannot find runFiles finally block');
    console.error('  Expected: } finally { ... generateCoverage ... _testRun.end ... reportCoverage }');
    process.exit(1);
  }
  src = src.replace(
    runFilesFinallyRegex,
    `$1__vitest_trace("B1a_finally_entered", { phase: "runFiles finally block entered" });\n\t\t\t\tconst coverage = await this.coverageProvider?.generateCoverage({ allTestsRun });\n\t\t\t\t__vitest_trace("B1b_after_generateCoverage", { phase: "generateCoverage returned" });\n\t\t\t\t$2this._checkUnhandledErrors(errors);\n\t\t\t\t__vitest_trace("B1c_after_checkUnhandledErrors", { phase: "unhandled errors checked" });\n\t\t\t\t$3__vitest_trace("B1d_after_testRun_end", { phase: "_testRun.end returned" });\n\t\t\t\tawait this.reportCoverage(coverage, allTestsRun);\n\t\t\t\t__vitest_trace("B1e_after_reportCoverage", { phase: "reportCoverage returned, finally block complete" });\n\t\t\t}`
  );

  // === Patch 1f: Around `return await this.runningPromise` ===
  // Per maintainer v6.1: capture active resources at last confirmed point.
  // We split `return await this.runningPromise` into:
  //   const __runningResult = await this.runningPromise;
  //   __vitest_trace("B1f_post_await", { active_resources, ... });
  //   return __runningResult;
  //
  // B1f_post_await fires AFTER runningPromise resolves (i.e. after the
  // async IIFE + its .finally() callback complete). This is the true
  // "runFiles fully complete" point.
  //
  // We match `\t\treturn await this.runningPromise;\n\t}` — this is the
  // runFiles method (collectTests at line 9716 uses the same pattern but
  // we only replace the FIRST occurrence, which is runFiles).
  const runFilesReturnRegex = /\t\treturn await this\.runningPromise;\n\t\}\n/;
  if (!runFilesReturnRegex.test(src)) {
    console.error('[vitest-instrument] cannot find runFiles return point');
    console.error('  Expected: \\t\\treturn await this.runningPromise;');
    process.exit(1);
  }
  // Replace only the FIRST occurrence (runFiles, not collectTests)
  src = src.replace(
    runFilesReturnRegex,
    '\t\tconst __runningResult = await this.runningPromise;\n' +
    '\t\t__vitest_trace("B1f_post_await", {\n' +
    '\t\t\tphase: "runningPromise resolved, runFiles about to return",\n' +
    '\t\t\tactive_resources: (typeof process.getActiveResourcesInfo === "function" ? process.getActiveResourcesInfo() : "getActiveResourcesInfo not available"),\n' +
    '\t\t\thandles_count: (typeof process._getActiveHandles === "function" ? process._getActiveHandles().length : -1),\n' +
    '\t\t\trequests_count: (typeof process._getActiveRequests === "function" ? process._getActiveRequests().length : -1)\n' +
    '\t\t});\n' +
    '\t\treturn __runningResult;\n' +
    '\t}\n'
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
  console.log(`  B0_pre_runTests  — before await this.pool.runTests()`);
  console.log(`  B0_post_runTests — after pool.runTests() returns`);
  console.log(`  B1a — runFiles finally block entered`);
  console.log(`  B1b — after generateCoverage`);
  console.log(`  B1c — after checkUnhandledErrors`);
  console.log(`  B1d — after _testRun.end`);
  console.log(`  B1e — after reportCoverage (finally complete)`);
  console.log(`  B1f — after runningPromise resolves, before runFiles returns (with getActiveResourcesInfo, handles_count, requests_count)`);
  console.log(`  B2  — before ctx.close() (with getActiveResourcesInfo)`);
  console.log(`  B2a — inside ctx.close() entry`);
  console.log(`  B3  — after ctx.close() returns`);
  console.log(`  B4  — before startVitest returns`);
  console.log(`  B5  — process.on('beforeExit')`);
  console.log(`  B6  — process.on('exit')`);
  console.log(`[vitest-instrument] trace lines: VITEST_TRACE:{json} on stderr`);
  patcherLog('vitest_instrument_applied', {
    beacons: ['B1a', 'B1b', 'B1c', 'B1d', 'B1e', 'B1f', 'B2', 'B2a', 'B3', 'B4', 'B5', 'B6'],
  });
}

try {
  patch();
} catch (e) {
  console.error(`[vitest-instrument] fatal: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}
