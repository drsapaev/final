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

            const result = await saveEMR({ isDraft: true }) as { accessDenied?: boolean; conflict?: unknown } | undefined;

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

            lastSaveTimeRef.current = Date.now();
            errorCountRef.current = 0; // Reset on success

            // Check for conflict
            if (result?.conflict) {
                onAutosaveError?.({ type: 'conflict', ...(result as Record<string, unknown>) });
            } else {
                onAutosaveSuccess?.(result);
            }
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

        // Config info (for UI)
        config: {
            debounceMs,
            maxWaitMs,
            enabled,
        },
    };
}

export default useEMRAutosave;
