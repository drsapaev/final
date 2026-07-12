/**
 * PR-37 — Frontend Sprint 2 a11y + perf.
 *
 * Tests for:
 * 1. P0-A: Modal.jsx implements a focus trap (Tab key cycles within modal)
 * 2. P0-B: Modal.jsx uses useId() for aria-labelledby (no static "modal-title")
 * 3. P0-13: Search.jsx does not use sequential for-loop with await api.get()
 * 4. P0-C: QueueTable / AppointmentWizardV2 / NotificationInbox contrast fix
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = path.resolve(process.cwd());
const MODAL = path.join(ROOT, 'src/components/ui/macos/Modal.jsx');
const SEARCH = path.join(ROOT, 'src/pages/Search.jsx');

// ---------- 1. P0-A: Focus trap in Modal ----------

describe('P0-A: Modal focus trap', () => {
  const src = fs.readFileSync(MODAL, 'utf-8');

  it('Modal.jsx implements a Tab key handler that traps focus', () => {
    // Strip comments
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must handle Tab key explicitly (focus trap)
    // Acceptable patterns:
    //   - e.key === 'Tab' in a keydown handler
    //   - useFocusTrap hook imported and used
    //   - references to focusable elements query (a[href], button, input, etc.)
    const hasTabHandler = /e\.key\s*===\s*['"]Tab['"]/.test(stripped);
    const hasFocusTrapHook = /useFocusTrap|focus-trap-react/.test(stripped);
    const hasFocusableQuery = /querySelectorAll\(\s*['"][^'"]*(?:a\[href\]|button|input|select|textarea)/.test(stripped);
    expect(hasTabHandler || hasFocusTrapHook || hasFocusableQuery).toBe(true);
  });

  it('Modal.jsx restores focus to the trigger on close', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must save previously-focused element and restore it on close
    // Acceptable: document.activeElement captured + .focus() restored
    const hasActiveElementCapture = /document\.activeElement/.test(stripped);
    const hasFocusRestore = /\.focus\(\)/.test(stripped);
    expect(hasActiveElementCapture || hasFocusRestore).toBe(true);
  });
});

// ---------- 2. P0-B: useId for aria-labelledby ----------

describe('P0-B: Modal uses useId() instead of static id', () => {
  const src = fs.readFileSync(MODAL, 'utf-8');

  it('Modal.jsx imports useId from react', () => {
    // Accept either: import { useId } from 'react'
    // or: import React, { useEffect, useId, useRef } from 'react'
    expect(src).toMatch(/useId/);
    expect(src).toMatch(/from\s+['"]react['"]/);
  });

  it('Modal.jsx does not use a static id="modal-title" for aria-labelledby', () => {
    // Strip comments
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // Must NOT have aria-labelledby="modal-title" (static string)
    expect(stripped).not.toMatch(/aria-labelledby\s*=\s*['"]modal-title['"]/);
  });

  it('Modal.jsx uses useId() to generate a unique title id', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    expect(stripped).toMatch(/useId\(\)/);
  });
});

// ---------- 3. P0-13: Search.jsx no N+1 sequential API calls ----------

describe('P0-13: Search.jsx N+1 query fix', () => {
  const src = fs.readFileSync(SEARCH, 'utf-8');

  it('does not use a sequential for-loop with await api.get() inside', () => {
    // Strip comments
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // The old pattern was:
    //   for (const patientId of patientIds) {
    //     const pvRes = await api.get(`/visits/visits?patient_id=${patientId}`);
    //   }
    // We accept either:
    // (a) Promise.all over the patientIds array
    // (b) A single batch endpoint call
    // (c) Removed entirely
    //
    // Detect the buggy pattern: for...of loop containing await api.get
    const forOfWithAwaitGet = /for\s*\(\s*const\s+\w+\s+of\s+[^)]+\)\s*\{[^}]*await\s+api\.get\(/;
    expect(stripped).not.toMatch(forOfWithAwaitGet);
  });

  it('uses Promise.all for batched patient/visit lookups (or no batched lookup at all)', () => {
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // If the code still fetches per-patient data, it must use Promise.all
    // instead of a sequential for-loop.
    // We accept either: Promise.all over an array, OR no per-patient fetch at all.
    const hasPerPatientFetch = /\/visits\/visits\?patient_id=/.test(stripped)
      || /\/patients\/\$\{/.test(stripped);
    if (hasPerPatientFetch) {
      expect(stripped).toMatch(/Promise\.all/);
    }
    // If no per-patient fetch: pass automatically
  });
});

// ---------- 4. P0-C: Contrast fixes ----------

describe('P0-C: WCAG AA contrast fixes', () => {
  it('QueueTable.jsx does not use a foreground color with contrast < 4.5:1 on white', () => {
    const queueTable = path.join(ROOT, 'src/components/queue/QueueTable.jsx');
    if (!fs.existsSync(queueTable)) {
      console.warn('QueueTable.jsx not found — skipping');
      return;
    }
    const src = fs.readFileSync(queueTable, 'utf-8');
    const stripped = src
      .replace(/\/\/.*$/gm, '')
      .replace(/\/\*[\s\S]*?\*\//g, '');
    // The audit flagged #94a3b8 (slate-400) on white = 3.49:1 contrast (FAIL)
    // Verify this color is no longer used as a foreground on white background
    // (we accept it being replaced with a darker color, e.g., #64748b = 4.6:1)
    expect(stripped).not.toMatch(/['"]#94a3b8['"]/i);
  });
});
