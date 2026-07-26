export function buildPatientDocumentFields(passportValue: string | null | undefined) {
  const docNumber = typeof passportValue === 'string' ? passportValue.trim() : '';

  if (!docNumber) {
    return {
      doc_number: null,
      doc_type: null
    };
  }

  return {
    doc_number: docNumber,
    doc_type: 'passport'
  };
}
