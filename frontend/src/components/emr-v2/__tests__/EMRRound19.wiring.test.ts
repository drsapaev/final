import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// This file lives at components/emr-v2/__tests__/ — ROOT is emr-v2 itself.
const ROOT = path.resolve(__dirname, '..');

/**
 * EMRPRES-FE-001 / EMRHIST-FE-002 container wiring (audit 3886, round 19).
 *
 * Source-contract test (repo precedent): the behavioral suites cover the
 * leaf components in isolation; this file pins the CONTAINER wiring that
 * connects them —
 *   - EMRContainerV2 passes the canonical visit identity down to the
 *     prescription editor (visitKey), so the in-place visit switch of a
 *     mounted EMR (e.g. the dermatologist panel) resets the draft form;
 *   - the container resets the diff-viewer selection (selectedVersion +
 *     showDiff) on a visit change so a stale version selection cannot
 *     survive into another patient's EMR.
 * Fails on the pre-fix source.
 */

const container = fs.readFileSync(path.join(ROOT, 'EMRContainerV2.tsx'), 'utf8');
const treatment = fs.readFileSync(path.join(ROOT, 'sections/TreatmentSection.tsx'), 'utf8');
const editor = fs.readFileSync(path.join(ROOT, 'sections/PrescriptionEditor.tsx'), 'utf8');

describe('EMR round 19 wiring (source contract)', () => {
  it('EMRContainerV2 wires visitKey into the TreatmentSection mount', () => {
    const treatmentStart = container.indexOf('<TreatmentSection');
    expect(treatmentStart).toBeGreaterThan(-1);
    const treatmentEnd = container.indexOf('/>', treatmentStart);
    const treatmentBlock = container.slice(treatmentStart, treatmentEnd);
    expect(treatmentBlock).toContain('visitKey={visitId}');
  });

  it('TreatmentSection passes visitKey down to the PrescriptionEditor', () => {
    const editorStart = treatment.indexOf('<PrescriptionEditor');
    expect(editorStart).toBeGreaterThan(-1);
    const editorEnd = treatment.indexOf('/>', editorStart);
    const editorBlock = treatment.slice(editorStart, editorEnd);
    expect(editorBlock).toContain('visitKey={visitKey}');
  });

  it('PrescriptionEditor owns the visit-scoped draft reset', () => {
    expect(editor).toContain('lastVisitKeyRef');
    expect(editor).toMatch(/useEffect\(\(\) => \{\s*if \(lastVisitKeyRef\.current === visitKey\) return;/);
  });

  it('PrescriptionEditor deletes by object identity (no inert id guard)', () => {
    expect(editor).toContain('handleDeleteItem');
    // The inert guard must be gone from the WIRING (the historical pattern
    // is documented only inside a comment, never in the JSX).
    expect(editor).not.toContain('onClick={() => p.id !== undefined');
    expect(editor).toContain('onClick={() => handleDeleteItem(p)}');
  });

  it('PrescriptionEditor allocates collision-resistant client ids', () => {
    expect(editor).toContain('nextClientId');
    expect(editor).not.toContain('id: Date.now()');
  });

  it('PrescriptionEditor renders alias DTO fields at the display boundary', () => {
    expect(editor).toContain('displayName');
    expect(editor).toContain('displayDose');
    expect(editor).toContain('displayFrequency');
  });

  it('the container resets the diff selection on a visit change (EMRHIST-FE-002)', () => {
    const onVisitChangeStart = container.indexOf('onVisitChange: ({ prevVisitId, newVisitId }) => {');
    expect(onVisitChangeStart).toBeGreaterThan(-1);
    const onVisitChangeEnd = container.indexOf('},', onVisitChangeStart);
    const block = container.slice(onVisitChangeStart, onVisitChangeEnd);
    expect(block).toContain('setSelectedVersion(null)');
    expect(block).toContain('setShowDiff(false)');
  });

  it('LabResultsSection rechecks the mounted context before the irreversible order (EMRORDER-FE-001)', () => {
    const lab = fs.readFileSync(path.join(ROOT, 'sections/LabResultsSection.tsx'), 'utf8');
    const orderStart = lab.indexOf('const handleOrder = async (templateId: string | number, templateName: string) => {');
    expect(orderStart).toBeGreaterThan(-1);
    const orderEnd = lab.indexOf('\n  };', orderStart);
    const orderBlock = lab.slice(orderStart, orderEnd);
    // Intent captured at start, rechecked after the confirm and before the POST.
    expect(orderBlock).toContain('const startContext = contextRef.current');
    const confirmIdx = orderBlock.indexOf('await (confirm');
    const recheckIdx = orderBlock.indexOf('if (contextRef.current.patientId !== startContext.patientId');
    const createIdx = orderBlock.indexOf('labReportingApi.createOrder(');
    expect(confirmIdx).toBeGreaterThan(-1);
    expect(recheckIdx).toBeGreaterThan(confirmIdx);
    expect(createIdx).toBeGreaterThan(recheckIdx);
    // The success toast is rechecked as well (context switch during the POST).
    const successIdx = orderBlock.indexOf('notify.success(');
    const secondRecheckIdx = orderBlock.indexOf('if (contextRef.current.patientId !== startContext.patientId', recheckIdx + 1);
    expect(secondRecheckIdx).toBeGreaterThan(-1);
    expect(successIdx).toBeGreaterThan(secondRecheckIdx);
  });

  it('EMRHistoryPanel binds the canonical created_at/created_by keys (EMRHIST-FE-001)', () => {
    const panel = fs.readFileSync(path.join(ROOT, 'EMRHistoryPanel.tsx'), 'utf8');
    expect(panel).toContain('revision.created_at ?? revision.edited_at');
    expect(panel).toContain('revision.created_by ?? revision.edited_by');
  });

  it('EMRDiffViewer clears the stale diff when a new request starts (EMRHIST-FE-002)', () => {
    const diff = fs.readFileSync(path.join(ROOT, 'EMRDiffViewer.tsx'), 'utf8');
    const effectStart = diff.indexOf('const epoch = fetchEpochRef.current + 1;');
    expect(effectStart).toBeGreaterThan(-1);
    const effectEnd = diff.indexOf('void loadDiff();', effectStart);
    const block = diff.slice(effectStart, effectEnd);
    expect(block).toContain('setDiff(null)');
  });
});
