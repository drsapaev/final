import { describe, expect, it } from 'vitest';

import { selectEntriesForSpecialist } from '../cardiologyQueue';

describe('selectEntriesForSpecialist', () => {
  it('selects entries only from queues owned by the current Doctor.id', () => {
    const result = selectEntriesForSpecialist(
      {
        queues: [
          { specialist_id: 12, specialty: 'cardiology', entries: [{ id: 1, service_codes: ['K01'] }] },
          { specialist_id: 13, specialty: 'cardiology', entries: [{ id: 2, service_codes: ['K02'] }] },
          { specialist_id: 12, specialty: 'ecg', entries: [{ id: 3, service_codes: ['ECG'] }] },
        ],
      },
      '12',
    );

    expect(result.map(({ entry }) => entry.id)).toEqual([1, 3]);
  });

  it('does not infer ownership from specialty or service codes', () => {
    const result = selectEntriesForSpecialist(
      { queues: [{ specialty: 'cardiology', entries: [{ id: 1, service_codes: ['K01'] }] }] },
      12,
    );

    expect(result).toEqual([]);
  });

  it('returns no entries when the current specialist id is unavailable', () => {
    expect(selectEntriesForSpecialist({ queues: [{ specialist_id: 12, entries: [{ id: 1 }] }] }, null)).toEqual([]);
  });
});
