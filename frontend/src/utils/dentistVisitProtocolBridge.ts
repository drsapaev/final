function cloneValue(value) {
  if (value == null || typeof value !== 'object') {
    return value ?? {};
  }

  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }

  return JSON.parse(JSON.stringify(value));
}

function resolvePatientId(patient) {
  return patient?.patient?.id || patient?.patient_id || patient?.id || null;
}

function resolvePatientName(patient) {
  return patient?.patient_name || patient?.patient_fio || patient?.name || 'Пациент';
}

function resolveSavedAt(visitData, fallback = null) {
  return (
    visitData?.saved_at ||
    visitData?.updatedAt ||
    visitData?.createdAt ||
    fallback ||
    new Date().toISOString()
  );
}

export function buildDentistVisitProtocolData(patient: unknown, visitData: Record<string, unknown>, options: Record<string, unknown> = {}): Record<string, unknown> {
  const source = options.source || 'local_cache';
  const protocolData = cloneValue(visitData);
  const patientId = resolvePatientId(patient);
  const patientName = resolvePatientName(patient);
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

export function buildDentistVisitProtocolEmrPayload(patient, visitData) {
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

export function extractDentistVisitProtocolFromEmr(emrRecord) {
  const data = emrRecord?.data;
  if (!data || typeof data !== 'object') {
    return null;
  }

  const protocol = data.visit_protocol || data.specialty_data?.visit_protocol;
  if (!protocol || typeof protocol !== 'object') {
    return null;
  }

  return cloneValue(protocol);
}

export function mapDentistVisitProtocolFromEmr(emrRecord, fallbackPatient = null) {
  const protocolData = extractDentistVisitProtocolFromEmr(emrRecord);
  if (!protocolData) {
    return null;
  }

  const patient = fallbackPatient || {
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

export function mergeDentistVisitProtocolCards(records, incomingRecords, maxItems = 20) {
  const currentRecords = Array.isArray(records) ? records : [];
  const incoming = Array.isArray(incomingRecords) ? incomingRecords : [];
  const merged = [...incoming, ...currentRecords];
  const seenVisitIds = new Set();
  const result = [];

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
