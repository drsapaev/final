/**
 * RETRO-3953-01 (post-merge review PR 3958, dossier of merged PR 3953) — fail-first.
 *
 * P1: changing the authenticated principal while the SAME hook instance stays
 * mounted kept the previous doctor's personal clinical phrases in the render
 * state until the new principal's GET resolved (or failed). The module cache
 * was already principal-scoped (EMRTMPL-FE-001, audit 3886 round 23), but the
 * per-hook `templates` state was initialized once and never reset on an owner
 * swap, so doctor B could see doctor A's phrases during B's pending or denied
 * load.
 *
 * Required evidence (audit): one hook mounted as doctor A; principal swaps to
 * B while mounted; A's phrase must be absent immediately, before B's GET
 * resolves; after B's denial A's data never reappears and the failure is
 * surfaced; a late A-context response neither commits nor repopulates the
 * cleared cache.
 */
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}));

const authState = vi.hoisted(() => ({ profile: { id: 1 } as { id: number } | null }));

vi.mock('../../api/client', () => ({
  default: {
    get: apiMocks.get,
    post: apiMocks.post,
    put: apiMocks.put,
    delete: apiMocks.delete,
  },
}));

vi.mock('../../stores/auth', () => ({
  getState: () => ({ profile: authState.profile }),
}));

import apiClient from '../../api/client';
import { useDoctorSectionTemplates } from '../useDoctorSectionTemplates';

const apiGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;

function tmpl(id: number, text: string): Record<string, unknown> {
  return { id, template_text: text, icd10_code: null, is_pinned: false };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const flush = () => new Promise<void>((r) => setTimeout(r, 0));

function renderTemplatesHook(props: { section?: string; icd10Code?: string | null }) {
  return renderHook(
    (next: { section?: string; icd10Code?: string | null }) =>
      useDoctorSectionTemplates({ section: next.section, icd10Code: next.icd10Code }),
    { initialProps: props },
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.profile = { id: 1 };
});

describe('RETRO-3953-01: principal swap on a still-mounted hook', () => {
  it('drops A\u2019s phrases the moment the principal changes, before B\u2019s GET resolves', async () => {
    // Doctor A loads their personal treatment templates.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Фраза врача А')] } });
    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: null });
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Фраза врача А');
    });

    // Principal swaps to B while the SAME hook stays mounted; B's GET is deferred.
    const gateB = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateB.promise);
    authState.profile = { id: 2 };
    act(() => {
      utils.rerender({ section: 'treatment', icd10Code: null });
    });

    // Immediately: A's phrase must be gone from the render state — before B's
    // request resolves, with no Apply/Edit-capable list on screen.
    expect(utils.result.current.templates).toHaveLength(0);
    expect(utils.result.current.hasTemplates).toBe(false);

    // B's authorized GET resolves: only B's phrases render.
    await act(async () => {
      gateB.resolve({ data: { templates: [tmpl(2, 'Фраза врача Б')] } });
      await flush();
    });
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Фраза врача Б');
    });
    expect((utils.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Фраза врача А',
    )).toBe(false);
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('a denied B GET surfaces the failure and A\u2019s data never reappears', async () => {
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Фраза врача А')] } });
    const utils = renderTemplatesHook({ section: 'complaints', icd10Code: null });
    await waitFor(() => {
      expect(utils.result.current.hasTemplates).toBe(true);
    });

    const gateB = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateB.promise);
    authState.profile = { id: 2 };
    act(() => {
      utils.rerender({ section: 'complaints', icd10Code: null });
    });

    // While B's (about-to-fail) request is pending, A's phrase is already gone.
    expect(utils.result.current.templates).toHaveLength(0);

    // B is denied (403): the failure is surfaced, A's data never reappears.
    await act(async () => {
      gateB.reject({ message: '403 Forbidden' });
      await flush();
    });
    await waitFor(() => {
      expect(utils.result.current.error).not.toBeNull();
    });
    expect(utils.result.current.templates).toHaveLength(0);
    expect((utils.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Фраза врача А',
    )).toBe(false);
    expect(utils.result.current.hasTemplates).toBe(false);
  });

  it('a late A-context response after the swap neither commits nor repopulates the cleared cache', async () => {
    // A's GET is deferred and never resolved before the swap.
    const gateA = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateA.promise);
    const utils = renderTemplatesHook({ section: 'examination', icd10Code: null });

    // Principal swaps to B while A's GET is still pending; B loads normally.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(2, 'Осмотр врача Б')] } });
    authState.profile = { id: 2 };
    act(() => {
      utils.rerender({ section: 'examination', icd10Code: null });
    });
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Осмотр врача Б');
    });

    // A's stale response arrives LAST — it must not commit through the epoch
    // guard and must not write an A-keyed entry back into the cleared cache.
    await act(async () => {
      gateA.resolve({ data: { templates: [tmpl(1, 'Фраза врача А')] } });
      await flush();
    });
    expect((utils.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Фраза врача А',
    )).toBe(false);

    // Back to doctor A: a FRESH authorized GET must fire — the late A response
    // may not have been parked in the cache during B's ownership.
    authState.profile = { id: 1 };
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(5, 'Свежая фраза врача А')] } });
    const second = renderTemplatesHook({ section: 'examination', icd10Code: null });
    await waitFor(() => {
      expect((second.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Свежая фраза врача А');
    });
    expect(apiGet).toHaveBeenCalledTimes(3);
    second.unmount();
  });
});
