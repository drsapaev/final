/**
 * Analytics utility for EMR telemetry
 * 
 * Minimal tracking for AI feature usage.
 * Only counters, no content.
 */

/**
 * Track EMR-related events
 * @param {string} eventType - Event type (ghost.enabled, ghost.accepted, etc.)
 * @param {Object} payload - Event payload (no PHI)
 */
export function trackEMREvent(eventType, payload = {}) {
    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
        console.log('[EMR Analytics]', eventType, payload);
    }

    // In production, this would send to analytics backend
    // Example: fetch('/api/analytics/emr', { method: 'POST', body: JSON.stringify({ eventType, payload, timestamp: Date.now() }) })
}

export default {
    trackEMREvent
};
