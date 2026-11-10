/**
 * RETRO-3963-01 (post-merge review 3968, P1) — fail-first, panel source
 * contract.
 *
 * A late appointment navigation (row click / view_emr / complete) must not
 * steal a NEWER patient selection made through any other authoritative
 * entry path while the appointment lookup or EMR fetch is still pending:
 *
 *  - handlePatientSearchPick, handleDoctorQueueStartVisit, the URL-derived
 *    selections, completion deselect, the explicit cancel and unmount are
 *    authoritative selection changes: each invalidates outstanding
 *    navigation tickets.
 *  - handleDoctorQueueOpenVisit and the URL hydration capture a ticket and
 *    recheck after every await.
 *  - loadEMR rechecks its ticket after each await, so a late EMR payload
 *    cannot be displayed under a newer patient selection.
 *  - The three appointment paths recheck after `await loadEMR` before
 *    switching the tab.
 *
 * Repo-precedent source-contract pattern (see
 * CardiologistPanel.patientIdentity.contract.test.tsx and
 * CardiologistPanel.retro3941.contract.test.tsx).
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

describe('RETRO-3963-01: every authoritative selection invalidates or owns the navigation epoch', () => {
  it('handlePatientSearchPick invalidates pending tickets before selecting', () => {
    const fn = panel.slice(
      panel.indexOf('const handlePatientSearchPick'),
      panel.indexOf('const handleDoctorQueueStartVisit'),
    );
    const bumpIdx = fn.indexOf('navigationEpochRef.current += 1');
    const selectIdx = fn.indexOf('setSelectedPatient({');
    expect(bumpIdx).toBeGreaterThan(-1);
    expect(selectIdx).toBeGreaterThan(bumpIdx);
  });

  it('handleDoctorQueueStartVisit invalidates pending tickets before selecting', () => {
    const fn = panel.slice(
      panel.indexOf('const handleDoctorQueueStartVisit'),
      panel.indexOf('const handleDoctorQueueOpenVisit'),
    );
    const bumpIdx = fn.indexOf('navigationEpochRef.current += 1');
    const selectIdx = fn.indexOf('setSelectedPatient({');
    expect(bumpIdx).toBeGreaterThan(-1);
    expect(selectIdx).toBeGreaterThan(bumpIdx);
  });

  it('handleDoctorQueueOpenVisit takes a ticket and rechecks after the EMR await before goToTab', () => {
    const fn = panel.slice(
      panel.indexOf('const handleDoctorQueueOpenVisit'),
      panel.indexOf('// Keep this dynamic JSX slot'),
    );
    expect(fn).toContain('const epoch = ++navigationEpochRef.current');
    const awaitIdx = fn.indexOf('await loadEMR(entry.visit_id)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current');
    const tabIdx = fn.indexOf("goToTab('visit')");
    expect(awaitIdx).toBeGreaterThan(-1);
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(tabIdx).toBeGreaterThan(guardIdx);
  });

  it('loadEMR rechecks its ticket after every await so a late EMR cannot land on a newer selection', () => {
    const fn = panel.slice(
      panel.indexOf('const loadEMR = async'),
      panel.indexOf('// Сохранение EMR'),
    );
    expect(fn).toContain('const epoch = navigationEpochRef.current');
    expect((fn.match(/epoch !== navigationEpochRef\.current/g) ?? []).length).toBe(3);
    const fetchIdx = fn.indexOf('await fetch(');
    const firstGuard = fn.indexOf('epoch !== navigationEpochRef.current');
    expect(firstGuard).toBeGreaterThan(fetchIdx);
    // the ok-branch json parse is also an async boundary
    const jsonIdx = fn.indexOf('await response.json()');
    const okGuard = fn.indexOf('epoch !== navigationEpochRef.current', jsonIdx);
    const setEmrIdx = fn.indexOf('setEmr(emrData)');
    expect(okGuard).toBeGreaterThan(jsonIdx);
    expect(setEmrIdx).toBeGreaterThan(okGuard);
  });

  it('row-click branch rechecks after await loadEMR before goToTab', () => {
    const fn = panel.slice(
      panel.indexOf('const handleAppointmentRowClick'),
      panel.indexOf('// C-3 fix'),
    );
    const awaitIdx = fn.indexOf('await loadEMR(visitId)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current', awaitIdx);
    const tabIdx = fn.indexOf("goToTab('visit')");
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(tabIdx).toBeGreaterThan(guardIdx);
  });

  it('view_emr branch rechecks after await loadEMR before goToTab', () => {
    const fn = panel.slice(
      panel.indexOf("case 'view_emr':"),
      panel.indexOf("case 'call':"),
    );
    const awaitIdx = fn.indexOf('await loadEMR(visitId)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current', awaitIdx);
    const tabIdx = fn.indexOf("goToTab('visit')");
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(tabIdx).toBeGreaterThan(guardIdx);
  });

  it('complete branch rechecks after await loadEMR before goToTab', () => {
    const fn = panel.slice(
      panel.indexOf("case 'complete':"),
      panel.indexOf("case 'edit':"),
    );
    const awaitIdx = fn.indexOf('await loadEMR(patient.visit_id)');
    const guardIdx = fn.indexOf('epoch !== navigationEpochRef.current', awaitIdx);
    const tabIdx = fn.indexOf("goToTab('visit')");
    expect(guardIdx).toBeGreaterThan(awaitIdx);
    expect(tabIdx).toBeGreaterThan(guardIdx);
  });

  it('URL hydration captures a ticket and rechecks after both awaits', () => {
    const fn = panel.slice(
      panel.indexOf('const hydratePatientFromUrl'),
      panel.indexOf('useEffect(() => {', panel.indexOf('const hydratePatientFromUrl')),
    );
    expect(fn).toContain('const epoch = navigationEpochRef.current');
    expect((fn.match(/epoch !== navigationEpochRef\.current/g) ?? []).length).toBe(2);
    const fetchIdx = fn.indexOf('await fetch(');
    const jsonIdx = fn.indexOf('await patientResponse.json()');
    const firstGuard = fn.indexOf('epoch !== navigationEpochRef.current');
    const secondGuard = fn.indexOf('epoch !== navigationEpochRef.current', firstGuard + 1);
    expect(firstGuard).toBeGreaterThan(fetchIdx);
    expect(secondGuard).toBeGreaterThan(jsonIdx);
    const selectIdx = fn.indexOf('setSelectedPatient((prev');
    expect(selectIdx).toBeGreaterThan(secondGuard);
  });

  it('URL-appointment sync invalidates tickets only when the selection actually changes', () => {
    const fn = panel.slice(
      panel.indexOf('const didChange ='),
      panel.indexOf('}, [appointments, patientIdFromUrl, visitIdFromUrl, setSelectedPatient]);'),
    );
    expect(fn).toContain('if (didChange) {');
    const bumpIdx = fn.indexOf('navigationEpochRef.current += 1');
    const returnIdx = fn.indexOf('return nextPatient');
    expect(bumpIdx).toBeGreaterThan(-1);
    expect(returnIdx).toBeGreaterThan(bumpIdx);
  });

  it('completion deselect and the explicit visit cancel invalidate in-flight tickets', () => {
    const completion = panel.slice(
      panel.indexOf("notify.success(tI18n('cardio.visit_completed'))"),
      panel.indexOf('Автоматически вызвать следующего пациента'),
    );
    expect(completion).toContain('navigationEpochRef.current += 1');
    expect(completion.indexOf('navigationEpochRef.current += 1')).toBeLessThan(
      completion.indexOf('setSelectedPatient(null)'),
    );

    const cancel = panel.slice(
      panel.indexOf('onCancel={() => {'),
      panel.indexOf('onComplete={handleCompleteVisitFromEMR}'),
    );
    expect(cancel).toContain('navigationEpochRef.current += 1');
    expect(cancel.indexOf('navigationEpochRef.current += 1')).toBeLessThan(
      cancel.indexOf('setSelectedPatient(null)'),
    );
  });

  it('unmount invalidates every in-flight navigation ticket', () => {
    const refIdx = panel.indexOf('const navigationEpochRef = useRef(0)');
    const effect = panel.slice(refIdx, refIdx + 600);
    expect(effect).toContain("useEffect(() => () => { navigationEpochRef.current += 1; }, []);");
  });
});
