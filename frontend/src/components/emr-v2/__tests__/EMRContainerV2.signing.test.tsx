import { describe, expect, it, vi } from 'vitest';
import { persistAndSignEMR, persistEMRAndRefresh } from '../EMRContainerV2';

describe('EMRContainerV2 save and sign flow', () => {
  it('refreshes the parent after a successful manual save', async () => {
    const refresh = vi.fn();
    const save = vi.fn(async () => ({ status: 'in_progress', row_version: 3 }));

    await persistEMRAndRefresh(save, refresh, { isDraft: false });

    expect(save).toHaveBeenCalledWith({ isDraft: false });
    expect(refresh).toHaveBeenCalledOnce();
  });

  it.each([
    ['a conflict', { conflict: true }],
    ['an access denial', { accessDenied: true }],
    ['a failed write', { success: false }],
  ])('does not refresh after %s', async (_caseName, result) => {
    const refresh = vi.fn();

    await persistEMRAndRefresh(async () => result, refresh);

    expect(refresh).not.toHaveBeenCalled();
  });

  it('keeps a successful save successful when the parent refresh fails', async () => {
    const saveResult = { status: 'draft', row_version: 4 };
    const result = await persistEMRAndRefresh(
      async () => saveResult,
      async () => { throw new Error('refresh failed'); },
    );

    expect(result).toBe(saveResult);
  });

  it('does not save or sign when confirmation is cancelled', async () => {
    const save = vi.fn();
    const sign = vi.fn();

    const result = await persistAndSignEMR({
      confirm: async () => false,
      save,
      sign,
    });

    expect(result).toBe('cancelled');
    expect(save).not.toHaveBeenCalled();
    expect(sign).not.toHaveBeenCalled();
  });

  it.each([
    ['a conflict', { conflict: true, row_version: 4, status: 'in_progress' }],
    ['access denial', { accessDenied: true, row_version: 4, status: 'in_progress' }],
    ['a draft response', { row_version: 4, status: 'draft' }],
    ['a response without a version', { status: 'in_progress' }],
  ])('stops before signing when save returns %s', async (_caseName, saveResult) => {
    const sign = vi.fn();

    const result = await persistAndSignEMR({
      confirm: async () => true,
      save: async () => saveResult,
      sign,
    });

    expect(result).toBe('save_failed');
    expect(sign).not.toHaveBeenCalled();
  });

  it('stops before signing when save throws', async () => {
    const sign = vi.fn();

    const result = await persistAndSignEMR({
      confirm: async () => true,
      save: async () => {
        throw new Error('save failed');
      },
      sign,
    });

    expect(result).toBe('save_failed');
    expect(sign).not.toHaveBeenCalled();
  });

  it('signs only after save and uses the returned row version', async () => {
    const calls: string[] = [];
    const refresh = vi.fn(async () => { calls.push('refresh'); });
    const save = vi.fn(async () => {
      calls.push('save');
      return { row_version: 7, status: 'in_progress' };
    });
    const sign = vi.fn(async () => {
      calls.push('sign');
      return { row_version: 8, status: 'signed' };
    });

    const result = await persistAndSignEMR({
      confirm: async () => true,
      save,
      sign,
      onPersisted: refresh,
    });

    expect(result).toBe('sign_attempted');
    expect(calls).toEqual(['save', 'sign', 'refresh']);
    expect(refresh).toHaveBeenCalledOnce();
    expect(save).toHaveBeenCalledWith({ isDraft: false });
    expect(sign).toHaveBeenCalledWith({ rowVersion: 7 });
  });

  it('reports a signing conflict after a successful save', async () => {
    const sign = vi.fn(async () => ({ conflict: true }));
    const refresh = vi.fn();

    const result = await persistAndSignEMR({
      confirm: async () => true,
      save: async () => ({ row_version: 7, status: 'in_progress' }),
      sign,
      onPersisted: refresh,
    });

    expect(result).toBe('sign_failed');
    expect(sign).toHaveBeenCalledWith({ rowVersion: 7 });
    expect(refresh).toHaveBeenCalledOnce();
  });

  it('does not refresh when save-and-sign is cancelled or the save fails', async () => {
    const refresh = vi.fn();

    await persistAndSignEMR({
      confirm: async () => false,
      save: async () => ({ row_version: 7, status: 'in_progress' }),
      sign: async () => ({ status: 'signed' }),
      onPersisted: refresh,
    });
    await persistAndSignEMR({
      confirm: async () => true,
      save: async () => ({ conflict: true }),
      sign: async () => ({ status: 'signed' }),
      onPersisted: refresh,
    });

    expect(refresh).not.toHaveBeenCalled();
  });
});
