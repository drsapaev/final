#!/usr/bin/env node
/*
 * v8 instrumentation: tinypool worker lifecycle beacons.
 *
 * Per maintainer v8 plan: v7 confirmed hang is INSIDE pool.run() for
 * the 170-file singleFork batch. All tests complete (✓ markers print),
 * but pool.run() never resolves. This means worker process either:
 *   (a) doesn't send final result to parent, OR
 *   (b) sends result but parent doesn't process it, OR
 *   (c) worker can't exit after sending result (active handles)
 *
 * This patcher instruments tinypool worker (entry/process.js) to answer:
 *   1. Does worker receive the task message? (W_MSG_RECV)
 *   2. Does handler(task) return? (W_HANDLER_DONE)
 *   3. Does worker send response? (W_SEND)
 *   4. What active resources exist after handler returns?
 *   5. Does worker process exit? (process.on('beforeExit'/'exit'))
 *
 * Target: node_modules/tinypool/dist/entry/process.js (71 lines)
 *
 * Per-spec beacons added:
 *   W_MSG_RECV       — worker received task message (with taskId)
 *   W_HANDLER_PRE    — before handler(task) call
 *   W_HANDLER_DONE   — handler(task) returned (with active_resources)
 *   W_SEND_PRE       — before send(response)
 *   W_SEND_POST      — send(response) callback fired
 *   W_BEFOREEXIT     — process.on('beforeExit')
 *   W_EXIT           — process.on('exit')
 *
 * Interpretation:
 *   W_MSG_RECV yes, W_HANDLER_DONE no → hang INSIDE handler(task)
 *   W_HANDLER_DONE yes, W_SEND_POST no → hang in send() IPC
 *   W_SEND_POST yes, W_BEFOREEXIT no → parent has result but worker
 *                                        can't exit (active handles)
 *   W_BEFOREEXIT yes, W_EXIT no → hang in exit handlers
 */

'use strict';

const fs = require('fs');
const path = require('path');

const TINYPOOL_WORKER = path.join(
  process.cwd(),
  'node_modules/tinypool/dist/entry/process.js'
);
const TRACE_FILE = '/tmp/worker-trace.jsonl';
const SENTINEL = '__worker_trace';

