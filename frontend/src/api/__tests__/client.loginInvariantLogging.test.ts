import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const loggerMock = vi.hoisted(() => ({
  log: vi.fn(),
  warn: vi.fn(),
  info: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
}));

vi.mock('../../utils/logger', () => ({ default: loggerMock }));

import logger from '../../utils/logger';
import { api, login } from '../client';
import { AuthInvariantViolationError } from '../../types/auth-mapper';

describe('login invariant logging', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('logs only the invariant code when the response violates the 2FA contract', async () => {
    const backendResponse = {
      requires_2fa: true,
      pending_2fa_token: 'SYNTHETIC_PENDING_MARKER',
      access_token: 'SYNTHETIC_ACCESS_MARKER',
      refresh_token: null,
    };
    vi.spyOn(api, 'post').mockResolvedValue({ data: backendResponse } as never);

    await expect(login('synthetic-user', 'not-a-secret')).rejects.toBeInstanceOf(
      AuthInvariantViolationError,
    );

    expect(logger.error).toHaveBeenCalledTimes(1);
    expect(logger.error).toHaveBeenCalledWith(
      '[api/client] login() backend violated auth invariant:',
      'AUTH_LAW_2_BLOCKING_2FA',
    );
  });
});
