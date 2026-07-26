function cloneValue(value: unknown): Record<string, unknown> {
  if (value == null || typeof value !== 'object') {
    if (value == null) return {};
    return value as Record<string, unknown>;
  }

  if (typeof structuredClone === 'function') {
    return structuredClone(value) as Record<string, unknown>;
  }

  return JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
}

function resolvePatientId(patient: Record<string, unknown> | null | undefined): string | number | null {
  const inner = patient?.patient as Record<string, unknown> | undefined;
  return (
    (inner?.id as string | number | undefined) ||
    (patient?.patient_id as string | number | undefined) ||
    (patient?.id as string | number | undefined) ||
    null
  );
}

function resolvePatientName(patient: Record<string, unknown> | null | undefined): string {
  return (
    (patient?.patient_name as string | undefined) ||
    (patient?.patient_fio as string | undefined) ||
    (patient?.name as string | undefined) ||
    'Пациент'
  );
}

function resolveSavedAt(visitData: Record<string, unknown> | null | undefined, fallback: unknown = null): string {
  return (
    (visitData?.saved_at as string | undefined) ||
    (visitData?.updatedAt as string | undefined) ||
    (visitData?.createdAt as string | undefined) ||
    (fallback as string | undefined) ||
    new Date().toISOString()
  );
}

export function buildDentistVisitProtocolData(patient: unknown, visitData: Record<string, unknown>, options: Record<string, unknown> = {}): Record<string, unknown> {
  const source = options.source || 'local_cache';
  const protocolData = cloneValue(visitData);
  const patientRecord = patient && typeof patient === 'object'
    ? patient as Record<string, unknown>
    : null;
  const patientId = resolvePatientId(patientRecord);
  const patientName = resolvePatientName(patientRecord);
  const visitId = options.visitId || (patient as { visit_id?: unknown })?.visit_id || protocolData.visit_id || null;
  const savedAt = resolveSavedAt(protocolData, options.savedAt);

  protocolData.patient_id = patientId;
  protocolData.patient_name = patientName;
  protocolData.visit_id = visitId;
  protocolData.saved_at = savedAt;
  protocolData.source = source;
  protocolData.updatedAt = protocolData.updatedAt || savedAt;

  return protocolData;
}

export function buildDentistVisitProtocolCard(patient: unknown, visitData: Record<string, unknown>, options: Record<string, unknown> = {}): Record<string, unknown> {
  const protocolData = buildDentistVisitProtocolData(patient, visitData, options);

  return {
    visit_id: protocolData.visit_id,
    patient_id: protocolData.patient_id,
    patient_name: protocolData.patient_name,
    saved_at: protocolData.saved_at,
    visitData: protocolData,
    source: options.source || protocolData.source || 'local_cache',
    emr_id: options.emr_id ?? null,
    emr_version: options.emr_version ?? null,
    emr_status: options.emr_status ?? null,
  };
}

export function buildDentistVisitProtocolEmrPayload(patient: unknown, visitData: Record<string, unknown>): Record<string, unknown> {
  const protocolData = buildDentistVisitProtocolData(patient, visitData, {
    source: 'emr_v2',
  });

  return {
    specialty: 'dentistry',
    specialty_data: {
      visit_protocol: protocolData,
    },
    visit_protocol: protocolData,
    complaints: protocolData.chiefComplaint || '',
    anamnesis_morbi: protocolData.historyOfPresentIllness || '',
    recommendations: protocolData.recommendations || '',
    notes: protocolData.recommendations || '',
    procedures: Array.isArray(protocolData.procedures) ? protocolData.procedures : [],
    prescriptions: Array.isArray(protocolData.prescriptions)
      ? protocolData.prescriptions
      : [],
  };
}

export function buildDentistVisitProtocolSaveRequest(patient: unknown, visitData: Record<string, unknown>, options: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    data: buildDentistVisitProtocolEmrPayload(patient, visitData),
    row_version: options.rowVersion ?? 0,
    client_session_id: options.clientSessionId ?? null,
    is_draft: options.isDraft ?? true,
  };
}

export function extractDentistVisitProtocolFromEmr(emrRecord: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  const data = emrRecord?.data;
  if (!data || typeof data !== 'object') {
    return null;
  }

  const dataRecord = data as Record<string, unknown>;
  const specialtyData = dataRecord.specialty_data;
  const specialtyDataRecord = specialtyData && typeof specialtyData === 'object'
    ? specialtyData as Record<string, unknown>
    : null;
  const protocol = dataRecord.visit_protocol || specialtyDataRecord?.visit_protocol;
  if (!protocol || typeof protocol !== 'object') {
    return null;
  }

  return cloneValue(protocol);
}

export function mapDentistVisitProtocolFromEmr(emrRecord: Record<string, unknown> | null | undefined, fallbackPatient: Record<string, unknown> | null = null): Record<string, unknown> | null {
  const protocolData = extractDentistVisitProtocolFromEmr(emrRecord);
  if (!protocolData) {
    return null;
  }

  const patient: Record<string, unknown> = fallbackPatient || {
    patient_id: emrRecord?.patient_id,
    patient_name: emrRecord?.patient_name,
    visit_id: emrRecord?.visit_id,
  };

  return buildDentistVisitProtocolCard(patient, protocolData, {
    source: 'emr_v2',
    savedAt:
      emrRecord?.updated_at ||
      emrRecord?.signed_at ||
      emrRecord?.created_at ||
      protocolData.saved_at,
    visitId: emrRecord?.visit_id || protocolData.visit_id || resolvePatientId(patient),
    emr_id: emrRecord?.id ?? null,
    emr_version: emrRecord?.version ?? null,
    emr_status: emrRecord?.status ?? null,
  });
}

export function mergeDentistVisitProtocolCards(records: ReadonlyArray<Record<string, unknown>> | null | undefined, incomingRecords: ReadonlyArray<Record<string, unknown>> | null | undefined, maxItems: number = 20): Record<string, unknown>[] {
  const currentRecords: Record<string, unknown>[] = Array.isArray(records) ? records as Record<string, unknown>[] : [];
  const incoming: Record<string, unknown>[] = Array.isArray(incomingRecords) ? incomingRecords as Record<string, unknown>[] : [];
  const merged = [...incoming, ...currentRecords];
  const seenVisitIds = new Set<unknown>();
  const result: Record<string, unknown>[] = [];

  for (const record of merged) {
    const visitId = record?.visit_id;
    if (!visitId || seenVisitIds.has(visitId)) {
      continue;
    }

    seenVisitIds.add(visitId);
    result.push(record);

    if (result.length >= maxItems) {
      break;
    }
  }

  return result;
}
