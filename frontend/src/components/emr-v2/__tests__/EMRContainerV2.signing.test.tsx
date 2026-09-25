import { describe, expect, it, vi } from 'vitest';
import { persistAndSignEMR, signSavedEMR } from '../EMRContainerV2';

describe('EMRContainerV2 save and sign flow', () => {
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
    });

    expect(result).toBe('sign_attempted');
    expect(calls).toEqual(['save', 'sign']);
    expect(save).toHaveBeenCalledWith({ isDraft: false });
    expect(sign).toHaveBeenCalledWith({ rowVersion: 7 });
  });

  it('reports a signing conflict after a successful save', async () => {
    const sign = vi.fn(async () => ({ conflict: true }));

    const result = await persistAndSignEMR({
      confirm: async () => true,
      save: async () => ({ row_version: 7, status: 'in_progress' }),
      sign,
    });

    expect(result).toBe('sign_failed');
    expect(sign).toHaveBeenCalledWith({ rowVersion: 7 });
  });

  it('signs an existing saved EMR by its loaded row version without saving it again', async () => {
    const sign = vi.fn(async () => ({ row_version: 8, status: 'signed' }));

    const result = await signSavedEMR({
      confirm: async () => true,
      rowVersion: 7,
      sign,
    });

    expect(result).toBe('sign_attempted');
    expect(sign).toHaveBeenCalledOnce();
    expect(sign).toHaveBeenCalledWith({ rowVersion: 7 });
  });

  it('does not sign a completed visit EMR when its saved version is unavailable', async () => {
    const sign = vi.fn();

    const result = await signSavedEMR({
      confirm: async () => true,
      rowVersion: null,
      sign,
    });

    expect(result).toBe('sign_failed');
    expect(sign).not.toHaveBeenCalled();
  });
});
