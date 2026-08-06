#!/usr/bin/env node
/*
 * v4 diagnostic: connect to Node.js inspector via CDP WebSocket,
 * evaluate safe process._getActiveHandles() / _getActiveRequests().
 *
 * Usage:
 *   node diag-handles-v4.js <port> [label]
 *
 * Why a custom WebSocket client:
 *   - Node's `inspector` module can only connect to the CURRENT process,
 *     not to a remote inspector.
 *   - The HTTP `/json` endpoint only LISTS inspector contexts; it cannot
 *     evaluate expressions.
 *   - To call `Runtime.evaluate` we need a WebSocket connection speaking
 *     the Chrome DevTools Protocol.
 *   - Node 20 has no built-in WebSocket in stable, so we implement the
 *     minimum RFC 6455 client needed for CDP.
 *
 * Safe serialization (per maintainer feedback):
 *   We do NOT call JSON.stringify(process._getActiveHandles()) directly —
 *   Socket/Pipe/MessagePort objects have circular references and internal
 *   fields that break serialization. Instead we project each handle to a
 *   plain object with only the fields that matter for diagnosis:
 *     type, hasRef, destroyed, readable, writable, fd
 */

'use strict';

const http = require('http');
const net = require('net');
const crypto = require('crypto');

const HOST = '127.0.0.1';
const CONNECT_TIMEOUT_MS = 5000;
const CDP_TIMEOUT_MS = 10000;

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse failed: ${e.message}`)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(CONNECT_TIMEOUT_MS, () => {
      req.destroy(new Error('HTTP timeout'));
    });
  });
}

/**
 * Minimal RFC 6455 WebSocket client sufficient for CDP.
 * - Client-to-server frames MUST be masked (we mask).
 * - Server-to-client frames are NOT masked (we handle both).
 * - Only text frames (opcode 1) are processed; close/ping ignored.
 */
class CdpWebSocketClient {
  constructor(port, path) {
    this.port = port;
    this.path = path;
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.upgraded = false;
    this.pending = new Map(); // id -> {resolve, reject}
    this.nextId = 1;
  }

  connect() {
    return new Promise((resolve, reject) => {
      const key = crypto.randomBytes(16).toString('base64');
      this.socket = net.connect(this.port, HOST, () => {
        const lines = [
          `GET ${this.path} HTTP/1.1`,
          `Host: ${HOST}:${this.port}`,
          `Upgrade: websocket`,
          `Connection: Upgrade`,
          `Sec-WebSocket-Key: ${key}`,
          `Sec-WebSocket-Version: 13`,
          ``,
          ``,
        ];
        this.socket.write(lines.join('\r\n'));
      });

      const onTimeout = () => {
        if (!this.upgraded) {
          this.socket.destroy();
          reject(new Error(`WebSocket handshake timeout (port ${this.port})`));
        }
      };
      const timer = setTimeout(onTimeout, CONNECT_TIMEOUT_MS);

      this.socket.on('data', (chunk) => {
        this.buffer = Buffer.concat([this.buffer, chunk]);
        if (!this.upgraded) {
          const idx = this.buffer.indexOf('\r\n\r\n');
          if (idx === -1) return;
          const headerBlock = this.buffer.slice(0, idx).toString();
          if (!headerBlock.includes('101')) {
            clearTimeout(timer);
            this.socket.destroy();
            reject(new Error(`WebSocket upgrade failed:\n${headerBlock}`));
            return;
          }
          this.buffer = this.buffer.slice(idx + 4);
          this.upgraded = true;
          clearTimeout(timer);
          resolve();
        }
        this._parseFrames();
      });

      this.socket.on('error', (err) => {
        if (!this.upgraded) {
          clearTimeout(timer);
          reject(err);
        }
      });

      this.socket.on('close', () => {
        // Reject any pending requests
        for (const [id, { reject }] of this.pending) {
          reject(new Error('WebSocket closed'));
        }
        this.pending.clear();
      });
    });
  }

  _parseFrames() {
    while (this.buffer.length >= 2) {
      const b0 = this.buffer[0];
      const b1 = this.buffer[1];
      const opcode = b0 & 0x0F;
      const masked = (b1 & 0x80) !== 0;
      let payloadLen = b1 & 0x7F;
      let offset = 2;

      if (payloadLen === 126) {
        if (this.buffer.length < 4) return;
        payloadLen = this.buffer.readUInt16BE(2);
        offset = 4;
      } else if (payloadLen === 127) {
        if (this.buffer.length < 10) return;
        const hi = this.buffer.readUInt32BE(2);
        const lo = this.buffer.readUInt32BE(6);
        payloadLen = hi * 0x100000000 + lo;
        offset = 10;
      }

      let payload;
      if (masked) {
        if (this.buffer.length < offset + 4 + payloadLen) return;
        const mask = this.buffer.slice(offset, offset + 4);
        offset += 4;
        payload = Buffer.alloc(payloadLen);
        const src = this.buffer.slice(offset, offset + payloadLen);
        for (let i = 0; i < payloadLen; i++) {
          payload[i] = src[i] ^ mask[i % 4];
        }
        this.buffer = this.buffer.slice(offset + payloadLen);
      } else {
        if (this.buffer.length < offset + payloadLen) return;
        payload = this.buffer.slice(offset, offset + payloadLen);
        this.buffer = this.buffer.slice(offset + payloadLen);
      }

      if (opcode === 1) { // text
        const text = payload.toString('utf8');
        this._onMessage(text);
      } else if (opcode === 8) { // close
        this.socket.end();
        return;
      }
      // opcode 9 (ping) / 10 (pong) — ignored, sufficient for CDP
    }
  }

  _onMessage(text) {
    let msg;
    try { msg = JSON.parse(text); } catch { return; }
    if (msg.id !== undefined && this.pending.has(msg.id)) {
      const { resolve, reject } = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      if (msg.error) {
        reject(new Error(`CDP error: ${JSON.stringify(msg.error)}`));
      } else {
        resolve(msg.result);
      }
    }
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.nextId++;
      const payload = Buffer.from(JSON.stringify({ id, method, params }), 'utf8');
      const mask = crypto.randomBytes(4);

      let header;
      if (payload.length < 126) {
        header = Buffer.alloc(6);
        header[0] = 0x81; // FIN + text
        header[1] = 0x80 | payload.length; // masked + len
        mask.copy(header, 2);
      } else if (payload.length < 65536) {
        header = Buffer.alloc(8);
        header[0] = 0x81;
        header[1] = 0x80 | 126;
        header.writeUInt16BE(payload.length, 2);
        mask.copy(header, 4);
      } else {
        header = Buffer.alloc(14);
        header[0] = 0x81;
        header[1] = 0x80 | 127;
        header.writeUInt32BE(0, 2);
        header.writeUInt32BE(payload.length, 6);
        mask.copy(header, 10);
      }

      const masked = Buffer.alloc(payload.length);
      for (let i = 0; i < payload.length; i++) {
        masked[i] = payload[i] ^ mask[i % 4];
      }

      this.pending.set(id, { resolve, reject });
      this.socket.write(Buffer.concat([header, masked]));

      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP method "${method}" timed out after ${CDP_TIMEOUT_MS}ms`));
        }
      }, CDP_TIMEOUT_MS);
    });
  }

  close() {
    if (this.socket) {
      try { this.socket.end(); } catch {}
    }
  }
}

