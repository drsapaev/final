export const DENTIST_DOCUMENTS_STORAGE_KEY = 'dentist_panel_documents_v1';

export function getDefaultDentistDocuments() {
  return {
    visitProtocols: [],
  };
}

export function parseDentistDocuments(rawValue) {
  if (!rawValue) {
    return getDefaultDentistDocuments();
  }

  try {
    const parsed = typeof rawValue === 'string' ? JSON.parse(rawValue) : rawValue;
    return {
      visitProtocols: Array.isArray(parsed?.visitProtocols) ? parsed.visitProtocols : [],
    };
  } catch {
    return getDefaultDentistDocuments();
  }
}

export function upsertDentistVisitProtocol(records, record, maxItems = 20) {
  if (!record?.visit_id) {
    return Array.isArray(records) ? records : [];
  }

  const currentRecords = Array.isArray(records) ? records : [];
  return [record, ...currentRecords.filter((item) => item.visit_id !== record.visit_id)].slice(0, maxItems);
}