// ESM-safe trace helper
const TRACE_HELPER = `
var __worker_trace_start = null;
function __worker_trace(event, context) {
  try {
    var now = Date.now();
    var hr = process.hrtime.bigint();
    if (__worker_trace_start === null) __worker_trace_start = hr;
    var mono_ns = Number(hr - __worker_trace_start);
    var line = JSON.stringify({
      ts: now,
      mono_ms: Math.round(mono_ns / 1000000),
      pid: process.pid,
      ppid: process.ppid,
      event: event,
      context: context || {}
    });
    process.stderr.write('WORKER_TRACE:' + line + '\\n');
  } catch (e) { /* never break worker */ }
}
// Register exit handlers at module load
process.on('beforeExit', function(code) {
  __worker_trace('W_BEFOREEXIT', { code: code, active_resources: (typeof process.getActiveResourcesInfo === "function" ? process.getActiveResourcesInfo() : []), handles_count: (typeof process._getActiveHandles === "function" ? process._getActiveHandles().length : -1), requests_count: (typeof process._getActiveRequests === "function" ? process._getActiveRequests().length : -1) });
});
process.on('exit', function(code) {
  __worker_trace('W_EXIT', { code: code });
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
    process.stderr.write(`[worker-instrument] failed to log: ${e.message}\n`);
  }
}

function patch() {
  if (process.env.WORKER_INSTRUMENT === '0') {
    console.log('[worker-instrument] disabled by env, skipping');
    return;
  }

  if (!fs.existsSync(TINYPOOL_WORKER)) {
    console.error(`[worker-instrument] not found: ${TINYPOOL_WORKER}`);
    console.error('  Run this script from frontend/ after `npm ci`');
    process.exit(1);
  }

  try {
    fs.writeFileSync(TRACE_FILE, '');
    patcherLog('worker_instrument_start', {
      file: TINYPOOL_WORKER,
      node: process.version,
    });
  } catch (e) {
    console.error(`[worker-instrument] cannot write ${TRACE_FILE}: ${e.message}`);
    process.exit(1);
  }

  let src = fs.readFileSync(TINYPOOL_WORKER, 'utf8');

  if (src.includes(SENTINEL)) {
    console.log('[worker-instrument] already patched, skipping');
    return;
  }

  // Backup original
  fs.writeFileSync(TINYPOOL_WORKER + '.bak', src);
  console.log(`[worker-instrument] backup saved to ${TINYPOOL_WORKER}.bak`);

  // === Patch 0: Inject trace helper at top of file ===
  src = TRACE_HELPER + src;

  // === Patch 1: Instrument onMessage() — task execution lifecycle ===
  // Original onMessage (line 33-61):
  //   async function onMessage(message) {
  //           const { taskId, task, filename, name } = message;
  //           let response;
  //           try {
  //                   const handler = await getHandler(filename, name);
  //                   if (handler === null) throw new Error(...);
  //                   const result = await handler(task);
  //                   response = { source: "port", ... result, error: null, ... };
  //                   if (stdout()?.writableLength > 0) await new Promise(...);
  //                   if (stderr()?.writableLength > 0) await new Promise(...);
  //           } catch (error) {
  //                   response = { source: "port", ... result: null, error: serializeError(error), ... };
  //           }
  //           send(response);
  //   }
  //
  // We add:
  //   W_MSG_RECV at function entry (with taskId)
  //   W_HANDLER_PRE before `await handler(task)`
  //   W_HANDLER_DONE after handler returns (with active_resources)
  //   W_SEND_PRE before send(response)
  //   W_SEND_POST inside send() callback

  // Patch 1a: W_MSG_RECV at onMessage entry
  // Indentation: top-level function, 1 tab for body
  const onMsgEntryRegex = /(async function onMessage\(message\) \{\n\tconst \{ taskId, task, filename, name \} = message;)/;
  if (!onMsgEntryRegex.test(src)) {
    console.error('[worker-instrument] cannot find onMessage entry');
    process.exit(1);
  }
  src = src.replace(
    onMsgEntryRegex,
    `$1\n\t__worker_trace("W_MSG_RECV", { taskId: taskId, filename: filename, name: name });`
  );

  // Patch 1b: W_HANDLER_PRE before handler(task)
  // Indentation: 2 tabs for try body
  const handlerCallRegex = /(\t\tconst result = await )handler\(task\);/;
  if (!handlerCallRegex.test(src)) {
    console.error('[worker-instrument] cannot find handler(task) call');
    process.exit(1);
  }
  src = src.replace(
    handlerCallRegex,
    `$1(__worker_trace("W_HANDLER_PRE", { taskId: taskId }), handler(task));`
  );

  // Patch 1c: W_HANDLER_DONE after handler returns (success path)
  // Indentation: 2 tabs for try body
  const responseAssignRegex = /(\t\tresponse = \{\n\t\t\tsource: "port",\n\t\t\t__tinypool_worker_message__: true,\n\t\t\ttaskId,\n\t\t\tresult,\n\t\t\terror: null,)/;
  if (!responseAssignRegex.test(src)) {
    console.error('[worker-instrument] cannot find response assignment (success path)');
    process.exit(1);
  }
  src = src.replace(
    responseAssignRegex,
    `\t\t__worker_trace("W_HANDLER_DONE", { taskId: taskId, success: true, active_resources: (typeof process.getActiveResourcesInfo === "function" ? process.getActiveResourcesInfo() : []), handles_count: (typeof process._getActiveHandles === "function" ? process._getActiveHandles().length : -1), requests_count: (typeof process._getActiveRequests === "function" ? process._getActiveRequests().length : -1) });\n$1`
  );

  // Patch 1d: W_HANDLER_DONE in catch path (error case)
  // Indentation: 2 tabs for catch body
  const catchResponseRegex = /(\t\tresponse = \{\n\t\t\tsource: "port",\n\t\t\t__tinypool_worker_message__: true,\n\t\t\ttaskId,\n\t\t\tresult: null,\n\t\t\terror: serializeError\(error\),)/;
  if (!catchResponseRegex.test(src)) {
    console.error('[worker-instrument] cannot find response assignment (error path)');
    process.exit(1);
  }
  src = src.replace(
    catchResponseRegex,
    `\t\t__worker_trace("W_HANDLER_DONE", { taskId: taskId, success: false, error: String(error && error.message || error), active_resources: (typeof process.getActiveResourcesInfo === "function" ? process.getActiveResourcesInfo() : []), handles_count: (typeof process._getActiveHandles === "function" ? process._getActiveHandles().length : -1) });\n$1`
  );

  // Patch 1e: W_SEND_PRE/W_SEND_POST around send(response)
  // Indentation: 1 tab for onMessage body
  const sendCallRegex = /(\t)send\(response\);(\n\})/;
  if (!sendCallRegex.test(src)) {
    console.error('[worker-instrument] cannot find send(response) call');
    process.exit(1);
  }
  src = src.replace(
    sendCallRegex,
    `$1__worker_trace("W_SEND_PRE", { taskId: taskId });\n$1send(response);\n$1__worker_trace("W_SEND_POST", { taskId: taskId });$2`
  );

  // Write patched file
  fs.writeFileSync(TINYPOOL_WORKER, src);
  console.log(`[worker-instrument] patched ${TINYPOOL_WORKER}`);
  console.log(`[worker-instrument] beacons added:`);
  console.log(`  W_MSG_RECV      — worker received task message (taskId, filename)`);
  console.log(`  W_HANDLER_PRE   — before handler(task) call`);
  console.log(`  W_HANDLER_DONE  — handler returned (with active_resources, handles_count)`);
  console.log(`  W_SEND_PRE      — before send(response)`);
  console.log(`  W_SEND_POST     — send(response) returned`);
  console.log(`  W_BEFOREEXIT    — process.on('beforeExit') (with active_resources)`);
  console.log(`  W_EXIT          — process.on('exit')`);
  console.log(`[worker-instrument] trace lines: WORKER_TRACE:{json} on stderr`);
  patcherLog('worker_instrument_applied', {
    beacons: ['W_MSG_RECV', 'W_HANDLER_PRE', 'W_HANDLER_DONE', 'W_SEND_PRE', 'W_SEND_POST', 'W_BEFOREEXIT', 'W_EXIT'],
  });
}

try {
  patch();
} catch (e) {
  console.error(`[worker-instrument] fatal: ${e.message}`);
  console.error(e.stack);
  process.exit(1);
}