async function diagnose(port, label) {
  console.log(`\n========================================`);
  console.log(`=== ${label} (inspector port ${port}) ===`);
  console.log(`========================================`);

  // 1. Discover the WebSocket URL via /json
  let contexts;
  try {
    contexts = await fetchJSON(`http://${HOST}:${port}/json`);
  } catch (e) {
    console.log(`✗ Cannot reach inspector on port ${port}: ${e.message}`);
    return false;
  }

  if (!Array.isArray(contexts) || contexts.length === 0) {
    console.log(`✗ No inspector contexts on port ${port}`);
    return false;
  }

  console.log(`Inspector contexts: ${contexts.length}`);
  contexts.forEach((c, i) => {
    console.log(`  [${i}] title=${JSON.stringify(c.title)} url=${JSON.stringify(c.url)}`);
  });

  const wsUrl = contexts[0].webSocketDebuggerUrl;
  if (!wsUrl) {
    console.log(`✗ No webSocketDebuggerUrl in first context`);
    return false;
  }

  // Parse ws://127.0.0.1:PORT/UUID → path = /UUID
  const match = wsUrl.match(/^ws:\/\/[^/]+\/(.+)$/);
  const path = match ? `/${match[1]}` : '/';
  console.log(`WebSocket path: ${path}`);

  // 2. Connect via WebSocket
  const ws = new CdpWebSocketClient(port, path);
  try {
    await ws.connect();
    console.log(`✓ WebSocket connected`);
  } catch (e) {
    console.log(`✗ WebSocket connect failed: ${e.message}`);
    return false;
  }

  try {
    // 3. Enable Runtime domain (required for Runtime.evaluate)
    await ws.send('Runtime.enable');
    console.log(`✓ Runtime.enable OK`);

    // 4. Evaluate safe expression for active handles
    //    Per maintainer: do NOT JSON.stringify handles directly (circular refs).
    //    Project each handle to a plain object with diagnostic fields.
    const handlesExpr = [
      '(() => {',
      '  try {',
      '    return process._getActiveHandles().map(h => ({',
      '      type: h && h.constructor ? h.constructor.name : String(h),',
      '      hasRef: typeof h.hasRef === "function" ? h.hasRef() : undefined,',
      '      destroyed: h.destroyed,',
      '      readable: h.readable,',
      '      writable: h.writable,',
      '      fd: typeof h.fd === "number" ? h.fd : undefined',
      '    }))',
      '  } catch (e) {',
      '    return { error: String(e && e.message || e) }',
      '  }',
      '})()',
    ].join('\n');

    console.log(`\n--- process._getActiveHandles() ---`);
    const handlesResult = await ws.send('Runtime.evaluate', {
      expression: handlesExpr,
      returnByValue: true,
      awaitPromise: false,
    });

    if (handlesResult && handlesResult.result) {
      const val = handlesResult.result.value;
      if (Array.isArray(val)) {
        console.log(`Count: ${val.length}`);
        val.forEach((h, i) => {
          console.log(`  [${i}] ${JSON.stringify(h)}`);
        });
      } else {
        console.log(`Non-array result: ${JSON.stringify(val, null, 2)}`);
      }
      if (handlesResult.exceptionDetails) {
        console.log(`Exception: ${JSON.stringify(handlesResult.exceptionDetails, null, 2)}`);
      }
    } else {
      console.log(`Unexpected result: ${JSON.stringify(handlesResult, null, 2)}`);
    }

    // 5. Evaluate safe expression for active requests
    const requestsExpr = [
      '(() => {',
      '  try {',
      '    return process._getActiveRequests().map(r => r && r.constructor ? r.constructor.name : String(r))',
      '  } catch (e) {',
      '    return { error: String(e && e.message || e) }',
      '  }',
      '})()',
    ].join('\n');

    console.log(`\n--- process._getActiveRequests() ---`);
    const requestsResult = await ws.send('Runtime.evaluate', {
      expression: requestsExpr,
      returnByValue: true,
      awaitPromise: false,
    });

    if (requestsResult && requestsResult.result) {
      const val = requestsResult.result.value;
      if (Array.isArray(val)) {
        console.log(`Count: ${val.length}`);
        val.forEach((r, i) => {
          console.log(`  [${i}] ${r}`);
        });
      } else {
        console.log(`Non-array result: ${JSON.stringify(val, null, 2)}`);
      }
      if (requestsResult.exceptionDetails) {
        console.log(`Exception: ${JSON.stringify(requestsResult.exceptionDetails, null, 2)}`);
      }
    } else {
      console.log(`Unexpected result: ${JSON.stringify(requestsResult, null, 2)}`);
    }

    // 6. Bonus: event loop info (libuv alive?, ref'd handles count)
    const loopExpr = [
      '(() => {',
      '  try {',
      '    return {',
      '      uptime: process.uptime(),',
      '      pid: process.pid,',
      '      ppid: process.ppid,',
      '      argv: process.argv,',
      '      execArgv: process.execArgv,',
      '      NODE_OPTIONS: process.env.NODE_OPTIONS || null',
      '    }',
      '  } catch (e) {',
      '    return { error: String(e && e.message || e) }',
      '  }',
      '})()',
    ].join('\n');

    console.log(`\n--- process identity ---`);
    const loopResult = await ws.send('Runtime.evaluate', {
      expression: loopExpr,
      returnByValue: true,
      awaitPromise: false,
    });
    if (loopResult && loopResult.result) {
      console.log(JSON.stringify(loopResult.result.value, null, 2));
    }

    return true;
  } catch (e) {
    console.log(`✗ Diagnosis failed: ${e.message}`);
    return false;
  } finally {
    ws.close();
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node diag-handles-v4.js <port> [label]');
    process.exit(2);
  }

  const port = parseInt(args[0], 10);
  const label = args[1] || `Port ${port}`;

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    console.error(`Invalid port: ${args[0]}`);
    process.exit(2);
  }

  const ok = await diagnose(port, label);
  // Give the socket time to flush
  setTimeout(() => process.exit(ok ? 0 : 1), 300);
}

main().catch((e) => {
  console.error('Fatal:', e);
  process.exit(1);
});
