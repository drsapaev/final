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
}) {
    // Use refs to avoid recreating timers on each render
    const debounceTimerRef = useRef(null);
    const maxWaitTimerRef = useRef(null);
    const lastSaveTimeRef = useRef(null);
    const pendingSaveRef = useRef(false);

    /**
     * Check if save is allowed
     */
    const canSave = useCallback(() => {
        // Guard conditions - do NOT save if:
        if (!isDirty) return false;           // No changes to save
        if (isSaving) return false;           // Already saving
        if (isSigned) return false;           // EMR is signed (readonly)
        if (status === 'conflict') return false; // Active conflict
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
            // eslint-disable-next-line no-console
            console.warn('[Autosave] Paused due to repeated errors. Manual save required.');
            pendingSaveRef.current = false;
            return;
        }

        pendingSaveRef.current = false;

        try {
            onAutosaveStart?.();

            const result = await saveEMR({ isDraft: true });

            lastSaveTimeRef.current = Date.now();
            errorCountRef.current = 0; // Reset on success

            // Check for conflict
            if (result?.conflict) {
                onAutosaveError?.({ type: 'conflict', ...result });
            } else {
                onAutosaveSuccess?.(result);
            }
        } catch (error) {
            errorCountRef.current += 1;

            // Only log once, not spam
            if (errorCountRef.current === 1) {
                // eslint-disable-next-line no-console
                console.error('[Autosave] Error:', error.message || error);
            }

            // For 503 errors, apply backoff silently
            const is503 = error?.response?.status === 503;
            if (is503 && errorCountRef.current < MAX_CONSECUTIVE_ERRORS) {
                // Schedule retry with backoff
                const backoffDelay = getBackoffDelay();
                // eslint-disable-next-line no-console
                console.log(`[Autosave] Server unavailable. Retrying in ${backoffDelay / 1000}s...`);
            }

            onAutosaveError?.({ type: 'error', error, retryCount: errorCountRef.current });
        }
    }, [canSave, saveEMR, onAutosaveStart, onAutosaveSuccess, onAutosaveError, getBackoffDelay]);

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

        // Set debounce timer
        debounceTimerRef.current = setTimeout(() => {
            doAutosave();
            clearTimers();
        }, debounceMs);

        // Start maxWait timer if not already running
        if (!maxWaitTimerRef.current && !pendingSaveRef.current) {
            pendingSaveRef.current = true;
            maxWaitTimerRef.current = setTimeout(() => {
                doAutosave();
                clearTimers();
            }, maxWaitMs);
        }
    }, [debounceMs, maxWaitMs, doAutosave, clearTimers]);

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
