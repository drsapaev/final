/**
 * useEMRAutosave - Debounced autosave with safeguards
 * 
 * Rules:
 * - DOES NOT save if: !isDirty, isSaving, status === "signed"
 * - DOES pass client_session_id and respect row_version
 * - DOES NOT create new timer on each rerender (useRef)
 * - DOES NOT trigger save immediately after UNDO (checks actual dirty state)
 * 
 * Config:
 * - debounce: 3 seconds
 * - maxWait: 30 seconds (force save even if user keeps typing)
 */

import { useEffect, useRef, useCallback } from 'react';
import logger from '../utils/logger';

const DEFAULT_DEBOUNCE_MS = 3000;   // 3 seconds
const DEFAULT_MAX_WAIT_MS = 30000;  // 30 seconds

/**
 * useEMRAutosave Hook
 * 
 * @param {Object} options
 * @param {boolean} options.isDirty - Has unsaved changes
 * @param {boolean} options.isSaving - Currently saving
 * @param {boolean} options.isSigned - EMR is signed (readonly)
 * @param {string} options.status - Current status
 * @param {Function} options.saveEMR - Save function from useEMR
 * @param {number} options.debounceMs - Debounce delay (default: 3000)
 * @param {number} options.maxWaitMs - Max wait before force save (default: 30000)
 * @param {boolean} options.enabled - Enable/disable autosave (default: true)
 * @param {Function} options.onAutosaveStart - Callback when autosave starts
 * @param {Function} options.onAutosaveSuccess - Callback when autosave succeeds
 * @param {Function} options.onAutosaveError - Callback when autosave fails
 */
