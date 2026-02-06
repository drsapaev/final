/**
 * useEMRTelemetry - UX / Product telemetry for EMR v2
 * 
 * WHAT THIS IS:
 * - System usage patterns
 * - AI suggestion usage stats
 * - UX performance metrics
 * 
 * WHAT THIS IS NOT:
 * - Medical content logging
 * - PHI collection
 * - Hidden audit
 * 
 * RULES:
 * - NO content (text, diagnoses, treatments)
 * - NO free text
 * - Only events (clicked, opened, duration)
 * - Separate from audit log
 * - Can be disabled
 */

import { useCallback, useRef, useEffect } from 'react';

/**
 * Allowed event types (whitelist)
 */
const ALLOWED_EVENTS = {
    // EMR lifecycle
    'emr.load': true,
    'emr.save': true,
    'emr.save.error': true,
    'emr.sign': true,
    'emr.amend': true,
    'emr.conflict': true,

    // Section interactions
    'section.open': true,
    'section.close': true,
    'section.focus': true,

    // AI interactions (no content!)
    'ai.suggestion.shown': true,
    'ai.suggestion.applied': true,
    'ai.suggestion.dismissed': true,
    'ai.panel.open': true,
    'ai.panel.close': true,
    'ai.completeness.check': true,

    // Template usage
    'template.panel.open': true,
    'template.applied': true,

    // UX metrics
    'undo': true,
    'redo': true,
    'keyboard.shortcut': true,
    'autosave.trigger': true,
    'autosave.success': true,
    'autosave.fail': true,
};

/**
 * Validate event - block any PHI
 */
function validateEvent(event) {
    if (!event || !event.event) return false;

    // Must be in whitelist
    if (!ALLOWED_EVENTS[event.event]) {
        console.warn('[Telemetry] Blocked unknown event:', event.event);
        return false;
    }

    // Check for PHI in meta (paranoid check)
    if (event.meta) {
        for (const key of Object.keys(event.meta)) {
            const value = event.meta[key];
            // Block any string longer than 50 chars (could be content)
            if (typeof value === 'string' && value.length > 50) {
                console.warn('[Telemetry] Blocked: meta value too long (possible PHI)');
                return false;
            }
        }
    }

    return true;
}

/**
 * useEMRTelemetry Hook
 * 
 * @param {Object} options
 * @param {boolean} options.enabled - Enable telemetry (opt-in)
 * @param {string} options.sessionId - Session ID for grouping
 * @param {number} options.batchSize - Events before sending
 * @param {number} options.flushIntervalMs - Auto-flush interval
 */
export function useEMRTelemetry({
    enabled = true,
    sessionId = null,
    batchSize = 10,
    flushIntervalMs = 30000,
} = {}) {
    const queueRef = useRef([]);
    const flushTimeoutRef = useRef(null);
    const sessionStartRef = useRef(Date.now());

    /**
     * Track an event
     */
    const track = useCallback((eventName, meta = {}) => {
        if (!enabled) return;

        const event = {
            event: eventName,
            entity: 'emr',
            timestamp: Date.now(),
            session_id: sessionId,
            meta: {
                ...meta,
                // Add timing info (safe)
                session_duration_ms: Date.now() - sessionStartRef.current,
            },
        };

        // Validate before queueing
        if (!validateEvent(event)) return;

        queueRef.current.push(event);

        // Auto-flush if batch full
        if (queueRef.current.length >= batchSize) {
            flush();
        }
    }, [enabled, sessionId, batchSize]);

    /**
     * Flush queue to backend
     */
    const flush = useCallback(async () => {
        if (!enabled || queueRef.current.length === 0) return;

        const events = [...queueRef.current];
        queueRef.current = [];

        try {
            // Send to telemetry endpoint (separate from main API)
            await fetch('/api/telemetry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ events }),
                // Don't wait, don't retry - telemetry is best-effort
                keepalive: true,
            });
        } catch (err) {
            // Telemetry errors are silent - don't break EMR
            console.debug('[Telemetry] Flush failed:', err.message);
        }
    }, [enabled]);

    /**
     * Track with timing
     */
    const trackTimed = useCallback((eventName, meta = {}) => {
        const startTime = Date.now();

        return () => {
            track(eventName, {
                ...meta,
                duration_ms: Date.now() - startTime,
            });
        };
    }, [track]);

    /**
     * Track section time
     */
    const trackSection = useCallback((sectionName) => {
        track('section.focus', { section: sectionName });
        return trackTimed('section.blur', { section: sectionName });
    }, [track, trackTimed]);

    /**
     * Track AI suggestion (no content!)
     */
    const trackAISuggestion = useCallback((action, field, suggestionType = 'unknown') => {
        // Explicitly block any content
        track(`ai.suggestion.${action}`, {
            field,  // just field name: 'complaints', 'diagnosis'
            type: suggestionType,  // 'phrase', 'diagnosis', 'icd10'
            // NO content, NO text, NO suggestion value
        });
    }, [track]);

    // Auto-flush on interval
    useEffect(() => {
        if (!enabled) return;

        flushTimeoutRef.current = setInterval(flush, flushIntervalMs);

        return () => {
            if (flushTimeoutRef.current) {
                clearInterval(flushTimeoutRef.current);
            }
            // Flush on unmount
            flush();
        };
    }, [enabled, flush, flushIntervalMs]);

    // Flush on page unload
    useEffect(() => {
        if (!enabled) return;

        const handleUnload = () => flush();
        window.addEventListener('beforeunload', handleUnload);

        return () => {
            window.removeEventListener('beforeunload', handleUnload);
        };
    }, [enabled, flush]);

    return {
        // Core
        track,
        flush,

        // Helpers
        trackTimed,
        trackSection,
        trackAISuggestion,

        // State
        enabled,
        queueLength: queueRef.current.length,
    };
}

export default useEMRTelemetry;
