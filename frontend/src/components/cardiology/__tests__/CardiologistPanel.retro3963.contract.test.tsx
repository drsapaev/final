/**
 * RETRO-3963-01 (post-merge review 3968, P1) — fail-first, panel source
 * contract.
 *
 * A late appointment navigation (row click / view_emr / complete) must not
 * steal a NEWER patient selection made through any other authoritative
 * entry path while the appointment lookup or EMR fetch is still pending:
 *
 *  - handlePatientSearchPick, handleDoctorQueueStartVisit, completion
 *    deselect, the explicit cancel and unmount are authoritative selection
 *    changes: each invalidates outstanding navigation tickets.
 *  - handleDoctorQueueOpenVisit and the URL hydration capture a ticket and
 *    recheck after every await; the hydration additionally bails when the
 *    live committed selection is a DIFFERENT patient than the deep link
 *    (independent re-review: a shared ticket let the URL merge produce a
 *    hybrid record over a newer human selection).
 *  - loadEMR rechecks its ticket after each await (including the catch
 *    block), so a late EMR payload cannot be displayed under a newer
 *    patient selection.
 *  - The three appointment paths recheck after `await loadEMR` before
 *    switching the tab.
 *  - The synchronous URL-appointment sync never touches the epoch: a
 *    background status refresh must not cancel an in-flight human click.
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

  it('loadEMR rechecks its ticket after every await — including the catch block — so a late EMR cannot land on a newer selection', () => {
    const fn = panel.slice(
      panel.indexOf('const loadEMR = async'),
      panel.indexOf('// Сохранение EMR'),
    );
    // the epoch is captured OUTSIDE the try so the catch block can recheck too
    const epochDecl = fn.indexOf('const epoch = navigationEpochRef.current');
    const tryIdx = fn.indexOf('try {');
    expect(epochDecl).toBeGreaterThan(-1);
    expect(tryIdx).toBeGreaterThan(epochDecl);
    expect((fn.match(/epoch !== navigationEpochRef\.current/g) ?? []).length).toBe(4);
    const fetchIdx = fn.indexOf('await fetch(');
    const firstGuard = fn.indexOf('epoch !== navigationEpochRef.current');
    expect(firstGuard).toBeGreaterThan(fetchIdx);
    // the ok-branch json parse is also an async boundary
    const jsonIdx = fn.indexOf('await response.json()');
    const okGuard = fn.indexOf('epoch !== navigationEpochRef.current', jsonIdx);
    const setEmrIdx = fn.indexOf('setEmr(emrData)');
    expect(okGuard).toBeGreaterThan(jsonIdx);
    expect(setEmrIdx).toBeGreaterThan(okGuard);
    // the catch block rechecks before toasting (stale failure ≠ user-visible)
    const catchIdx = fn.indexOf('} catch (error: unknown) {');
    const catchGuard = fn.indexOf('epoch !== navigationEpochRef.current', catchIdx);
    const catchNotify = fn.indexOf('notify.error(', catchIdx);
    expect(catchGuard).toBeGreaterThan(catchIdx);
    expect(catchNotify).toBeGreaterThan(catchGuard);
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

  it('URL hydration bails when a newer human selection exists — live-selection guard plus epoch (independent re-review)', () => {
    const fn = panel.slice(
      panel.indexOf('const hydratePatientFromUrl'),
      panel.indexOf('useEffect(() => {', panel.indexOf('const hydratePatientFromUrl')),
    );
    // the live-selection guard reads the committed selection via the ref
    expect(fn).toContain('const liveSelectionIsOtherPatient = (): boolean =>');
    expect(fn).toContain('selectedPatientRef.current');
    // RETRO-3969-02: the failure path owns the same guard — four call sites
    // (entry / post-fetch / post-json + the catch before its toast).
    expect((fn.match(/liveSelectionIsOtherPatient\(\)/g) ?? []).length).toBe(4);
    // RETRO-3969-01: the guard was widened to the visit dimension — the
    // patient check is now combined with liveSelectionContradictsVisit()
    // at every site; the patient-identity semantics are unchanged.
    const entryGuard = fn.indexOf(
      'if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;',
    );
    const fetchIdx = fn.indexOf('await fetch(');
    expect(entryGuard).toBeGreaterThan(-1);
    expect(fetchIdx).toBeGreaterThan(entryGuard);
    // epoch guards stay (newer intent took a ticket while fetching) — three
    // now: post-fetch, post-json, and the RETRO-3969-02 catch
    expect(fn).toContain('const epoch = navigationEpochRef.current');
    expect((fn.match(/epoch !== navigationEpochRef\.current/g) ?? []).length).toBe(3);
    // both post-await guards precede the identity merge — the RETRO-3969-02
    // catch adds its own combined guard AFTER the merge (failure path), so
    // the ordering invariant is computed over the pre-catch (success-path)
    // scope only
    const jsonIdx = fn.indexOf('await patientResponse.json()');
    const catchStart = fn.indexOf('} catch (error: unknown) {');
    const preCatchScope = catchStart > -1 ? fn.slice(0, catchStart) : fn;
    const lastLiveGuard = preCatchScope.lastIndexOf(
      'if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;',
    );
    const selectIdx = fn.indexOf('setSelectedPatient((prev');
    expect(lastLiveGuard).toBeGreaterThan(jsonIdx);
    expect(selectIdx).toBeGreaterThan(lastLiveGuard);
  });

  it('URL-appointment sync stays pure and never bumps the epoch (independent re-review)', () => {
    const fn = panel.slice(
      panel.indexOf('const matchingAppointment'),
      panel.indexOf('}, [appointments, patientIdFromUrl, visitIdFromUrl, setSelectedPatient]);'),
    );
    // the updater must be PURE: no render-phase side effects, and no epoch
    // bump — a background status refresh must not cancel an in-flight
    // human click (the pre-review-fix bump did exactly that).
    expect(fn).not.toContain('navigationEpochRef.current += 1');
    expect(fn).not.toContain('navigationEpochRef');
    expect(fn).toContain('return didChange ? nextPatient : prev;');
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
    const transition = cancel.indexOf('goToTab(\'queue\', () => {');
    const bump = cancel.indexOf('navigationEpochRef.current += 1');
    const clear = cancel.indexOf('setSelectedPatient(null)');
    expect(transition).toBeGreaterThan(-1);
    expect(bump).toBeGreaterThan(transition);
    expect(clear).toBeGreaterThan(bump);
    expect(cancel).not.toContain('setActiveTab(\'queue\')');
  });

  it('unmount invalidates every in-flight navigation ticket', () => {
    const refIdx = panel.indexOf('const navigationEpochRef = useRef(0)');
    const effect = panel.slice(refIdx, refIdx + 600);
    expect(effect).toContain("useEffect(() => () => { navigationEpochRef.current += 1; }, []);");
  });
});
