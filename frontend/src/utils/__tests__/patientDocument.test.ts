import { describe, expect, it } from 'vitest';

import { buildPatientDocumentFields } from '../patientDocument';

describe('patientDocument helpers', () => {
  it('returns null document fields when passport input is empty', () => {
    expect(buildPatientDocumentFields('')).toEqual({
      doc_number: null,
      doc_type: null
    });

    expect(buildPatientDocumentFields('   ')).toEqual({
      doc_number: null,
      doc_type: null
    });
  });

  it('maps a filled passport field to the backend document pair', () => {
    expect(buildPatientDocumentFields('  AA1234567  ')).toEqual({
      doc_number: 'AA1234567',
      doc_type: 'passport'
    });
  });
});
