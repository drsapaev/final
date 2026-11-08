/**
 * Fail-first regression suite: EMR v2 container lifecycle UI guards
 * (audit 3886, round 17) — source-contract style, following the precedent
 * of EMRContainerV2.completion.contract.test.ts.
 *
 * - EMRAMEND-FE-001    — the amendment workflow must be reachable on signed
 *   records (the old `disabled={editingDisabled}` permanently disabled it
 *   because editingDisabled contains isSigned).
 * - EMRAMEND-FE-002 (frontend side) — an amended record must not offer the
 *   ordinary Save / Save-and-Sign path; editingDisabled includes isAmended.
 * - EMRSIGN-FE-001     — field editing is locked while a save/sign request
 *   is in flight (isSaving in editingDisabled).
 * - EMRRELOAD-FE-001   — the toolbar Refresh must guard a dirty document
 *   behind an explicit discard confirmation and then bypass the cache.
 * - EMRCONFLICT-FE-002 — the conflict dialog is wired without the dead
 *   force-overwrite action.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(__dirname, '../EMRContainerV2.tsx'), 'utf8');
const dialogSource = fs.readFileSync(path.join(__dirname, '../EMRConflictDialog.tsx'), 'utf8');
const hookSource = fs.readFileSync(path.join(__dirname, '../../../hooks/useEMR.ts'), 'utf8');

describe('EMRContainerV2 lifecycle guards (audit 3886 round 17)', () => {
    it('EMRAMEND-FE-002: editingDisabled locks amended records and in-flight saves', () => {
        const m = source.match(/const editingDisabled = ([^;]+);/);
        expect(m).not.toBeNull();
        expect(m![1]).toContain('isReadOnly');
        expect(m![1]).toContain('isSigned');
        expect(m![1]).toContain('isAmended');
        expect(m![1]).toContain('isSaving');
    });

    it('EMRAMEND-FE-001: the amend flow has its own reachability flag, not editingDisabled', () => {
        const m = source.match(/const amendAllowed = ([^;]+);/);
        expect(m).not.toBeNull();
        expect(m![1]).toContain('isSigned || isAmended');
        expect(m![1]).toContain('!isReadOnly');
        // The amend UI must no longer be gated on editingDisabled
        expect(source).not.toContain('disabled={editingDisabled}\n                                    aria-label={t(\'misc.emr_amend_aria\')}');
        expect(source).toContain("disabled={!amendAllowed || isSaving}");
        // handleAmend must not early-return on editingDisabled
        const handler = source.match(/const handleAmend = async \(\) => \{[\s\S]*?\n {4}\};/);
        expect(handler).not.toBeNull();
        expect(handler![0]).not.toContain('if (editingDisabled) return;');
    });

    it('EMRAMEND-FE-002: the ordinary save/sign branch excludes amended records', () => {
        expect(source).toContain(') : !isSigned && !isAmended ? (');
    });

    it('EMRRELOAD-FE-001: toolbar refresh guards dirty edits behind a confirmation and bypasses the cache', () => {
        expect(source).toContain('const handleToolbarRefresh = async () => {');
        const handler = source.match(/const handleToolbarRefresh = async \(\) => \{[\s\S]*?\n {4}\};/);
        expect(handler).not.toBeNull();
        expect(handler![0]).toContain('isDirty');
        expect(handler![0]).toContain('confirm(');
        expect(handler![0]).toContain('if (!confirmed) return;');
        expect(handler![0]).toContain('await loadEMR(true)');
        // The button must route through the guard, not call loadEMR directly
        expect(source).toContain('void handleToolbarRefresh()');
        expect(source).not.toContain("onClick={() => { void loadEMR(); }}");
    });

    it('EMRCONFLICT-FE-002: no force-overwrite wiring remains', () => {
        expect(source).not.toContain('onForceOverwrite');
        expect(dialogSource).not.toContain('onForceOverwrite');
        expect(dialogSource).not.toContain('Перезаписать принудительно');
        expect(dialogSource).toContain('409');
    });

    it('EMRSIGN-FE-001: write requests serialize the live document (stateRef)', () => {
        expect(hookSource).toContain('stateRef.current.data');
        expect(hookSource).not.toContain('data: normalizeEMRData(state.data, specialty)');
    });
});
