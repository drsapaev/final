#!/usr/bin/env node
/*
 * Instrumentation patcher for tinypool 1.1.1.
 *
 * Patches `node_modules/tinypool/dist/index.js` AFTER `npm ci` to add
 * structured logging to the pool shutdown path:
 *
 *   Tinypool.prototype.destroy     (top-level entry, called by vitest)
 *   Pool.prototype.destroy         (internal pool teardown)
 *   WorkerInfo.prototype.destroy   (per-worker teardown)
 *   worker.terminate() call        (actual Node worker_threads terminate)
 *
 * Each instrumentation point writes a "TINYPOOL_TRACE:" prefixed JSON line
 * to process.stderr (synchronous, available in ESM). The CI workflow greps
 * these out of the combined log to reconstruct the shutdown sequence.
 *
 * Why patch (not require hook):
 *   - Vitest imports tinypool via static `import 'tinypool'` at module load.
 *   - A require hook would only fire after the module is already loaded,
 *     so the prototype methods would already be cached.
 *   - Patching the file on disk before vitest starts is the most reliable
 *     way to ensure instrumentation is in place.
 *
 * Why process.stderr (not fs):
 *   - tinypool dist is ESM ("type": "module"), and `require('fs')` is
 *     NOT available inside an ES module.
 *   - process.stderr is a global, always available, and is synchronous.
 *
 * Approach: regex-based patching
 *   Original source uses tab indentation, which is fragile to match
 *   exactly in JS template literals. Instead, we find each method by
 *   a unique signature regex and inject trace calls at known points.
 *
 * Idempotency:
 *   Checks for a sentinel (`__tp_trace`) and skips if already applied.
 *
 * Rollback:
 *   Set TINYPOOL_INSTRUMENT=0 in env, OR delete node_modules/tinypool/dist/index.js
 *   and re-run `npm ci` to restore original.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const TINYPOOL_INDEX = path.join(
  process.cwd(),
  'node_modules/tinypool/dist/index.js'
);
const TRACE_FILE = '/tmp/tinypool-trace.jsonl';
const SENTINEL = '__tp_trace';

// ESM-safe trace helper injected at top of patched file.
// Captures BOTH wall-clock (Date.now) AND monotonic time (process.hrtime.bigint)
// relative to the first trace call. The monotonic offset lets us distinguish
// "events stopped immediately" from "events stopped after a long wait".
// Monotonic nanoseconds are immune to system clock adjustments and are the
// correct primitive for measuring elapsed time between events.
const TRACE_HELPER = `
var __tp_trace_start = null;
function __tp_trace(event, payload) {
  try {
    var now = Date.now();
    var hr = process.hrtime.bigint();
    if (__tp_trace_start === null) __tp_trace_start = hr;
    var monotonic_ns = Number(hr - __tp_trace_start);
    var line = JSON.stringify({
      ts: now,
      mono_ms: Math.round(monotonic_ns / 1000000),
      pid: process.pid,
      event: event,
      payload: payload || {}
    });
    process.stderr.write('TINYPOOL_TRACE:' + line + '\\n');
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
    process.stderr.write(`[tinypool-instrument] failed to log: ${e.message}\n`);
  }
}

function patch() {
  if (process.env.TINYPOOL_INSTRUMENT === '0') {
    console.log('[tinypool-instrument] disabled by env, skipping');
    return;
  }

  if (!fs.existsSync(TINYPOOL_INDEX)) {
    console.error(`[tinypool-instrument] not found: ${TINYPOOL_INDEX}`);
    console.error('  Run this script from frontend/ after `npm ci`');
    process.exit(1);
  }

  // Patcher's own diagnostic log (separate from runtime TINYPOOL_TRACE: lines)
  try {
    fs.writeFileSync(TRACE_FILE, '');
    patcherLog('instrument_start', {
      file: TINYPOOL_INDEX,
      node: process.version,
    });
  } catch (e) {
    console.error(`[tinypool-instrument] cannot write ${TRACE_FILE}: ${e.message}`);
    process.exit(1);
  }

  let src = fs.readFileSync(TINYPOOL_INDEX, 'utf8');

  if (src.includes(SENTINEL)) {
    console.log('[tinypool-instrument] already patched, skipping');
    return;
  }

  // Backup original
  fs.writeFileSync(TINYPOOL_INDEX + '.bak', src);
  console.log(`[tinypool-instrument] backup saved to ${TINYPOOL_INDEX}.bak`);

  // === Patch 0: Inject trace helper at top of file ===
  src = TRACE_HELPER + src;

  // === Patch 1: WorkerInfo.destroy(timeout) ===
  // Match the entire method body via regex, then replace with instrumented version.
  // The method starts with `async destroy(timeout) {` and ends with the
  // matching `}` before the next method definition `clearIdleTimeout()`.
  const workerDestroyRegex = /async destroy\(timeout\) \{[\s\S]*?\n\t\}\n\tclearIdleTimeout\(\) \{/;
  const workerDestroyMatch = src.match(workerDestroyRegex);
  if (!workerDestroyMatch) {
    console.error('[tinypool-instrument] cannot find WorkerInfo.destroy() to patch');
    console.error('  tinypool 1.1.1 source structure may have changed');
    console.error('  Expected pattern: async destroy(timeout) { ... } clearIdleTimeout() {');
    process.exit(1);
  }

  const workerDestroyOriginal = workerDestroyMatch[0];
  // Extract just the method body (without trailing clearIdleTimeout)
  const workerDestroyNew =
    'async destroy(timeout) {\n' +
    '\t\t__tp_trace("workerinfo_destroy_enter", { has_teardown: !!(this.teardown && this.filename), task_count: this.taskInfos ? this.taskInfos.size : -1, timeout: timeout || null });\n' +
    '\t\tlet resolve;\n' +
    '\t\tlet reject;\n' +
    '\t\tconst ret = new Promise((res, rej) => {\n' +
    '\t\t\tresolve = res;\n' +
    '\t\t\treject = rej;\n' +
    '\t\t});\n' +
    '\t\tif (this.teardown && this.filename) {\n' +
    '\t\t\tconst { teardown, filename } = this;\n' +
    '\t\t\t__tp_trace("workerinfo_destroy_teardown_start", {});\n' +
    '\t\t\tawait new Promise((resolve$1, reject$1) => {\n' +
    '\t\t\t\tthis.postTask(new TaskInfo({}, [], filename, teardown, (error, result) => error ? reject$1(error) : resolve$1(result), null, 1, void 0));\n' +
    '\t\t\t});\n' +
    '\t\t\t__tp_trace("workerinfo_destroy_teardown_done", {});\n' +
    '\t\t}\n' +
    '\t\tconst timer = timeout ? setTimeout(() => { __tp_trace("workerinfo_destroy_timeout_fired", {}); reject(new Error("Failed to terminate worker")); }, timeout) : null;\n' +
    '\t\t__tp_trace("workerinfo_destroy_terminate_pre", {});\n' +
    '\t\tthis.worker.terminate().then(() => {\n' +
    '\t\t\t__tp_trace("workerinfo_destroy_terminate_done", {});\n' +
    '\t\t\tif (timer !== null) clearTimeout(timer);\n' +
    '\t\t\tthis.port.close();\n' +
    '\t\t\tthis.clearIdleTimeout();\n' +
    '\t\t\tfor (const taskInfo of this.taskInfos.values()) taskInfo.done(Errors.ThreadTermination());\n' +
    '\t\t\tthis.taskInfos.clear();\n' +
    '\t\t\t__tp_trace("workerinfo_destroy_resolved", {});\n' +
    '\t\t\tresolve();\n' +
    '\t\t}).catch((err) => {\n' +
    '\t\t\t__tp_trace("workerinfo_destroy_terminate_error", { error: String(err && err.message || err) });\n' +
    '\t\t\tif (timer !== null) clearTimeout(timer);\n' +
    '\t\t\treject(err);\n' +
    '\t\t});\n' +
    '\t\treturn ret;\n' +
    '\t}\n' +
    '\tclearIdleTimeout() {';

  src = src.replace(workerDestroyRegex, workerDestroyNew);

  // === Patch 2: Pool.destroy() ===
  // Match the Pool class destroy method, which ends right before recycleWorkers.
  const poolDestroyRegex = /async destroy\(\) \{\n\t\twhile \(this\.skipQueue[\s\S]*?await Promise\.all\(exitEvents\);\n\t\}\n\tasync recycleWorkers/;
  const poolDestroyMatch = src.match(poolDestroyRegex);
  if (!poolDestroyMatch) {
    console.error('[tinypool-instrument] cannot find Pool.destroy() to patch');
    console.error('  Expected pattern: async destroy() { ... while (this.skipQueue ... await Promise.all(exitEvents); } async recycleWorkers');
    process.exit(1);
  }

  const poolDestroyNew =
    'async destroy() {\n' +
    '\t\t__tp_trace("pool_destroy_enter", { workers_size: this.workers ? this.workers.size : -1, task_queue_size: this.taskQueue ? this.taskQueue.size : -1, skip_queue_size: this.skipQueue ? this.skipQueue.length : -1 });\n' +
    '\t\twhile (this.skipQueue.length > 0) {\n' +
    '\t\t\tconst taskInfo = this.skipQueue.shift();\n' +
    '\t\t\ttaskInfo.done(new Error("Terminating worker thread"));\n' +
    '\t\t}\n' +
    '\t\twhile (this.taskQueue.size > 0) {\n' +
    '\t\t\tconst taskInfo = this.taskQueue.shift();\n' +
    '\t\t\ttaskInfo.done(new Error("Terminating worker thread"));\n' +
    '\t\t}\n' +
    '\t\t__tp_trace("pool_destroy_queues_drained", { workers_size: this.workers ? this.workers.size : -1 });\n' +
    '\t\tconst exitEvents = [];\n' +
    '\t\twhile (this.workers.size > 0) {\n' +
    '\t\t\tconst [workerInfo] = this.workers;\n' +
    '\t\t\texitEvents.push(once(workerInfo.worker, "exit"));\n' +
    '\t\t\tthis._removeWorker(workerInfo);\n' +
    '\t\t}\n' +
    '\t\t__tp_trace("pool_destroy_workers_removed", { exit_events: exitEvents.length });\n' +
    '\t\tawait Promise.all(exitEvents);\n' +
    '\t\t__tp_trace("pool_destroy_exit_events_resolved", {});\n' +
    '\t}\n' +
    '\tasync recycleWorkers';

  src = src.replace(poolDestroyRegex, poolDestroyNew);

  // === Patch 3: Tinypool.prototype.destroy() ===
  // Match: async destroy() { await this.#pool.destroy(); this.emitDestroy(); }
  // This is the only method that calls this.#pool.destroy() and this.emitDestroy() in sequence.
  const tinypoolDestroyRegex = /async destroy\(\) \{\n\t\tawait this\.#pool\.destroy\(\);\n\t\tthis\.emitDestroy\(\);\n\t\}/;
  const tinypoolDestroyMatch = src.match(tinypoolDestroyRegex);
  if (!tinypoolDestroyMatch) {
    console.error('[tinypool-instrument] cannot find Tinypool.destroy() to patch');
    console.error('  Expected pattern: async destroy() { await this.#pool.destroy(); this.emitDestroy(); }');
    process.exit(1);
  }

  const tinypoolDestroyNew =
    'async destroy() {\n' +
    '\t\t__tp_trace("tinypool_destroy_enter", {});\n' +
    '\t\ttry {\n' +
    '\t\t\tawait this.#pool.destroy();\n' +
    '\t\t\t__tp_trace("tinypool_destroy_pool_done", {});\n' +
    '\t\t} catch (e) {\n' +
    '\t\t\t__tp_trace("tinypool_destroy_pool_error", { error: String(e && e.message || e) });\n' +
    '\t\t\tthrow e;\n' +
    '\t\t}\n' +
    '\t\tthis.emitDestroy();\n' +
    '\t\t__tp_trace("tinypool_destroy_complete", {});\n' +
    '\t}';

  src = src.replace(tinypoolDestroyRegex, tinypoolDestroyNew);

  // Write patched file
  fs.writeFileSync(TINYPOOL_INDEX, src);
  console.log(`[tinypool-instrument] patched ${TINYPOOL_INDEX}`);
  console.log(`[tinypool-instrument] trace lines will appear as "TINYPOOL_TRACE:{...}" on stderr`);
  patcherLog('instrument_applied', {
    patches: ['workerinfo_destroy', 'pool_destroy', 'tinypool_destroy'],
  });
}

try {
  patch();
} catch (e) {
  console.error(`[tinypool-instrument] fatal: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}
