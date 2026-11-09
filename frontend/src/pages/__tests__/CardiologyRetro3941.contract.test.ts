/**
 * RETRO-3941-01/02/03 (post-merge review #3944) — source contract for the
 * cardiology clinical-integrity fixes on PR #3941's surface:
 *
 *  - 01: the manual ECG form is keyed by the canonical patient+visit owner
 *    identity AND explicitly closed on a selection switch; the form itself
 *    refuses submissions under a changed owner (component-level guard is
 *    covered behaviorally in ManualEcgForm.ownerIdentity.test.tsx).
 *  - 02: Echo hydration fails closed (retry surfaced, Save blocked while the
 *    stored echo state is unknown) — behavioral coverage lives in
 *    EchoForm.visitHydration.test.tsx.
 *  - 03: echo editor inputs are disabled during save and in-flight edits
 *    keep the form dirty.
 *
 * Red-first: on pre-fix source the ManualEcgForm mount had no `key`, the
 * selection-switch effect never closed the open form, the Echo hydration
 * catch silently blanked the form, and no input was disabled during save.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const readSource = (relative: string) =>
  fs.readFileSync(path.join(__dirname, relative), 'utf8');

describe('RETRO-3941-01 — ECG form patient identity (source contract)', () => {
  const source = readSource('../CardiologistPanelUnified.tsx');
  const manualFormSource = readSource('../../components/cardiology/ManualEcgForm.tsx');

  it('mounts ManualEcgForm with an owner-identity key derived from patient+visit', () => {
    const ecgBlock =
      source.match(/\{showForm\.open && showForm\.type === 'ecg' && \([\s\S]*?\n {10}\)\}/)?.[0] ?? '';
    expect(ecgBlock).not.toBe('');
    expect(ecgBlock).toContain('<ManualEcgForm');
    // The identity key forces a remount (blank state) on every context switch.
    expect(ecgBlock).toMatch(/key=\{manualEcgFormKey\}/);
    // The key is built from the same canonical ids the props use.
    expect(source).toMatch(/const manualEcgFormKey = `manual-ecg-\$\{String\(manualEcgOwnerPatientId\)\}-\$\{String\(manualEcgOwnerVisitId\)\}`/);
    expect(source).toMatch(/manualEcgOwnerPatientId = \(\(selectedPatient\?\.patient\?\.id \|\| selectedPatient\?\.patient_id\)/);
  });

  it('closes the open entry form when the selected patient switches', () => {
    const selectionEffect =
      source.match(/\/\/ ✅ Очистка EMR и visitData при смене пациента[\s\S]*?\n {2}\}, \[selectedPatient, loadPatientData, authRefreshTick\]\);/)?.[0] ?? '';
    expect(selectionEffect).not.toBe('');
    // New patient selected → the form opened for the previous patient closes.
    expect(selectionEffect).toMatch(/previousPatientId !== null && previousPatientId !== currentPatientId[\s\S]*?setShowForm\(\{ open: false \}\)/);
    // Patient deselected → no open data-entry form either.
    expect(selectionEffect).toMatch(/\} else \{[\s\S]*?setShowForm\(\{ open: false \}\)/);
  });

  it('ManualEcgForm carries the owner guard against cross-patient submission', () => {
    expect(manualFormSource).toMatch(/const ownerRef = useRef\(\{/);
    expect(manualFormSource).toMatch(/cardio_manual_ecg_context_changed/);
    expect(manualFormSource).toMatch(/String\(patientId\) !== String\(ownerRef\.current\.patientId\)/);
  });
});

describe('RETRO-3941-02/03 — EchoForm fail-closed hydration and in-flight edits (source contract)', () => {
  const echoSource = readSource('../../components/cardiology/EchoForm.tsx');

  it('hydration failure fails closed with a visible retry', () => {
    expect(echoSource).toMatch(/const \[hydrationFailed, setHydrationFailed\] = useState\(false\)/);
    expect(echoSource).toMatch(/const \[retryTick, setRetryTick\] = useState\(0\)/);
    // The catch marks the failure instead of blanking the form.
    expect(echoSource).toMatch(/\.catch\(\(\) => \{[\s\S]*?setHydrationFailed\(true\)/);
    expect(echoSource).not.toMatch(/\.catch\(\(\) => \{[\s\S]*?setEchoData\(DEFAULT_ECHO_DATA as EchoData\)[\s\S]*?\}\)\s*\.finally/);
    // Save is blocked while the canonical state is unknown…
    expect(echoSource).toMatch(/if \(hydrating \|\| hydrationFailed\) \{/);
    expect(echoSource).toMatch(/disabled=\{loading \|\| hydrating \|\| hydrationFailed\}/);
    // …and a retry re-runs the canonical hydration.
    expect(echoSource).toMatch(/setRetryTick\(\(n\) => n \+ 1\)/);
    expect(echoSource).toMatch(/\}, \[visitId, initialData, retryTick\]\)/);
    expect(echoSource).toContain('cardio_echo_load_failed');
  });

  it('editor inputs are disabled while a save is in flight', () => {
    // Numeric fields render through the shared renderSection Input.
    expect(echoSource).toMatch(/placeholder=\{field\.placeholder\}\s*\n\s*disabled=\{loading\}/);
    // Comments + conclusion textareas too.
    const disabledTextareas = echoSource.match(/disabled=\{loading\}/g) ?? [];
    expect(disabledTextareas.length).toBeGreaterThanOrEqual(3);
  });

  it('an edit landing during save keeps the form dirty — no false success', () => {
    expect(echoSource).toMatch(/const savingRef = useRef\(false\)/);
    expect(echoSource).toMatch(/const editsDuringSaveRef = useRef\(false\)/);
    expect(echoSource).toMatch(/if \(savingRef\.current\) \{\s*\n\s*editsDuringSaveRef\.current = true;\s*\n\s*\}/);
    expect(echoSource).toMatch(/if \(editsDuringSaveRef\.current\) \{/);
    expect(echoSource).toMatch(/cardio_echo_edits_after_save/);
  });
});
