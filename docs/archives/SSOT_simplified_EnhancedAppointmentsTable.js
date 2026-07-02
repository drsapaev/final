/**
 * ⭐ SSOT SIMPLIFIED VERSION: EnhancedAppointmentsTable
 * 
 * This document defines the simplified versions of functions that need to be
 * modified in EnhancedAppointmentsTable.jsx.
 * 
 * REMOVED:
 * - getPatientEntries (L147-152)
 * - getEarliestQueueTime (L155-179)
 * - buildPatientTooltip (L182-246)
 * 
 * SIMPLIFIED:
 * - renderServices (L584+)
 * - renderQueueNumbers (location TBD)
 * 
 * KEPT UNCHANGED:
 * - renderStatus
 * - renderVisitType
 * - renderPaymentType
 * - Sorting/filtering/pagination logic
 */


// =====================================================
// ❌ DELETE: getPatientEntries (L147-152)
// =====================================================
/*
 * This function aggregates entries from multiple patients.
 * In SSOT mode, each row = one entry, no aggregation needed.
 * 
 * BEFORE: Used to find all entries for a patient to show in tooltip
 * AFTER: Tooltip only shows data from the current row
 */


// =====================================================
// ❌ DELETE: getEarliestQueueTime (L155-179)
// =====================================================
/*
 * This function computed the earliest queue time from all patient entries.
 * In SSOT mode, each row has its own queue_time, no computation needed.
 * 
 * BEFORE: Computed earliest time across multiple patient entries
 * AFTER: Just use row.queue_time directly
 */


// =====================================================
// ❌ DELETE: buildPatientTooltip (L182-246)
// =====================================================
/*
 * This function built a complex tooltip with all patient's queue numbers.
 * In SSOT mode, each row shows only its own data.
 * 
 * BEFORE: Tooltip showed all queues for a patient
 * AFTER: Tooltip shows only data from the current row
 */


// =====================================================
// ✅ SIMPLIFIED: renderServices (L584+)
// =====================================================

/**
 * Display services exactly as received from backend.
 * 
 * REMOVED:
 * - Complex mapping from IDs to names (backend already returns codes)
 * - Tooltip showing "all patient services" (SSOT = single row data only)
 * - Fallback code generation (C01, K01, etc.)
 * 
 * KEPT:
 * - Basic display of service codes/names
 * - Simple tooltip with service names
 */
const renderServices = useCallback((services) => {
    // Empty check
    if (!services || !Array.isArray(services) || services.length === 0) {
        return <span style={{ color: 'var(--mac-text-secondary)' }}>—</span>;
    }

    // Helper to extract display text from service item
    const getServiceText = (item) => {
        if (typeof item === 'string') {
            return item;
        }
        if (typeof item === 'object' && item !== null) {
            return item.code || item.service_code || item.name || String(item);
        }
        return String(item);
    };

    // Build tooltip from full names if available
    const tooltipLines = services.map(item => {
        if (typeof item === 'object' && item !== null && item.name) {
            return item.name;
        }
        return getServiceText(item);
    });

    return (
        <div
            style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '4px'
            }}
            title={tooltipLines.join('\n')}
        >
            {services.slice(0, 3).map((item, index) => (
                <span
                    key={index}
                    style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--mac-bg-secondary)',
                        color: 'var(--mac-text-primary)',
                        fontSize: '11px',
                        fontWeight: '500',
                        letterSpacing: '0.5px'
                    }}
                >
                    {getServiceText(item)}
                </span>
            ))}
            {services.length > 3 && (
                <span
                    style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--mac-bg-tertiary)',
                        color: 'var(--mac-text-secondary)',
                        fontSize: '11px'
                    }}
                >
                    +{services.length - 3}
                </span>
            )}
        </div>
    );
}, []);


// =====================================================
// ✅ SIMPLIFIED: renderQueueNumbers
// =====================================================

