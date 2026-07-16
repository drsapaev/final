import { describe, expect, it } from 'vitest';

import {
  getDefaultDentistDocuments,
  parseDentistDocuments,
  upsertDentistVisitProtocol,
} from '../dentistryDocuments';

describe('dentistryDocuments helpers', () => {
  it('returns defaults for empty or invalid storage payloads', () => {
    expect(parseDentistDocuments(null)).toEqual(getDefaultDentistDocuments());
    expect(parseDentistDocuments('not-json')).toEqual(getDefaultDentistDocuments());
    expect(parseDentistDocuments('{}')).toEqual(getDefaultDentistDocuments());
  });

  it('upserts visit protocols by visit_id and keeps newest first', () => {
    const first = { visit_id: 101, patient_name: 'First' };
    const second = { visit_id: 202, patient_name: 'Second' };
    const updatedFirst = { visit_id: 101, patient_name: 'First Updated' };

    const initial = upsertDentistVisitProtocol([], first);
    const withSecond = upsertDentistVisitProtocol(initial, second);
    const withUpdatedFirst = upsertDentistVisitProtocol(withSecond, updatedFirst);

    expect(withUpdatedFirst).toEqual([updatedFirst, second]);
  });
});
