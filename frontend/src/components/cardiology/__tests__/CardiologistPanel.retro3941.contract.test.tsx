/**
 * RETRO-3941-01 (consolidated post-merge review of #3941, PR #3944) —
 * fail-first, panel source contract.
 *
 * CardiologistPanelUnified mounts <ManualEcgForm> OUTSIDE the ECG tab
 * conditional, so the form does not unmount on tab navigation, and the
 * selectedPatient change effect cleared the cached patient data stores but
 * never closed/reset the open ECG form: patient A's typed measurements
 * stayed live under patient B's identity props after a selection switch.
 *
 * The 2100+ line panel is covered by the repo-precedent source-contract
 * pattern (see CardiologistPanel.phase1.contract.test.tsx):
 *  - the manual ECG form mount is KEYED by the canonical patient+visit
 *    identity, so an identity change can never reuse A's local state;
 *  - the selection-change effect explicitly closes an open ECG form on
 *    owner change (new patient AND cleared selection);
 *  - ManualEcgForm itself resets its local form on an identity prop change
 *    (defense in depth for callers that do not key or close it).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../../..');

const readSource = (relPath: string) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

describe('RETRO-3941-01: the manual ECG form cannot outlive its patient context', () => {
  it('keys the ManualEcgForm mount by the canonical patient+visit identity', () => {
    const source = readSource('pages/CardiologistPanelUnified.tsx');

    // The mount must be keyed so a selection switch remounts a fresh form
    // instead of reusing patient A's local state under patient B's props.
    expect(source).toContain('key={`manual-ecg-');
    // The key is derived from the SAME canonical identity the props use
    // (patient id first, visit id second).
    const keyLine = source.match(/key=\{`manual-ecg-[^\n]*\}/);
    expect(keyLine).not.toBeNull();
    expect(keyLine![0]).toContain('selectedPatient');
    expect(keyLine![0]).toContain('visit_id');
  });

  it('closes an open ECG form when the selected patient changes', () => {
    const source = readSource('pages/CardiologistPanelUnified.tsx');

    // RETRO-3941-01: on owner change the open manual ECG form is closed —
    // no typed A payload may remain editable under B.
    expect(source).toContain('prev.open && prev.type === \'ecg\'');
    // The close lives inside the selection-change effect (owner change),
    // in both the switch branch and the cleared-selection branch.
    const effectStart = source.indexOf('const previousPatientId = prevSelectedPatientRef.current;');
    expect(effectStart).toBeGreaterThan(-1);
    const effectEnd = source.indexOf('}, [selectedPatient, loadPatientData, authRefreshTick]);');
    expect(effectEnd).toBeGreaterThan(effectStart);
    const effectBody = source.slice(effectStart, effectEnd);
    expect(effectBody).toContain('prev.open && prev.type === \'ecg\'');
  });

  it('ManualEcgForm resets its local form when the identity props change', () => {
    const source = readSource('components/cardiology/ManualEcgForm.tsx');

    // Defense in depth for callers that neither key nor close the form.
    expect(source).toContain('RETRO-3941-01');
    expect(source).toMatch(/identityRef/);
    expect(source).toMatch(/EMPTY_ECG_FORM/);
  });
});