/**
 * Display single queue number from row.queue_number.
 * 
 * REMOVED:
 * - queue_numbers[] array handling (now single number)
 * - getEarliestQueueTime() call
 * - buildPatientTooltip() call
 * - Index calculation fallback
 * 
 * KEPT:
 * - Status-based styling
 * - Basic number display
 */
const renderQueueNumbers = useCallback((row) => {
    const number = row.queue_number ?? row.number ?? '—';
    const status = row.status || 'waiting';

    // Status-based colors (simplified)
    const statusColors = {
        waiting: { bg: 'var(--mac-warning)', color: 'white' },
        called: { bg: 'var(--mac-info)', color: 'white' },
        served: { bg: 'var(--mac-success)', color: 'white' },
        no_show: { bg: 'var(--mac-error)', color: 'white' }
    };

    const colors = statusColors[status] || statusColors.waiting;

    // Format queue time for tooltip
    const queueTime = row.queue_time ?
        new Date(row.queue_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) :
        '';

    return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span
                style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minWidth: '32px',
                    height: '24px',
                    padding: '0 8px',
                    borderRadius: '12px',
                    backgroundColor: colors.bg,
                    color: colors.color,
                    fontSize: '13px',
                    fontWeight: '600'
                }}
                title={queueTime ? `Время очереди: ${queueTime}` : ''}
            >
                {number}
            </span>
            {queueTime && (
                <span style={{
                    fontSize: '10px',
                    color: 'var(--mac-text-secondary)',
                    marginTop: '2px'
                }}>
                    {queueTime}
                </span>
            )}
        </div>
    );
}, []);


// =====================================================
// HOW TO APPLY THESE CHANGES
// =====================================================

/**
 * 1. OPEN: frontend/src/components/tables/EnhancedAppointmentsTable.jsx
 *
 * 2. DELETE these functions entirely (lines 147-246):
 *    - getPatientEntries
 *    - getEarliestQueueTime
 *    - buildPatientTooltip
 *
 * 3. REPLACE renderServices (starting at line 584) with the simplified version above
 *
 * 4. FIND renderQueueNumbers and replace with the simplified version above
 *
 * 5. REMOVE rawEntries prop usage (line 43):
 *    - Remove: rawEntries = [],
 *    - Remove any references to rawEntries in the component
 *
 * 6. SEARCH & REMOVE any references to:
 *    - getPatientEntries()
 *    - getEarliestQueueTime()
 *    - buildPatientTooltip()
 *    - allPatientServices
 */


// =====================================================
// VISUAL COMPARISON
// =====================================================

/**
 * BEFORE (aggregated view):
 * ┌─────┬─────────────────┬────────────────────┬─────────────────────┐
 * │  №  │    Пациент      │      Услуги        │     Очередь         │
 * ├─────┼─────────────────┼────────────────────┼─────────────────────┤
 * │  1  │ Иванов И.И.     │ K01, D01, L10      │ ① ② ③              │
 * │     │                 │                    │ (все очереди)       │
 * │     │                 │ [Tooltip: все      │                     │
 * │     │                 │  услуги пациента]  │                     │
 * └─────┴─────────────────┴────────────────────┴─────────────────────┘
 * 
 * AFTER (SSOT - each entry is a row):
 * ┌─────┬─────────────────┬────────────────────┬─────────────────────┐
 * │  №  │    Пациент      │      Услуги        │     Очередь         │
 * ├─────┼─────────────────┼────────────────────┼─────────────────────┤
 * │  1  │ Иванов И.И.     │ K01                │ ①                  │
 * │  2  │ Иванов И.И.     │ D01                │ ②                  │
 * │  3  │ Иванов И.И.     │ L10                │ ③                  │
 * └─────┴─────────────────┴────────────────────┴─────────────────────┘
 * 
 * Each backend entry = 1 row. No aggregation.
 * Patient appears multiple times if they have multiple queue entries.
 */
