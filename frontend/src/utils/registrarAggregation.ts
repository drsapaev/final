import { parseRegistrarTimestamp } from './dateUtils';

export const normalizeRegistrationMode = (value: unknown) => {
  const normalized = String(value || 'none').toLowerCase();
  return ['none', 'repeat', 'benefit', 'all_free'].includes(normalized) ? normalized : 'none';
};

export const normalizePaymentStatus = (value: unknown) => String(value || 'pending').toLowerCase() === 'paid' ? 'paid' : 'pending';

export const getRecordAmount = (appointment: Record<string, unknown>) => {
  const amount = Number(appointment?.cost ?? 0);
  return Number.isFinite(amount) ? amount : 0;
};

/**
 * PR-11: Unified time-field adaptation for registrar/doctor/specialty panels.
 *
 * Extracts the 6 time-related fields that EnhancedAppointmentsTable's
 * getRegistrarTimestampDisplay() needs to render "Очередь" / "Создано" +
 * "Изменено" indicator correctly.
 *
 * Before PR-11, only RegistrarPanel.adaptEntry passed these through.
 * Cardio/Derma/Dental panels dropped them, causing:
 *   - "Очередь" label never showed (fell back to "Создано")
 *   - "Изменено" indicator never rendered after services added
 *
 * Usage:
 *   import { adaptTimeFields } from '../utils/registrarAggregation';
 *   const row = { ...otherFields, ...adaptTimeFields(entry: Record<string, unknown>, data: Record<string, unknown>) };
 *
 * @param {Object} entry - backend queue entry (from /registrar/queues/today)
 * @param {Object} [data] - top-level response (for timezone fallback)
 * @returns {Object} { created_at, queue_time, updated_at, last_changed_at, display_time_kind, timezone }
 */
export const adaptTimeFields = (entry: Record<string, unknown>, data: Record<string, unknown>): Record<string, unknown> => {
  const fullEntry: Record<string, unknown> = (entry?.data as Record<string, unknown>) || entry || {};
  const sourceEntry: Record<string, unknown> = entry || {};

  const createdAt = fullEntry.created_at || sourceEntry.created_at || null;
  const hasQueueTime = Boolean(fullEntry.queue_time || sourceEntry.queue_time);
  const queueTime = fullEntry.queue_time || sourceEntry.queue_time || createdAt;

  return {
    created_at: createdAt,
    queue_time: queueTime,
    updated_at: fullEntry.updated_at || fullEntry.last_changed_at || sourceEntry.updated_at || sourceEntry.last_changed_at || null,
    last_changed_at: fullEntry.last_changed_at || fullEntry.updated_at || sourceEntry.last_changed_at || sourceEntry.updated_at || null,
    display_time_kind: fullEntry.display_time_kind || sourceEntry.display_time_kind || (hasQueueTime ? 'queue_time' : 'created_at'),
    timezone: fullEntry.timezone || sourceEntry.timezone || data?.timezone || 'Asia/Tashkent',
  };
};

export const getRegistrarPresentationSortTime = (record: Record<string, unknown>) => {
  const value = record?.queue_time || record?.created_at || null;
  if (!value) return 0;
  const date = parseRegistrarTimestamp(value);
  return !date || Number.isNaN(date.getTime()) ? 0 : date.getTime();
};

export const compareRegistrarPresentationOrder = (a: Record<string, unknown>, b: Record<string, unknown>) => {
  const aTime = getRegistrarPresentationSortTime(a);
  const bTime = getRegistrarPresentationSortTime(b);
  if (aTime === bTime) {
    return Number(a?.id || 0) - Number(b?.id || 0);
  }
  return aTime - bTime;
};

export const sortRegistrarRowsForPresentation = (records: Record<string, unknown>[] = []) => (
  [...records].sort(compareRegistrarPresentationOrder)
);

const normalizeRecordKind = (appointment: Record<string, unknown>): string => String(
  appointment?.record_kind ?? appointment?.source_kind ?? appointment?.record_type ?? appointment?.type ?? ''
).trim().toLowerCase();

const pickCanonicalVisitId = (appointment: Record<string, unknown>): unknown => appointment?.visit_id ?? appointment?.visitId ?? null;

