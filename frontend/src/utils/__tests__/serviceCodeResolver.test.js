import { describe, expect, it } from 'vitest';

import { normalizeServicesFromInitialData } from '../serviceCodeResolver';

describe('normalizeServicesFromInitialData', () => {
  it('uses explicit queue_entry_id instead of DailyQueue identifiers for edit cancellation', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        service_details: [
          {
            id: 5,
            code: 'K01',
            name: 'Cardiology consult',
          },
        ],
        queue_numbers: [
          {
            id: 31,
            queue_id: 31,
            queue_entry_id: 9001,
            service_id: 5,
            service_code: 'K01',
            service_name: 'Cardiology consult',
          },
        ],
      },
      [{ id: 5, service_code: 'K01', name: 'Cardiology consult' }],
    );

    expect(item.original_queue_id).toBe(9001);
  });

  it('does not treat a bare queue_id as an OnlineQueueEntry id', () => {
    const [item] = normalizeServicesFromInitialData(
      {
        service_details: [
          {
            id: 7,
            code: 'D01',
            name: 'Dermatology consult',
          },
        ],
        queue_numbers: [
          {
            id: 44,
            queue_id: 44,
            service_id: 7,
            service_code: 'D01',
            service_name: 'Dermatology consult',
          },
        ],
      },
      [{ id: 7, service_code: 'D01', name: 'Dermatology consult' }],
    );

    expect(item.original_queue_id).toBeNull();
  });
});
