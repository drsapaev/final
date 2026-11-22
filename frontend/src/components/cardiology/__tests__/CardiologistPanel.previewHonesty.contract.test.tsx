/**
 * CARDHIST-FE-001 (audit 3886, round 28) — panel source contract for the
 * honest attachment preview wiring (repo precedent for the 2200-line
 * panel: CardiologistPanel.patientIdentity.contract.test.tsx,
 * CardiologistPanel.retro3941.contract.test.tsx).
 *
 * Pre-fix source: `previewPatientFile` awaited the full preview response,
 * created a blob: URL, called `window.open(url, '_blank',
 * 'noopener,noreferrer')` and threw the "blocked" error whenever the
 * return was falsy — which the `noopener` feature guarantees even on a
 * SUCCESSFUL open, so every working preview was reported as blocked.
 *
 * Post-fix contract: the panel delegates to utils/patientFilePreview
 * (reserved-window strategy with preserved opener isolation), and the old
 * false-failure pattern is gone. Download transport is unchanged.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../../..');

const readSource = (relPath: string) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

const panel = readSource('pages/CardiologistPanelUnified.tsx');
const helper = readSource('utils/patientFilePreview.ts');

const previewFn = panel.slice(
  panel.indexOf('const previewPatientFile'),
  panel.indexOf('const historyEntries'),
);

describe('CARDHIST-FE-001: no false "blocked" failure for successful previews', () => {
  it('the panel no longer treats a noopener-open null return as a block signal', () => {
    expect(panel).not.toContain("window.open(url, '_blank', 'noopener,noreferrer')");
    expect(panel).not.toContain('const previewWindow = window.open');
    expect(panel).not.toContain('if (!previewWindow)');
  });

  it('preview delegates to the honest reserved-window helper with the canonical wiring', () => {
    expect(previewFn).toContain('openPatientFilePreview({');
    expect(previewFn).toContain('apiBase: API_V1_BASE');
    expect(previewFn).toContain('fileId: file.id');
    expect(previewFn).toContain('cardio.cardio_panel_preview_blocked_short');
    expect(previewFn).toContain('cardio.cardio_panel_preview_unavailable_short');
    expect(previewFn).toContain('cardio.cardio_panel_open_file_failed');
  });
});

describe('CARDHIST-FE-001: helper contract (reserved window, opener isolation)', () => {
  it('reserves the browsing context synchronously before the first await', () => {
    const reserveIdx = helper.indexOf("window.open('', '_blank')");
    const fetchIdx = helper.indexOf('await fetch(');
    expect(reserveIdx).toBeGreaterThan(-1);
    expect(fetchIdx).toBeGreaterThan(reserveIdx);
  });

  it('preserves opener isolation and closes the reserved context on failure', () => {
    expect(helper).toContain('.opener = null');
    expect(helper).toContain('.close()');
    // Code (comments stripped) must not hand the blob URL to an
    // opener-enabled window.open — the old false-failure pattern.
    const helperCode = helper.replace(/^\s*(\/\/|\*|\/\*).*$/gm, '');
    expect(helperCode).not.toContain("window.open(url, '_blank', 'noopener,noreferrer')");
    expect(helperCode).not.toContain('const previewWindow = window.open');
  });

  it('does not switch to opener-enabled blob popups (privacy semantics preserved)', () => {
    // The blob URL must never be handed to a window.open call that would
    // keep an opener relationship.
    expect(helper).not.toMatch(/window\.open\(\s*blob/i);
  });
});

describe('CARDHIST-FE-001: adjacent transport is unchanged (controls)', () => {
  it('download still uses the configured API origin with an explicit filename', () => {
    expect(panel).toContain('/files/${file.id}/download');
    expect(panel).toContain('link.download =');
  });

  it('preview still requests the same authorized backend endpoint', () => {
    expect(helper).toContain('${apiBase}/files/${fileId}/preview');
    expect(helper).toContain('Authorization: `Bearer');
  });
});
