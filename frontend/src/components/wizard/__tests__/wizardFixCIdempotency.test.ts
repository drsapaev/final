/**
 * Fix C — the cart submission carries an Idempotency-Key so a retried
 * request after a lost response cannot create a second cart (server-side
 * idempotency middleware dedupes by that key).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn().mockResolvedValue({ data: { success: true } }),
}));

vi.mock('../../../api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: postMock,
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
  buildApiUrl: (p: string) => `http://test${p}`,
  buildWsUrl: (p: string) => `ws://test${p}`,
  default: {},
}));

import { createRegistrarCart } from '../../../api/patients';

beforeEach(() => {
  postMock.mockClear();
});

describe('Fix C: cart submission idempotency header', () => {
  it('sends the Idempotency-Key header when a key is provided', async () => {
    await createRegistrarCart({ patient_id: 1, visits: [] }, 'test-key-123');
    expect(postMock).toHaveBeenCalledTimes(1);
    const [, , config] = postMock.mock.calls[0];
    expect(config?.headers?.['Idempotency-Key']).toBe('test-key-123');
  });

  it('works without a key (opt-in contract preserved)', async () => {
    await createRegistrarCart({ patient_id: 1, visits: [] });
    const [, , config] = postMock.mock.calls[0];
    expect(config).toBeUndefined();
  });
});