const pickCanonicalAppointmentId = (appointment: Record<string, unknown>): unknown => appointment?.appointment_id ?? null;

const hasQueueIdentityValue = (value: unknown) => value !== null && value !== undefined && value !== '';

const pickQueueNumberEntryId = (queueNumber: unknown): string | number | null => {
  if (!queueNumber || typeof queueNumber !== 'object') return null;
  const qn = queueNumber as Record<string, unknown>;

  const explicitQueueEntryId = qn.original_queue_id ??
    qn.queue_entry_id ??
    qn.doctor_queue_entry_id ??
    null;
  if (hasQueueIdentityValue(explicitQueueEntryId)) {
    return explicitQueueEntryId as string | number;
  }

  if (hasQueueIdentityValue(qn.queue_id)) {
    return null;
  }

  return hasQueueIdentityValue(qn.id) ? (qn.id as string | number) : null;
};

const pickCanonicalQueueEntryId = (appointment: Record<string, unknown>) => {
  const explicitQueueEntryId = appointment?.queue_entry_id ??
    appointment?.original_queue_id ??
    appointment?.doctor_queue_entry_id ??
    null;
  if (hasQueueIdentityValue(explicitQueueEntryId)) {
    return explicitQueueEntryId as string | number;
  }

  return pickQueueNumberEntryId((appointment?.queue_numbers as unknown[])?.[0]);
};

const pickOnlineQueueRecordId = (appointment: Record<string, unknown>) => {
  const queueEntryId = pickCanonicalQueueEntryId(appointment);
  if (hasQueueIdentityValue(queueEntryId)) {
    return queueEntryId;
  }
  if (
    hasQueueIdentityValue(appointment?.queue_id) ||
    hasQueueIdentityValue((appointment?.queue_numbers as unknown[])?.[0] && ((appointment?.queue_numbers as unknown[])[0] as Record<string, unknown>)?.queue_id)
  ) {
    return null;
  }
  return appointment?.id;
};

const buildRecordRef = (appointment: Record<string, unknown>) => {
  const recordKind = normalizeRecordKind(appointment);
  const recordId = appointment?.canonical_record_id
    ?? (recordKind === 'visit' ? appointment?.visit_id : null)
    ?? (recordKind === 'online_queue' ? pickOnlineQueueRecordId(appointment) : null)
    ?? (recordKind === 'appointment' ? appointment?.appointment_id : null)
    ?? (recordKind === 'online_queue' ? null : appointment?.id);

  if (!['visit', 'online_queue', 'appointment'].includes(recordKind)) return null;
  const numericId = Number(recordId);
  if (!Number.isFinite(numericId) || numericId <= 0) return null;
  return { record_kind: recordKind, record_id: numericId };
};

const buildPatientGroupKey = (appointment: Record<string, unknown>, index: number = 0): string => {
  const patientId = appointment?.patient_id;
  if (patientId !== null && patientId !== undefined && String(patientId).trim() !== '') {
    return `patient:${patientId}`;
  }

  const fio = String(appointment?.patient_fio || '').trim().toLowerCase();
  const phone = String(appointment?.patient_phone || appointment?.phone || '').replace(/\D/g, '');
  const birth = String(
    appointment?.patient_birth_date ||
    appointment?.birth_date ||
    appointment?.patient_birth_year ||
    ''
  ).trim();
  if (fio || phone || birth) {
    return `identity:${fio}|${phone}|${birth}`;
  }

  const recordRef = buildRecordRef(appointment);
  if (recordRef) {
    return `record:${recordRef.record_kind}:${recordRef.record_id}`;
  }

  return `row:${appointment?.id ?? index}`;
};

const pickPatientGender = (appointment: Record<string, unknown>): string => {
  const gender = appointment?.patient_gender ??
    appointment?.patient_sex ??
    appointment?.gender ??
    appointment?.sex ??
    null;
  return gender != null ? String(gender) : '';
};

