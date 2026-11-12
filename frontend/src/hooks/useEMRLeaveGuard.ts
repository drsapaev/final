import { useEffect, useRef } from 'react';
import { useLabDirtyGuard } from '../components/laboratory/LabDirtyGuardContext';
import { isRejectedEMRWrite } from '../components/emr-v2/emrWriteResult';

/**
 * useEMRLeaveGuard — route-level leave guard for a clinical EMR draft
 * (RETRO-3971-04 residual, post-merge re-review of 4009).
 *
 * 4009 added the last-chance unmount flush: when the editor unmounts
 * mid-debounce, the pending autosave POST is at least attempted. That
 * flush is fire-and-forget — a React effect cleanup cannot await its own
 * Promise, cannot block React Router navigation, and the editor's local
 * state is destroyed before the response is known. A clinical draft must
 * not depend on a best-effort destructor: the doctor needs an explicit
 * Stay / Retry / Discard decision, and «Save and leave» must happen only
 * after the server acknowledges the draft of the CURRENT visit.
 *
 * The App already owns the machinery (PR 3351): one shared dirty-source
 * registry + one guard dialog at the LabDirtyGuardProvider level, driven
 * by useGuardedLabNavigate (Header, sidebar, Command Palette, global
 * search, notification center, logout). This hook registers the EMR
 * container as a dirty source in that shared registry — the visit owner
 * level — so every SPA leave from the doctor routes goes through the same
 * dialog, and the browser-Back sentinel (armed on the guarded routes)
 * blocks silent history exits the same way it already does for /lab.
 *
 * Source contract:
 * - `isDirty` reads the LIVE render-time ref (keystrokes never re-register);
 * - `save` performs a draft autosave (`{ isDraft: true }`) of the current
 *   visit and resolves ONLY on a genuinely acknowledged write: a 409
 *   version conflict, a FINALIZED_STATE, an access denial, a signed
 *   rejection, a stale-visit drop (null) or a transport failure (throw)
 *   rejects the promise — the guard keeps the user on the route with the
 *   draft intact and the dialog actionable (Retry/Discard stay available);
 * - `discard` reloads the server baseline (the explicit «discard my
 *   edits» path, EMRCONFLICT-FE-001) — Discard is a deliberate choice,
 *   never a silent loss;
 * - an in-flight autosave (`isSaving`) registers the visit as a pending
 *   operation so a pending-only leave is blocked until it settles
 *   (PR 3351 round 7/8 contract), and unmounts the editor → the source
 *   is unregistered.
 *
 * `enabled: false` (read-only observers / access-denied mounts) never
 * registers anything: those editors hold nothing that a leave could
 * destroy.
 */

export interface UseEMRLeaveGuardOptions {
    /** Visit owner identity; null/undefined → the container has no EMR loaded. */
    visitId: string | number | null | undefined;
    /** Live dirty flag of the editor (unsaved clinical changes). */
    isDirty: boolean;
    /** A save/sign request is in flight (pending-only leave protection). */
    isSaving: boolean;
    /** useEMR's save function (draft autosave of the CURRENT visit). */
    saveEMR: (opts?: Record<string, unknown>) => Promise<unknown>;
    /** useEMR's reload — the explicit «discard my edits» baseline restore. */
    reloadFromServer: () => Promise<unknown>;
    /** Read-only observers / access-denied mounts register nothing. */
    enabled?: boolean;
    /** Synchronously stop queued/unmount autosave before explicit Discard. */
    onDiscard?: () => void;
}

export function useEMRLeaveGuard({
    visitId,
    isDirty,
    isSaving,
    saveEMR,
    reloadFromServer,
    enabled = true,
    onDiscard,
}: UseEMRLeaveGuardOptions): void {
    const guard = useLabDirtyGuard();

    // Render-time refs: the registry reads live values without re-registering
    // on every keystroke (same pattern as the lab workbench sources).
    const isDirtyRef = useRef(isDirty);
    isDirtyRef.current = isDirty;
    const saveEMRRef = useRef(saveEMR);
    saveEMRRef.current = saveEMR;
    const reloadRef = useRef(reloadFromServer);
    reloadRef.current = reloadFromServer;
    const onDiscardRef = useRef(onDiscard);
    onDiscardRef.current = onDiscard;

    const hasVisit = visitId !== null && visitId !== undefined && visitId !== '';
    const sourceId = `emr-visit-${visitId}`;
    // Стабильные accessor'ы (useCallback внутри провайдера/standalone):
    // эффекты не пересоздаются на рендрах контейнера.
    const registerDirtySource = guard.registerDirtySource;
    const notifyDirtyStateChange = guard.notifyDirtyStateChange;

    // Register the visit owner in the SHARED App-level registry. Unmount or
    // disable → unregister (the confirmed-leave flow already removed the
    // panel together with its draft).
    useEffect(() => {
        if (!enabled || !hasVisit) return undefined;
        return registerDirtySource({
            id: sourceId,
            isDirty: () => isDirtyRef.current,
            // Save-and-leave: await the server ack of the CURRENT visit.
            // Rejected outcomes (conflict / finalized / accessDenied /
            // signed / null / transport throw) reject → the guard keeps the
            // user on the route with the draft; the dialog stays
            // actionable (Retry / Discard).
            save: async () => {
                const result = await saveEMRRef.current({ isDraft: true });
                const unacknowledged = result == null
                    || isRejectedEMRWrite(result)
                    || (result as Record<string, unknown>)?.finalized === true;
                if (unacknowledged) {
                    throw new Error('emr_leave_save_not_acknowledged');
                }
            },
            // Discard is an explicit reload of the canonical server snapshot
            // (EMRCONFLICT-FE-001 «discard my edits» path). The transition
            // runs after this; the draft cannot «resurrect» from the reload.
            discard: () => {
                // The unmount cleanup of useEMRAutosave fires before a
                // pending reload GET can settle. Stop its POST synchronously.
                onDiscardRef.current?.();
                void reloadRef.current?.();
            },
        });
    }, [enabled, hasVisit, sourceId, registerDirtySource]);

    // Report dirty flips to the shared registry (guarded notify inside the
    // provider: re-renders only on the aggregated flip, never per keystroke).
    useEffect(() => {
        notifyDirtyStateChange();
    });

    // Pending-only protection (PR 3351 round 7/8): an in-flight draft
    // autosave must block the leave until it settles — aborting a
    // non-idempotent POST mid-write loses the response and invites a
    // duplicate revision. The document may be clean (dirty=false) while
    // the request is still in flight, so dirty alone cannot cover this.
    // NOTE: the provider setters replace the whole pending-source list —
    // an EMR editor can never be co-mounted with the /lab workbenches
    // (different routes), so the single-owner write is race-free here.
    const setPendingOperationSources = guard.setPendingOperationSources;
    const setHistoryGuardPendingSources = guard.setHistoryGuardPendingSources;
    useEffect(() => {
        if (!enabled || !hasVisit) {
            setPendingOperationSources([]);
            setHistoryGuardPendingSources([]);
            return () => {
                setPendingOperationSources([]);
                setHistoryGuardPendingSources([]);
            };
        }
        setPendingOperationSources(isSaving ? [sourceId] : []);
        setHistoryGuardPendingSources(isSaving ? [sourceId] : []);
        return () => {
            setPendingOperationSources([]);
            setHistoryGuardPendingSources([]);
        };
    }, [enabled, hasVisit, isSaving, sourceId, setPendingOperationSources, setHistoryGuardPendingSources]);
}
