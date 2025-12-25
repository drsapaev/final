/**
 * ⭐ SSOT with Presentation-Only Grouping
 * 
 * GOAL: 1 patient = 1 visual row, services shown as "K01 (1), D01 (2)"
 * 
 * CRITICAL RULES:
 * ✅ ALLOWED: groupBy(patient_id) for rendering
 * ✅ ALLOWED: sort within group by queue_time
 * ✅ ALLOWED: format display strings
 * ❌ FORBIDDEN: deduplication
 * ❌ FORBIDDEN: mergeAppointments
 * ❌ FORBIDDEN: calcPriority
 * ❌ FORBIDDEN: modifying original entries
 * ❌ FORBIDDEN: localStorage overrides
 */

// =====================================================
// PRESENTATION-ONLY GROUPING (Add to EnhancedAppointmentsTable.jsx)
// =====================================================

/**
 * Groups flat entries by patient_id for UI rendering ONLY.
 * Does NOT modify the original entries array.
 */
const groupedByPatient = useMemo(() => {
    // Guard: if data is not an array, return empty
    if (!Array.isArray(data) || data.length === 0) {
        return [];
    }

    const map = new Map();

    data.forEach(entry => {
        const patientId = entry.patient_id || entry.id; // fallback to entry id if no patient_id

        if (!map.has(patientId)) {
            map.set(patientId, {
                // Representative data from first entry (for display)
                patient_id: patientId,
                patient_fio: entry.patient_fio || entry.patient_name || 'Неизвестный пациент',
                patient_phone: entry.patient_phone || entry.phone || '',
                patient_birth_year: entry.patient_birth_year,
                address: entry.address || '',
                // Collect all entries for this patient
                rows: []
            });
        }

        // Push the ORIGINAL entry (no modification)
        map.get(patientId).rows.push(entry);
    });

    // Convert to array and sort rows within each group by queue_time
    const grouped = Array.from(map.values());

    grouped.forEach(group => {
        group.rows.sort((a, b) => {
            const timeA = a.queue_time ? new Date(a.queue_time).getTime() : 0;
            const timeB = b.queue_time ? new Date(b.queue_time).getTime() : 0;
            return timeA - timeB;
        });

        // Aggregate display values (presentation only)
        group.services_display = renderServicesByQueue(group.rows);
        group.queues_display = renderQueues(group.rows);
        group.status = group.rows[0]?.status || 'waiting'; // Use first entry's status
        group.cost = group.rows.reduce((sum, r) => sum + (r.cost || 0), 0);
        group.payment_status = group.rows.every(r => r.payment_status === 'paid') ? 'paid' : 'pending';
        group.visit_type = group.rows[0]?.visit_type || 'paid';
        // Keep reference to original entries for actions
        group.entry_ids = group.rows.map(r => r.id);
    });

    return grouped;
}, [data]);


// =====================================================
// DISPLAY FORMATTERS (Presentation Layer)
// =====================================================

/**
 * Formats services as "K01 (1), D01 (2), L10 (3)"
 * Each service shows its queue number in parentheses.
 */
const renderServicesByQueue = (rows) => {
    if (!rows || rows.length === 0) return '—';

    return rows.map(row => {
        // Get first service code or name
        let serviceDisplay = '—';
        if (Array.isArray(row.services) && row.services.length > 0) {
            const svc = row.services[0];
            serviceDisplay = typeof svc === 'object' ? (svc.code || svc.name || '—') : String(svc);
        } else if (row.service_codes && row.service_codes.length > 0) {
            serviceDisplay = row.service_codes[0];
        }

        const queueNum = row.queue_number ?? row.number ?? '?';
        return `${serviceDisplay} (${queueNum})`;
    }).join(', ');
};


/**
 * Formats queue numbers as "1, 2, 3"
 */
const renderQueues = (rows) => {
    if (!rows || rows.length === 0) return '—';
    return rows.map(r => r.queue_number ?? r.number ?? '?').join(', ');
};


// =====================================================
// RENDER TABLE WITH GROUPED DATA
// =====================================================

