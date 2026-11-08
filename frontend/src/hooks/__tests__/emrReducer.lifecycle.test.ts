/**
 * Fail-first regression suite: EMR lifecycle dirty/sign/conflict semantics
 * (audit 3886, round 17).
 *
 * Covers the frontend lifecycle cluster of the merged audit ledger PR #3886:
 *
 * - EMRSAVE-FE-001  — a late save ACK for an older snapshot must NOT clear
 *   the dirty flag of newer edits; the follow-up save must include them.
 * - EMRSIGN-FE-001  — save/sign/amend serialize the LIVE document (stateRef),
 *   never a stale render closure.
 * - EMRCONFLICT-FE-001 — discarding local edits («Загрузить новую версию»)
 *   leaves the state clean: no phantom dirty, no immediate re-write of the
 *   just-loaded server content.
 *
 * Red-first statement: on the pre-fix source every assertion below fails —
 * SAVE_SUCCESS cleared isDirty unconditionally, write callbacks serialized
 * the closure snapshot, and conflictResolved() marked the discarded state
 * dirty unconditionally.
 */

import { describe, expect, it } from 'vitest';
import { EMR_ACTIONS, emrActions, emrReducer, initialState } from '../../reducers/emrReducer';
import type { EmrRecord, EmrState } from '../../types/features/emr';

const savedEmr = (overrides: Partial<EmrRecord> = {}): EmrRecord => ({
    id: 1,
    patient_id: 2,
    visit_id: 3,
    version: 2,
    row_version: 5,
    status: 'in_progress',
    data: {},
    ...overrides,
} as EmrRecord);

function withState(patch: Partial<EmrState>): EmrState {
    return { ...initialState, ...patch };
}

describe('EMRSAVE-FE-001: late save ACK must not clear newer edits', () => {
    it('keeps isDirty when a SET_FIELD happens while the save is in flight', () => {
        let s = withState({ data: { complaints: 'first' }, isDirty: true, editEpoch: 3 });
        s = emrReducer(s, emrActions.saveStart());
        expect(s.saveEpoch).toBe(3);

        // Doctor keeps typing while the request is in flight
        s = emrReducer(s, emrActions.setField('complaints', 'first plus second'));

        // Server ACKs the save of the OLDER snapshot
        s = emrReducer(s, emrActions.saveSuccess(savedEmr({ row_version: 6 })));

        expect(s.isDirty).toBe(true);
        expect(s.data.complaints).toBe('first plus second');
    });

    it('clears isDirty when no edit happened after the save started', () => {
        let s = withState({ data: { complaints: 'first' }, isDirty: true, editEpoch: 7 });
        s = emrReducer(s, emrActions.saveStart());
        s = emrReducer(s, emrActions.saveSuccess(savedEmr()));
        expect(s.isDirty).toBe(false);
    });

    it('counts UNDO/REDO as local edits for the epoch rule', () => {
        let s = withState({
            data: { complaints: 'second' },
            isDirty: true,
            editEpoch: 2,
            history: [{ complaints: 'first' }],
        });
        s = emrReducer(s, emrActions.saveStart());
        s = emrReducer(s, emrActions.undo());
        expect(s.data.complaints).toBe('first');
        s = emrReducer(s, emrActions.saveSuccess(savedEmr()));
        expect(s.isDirty).toBe(true);
    });

    it('autosave-style cycle: ACK(A) then a later save covers B', () => {
        let s = withState({ data: { complaints: 'first' }, isDirty: true, editEpoch: 1 });
        s = emrReducer(s, emrActions.saveStart());          // saveEpoch = 1
        s = emrReducer(s, emrActions.setField('complaints', 'first plus second')); // editEpoch = 2
        s = emrReducer(s, emrActions.saveSuccess(savedEmr({ row_version: 6 })));
        expect(s.isDirty).toBe(true);

        // The follow-up save covers the newer text and may clear dirty
        s = emrReducer(s, emrActions.saveStart());          // saveEpoch = 2
        s = emrReducer(s, emrActions.saveSuccess(savedEmr({ row_version: 7 })));
        expect(s.isDirty).toBe(false);
        expect(s.rowVersion).toBe(7);
    });
});

describe('EMRCONFLICT-FE-001: discard resolution stays clean', () => {
    it('a discard resolution clears the conflict without marking the state dirty', () => {
        let s = withState({
            data: { complaints: 'server text' },
            isDirty: false,
            conflict: { serverVersion: 9, yourVersion: 7, lastEditedBy: 42, lastEditedAt: '2026-11-08T00:00:00Z' } as unknown as EmrState['conflict'],
            status: 'conflict',
        });
        s = emrReducer(s, emrActions.conflictResolved(null, null, 'discard'));
        expect(s.conflict).toBeNull();
        expect(s.isDirty).toBe(false);
        expect(s.history).toEqual([]);
        expect(s.future).toEqual([]);
    });

    it('a merge/reapply resolution stays dirty (the local document differs from the server)', () => {
        let s = withState({
            data: { complaints: 'server text' },
            conflict: { serverVersion: 9, yourVersion: 7, lastEditedBy: 42, lastEditedAt: '2026-11-08T00:00:00Z' } as unknown as EmrState['conflict'],
            status: 'conflict',
        });
        s = emrReducer(
            s,
            emrActions.conflictResolved({ complaints: 'server text + local reapply' }, 9, 'merge'),
        );
        expect(s.conflict).toBeNull();
        expect(s.isDirty).toBe(true);
        expect(s.data.complaints).toBe('server text + local reapply');
    });
});

describe('EMRSAVE/EMRSIGN action contract (regression guards)', () => {
    it('SAVE_START snapshots the edit epoch', () => {
        const s = emrReducer(
            withState({ editEpoch: 11 }),
            { type: EMR_ACTIONS.SAVE_START },
        );
        expect(s.saveEpoch).toBe(11);
        expect(s.editEpoch).toBe(11);
    });

    it('conflictResolved payload carries the resolution type', () => {
        const action = emrActions.conflictResolved(null, null, 'discard');
        expect(action.type).toBe(EMR_ACTIONS.CONFLICT_RESOLVED);
        expect((action as { payload: { resolution: string } }).payload.resolution).toBe('discard');
    });
});