export const aggregatePatientsForAllDepartments = (appointments: Record<string, unknown>[] = []) => {
  const patientGroups: Record<string, any> = {};

  const toTime = (value: unknown) => {
    if (!value) return null;
    const date = parseRegistrarTimestamp(value);
    return !date || Number.isNaN(date.getTime()) ? null : date.getTime();
  };

  const pickEarlierTimestamp = (currentValue: unknown, nextValue: unknown) => {
    if (!currentValue) return nextValue || currentValue;
    if (!nextValue) return currentValue;

    const currentTime = toTime(currentValue);
    const nextTime = toTime(nextValue);

    if (currentTime === null) return nextValue;
    if (nextTime === null) return currentValue;

    return nextTime < currentTime ? nextValue : currentValue;
  };

  const pickLaterTimestamp = (currentValue: unknown, nextValue: unknown) => {
    if (!currentValue) return nextValue || currentValue;
    if (!nextValue) return currentValue;

    const currentTime = toTime(currentValue);
    const nextTime = toTime(nextValue);

    if (currentTime === null) return nextValue;
    if (nextTime === null) return currentValue;

    return nextTime > currentTime ? nextValue : currentValue;
  };

  appointments.forEach((appointment: Record<string, unknown>, index: number) => {
    const patientKey = buildPatientGroupKey(appointment, index);
    const normalizedDiscountMode = normalizeRegistrationMode(appointment.discount_mode);
    const normalizedPayment = normalizePaymentStatus(appointment.payment_status);
    const appointmentCost = getRecordAmount(appointment);
    const recordRef = buildRecordRef(appointment);
    const patientGender: string = String(pickPatientGender(appointment) || '');

    if (!patientGroups[patientKey]) {
      const initialVisitId = pickCanonicalVisitId(appointment);
      const initialAppointmentId = pickCanonicalAppointmentId(appointment);
      const initialQueueEntryId = pickCanonicalQueueEntryId(appointment);

      patientGroups[patientKey] = {
        id: appointment.id,
        visit_id: initialVisitId,
        appointment_id: initialAppointmentId,
        queue_entry_id: initialQueueEntryId,
        // audit/phase-6, BS-60: use Sets for deduplication throughout the loop,
        // materialize to arrays only at the finalization step (line 440+).
        // Previously each push was followed by [...new Set(array)] which is
        // O(k) per appointment -> O(k^2) per patient for k appointments.
        // External consumers expect arrays, so we keep the array fields as
        // the canonical source and maintain Sets as a fast dedup index.
        visit_ids: initialVisitId !== null && initialVisitId !== undefined ? [initialVisitId] : [],
        appointment_ids: initialAppointmentId !== null && initialAppointmentId !== undefined ? [initialAppointmentId] : [],
        queue_entry_ids: initialQueueEntryId !== null && initialQueueEntryId !== undefined ? [initialQueueEntryId] : [],
        visit_ids_set: new Set(initialVisitId !== null && initialVisitId !== undefined ? [initialVisitId] : []),
        appointment_ids_set: new Set(initialAppointmentId !== null && initialAppointmentId !== undefined ? [initialAppointmentId] : []),
        queue_entry_ids_set: new Set(initialQueueEntryId !== null && initialQueueEntryId !== undefined ? [initialQueueEntryId] : []),
        aggregated_ids_set: new Set((appointment.aggregated_ids as unknown[]) ? [...(appointment.aggregated_ids as unknown[])] : [appointment.id]),
        patient_id: appointment.patient_id,
        patient_fio: appointment.patient_fio,
        patient_birth_year: appointment.patient_birth_year,
        patient_gender: patientGender,
        gender: patientGender,
        sex: patientGender,
        patient_phone: appointment.patient_phone,
        address: appointment.address,
        visit_type: appointment.visit_type ?? null,
        payment_type: appointment.payment_type ?? null,
        payment_status: normalizedPayment,
        cost: 0,
        status: appointment.status,
        date: appointment.date,
        appointment_date: appointment.appointment_date,
        created_at: appointment.created_at,
        queue_time: appointment.queue_time,
        updated_at: appointment.updated_at || appointment.last_changed_at || appointment.created_at,
        last_changed_at: appointment.last_changed_at || appointment.updated_at || appointment.created_at,
        display_time_kind: appointment.display_time_kind || (appointment.queue_time ? 'queue_time' : 'created_at'),
        timezone: appointment.timezone || 'Asia/Tashkent',
        services: [],
        service_details: Array.isArray(appointment.service_details) ? [...appointment.service_details] : [],
        departments: new Set(),
        doctors: new Set(),
        department: appointment.department,
        doctor_specialty: appointment.doctor_specialty,
        queue_numbers: Array.isArray(appointment.queue_numbers) ? [...appointment.queue_numbers] : [],
        confirmation_status: appointment.confirmation_status,
        confirmed_at: appointment.confirmed_at,
        confirmed_by: appointment.confirmed_by,
        record_type: appointment.record_type,
        source: appointment.source,
        discount_mode: normalizedDiscountMode,
        approval_status: appointment.approval_status,
        grouped_discount_modes: [],
        grouped_payment_statuses: [],
        grouped_payment_types: [],
        grouped_records: [],
        grouped_record_refs: [],
        // audit/phase-6, BS-60: arrays kept in sync with Sets for backward
        // compat (some consumers read array.length / array[0]); Sets are the
        // dedup source of truth.
        aggregated_ids: (appointment.aggregated_ids as unknown[]) ? [...(appointment.aggregated_ids as unknown[])] : [appointment.id],
        // (old field retained for shape compat; the Set above is the SSOT)
      };
    } else {
      // audit/phase-6, BS-60: dedup via Set.add (O(1) per id) instead of
      // [...new Set(array)] (O(k) per appointment). The array field is
      // rebuilt from the Set at the finalization step (line 440+).
      const newIds = (appointment.aggregated_ids as unknown[]) || [appointment.id];
      const aggregatedSet = patientGroups[patientKey].aggregated_ids_set as Set<unknown>;
      for (const id of newIds as unknown[]) {
        aggregatedSet.add(id);
      }
      patientGroups[patientKey].aggregated_ids = [...aggregatedSet];

      const nextVisitId = pickCanonicalVisitId(appointment);
      const nextAppointmentId = pickCanonicalAppointmentId(appointment);
      const nextQueueEntryId = pickCanonicalQueueEntryId(appointment);

      if (nextVisitId !== null && nextVisitId !== undefined) {
        const visitSet = patientGroups[patientKey].visit_ids_set as Set<unknown>;
        visitSet.add(nextVisitId);
        patientGroups[patientKey].visit_ids = [...visitSet];
        if (!patientGroups[patientKey].visit_id) {
          patientGroups[patientKey].visit_id = nextVisitId;
        }
      }

      if (nextAppointmentId !== null && nextAppointmentId !== undefined) {
        const apptSet = patientGroups[patientKey].appointment_ids_set as Set<unknown>;
        apptSet.add(nextAppointmentId);
        patientGroups[patientKey].appointment_ids = [...apptSet];
        if (!patientGroups[patientKey].appointment_id) {
          patientGroups[patientKey].appointment_id = nextAppointmentId;
        }
      }

      if (nextQueueEntryId !== null && nextQueueEntryId !== undefined) {
        const queueSet = patientGroups[patientKey].queue_entry_ids_set as Set<unknown>;
        queueSet.add(nextQueueEntryId);
        patientGroups[patientKey].queue_entry_ids = [...queueSet];
        if (!patientGroups[patientKey].queue_entry_id) {
          patientGroups[patientKey].queue_entry_id = nextQueueEntryId;
        }
      }

      if (!patientGroups[patientKey].patient_gender && patientGender) {
        patientGroups[patientKey].patient_gender = patientGender;
        patientGroups[patientKey].gender = patientGender;
        patientGroups[patientKey].sex = patientGender;
      }

      patientGroups[patientKey].queue_time = pickEarlierTimestamp(
        patientGroups[patientKey].queue_time,
        appointment.queue_time,
      );
      patientGroups[patientKey].updated_at = pickLaterTimestamp(
        patientGroups[patientKey].updated_at,
        appointment.updated_at || appointment.last_changed_at,
      );
      patientGroups[patientKey].last_changed_at = pickLaterTimestamp(
        patientGroups[patientKey].last_changed_at,
        appointment.last_changed_at || appointment.updated_at,
      );

      if (Array.isArray(appointment.queue_numbers)) {
        const existingQueueIds = new Set(
          (patientGroups[patientKey].queue_numbers || []).map((qn: Record<string, unknown>) => qn.id?.toString() || `${qn.queue_tag}_${qn.service_id}`),
        );

        appointment.queue_numbers.forEach((qn: Record<string, unknown>) => {
          const queueId = qn.id?.toString() || `${qn.queue_tag}_${qn.service_id}`;
          if (!existingQueueIds.has(queueId)) {
            patientGroups[patientKey].queue_numbers.push(qn);
            existingQueueIds.add(queueId);
          }
        });
      }

      const isQRSource = (src: unknown): boolean => src === 'online';
      const currentIsQR = isQRSource(appointment.source);
      const aggregatedIsQR = isQRSource(patientGroups[patientKey].source);

      if (currentIsQR && !aggregatedIsQR) {
        patientGroups[patientKey].source = appointment.source;
        patientGroups[patientKey].record_type = appointment.record_type || patientGroups[patientKey].record_type;
      }
    }

    patientGroups[patientKey].cost += appointmentCost;
    patientGroups[patientKey].grouped_discount_modes.push(normalizedDiscountMode);
    patientGroups[patientKey].grouped_payment_statuses.push(normalizedPayment);
    if (appointment.payment_type) {
      patientGroups[patientKey].grouped_payment_types.push(appointment.payment_type);
    }
    if (recordRef) {
      const refKey = `${recordRef.record_kind}:${recordRef.record_id}`;
      const existingRefKeys = new Set(
        patientGroups[patientKey].grouped_record_refs.map((ref: Record<string, unknown>) => `${ref.record_kind}:${ref.record_id}`),
      );
      if (!existingRefKeys.has(refKey)) {
        patientGroups[patientKey].grouped_record_refs.push(recordRef);
      }
    }
    patientGroups[patientKey].grouped_records.push({
      record_ref: recordRef,
      available_actions: Array.isArray(appointment.available_actions) ? [...appointment.available_actions] : [],
      can_mark_paid: Boolean(appointment.can_mark_paid),
      can_start_visit: Boolean(appointment.can_start_visit),
      can_cancel: Boolean(appointment.can_cancel),
      can_print_ticket: Boolean(appointment.can_print_ticket),
      can_complete: Boolean(appointment.can_complete),
      discount_mode: normalizedDiscountMode,
      approval_status: appointment.approval_status,
      payment_status: normalizedPayment,
      payment_type: appointment.payment_type || null,
      cost: appointmentCost,
    });

    if (Array.isArray(appointment.services)) {
      appointment.services.forEach((service) => {
        if (!patientGroups[patientKey].services.includes(service)) {
          patientGroups[patientKey].services.push(service);
        }
      });
    }

    if (Array.isArray(appointment.service_codes)) {
      if (!patientGroups[patientKey].service_codes) {
        patientGroups[patientKey].service_codes = [];
      }
      appointment.service_codes.forEach((code) => {
        if (!patientGroups[patientKey].service_codes.includes(code)) {
          patientGroups[patientKey].service_codes.push(code);
        }
      });
    }

    if (Array.isArray(appointment.service_details)) {
      if (!patientGroups[patientKey].service_details) {
        patientGroups[patientKey].service_details = [];
      }
      const existingServiceDetailKeys = new Set(
        patientGroups[patientKey].service_details.map((serviceDetail: Record<string, unknown>) => (
          serviceDetail?.service_id ??
          serviceDetail?.id ??
          serviceDetail?.service_code ??
          serviceDetail?.code ??
          serviceDetail?.service_name ??
          serviceDetail?.name
        )).filter((value: unknown) => value !== null && value !== undefined).map(String),
      );

      appointment.service_details.forEach((serviceDetail: Record<string, unknown>) => {
        if (!serviceDetail) return;
        const serviceDetailKey = serviceDetail.service_id ??
          serviceDetail.id ??
          serviceDetail.service_code ??
          serviceDetail.code ??
          serviceDetail.service_name ??
          serviceDetail.name ??
          null;
        if (serviceDetailKey === null || serviceDetailKey === undefined || existingServiceDetailKeys.has(String(serviceDetailKey))) {
          return;
        }
        patientGroups[patientKey].service_details.push(serviceDetail);
        existingServiceDetailKeys.add(String(serviceDetailKey));
      });
    }

    if (appointment.department) {
      patientGroups[patientKey].departments.add(appointment.department);
    }

    if (appointment.doctor_specialty) {
      patientGroups[patientKey].doctors.add(appointment.doctor_specialty);
    }
  });

  return Object.values(patientGroups).map((group): Record<string, unknown> => {
    // audit/phase-6, BS-60: strip the Set index fields before returning —
    // external consumers expect the array shape, not the Sets.
    const groupRecord = group as Record<string, unknown>;
    const {
      visit_ids_set: _visitIdsSet,
      appointment_ids_set: _apptIdsSet,
      queue_entry_ids_set: _queueIdsSet,
      aggregated_ids_set: _aggIdsSet,
      ...groupPublic
    } = groupRecord;
    void _visitIdsSet; void _apptIdsSet; void _queueIdsSet; void _aggIdsSet;

    const records: unknown[] = Array.isArray(group.grouped_records) ? group.grouped_records as unknown[] : [];
    const groupedDiscountModes: unknown[] = Array.isArray(group.grouped_discount_modes) ? group.grouped_discount_modes as unknown[] : [];
    const uniqueRegistrationModes = [...new Set(groupedDiscountModes.filter(Boolean))];
    const groupedPaymentStatuses: unknown[] = Array.isArray(group.grouped_payment_statuses) ? group.grouped_payment_statuses as unknown[] : [];
    const uniquePaymentStatuses = [...new Set(groupedPaymentStatuses.filter(Boolean))];
    const groupedPaymentTypes: unknown[] = Array.isArray(group.grouped_payment_types) ? group.grouped_payment_types as unknown[] : [];
    const uniquePaymentTypes = [...new Set(groupedPaymentTypes.filter(Boolean))];

    const allApprovedZeroCostRegistrations = records.length > 0 && (records as Record<string, unknown>[]).every((record: Record<string, unknown>) => (
      Number(record.cost) <= 0 &&
      (
        record.discount_mode === 'repeat' ||
        record.discount_mode === 'benefit' ||
        (record.discount_mode === 'all_free' && record.approval_status === 'approved')
      )
    ));

    const allPendingAllFree = records.length > 0 && (records as Record<string, unknown>[]).every(
      (record: Record<string, unknown>) => record.discount_mode === 'all_free' && record.approval_status !== 'approved',
    );
    const allPaid = records.length > 0 && (records as Record<string, unknown>[]).every((record: Record<string, unknown>) => record.payment_status === 'paid');
    const allUnpaidMonetary = records.length > 0 && (records as Record<string, unknown>[]).every((record: Record<string, unknown>) => (
      Number(record.cost) > 0 &&
      record.payment_status !== 'paid' &&
      record.discount_mode !== 'all_free'
    ));
    const hasMixedPaymentState = uniquePaymentStatuses.length > 1;
    const hasMixedPaymentMethod = uniquePaymentTypes.length > 1;

    let aggregatePaymentType: string | null = null;
    if (allPendingAllFree) {
      aggregatePaymentType = 'approval_pending';
    } else if (allApprovedZeroCostRegistrations && Number(group.cost as number | string) <= 0) {
      aggregatePaymentType = 'free';
    } else if (hasMixedPaymentState || hasMixedPaymentMethod) {
      aggregatePaymentType = 'mixed_payment';
    } else if (allPaid && uniquePaymentTypes.length === 1) {
      aggregatePaymentType = String(uniquePaymentTypes[0] ?? 'unknown');
    } else if (allPaid) {
      aggregatePaymentType = 'unknown_payment';
    } else if (allUnpaidMonetary) {
      aggregatePaymentType = 'pending_payment';
    } else {
      aggregatePaymentType = 'mixed_payment';
    }

    return {
      ...groupPublic,
      visit_type: uniqueRegistrationModes.length === 1 ? group.visit_type : 'mixed',
      discount_mode: uniqueRegistrationModes.length === 1 ? uniqueRegistrationModes[0] : 'mixed',
      payment_type: aggregatePaymentType,
      payment_status: uniquePaymentStatuses.length === 1 ? uniquePaymentStatuses[0] : 'mixed',
      cost: Number(group.cost as number | string | undefined || 0),
      cost_display: Number(group.cost as number | string | undefined || 0) <= 0 ? 'free' : null,
    };
  });
};