/**
 * Render grouped rows in the table.
 * Each group = 1 patient = 1 visual row.
 */
const renderGroupedTable = () => {
    return (
        <tbody>
            {groupedByPatient.map((group, index) => (
                <tr key={group.patient_id || index}>
                    {/* Queue Numbers */}
                    <td>{group.queues_display}</td>

                    {/* Patient */}
                    <td>
                        <div className="patient-cell">
                            <strong>{group.patient_fio}</strong>
                            {group.patient_birth_year && (
                                <span className="birth-year"> ({group.patient_birth_year})</span>
                            )}
                        </div>
                    </td>

                    {/* Phone */}
                    <td>{group.patient_phone || '—'}</td>

                    {/* Address */}
                    <td>{group.address || '—'}</td>

                    {/* Services (with queue numbers) */}
                    <td>
                        <div
                            className="services-cell"
                            title={group.rows.map(r =>
                                `№${r.queue_number}: ${r.services?.[0] || '—'}`
                            ).join('\n')}
                        >
                            {group.services_display}
                        </div>
                    </td>

                    {/* Visit Type */}
                    <td>{renderVisitType(group.visit_type)}</td>

                    {/* Cost */}
                    <td>{group.cost.toLocaleString()} ₽</td>

                    {/* Payment Status */}
                    <td>{renderPaymentStatus(group.payment_status)}</td>

                    {/* Status */}
                    <td>{renderStatus(group.status)}</td>

                    {/* Actions - pass entry_ids for batch operations */}
                    <td>
                        <ActionButtons
                            entryIds={group.entry_ids}
                            entries={group.rows}
                        />
                    </td>
                </tr>
            ))}
        </tbody>
    );
};


// =====================================================
// ACTIONS: Working with Multiple Entries
// =====================================================

/**
 * When user clicks an action button:
 * - Get entry_ids from the group
 * - Call backend for EACH entry (or use batch API)
 * - Original entries are never modified client-side
 */
const handleGroupAction = async (action, group) => {
    const { entry_ids, rows } = group;

    switch (action) {
        case 'cancel':
            // Call cancel for each entry
            for (const id of entry_ids) {
                await api.post(`/registrar/entries/${id}/cancel`);
            }
            // Reload from backend (SSOT)
            await loadAppointments();
            break;

        case 'call':
            // Call first entry (earliest queue_time)
            if (rows.length > 0) {
                await api.post(`/registrar/entries/${rows[0].id}/call`);
                await loadAppointments();
            }
            break;

        case 'serve':
            // Mark all as served
            for (const id of entry_ids) {
                await api.post(`/registrar/entries/${id}/serve`);
            }
            await loadAppointments();
            break;
    }
};


// =====================================================
// WHAT THIS CHANGES IN THE UI
// =====================================================

/**
 * BEFORE (flat SSOT):
 * | Queues | Patient     | Services |
 * |--------|-------------|----------|
 * |   1    | Иванов И.И. | K01      |
 * |   2    | Иванов И.И. | D01      |
 * |   3    | Иванов И.И. | L10      |
 *
 * AFTER (presentation grouping):
 * | Queues  | Patient     | Services              |
 * |---------|-------------|-----------------------|
 * | 1, 2, 3 | Иванов И.И. | K01 (1), D01 (2), L10 (3) |
 *
 * ✅ Backend data is unchanged
 * ✅ UI is doctor-friendly (1 patient = 1 row)
 * ✅ Actions work with ALL entries for the patient
 */


// =====================================================
// VALIDATION: What is NOT in this code
// =====================================================

/**
 * ❌ NO deduplication (all entries are preserved in rows[])
 * ❌ NO mergeAppointments function
 * ❌ NO calcPriority function
 * ❌ NO localStorage overrides
 * ❌ NO modification of original data array
 * ❌ NO status computation / business logic
 * 
 * ✅ ONLY useMemo for grouping (re-computed on data change)
 * ✅ ONLY display formatting (joins, string templates)
 * ✅ ONLY sorting within group (presentation order)
 */
