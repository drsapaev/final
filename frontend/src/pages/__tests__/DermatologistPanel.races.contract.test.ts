/**
 * DERMACOMPLETE-FE-002 / DERMARX-FE-004 / DERMACACHE-FE-001 /
 * DERMAHOTKEY-FE-001 / DERMAQUEUE-FE-001 / DERMAURL-FE-001/002 (audit
 * 3892, post-merge groups 7–10) — source contract for the
 * dermatologist panel's async write guards and identity wiring.
 *
 * Pinned invariants (each fails on the pre-fix source):
 *
 * - DERMACOMPLETE-FE-002: after the completion POST resolves (and after
 *   the DOCFLOW ack check), the handler must re-verify the captured
 *   completion context before ANY success reset, schedule-next modal or
 *   auto next-call.
 * - DERMARX-FE-004: `savePrescription` must re-verify the captured visit
 *   context after its POST resolves and before `setPrescription`.
 * - DERMAURL-FE-001/002: the deep-link resolution must AND-match both URL
 *   ids when both are supplied, must not force a URL visit onto a row,
 *   must not fabricate a patient/visit pair in the fallback, and must
 *   invalidate stale resolutions (generation guard + manual-selection
 *   skip).
 * - DERMACACHE-FE-001: the module request cache must be principal-scoped
 *   and reset on auth changes.
 * - DERMAHOTKEY-FE-001: the panel's Escape path must be dirty-guarded and
 *   the EMR container must expose its dirty state.
 * - DERMAQUEUE-FE-001: the live queue must be wired with the start-visit
 *   handoff.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const readSource = (relative: string) =>
  fs.readFileSync(path.join(__dirname, relative), 'utf8');

describe('DERMACOMPLETE-FE-002 — post-POST completion context guard (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');
  const completionHandler =
    source.match(/const handleSaveVisit = async[\s\S]*?\n {2}\};/)?.[0] ?? '';

  it('pins the handler block that owns completion', () => {
    expect(completionHandler).not.toBe('');
    expect(completionHandler).toContain('queueService.completeVisit');
  });

  it('rechecks the completion context AFTER the POST resolves, before any reset or auto-call', () => {
    const postIndex = completionHandler.indexOf('await queueService.completeVisit');
    expect(postIndex).toBeGreaterThan(-1);
    const afterPost = completionHandler.slice(postIndex);
    // The post-await guard must precede every effectful consequence.
    const guardIndex = afterPost.indexOf('isSameDermatologyVisit(completionContext, currentVisitContextRef.current)');
    expect(guardIndex).toBeGreaterThan(-1);
    for (const marker of ['setSelectedPatient(null)', 'setEmr(null)', 'callNextWaiting']) {
      expect(afterPost.indexOf(marker)).toBeGreaterThan(guardIndex);
    }
  });

  it('keeps the pre-existing pre-POST identity recheck and ack guard (DOCFLOW pins stay green)', () => {
    const prePost = completionHandler.slice(0, completionHandler.indexOf('await queueService.completeVisit'));
    expect(prePost).toContain('isSameDermatologyVisit(completionContext, currentVisitContextRef.current)');
    expect(completionHandler).toMatch(/completionAck\?\.success !== true/);
  });
});

describe('DERMARX-FE-004 — prescription save response context guard (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');
  const saveHandler =
    source.match(/const savePrescription = async[\s\S]*?\n {2}\};/)?.[0] ?? '';

  it('pins the handler block that owns prescription saves', () => {
    expect(saveHandler).not.toBe('');
    expect(saveHandler).toContain('postDermatologyPrescription');
  });

  it('rechecks the captured visit context after the POST, before setPrescription/notify', () => {
    const postIndex = saveHandler.indexOf('await postDermatologyPrescription');
    expect(postIndex).toBeGreaterThan(-1);
    const afterPost = saveHandler.slice(postIndex);
    const guardIndex = afterPost.indexOf('isSameDermatologyVisit(');
    expect(guardIndex).toBeGreaterThan(-1);
    expect(afterPost.indexOf('setPrescription(savedPrescription)')).toBeGreaterThan(guardIndex);
    expect(afterPost.indexOf('notify.success')).toBeGreaterThan(guardIndex);
    expect(saveHandler).toContain('currentVisitContextRef.current');
  });

  it('mounts the prescription editor per canonical visit (no shared child state bleed)', () => {
    const visitBranch = source.slice(
      source.indexOf('{activeTab === \'visit\' && currentAppointment'),
      source.indexOf('{' + 'activeTab === \'visit\' && !currentAppointment'),
    );
    const rxMount = visitBranch.slice(visitBranch.indexOf('<PrescriptionSystem'));
    expect(rxMount).toMatch(/key=\{/);
  });
});

describe('DERMAURL-FE-001/002 — deep-link resolution identity (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');
  const urlEffect = source.slice(
    source.indexOf('const loadPatientFromUrl = async'),
    source.indexOf('const currentVisitContext = useMemo'),
  );

  it('requires both URL ids to match the same row when both are supplied (no OR predicate)', () => {
    expect(urlEffect).toContain('matchesUrlPair');
    // The AND-match helper must be used for both the initial and the refreshed lookups.
    expect(urlEffect.match(/matchesUrlPair/g)?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it('does not force the URL visit id onto the matched row', () => {
    expect(urlEffect).not.toMatch(/visit_id: visitIdFromUrl \|\|/);
  });

  it('does not fabricate a patient/visit pair in the fallback when a visit id is supplied', () => {
    const fallbackBlock = urlEffect.slice(
      urlEffect.indexOf('const fallbackPatientId'),
      urlEffect.indexOf('if (!urlResolutionRef.current.notified)'),
    );
    expect(fallbackBlock).not.toMatch(/visit_id: visitIdFromUrl/);
  });

  it('invalidates stale deep-link resolutions (generation guard + manual-selection skip)', () => {
    expect(source).toContain('urlResolutionGenerationRef');
    expect(urlEffect).toContain('urlResolutionGenerationRef.current !== generation');
    expect(urlEffect).toContain('selectionContradictsUrl');
  });
});

describe('DERMACACHE-FE-001 — principal-scoped module request cache (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');

  it('scopes the module cache entries to the authenticated principal', () => {
    expect(source).toContain('dermatologyCacheOwnerKey');
    expect(source).toContain('ownerKey');
  });

  it('resets the cache when the authenticated principal changes', () => {
    expect(source).toContain('resetDermatologyRequestCache');
    expect(source).toMatch(/authStateChanged|subscribeAuth/);
  });
});

describe('DERMAHOTKEY-FE-001 — dirty-guarded panel exits (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');
  const emrContainer = readSource('../../components/emr-v2/EMRContainerV2.tsx');
  const hotkeys = readSource('../../hooks/useDermaHotkeys.ts');

  it('the derma Escape hotkey honours open modal dialogs (dental parity)', () => {
    expect(hotkeys).toMatch(/aria-modal="true"/);
  });

  it('Escape delegates the current visit to the shared dirty-source guard', () => {
    expect(source).not.toContain('emrDirtyRef');
    expect(source).not.toContain('handleEmrDirtyChange');
    expect(source).toContain('hasPendingOperations');
    expect(source).toContain('guardTransition(() =>');
    expect(source).toContain('{ sourceIds, intentPolicy: \'leave\' }');
    expect(source).toContain('dialogVisitContext');
    expect(source).toContain('isSameDermatologyVisit(dialogVisitContext, currentVisitContextRef.current)');
    const visitBranch = source.slice(
      source.indexOf('{activeTab === \'visit\' && currentAppointment'),
      source.indexOf('{' + 'activeTab === \'visit\' && !currentAppointment'),
    );
    const emrMount = visitBranch.slice(visitBranch.indexOf('<EMRContainerV2'));
    expect(emrMount).not.toContain('onDirtyChange');
  });

  it('EMRContainerV2 exposes its dirty flag through an optional callback prop', () => {
    expect(emrContainer).toContain('onDirtyChange?: (dirty: boolean) => void');
  });
});

describe('DERMAQUEUE-FE-001 — live queue start-visit handoff (source contract)', () => {
  const source = readSource('../DermatologistPanelUnified.tsx');

  it('wires onStartVisit into the dermatology live queue', () => {
    expect(source).toContain('onStartVisit={handleStartQueueVisit}');
    expect(source).toContain('useDermaQueueVisit');
  });

  it('the handoff hook fails closed on unconfirmed or identity-less acks', () => {
    const hook = readSource('../useDermaQueueVisit.ts');
    expect(hook).toContain("success !== true");
    expect(hook).toContain('patient_id');
    expect(hook).toContain('visit_id');
    expect(hook).toContain('queueService.startVisit');
  });
});
