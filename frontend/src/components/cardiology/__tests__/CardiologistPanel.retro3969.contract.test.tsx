/**
 * RETRO-3969-01 (post-merge review of the #3969–#3996 window, group 2
 * archive PR #4000) — fail-first, panel source contract.
 *
 * The URL deep-link hydration must never revert a committed
 * same-patient / different-visit selection back to the stale URL
 * visitId:
 *
 *  - `hydratePatientFromUrl` re-fires on every selection change
 *    (`selectedPatient` is in its dep array). The doctor row-clicks
 *    patient P1 at visit V_row while the URL carries
 *    `?patientId=P1&visitId=V1` (the pre-#3969 deep link): the entry
 *    bail does not fire (patient matches, visit differs), the epoch
 *    guard passes (the row-click ticket was the LAST write, and this
 *    effect re-fire captures it), and the merge stamps
 *    `visit_id: visitIdFromUrl || prev?.visit_id` — V1 over V_row —
 *    hijacks the tab (`setActiveTab('patients')`), and the P-019 effect
 *    reloads the EMR for the URL visit. Documentation entered afterwards
 *    lands on the stale visit (the visit tab binds its editor to
 *    `selectedPatient.visit_id`).
 *  - The dermatology panel already guards this exact class
 *    (`DermatologistPanelUnified.tsx`, `selectionContradictsUrl` checks
 *    patient AND visit, DERMAURL-FE-002); the sibling URL-appointment
 *    sync of THIS panel also bails on a visit mismatch — the guard was
 *    known and omitted in the patient-identity hydration.
 *
 * Fix contract (mirrors the derm precedent and the sibling sync):
 * the hydration's live-selection guard gains the visit dimension — a
 * committed selection of the same patient with a different visit is the
 * doctor's OWN newer intent and must survive every re-fire of the
 * hydration effect.
 *
 * Repo-precedent source-contract pattern (see
 * CardiologistPanel.retro3963.contract.test.tsx and
 * CardiologistPanel.patientIdentity.contract.test.tsx).
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

describe('RETRO-3969-01: the URL hydration never reverts a committed same-patient/different-visit selection', () => {
  const hydration = panel.slice(
    panel.indexOf('const hydratePatientFromUrl'),
    panel.indexOf('useEffect(() => {', panel.indexOf('const hydratePatientFromUrl')),
  );

  it('the hydration declares a visit-conflict guard reading the live selection and the URL visit', () => {
    expect(hydration).toContain('const liveSelectionContradictsVisit = (): boolean =>');
    const guardFn = hydration.slice(
      hydration.indexOf('const liveSelectionContradictsVisit'),
      hydration.indexOf('};', hydration.indexOf('const liveSelectionContradictsVisit')) + 2,
    );
    // reads the LIVE committed selection (not the closure-captured prop)
    expect(guardFn).toContain('selectedPatientRef.current');
    // compares the live visit id with the URL visit id, both-non-null
    expect(guardFn).toContain('visit_id');
    expect(guardFn).toContain('visitIdFromUrl');
    expect(guardFn).toContain('null');
  });

  it('the entry guard fires with BOTH dimensions before the patient fetch', () => {
    const combinedIdx = hydration.indexOf(
      'if (liveSelectionIsOtherPatient() || liveSelectionContradictsVisit()) return;',
    );
    const fetchIdx = hydration.indexOf('await fetch(');
    expect(combinedIdx).toBeGreaterThan(-1);
    expect(fetchIdx).toBeGreaterThan(combinedIdx);
  });

  it('every post-await guard site includes the visit dimension (entry + post-fetch + post-json + the RETRO-3969-02 catch)', () => {
    expect(
      (hydration.match(/liveSelectionIsOtherPatient\(\) \|\| liveSelectionContradictsVisit\(\)/g) ?? []).length,
    ).toBe(4);
  });

  it('the visit stamping merge is only reachable after the last combined guard', () => {
    const mergeIdx = hydration.indexOf('visit_id: visitIdFromUrl ||');
    // The RETRO-3969-02 catch adds a fourth combined guard AFTER the merge;
    // the ordering invariant is about the pre-catch (success-path) sites.
    const catchStart = hydration.indexOf('} catch (error: unknown) {');
    const tryScope = hydration.slice(0, catchStart);
    const lastGuard = tryScope.lastIndexOf('liveSelectionContradictsVisit()) return;');
    expect(mergeIdx).toBeGreaterThan(-1);
    expect(lastGuard).toBeGreaterThan(-1);
    expect(mergeIdx).toBeGreaterThan(lastGuard);
    // The catch's own combined guard sits after the merge (failure path).
    const catchGuard = hydration
      .slice(catchStart)
      .indexOf('liveSelectionIsOtherPatient() || liveSelectionContradictsVisit())');
    expect(catchGuard).toBeGreaterThan(-1);
  });

  it('the patient-identity dimension of RETRO-3963-01 is preserved unchanged (regression control)', () => {
    expect(hydration).toContain('const liveSelectionIsOtherPatient = (): boolean =>');
    // exactly four guard sites: entry / post-fetch / post-json + the RETRO-3969-02 catch
    expect((hydration.match(/liveSelectionIsOtherPatient\(\)/g) ?? []).length).toBe(4);
    // exactly three epoch guards: post-fetch / post-json + the RETRO-3969-02 catch
    expect((hydration.match(/epoch !== navigationEpochRef\.current/g) ?? []).length).toBe(3);
  });

  it('RETRO-3969-02: the hydration catch gates its toast behind the same epoch/live-selection guards', () => {
    const catchStart = hydration.indexOf('} catch (error: unknown) {');
    expect(catchStart).toBeGreaterThan(-1);
    const catchBlock = hydration.slice(catchStart);
    const notifyCall = catchBlock.indexOf('notify.error(');
    expect(notifyCall).toBeGreaterThan(-1);
    // A hydration fetch that failed AFTER the operator moved on must bail
    // silently: epoch recheck first, then both live-selection dimensions —
    // the same one-guard delta the loadEMR catch already owns.
    const epochGuard = catchBlock.indexOf('epoch !== navigationEpochRef.current');
    const patientGuard = catchBlock.indexOf('liveSelectionIsOtherPatient()');
    const visitGuard = catchBlock.indexOf('liveSelectionContradictsVisit()');
    expect(epochGuard).toBeGreaterThan(-1);
    expect(patientGuard).toBeGreaterThan(-1);
    expect(visitGuard).toBeGreaterThan(-1);
    expect(epochGuard).toBeLessThan(notifyCall);
    expect(patientGuard).toBeLessThan(notifyCall);
    expect(visitGuard).toBeLessThan(notifyCall);
  });

  it('the same-patient/same-visit nothing-to-do entry bail survives (regression control)', () => {
    const entryBail = hydration.indexOf('selectedVisitId === visitIdFromUrl');
    expect(entryBail).toBeGreaterThan(-1);
  });
});
