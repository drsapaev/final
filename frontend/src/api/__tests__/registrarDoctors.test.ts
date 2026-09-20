import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '../client';
import { fetchRegistrarDoctors } from '../registrar';

const apiMock = api as unknown as {
  get: ReturnType<typeof vi.fn>;
};

describe('fetchRegistrarDoctors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps envelope metadata while exposing only normalized doctor rows', async () => {
    apiMock.get.mockResolvedValueOnce({
      data: {
        doctors: [
          {
            id: 17,
            user_id: 31,
            specialty: 'dermatology',
            cabinet: '204',
            price_default: '50000',
            active: true,
          },
        ],
        total_doctors: 1,
        by_specialty: { dermatology: 1 },
      },
    });

    const result = await fetchRegistrarDoctors();

    expect(apiMock.get).toHaveBeenCalledWith('/registrar/doctors');
    expect(result.total_doctors).toBe(1);
    expect(result.by_specialty).toEqual({ dermatology: 1 });
    expect(result.doctors).toEqual([
      expect.objectContaining({
        id: 17,
        specialty: 'dermatology',
        cabinet: '204',
        price_default: 50000,
        is_active: true,
      }),
    ]);
  });

  it('does not turn envelope counters or grouping dictionaries into doctors', async () => {
    apiMock.get.mockResolvedValueOnce({
      data: {
        doctors: [],
        total_doctors: 3,
        by_specialty: { cardiology: 2, dermatology: 1 },
      },
    });

    const result = await fetchRegistrarDoctors();

    expect(result.doctors).toEqual([]);
  });
});
