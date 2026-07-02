/**
 * ⭐ SSOT SIMPLIFIED VERSION: loadAppointments
 * 
 * This is the simplified version of loadAppointments that removes:
 * - Client-side aggregation (mergedByPatientKey, getAppointmentKey, calcPriority, mergeAppointments)
 * - Deduplication via appointmentsMap
 * - Local overrides (localStorage)
 * - Complex enrichment logic
 * 
 * Backend is now SSOT: 1 entry = 1 row in UI
 */

// =====================================================
// SIMPLIFIED FIELD ADAPTER (ADD THIS TO RegistrarPanel.jsx)
// =====================================================

/**
 * Adapts a single backend entry to frontend row format.
 * This is the ONLY transformation layer allowed.
 * 
 * @param {Object} entry - Raw entry from backend API
 * @param {string} responseDate - Date from API response (YYYY-MM-DD)
 * @param {Object} queue - Parent queue object (for specialty)
 * @returns {Object} - Frontend-ready row
 */
const adaptEntry = (entry, responseDate, queue = {}) => ({
    // === SSOT PASSTHROUGH (no transformation) ===
    id: entry.id,
    patient_id: entry.patient_id,
    patient_birth_year: entry.patient_birth_year,
    address: entry.address || '',
    services: entry.services || [],
    service_codes: entry.service_codes || [],
    cost: entry.cost ?? 0,
    status: entry.status,
    payment_status: entry.payment_status,
    source: entry.source,
    created_at: entry.created_at,
    queue_time: entry.queue_time,
    discount_mode: entry.discount_mode,
    department_key: entry.department_key,
    department: entry.department || queue.specialty || null,
    specialty: queue.specialty || entry.specialty || null,
    queue_tag: queue.specialty || entry.queue_tag || null,
    record_type: entry.record_type || entry.type || 'unknown',

    // === FIELD NAME ADAPTATION ===
    patient_fio: entry.patient_name || 'Неизвестный пациент',
    patient_phone: entry.phone || 'Не указан',
    queue_number: entry.number,

    // === DERIVED DEFAULTS (Temporary until backend provides these) ===
    visit_type:
        entry.discount_mode === 'paid' ? 'paid' :
            entry.discount_mode === 'none' ? 'paid' :
                entry.discount_mode || 'paid',

    payment_type: 'cash', // Backend doesn't return this yet

    // === DATE NORMALIZATION ===
    date: responseDate || (entry.created_at ? entry.created_at.split('T')[0] : new Date().toISOString().split('T')[0]),
    appointment_date: responseDate || (entry.created_at ? entry.created_at.split('T')[0] : new Date().toISOString().split('T')[0]),
});


// =====================================================
// SIMPLIFIED loadAppointments (REPLACE EXISTING)
// =====================================================

/**
 * Simplified loadAppointments function.
 * 
 * REMOVED:
 * - appointmentsMap deduplication
 * - mergedByPatientKey aggregation
 * - getAppointmentKey, calcPriority, mergeAppointments functions
 * - flatEntries tracking
 * - aggregated_ids
 * - Local localStorage overrides
 * - Complex enrichment logic
 * 
 * KEPT:
 * - API call with date parameter
 * - Minimal field adaptation via adaptEntry()
 * - Error handling
 * - Loading state management
 */
const loadAppointments = useCallback(async (options = {}) => {
    const { silent = false, source: callSource = 'unknown' } = options || {};

    try {
        if (!silent) {
            setAppointmentsLoading(true);
            setDataSource('loading');
        }

        // Check token
        const token = localStorage.getItem('auth_token');
        if (!token) {
            console.warn('Токен аутентификации отсутствует');
            startTransition(() => {
                if (!silent) setDataSource('api');
                setAppointments([]);
            });
            return;
        }

        // Determine date
        const dateParam = showCalendar && historyDate ? historyDate : getLocalDateString();

        // ⭐ SSOT: Single API call, no client-side aggregation
        const response = await api.get('/registrar/queues/today', {
            params: { target_date: dateParam }
        });

        const data = response.data;

        if (data?.queues && Array.isArray(data.queues)) {
            // ⭐ SSOT: flatMap all entries, apply adapter, no deduplication
            const entries = data.queues.flatMap(queue =>
                (queue.entries || []).map(entry => {
                    // Handle nested structure (entry.data || entry)
                    const fullEntry = entry.data || entry;
                    return adaptEntry(fullEntry, data.date, queue);
                })
            );

            logger.info(`📊 SSOT: Loaded ${entries.length} entries (no aggregation)`);

            startTransition(() => {
                setAppointments(entries);
                setDataSource('api');
                setAppointmentsLoading(false);
            });

            setPaginationInfo({
                total: entries.length,
                hasMore: false,
                loadingMore: false
            });

        } else {
            logger.warn('⚠️ Invalid API response format:', data);
            startTransition(() => {
                setAppointments([]);
                setDataSource('api');
                setAppointmentsLoading(false);
            });
        }

    } catch (error) {
        logger.error('❌ loadAppointments error:', error);
        startTransition(() => {
            setAppointments([]);
            setDataSource('error');
            setAppointmentsLoading(false);
        });
        toast.error('Ошибка загрузки записей');
    }

}, [showCalendar, historyDate]);


// =====================================================
// SIMPLIFIED enrichAppointmentsWithPatientData (DELETE)
// =====================================================

/**
 * ❌ DELETE THIS FUNCTION ENTIRELY
 * 
 * The enrichAppointmentsWithPatientData function is no longer needed because:
 * 1. Backend returns patient_name, phone, address, birth_year directly
 * 2. No additional API calls required
 * 3. No local overrides needed
 * 4. All defaults are handled in adaptEntry()
 * 
 * If you need backwards compatibility, use this stub:
 */
const enrichAppointmentsWithPatientData = useCallback((appointments) => {
    // SSOT: Backend provides all data, just return as-is
    return appointments;
}, []);


// =====================================================
// FUNCTIONS TO DELETE ENTIRELY
// =====================================================

/**
 * ❌ DELETE: getAppointmentKey
 * ❌ DELETE: calcPriority
 * ❌ DELETE: mergeAppointments
 *
 * These functions aggregate multiple entries for the same patient.
 * In SSOT mode: 1 backend entry = 1 UI row, no aggregation needed.
 */


// =====================================================
// LOCAL OVERRIDES - DELETE ENTIRELY
// =====================================================

/**
 * ❌ DELETE ALL CODE RELATED TO:
 * - localStorage.getItem('appointments_local_overrides')
 * - localStorage.setItem('appointments_local_overrides', ...)
 * - apt._locallyModified
 * - overrides[String(apt.id)]
 * - expiresAt checks
 *
 * UI state should not persist across page refreshes.
 * Backend is the SSOT - what you see is what backend returns.
 */


// =====================================================
// WHAT CHANGES IN THE UI
// =====================================================

/**
 * BEFORE (aggregated):
 * | # | Patient     | Services     | Queues    |
 * |---|-------------|--------------|-----------|
 * | 1 | Иванов И.И. | K01, D01, S01| 1, 2, 3   |  <- 3 backend entries merged
 * 
 * AFTER (SSOT):
 * | # | Patient     | Services | Queue |
 * |---|-------------|----------|-------|
 * | 1 | Иванов И.И. | K01      | 1     |  <- Entry 1
 * | 2 | Иванов И.И. | D01      | 2     |  <- Entry 2
 * | 3 | Иванов И.И. | S01      | 3     |  <- Entry 3
 * 
 * Each entry is now a separate row.
 * This is intentional - backend is SSOT.
 */
