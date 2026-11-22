/**
 * RETRO-3966-01 (post-merge review 3968, P2) — read-only inspection wiring
 * contract for BOTH TeethChart consumers (repo-precedent source-contract
 * pattern).
 *
 *  - DentalVisitScreen: the locked-record chart routes inspection through
 *    onInspect into ToothModal — the modal MUST open with
 *    readOnly={fieldsDisabled}, otherwise a signed/locked record offers an
 *    editable UI that attempts POST /v2/emr on save.
 *  - TeethChart: a readOnly chart without an inspection handler renders
 *    DISABLED teeth (never enabled-but-dead ones); with onInspect the tooth
 *    stays clickable for inspection only.
 *  - DentistrySection (emr-v2): the readOnly chart previously received
 *    onToothClick with no onInspect — buttons were enabled yet did nothing
 *    on inspection. It now provides onInspect and renders the SAME
 *    inspection-only ToothModal.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../../..');

const readSource = (relPath: string) =>
  fs.readFileSync(path.join(ROOT, relPath), 'utf8').replace(/\r\n/g, '\n');

const visitScreen = readSource('components/dental/DentalVisitScreen.tsx');
const chart = readSource('components/dental/TeethChart.tsx');
const section = readSource('components/emr-v2/sections/specialty/DentistrySection.tsx');
const modal = readSource('components/dental/ToothModal.tsx');
const dialogsLayer = readSource('pages/dentist/views/DentistDialogsLayer.tsx');

describe('RETRO-3966-01: locked records open an inspection-only ToothModal', () => {
  it('DentalVisitScreen passes readOnly={fieldsDisabled} to ToothModal', () => {
    const invocation = visitScreen.slice(
      visitScreen.indexOf('{/* ToothModal */}'),
      visitScreen.indexOf('{/* DENTVISIT-FE-004'),
    );
    expect(invocation).toContain('<ToothModal');
    expect(invocation).toContain('readOnly={fieldsDisabled}');
    // the invocation still wires the mutation path for the EDITABLE case
    expect(invocation).toContain('onSave=');
  });

  it('TeethChart disables teeth on a readOnly chart without an inspection handler', () => {
    expect(chart).toContain('disabled={readOnly && !onInspect}');
    expect(chart).not.toContain('disabled={readOnly && !onToothClick && !onInspect}');
  });

  it('DentistrySection provides onInspect and renders the inspection-only modal', () => {
    const chartUsage = section.slice(
      section.indexOf('<TeethChart'),
      section.indexOf('{/* Hygiene Indices Tab */}'),
    );
    expect(chartUsage).toContain('onInspect={');
    expect(chartUsage).toContain('readOnly={disabled}');

    const modalUsage = section.slice(
      section.indexOf('inspectedTooth && ('),
      section.indexOf('</EMRSection>'),
    );
    expect(modalUsage).toContain('<ToothModal');
    expect(modalUsage).toContain('readOnly');
    expect(modalUsage).not.toContain('onSave');
  });

  it('ToothModal has an explicit readOnly contract: guard before write, no Save affordance', () => {
    // the save guard must run BEFORE any api.post path
    const saveFn = modal.slice(
      modal.indexOf('const handleSave = async () => {'),
      modal.indexOf('// H6 fix: getToothName now delegates'),
    );
    expect(saveFn).toContain('if (readOnly) {\n      return;\n    }');
    expect(saveFn.indexOf('api.post')).toBeGreaterThan(saveFn.indexOf('if (readOnly)'));

    // Save button is conditionally rendered (not merely disabled)
    const actions = modal.slice(
      modal.indexOf('<DialogActions>'),
      modal.indexOf('</DialogActions>'),
    );
    expect(actions).toContain('{!readOnly && (');
    expect(actions).toContain('dental.dental_tm_save');

    // honest inspection banner
    expect(modal).toContain("t('dental2.tooth_inspection_only')");
    // editable controls are wrapped in a disabled fieldset
    expect(modal).toContain('disabled={readOnly}');
  });
});

describe('RETRO-3986-01: the dormant third ToothModal consumer carries the contract', () => {
  it('DentistDialogsLayer requires the lock state and wires readOnly to BOTH ToothModal and TeethChart', () => {
    // The prop is REQUIRED on the props type — a future re-wiring cannot
    // mount this layer without making the record-lock state explicit.
    expect(dialogsLayer).toContain('toothModalReadOnly: boolean');

    // The ToothModal invocation carries the readOnly contract…
    const modalUsage = dialogsLayer.slice(
      dialogsLayer.indexOf('{toothModalOpen && selectedTooth &&'),
    );
    expect(modalUsage).toContain('<ToothModal');
    expect(modalUsage).toContain('readOnly={toothModalReadOnly}');

    // …and the chart in the same layer is not hardcoded writable.
    const chartUsage = dialogsLayer.slice(
      dialogsLayer.indexOf('<TeethChart'),
      dialogsLayer.indexOf('{showTreatmentPlanner &&'),
    );
    expect(chartUsage).toContain('readOnly={toothModalReadOnly}');
    expect(chartUsage).not.toContain('readOnly={false}');
  });

  it('DentistPanelUnified derives the lock from the visit EMR status and passes it down', () => {
    const panel = readSource('pages/DentistPanelUnified.tsx');
    expect(panel).toContain('selectedVisitRecordLocked');
    expect(panel).toContain('toothModalReadOnly={selectedVisitRecordLocked}');
    // the lock derives from the visit protocol record's EMR status with the
    // DENTVISIT-FE-001 semantics (`signed` is the read-only state)
    expect(panel).toContain("toLowerCase() === 'signed'");
  });
});
