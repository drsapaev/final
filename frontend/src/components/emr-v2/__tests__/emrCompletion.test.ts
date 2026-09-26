import { describe, expect, it, vi } from 'vitest';
import { emrTextValue, readSavedEMRForCompletion } from '../emrCompletion';

const emrRecord = (
  data: Record<string, unknown> = {},
  status = 'in_progress',
) => ({ id: 17, status, data });

describe('readSavedEMRForCompletion', () => {
  it('saves a dirty draft, then returns the freshly re-read EMR data', async () => {
    const events: string[] = [];
    const result = await readSavedEMRForCompletion({
      shouldSave: true,
      save: vi.fn(async () => {
        events.push('save');
        return emrRecord({ complaints: 'local draft' });
      }),
      reload: vi.fn(async () => {
        events.push('reload');
        return emrRecord({ complaints: 'saved server value', diagnosis: 'saved diagnosis' });
      }),
    });

    expect(events).toEqual(['save', 'reload']);
    expect(result).toEqual({ complaints: 'saved server value', diagnosis: 'saved diagnosis' });
  });

  it('re-reads an existing clean record without sending another save', async () => {
    const save = vi.fn();
    const result = await readSavedEMRForCompletion({
      shouldSave: false,
      save,
      reload: async () => emrRecord({ diagnosis: 'saved diagnosis' }),
    });

    expect(save).not.toHaveBeenCalled();
    expect(result).toEqual({ diagnosis: 'saved diagnosis' });
  });

  it.each([
    [{ ...emrRecord({ diagnosis: 'draft diagnosis' }), status: 'draft' }],
    [{ ...emrRecord({ diagnosis: 'unknown status' }), status: undefined }],
  ])('blocks completion unless the server re-read is non-draft EMR', async (latestEMR) => {
    await expect(readSavedEMRForCompletion({
      shouldSave: false,
      save: vi.fn(),
      reload: async () => latestEMR,
    })).rejects.toMatchObject({ reason: 'not_ready' });
  });

  it.each([
    [{ conflict: true }, 'conflict'],
    [{ accessDenied: true }, 'access_denied'],
    [undefined, 'save_failed'],
    [{ id: 17 }, 'save_failed'],
  ] as const)('blocks completion when save result is %j', async (saveResult, reason) => {
    const reload = vi.fn();
    await expect(readSavedEMRForCompletion({
      shouldSave: true,
      save: async () => saveResult,
      reload,
    })).rejects.toMatchObject({ reason });
    expect(reload).not.toHaveBeenCalled();
  });

  it('blocks completion after a save request throws', async () => {
    const reload = vi.fn();
    await expect(readSavedEMRForCompletion({
      shouldSave: true,
      save: async () => { throw new Error('request failed'); },
      reload,
    })).rejects.toMatchObject({ reason: 'save_failed' });
    expect(reload).not.toHaveBeenCalled();
  });

  it.each([
    [null, 'read_failed'],
    [{ accessDenied: true }, 'access_denied'],
    [{ id: 17, data: null }, 'read_failed'],
    [{ data: { complaints: 'not persisted' } }, 'read_failed'],
  ] as const)('blocks completion when the re-read response is %j', async (latestEMR, reason) => {
    await expect(readSavedEMRForCompletion({
      shouldSave: false,
      save: vi.fn(),
      reload: async () => latestEMR,
    })).rejects.toMatchObject({ reason });
  });
});

describe('emrTextValue', () => {
  it('accepts plain text and legacy text-shaped fields without stringifying objects', () => {
    expect(emrTextValue('complaints')).toBe('complaints');
    expect(emrTextValue({ text: 'diagnosis' })).toBe('diagnosis');
    expect(emrTextValue({ main: 'legacy diagnosis', icd10_code: 'I10' })).toBe('legacy diagnosis');
    expect(emrTextValue({ label: 'not clinical text' })).toBe('');
  });
});