export function useEMRAutosave({
    isDirty,
    isSaving,
    isSigned,
    status,
    saveEMR,
    debounceMs = DEFAULT_DEBOUNCE_MS,
    maxWaitMs = DEFAULT_MAX_WAIT_MS,
    enabled = true,
    onAutosaveStart,
    onAutosaveSuccess,
    onAutosaveError,
}: {
    isDirty: boolean;
    isSaving: boolean;
    isSigned: boolean;
    status: string;
    saveEMR: (opts?: Record<string, unknown>) => Promise<unknown>;
    debounceMs?: number;
    maxWaitMs?: number;
    enabled?: boolean;
    onAutosaveStart?: () => void;
    onAutosaveSuccess?: (result: unknown) => void;
    onAutosaveError?: (error: unknown) => void;
}) {
    // Use refs to avoid recreating timers on each render
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const maxWaitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastSaveTimeRef = useRef<number | null>(null);
    const pendingSaveRef = useRef(false);
    // Explicit user Discard must not resurrect old draft text via the
    // #4009 last-chance unmount flush (or a timer fired while leaving).
    const discardedRef = useRef(false);

    // audit/phase-1, BS-17: keep latest `doAutosave` in a ref so the
    // maxWait / debounce timers always invoke the CURRENT closure.
    // Previously both timers captured the `doAutosave` from the render when
    // the timer was first scheduled — so after 30s of continuous typing,
    // the maxWait timer fired with the ORIGINAL `doAutosave` (which closed
    // over the ORIGINAL `saveEMR` → ORIGINAL `state.data`), silently
    // saving a stale snapshot and losing everything typed since.
    // The ref is updated on every render so timer callbacks see the latest.
    const doAutosaveRef = useRef<(() => Promise<void>) | null>(null);

    /**
     * Check if save is allowed
     */
    const canSave = useCallback(() => {
        // An explicit Discard is a synchronous prohibition, not an async GET.
        if (discardedRef.current) return false;
        // Guard conditions - do NOT save if:
        if (!isDirty) return false;           // No changes to save
        if (isSaving) return false;           // Already saving
        if (isSigned) return false;           // EMR is signed (readonly)
        if (status === 'conflict') return false; // Active conflict
        if (errorCountRef.current >= MAX_CONSECUTIVE_ERRORS) return false; // Paused after repeated errors
        if (!enabled) return false;           // Autosave disabled

        return true;
    }, [isDirty, isSaving, isSigned, status, enabled]);

    // Track consecutive errors for backoff
    const errorCountRef = useRef(0);
    const MAX_CONSECUTIVE_ERRORS = 3;
    const BACKOFF_MULTIPLIER = 2;
    const MAX_BACKOFF_MS = 60000; // 1 minute max

    /**
     * Calculate backoff delay based on error count
     */
    const getBackoffDelay = useCallback(() => {
        if (errorCountRef.current === 0) return debounceMs;
        const delay = Math.min(
            debounceMs * Math.pow(BACKOFF_MULTIPLIER, errorCountRef.current),
            MAX_BACKOFF_MS
        );
        return delay;
    }, [debounceMs]);

    /**
     * Perform autosave
     */
    const doAutosave = useCallback(async () => {
        // Double-check guards (state may have changed since timer started)
        if (!canSave()) {
            pendingSaveRef.current = false;
            return;
        }

        // Stop if too many consecutive errors
        if (errorCountRef.current >= MAX_CONSECUTIVE_ERRORS) {
            pendingSaveRef.current = false;
            return;
        }

        pendingSaveRef.current = false;

        try {
            onAutosaveStart?.();

            const result = await saveEMR({ isDraft: true }) as { accessDenied?: boolean; conflict?: unknown; finalized?: boolean } | undefined;

            if (result?.accessDenied) {
                errorCountRef.current = MAX_CONSECUTIVE_ERRORS;
                pendingSaveRef.current = false;
                clearTimers();
                                logger.warn('[Autosave] Paused because EMR access is denied.');
                onAutosaveError?.({
                    type: 'accessDenied',
                    error: result,
                    retryCount: errorCountRef.current
                });
                return;
            }

            // EMRAUTOSAVE-FE-001 (audit 3886): a 409 conflict is NOT a
            // successful save. Conflict handling must precede ANY success
            // bookkeeping — the last-successful timestamp and the error
            // counter describe only genuinely successful saves. Policy: a
            // conflict is a deterministic state the doctor must resolve
            // (the UI shows the Conflict status); it neither resets the
            // transient-error counter (that would hide flaky-network
            // backoff state) nor increments it (backoff cannot fix a
            // version conflict).
            if (result?.conflict) {
                onAutosaveError?.({ type: 'conflict', ...(result as Record<string, unknown>) });
                return;
            }

            // RETRO-3971-03 (post-merge review of the 3969–3996 window):
            // saveEMR resolves { finalized: true } when the document was
            // signed/amended on the server — deterministic amendment routing,
            // never a successful save (and never "another user changed the
            // document"). The same honesty policy as a conflict: no
            // timestamp stamp, no error-counter reset — retrying cannot fix
            // a finalized state; the doctor must use the amend flow.
            if (result?.finalized) {
                onAutosaveError?.({ type: 'finalized', ...(result as Record<string, unknown>) });
                return;
            }

            // RETRO-3971-02 (post-merge review of the 3969–3996 window):
            // saveEMR resolves null/undefined when the save never actually
            // ran for the CURRENT visit — useEMR's stale-visit bail returns
            // null for a late failure of a previous visit, and the
            // dermatology panel mounts its EMR container without a
            // per-visit key, so the surviving hook instance carried the
            // previous visit's failure into the success bookkeeping and
            // the status indicator rendered "saved" for the new visit's
            // fresh editor. A save that did not happen is not a success:
            // no timestamp stamp, no error-counter reset; the drop is
            // reported through onAutosaveError (type 'staleVisit') and the
            // counter keeps the conflict policy (no reset, no increment).
            if (result == null) {
                onAutosaveError?.({ type: 'staleVisit', error: result, retryCount: errorCountRef.current });
                return;
            }

            lastSaveTimeRef.current = Date.now();
            errorCountRef.current = 0; // Reset on success only

            onAutosaveSuccess?.(result);
        } catch (error) {
            const err = error as Record<string, unknown>;
            const response = err?.response as Record<string, unknown> | undefined;
            const status = response?.status;
            errorCountRef.current += 1;

            const isAccessDenied = status === 401 || status === 403;
            if (isAccessDenied) {
                errorCountRef.current = MAX_CONSECUTIVE_ERRORS;
                pendingSaveRef.current = false;
                clearTimers();
                                logger.warn('[Autosave] Paused because EMR access is denied.');
                onAutosaveError?.({
                    type: 'accessDenied',
                    error,
                    retryCount: errorCountRef.current
                });
                return;
            }

            // Only log once, not spam
            if (errorCountRef.current === 1) {
                                logger.error('[Autosave] Error:', (error as Error).message || error);
            }

            // For 503 errors, apply backoff silently
            const is503 = status === 503;
            if (is503 && errorCountRef.current < MAX_CONSECUTIVE_ERRORS) {
                // Schedule retry with backoff
                const backoffDelay = getBackoffDelay();
                                logger.info(`[Autosave] Server unavailable. Retrying in ${backoffDelay / 1000}s...`);
            }

            onAutosaveError?.({ type: 'error', error, retryCount: errorCountRef.current });
        }
    }, [canSave, saveEMR, onAutosaveStart, onAutosaveSuccess, onAutosaveError, getBackoffDelay]);

    // Keep the ref in sync with the latest `doAutosave` closure on every render.
    // This is what allows the long-lived maxWait timer (set once, fires after 30s)
    // to invoke the latest `doAutosave` instead of the stale one captured at
    // the time the timer was scheduled.
    doAutosaveRef.current = doAutosave;

    // RETRO-3971-04 (post-merge review of the 3969–3996 window): a pending
    // autosave debounce must not be silently discarded when the editor
    // unmounts (SPA navigation / visit switch). Only the browser
    // beforeunload was guarded; the dirty-effect cleanup merely cleared
    // the timers, so keystrokes inside the debounce window never reached
    // the server. On unmount, invoke the LATEST doAutosave once — the
    // last-chance flush. Its own guards (canSave, the error-pause policy,
    // isDirty) decide whether a POST actually fires, and the BS-17
    // latest-ref guarantees the latest saveEMR closure over the LATEST
    // state.data snapshot. saveEMR itself already guards stale-visit
    // dispatches (RETRO-3930-01), so a post-unmount resolution cannot
    // touch the unmounted editor's state.
    useEffect(() => () => {
        if (!discardedRef.current) doAutosaveRef.current?.();
    }, []);

    /**
     * Clear all timers
     */
    const clearTimers = useCallback(() => {
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
            debounceTimerRef.current = null;
        }
        if (maxWaitTimerRef.current) {
            clearTimeout(maxWaitTimerRef.current);
            maxWaitTimerRef.current = null;
        }
    }, []);

    // Intentional Discard is distinct from a forced/uncontrolled unmount:
    // cancel pending timeouts and prevent both future timer saves and the
    // destructor's best-effort POST for this discarded draft.
    const suppressOnDiscard = useCallback(() => {
        discardedRef.current = true;
        pendingSaveRef.current = false;
        clearTimers();
    }, [clearTimers]);

    /**
     * Schedule autosave with debounce
     */
    const scheduleAutosave = useCallback(() => {
        // Clear existing debounce timer
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        // Set debounce timer — call through the ref so we always invoke the
        // latest `doAutosave` (and therefore the latest `saveEMR` / `state.data`).
        debounceTimerRef.current = setTimeout(() => {
            doAutosaveRef.current?.();
            clearTimers();
        }, debounceMs);

        // Start maxWait timer if not already running.
        // The maxWait timer fires only once per "dirty session" (guarded by
        // pendingSaveRef), so it MUST call through the ref — otherwise it
        // captures the first-render `doAutosave` and saves stale data.
        if (!maxWaitTimerRef.current && !pendingSaveRef.current) {
            pendingSaveRef.current = true;
            maxWaitTimerRef.current = setTimeout(() => {
                doAutosaveRef.current?.();
                clearTimers();
            }, maxWaitMs);
        }
    }, [debounceMs, maxWaitMs, clearTimers]);

    /**
     * Effect: Watch isDirty and schedule autosave
     */
    useEffect(() => {
        if (!enabled) {
            clearTimers();
            return;
        }

        // Only schedule if dirty and can save
        if (isDirty && canSave()) {
            scheduleAutosave();
        } else {
            // Clear timers if no longer dirty (e.g., manual save or undo back to clean)
            if (!isDirty) {
                clearTimers();
                pendingSaveRef.current = false;
            }
        }

        // Cleanup on unmount
        return () => {
            clearTimers();
        };
    }, [isDirty, enabled, canSave, scheduleAutosave, clearTimers]);

    /**
     * Force immediate save (for external triggers)
     */
    const forceSave = useCallback(async () => {
        clearTimers();
        errorCountRef.current = 0; // Reset errors on manual save
        if (canSave()) {
            await doAutosave();
        }
    }, [clearTimers, canSave, doAutosave]);

    /**
     * Reset error count (for manual retry)
     */
    const resetErrors = useCallback(() => {
        errorCountRef.current = 0;
    }, []);

    /**
     * Return info about autosave state
     */
    return {
        // Last successful autosave timestamp
        lastAutosave: lastSaveTimeRef.current,

        // Whether autosave is pending
        isPending: pendingSaveRef.current,

        // Error count (for UI display)
        errorCount: errorCountRef.current,

        // Whether autosave is paused due to errors
        isPausedDueToErrors: errorCountRef.current >= MAX_CONSECUTIVE_ERRORS,

        // Force immediate save
        forceSave,

        // Reset error counter (for retry)
        resetErrors,

        // Clear pending autosave
        cancel: clearTimers,

        // Synchronously suppress every later autosave for an explicit
        // user Discard; normal unmounts continue using the #4009 flush.
        suppressOnDiscard,

        // Config info (for UI)
        config: {
            debounceMs,
            maxWaitMs,
            enabled,
        },
    };
}

export default useEMRAutosave;
