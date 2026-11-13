/**
 * RETRO-3953-02/03/04 (post-merge review PR 3958, dossier of merged PR 3953) — fail-first.
 *
 * - RETRO-3953-02 (P2): an in-place section/ICD change kept the previous
 *   context's phrases rendered and actionable while the new context's request
 *   was pending; a section that became falsy returned early and NEVER cleared
 *   the displayed list (nor invalidated the pending request's epoch, so the
 *   late response could repopulate a list for a context that no longer
 *   exists).
 * - RETRO-3953-03 (P2): `forceRefresh` explicitly joined a stale pre-mutation
 *   in-flight GET, so after a successful template PUT the "forced" refresh
 *   rendered the OLD text while the edit modal reported success.
 * - RETRO-3953-04 (P2): the originating hook caught a failed shared GET and
 *   resolved the shared promise with `[]`; a joining subscriber consumed the
 *   resolved empty list, cleared its error and presented the failure as an
 *   honest-looking "no clinical templates" success.
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
const apiPut = apiClient.put as unknown as ReturnType<typeof vi.fn>;

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

describe('RETRO-3953-02: context transitions invalidate the displayed list', () => {
  it('I10\u2019s phrases are not rendered or actionable while the I20 request is pending', async () => {
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(10, 'Лечение по I10')] } });
    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Лечение по I10');
    });

    // Switch the diagnosis; the I20 GET is deferred.
    const gateI20 = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateI20.promise);
    act(() => {
      utils.rerender({ section: 'treatment', icd10Code: 'I20' });
    });

    // Immediately: the previous diagnosis's phrases must be gone from the
    // render state — not still displayed while the new request is pending.
    expect(utils.result.current.templates).toHaveLength(0);
    expect(utils.result.current.hasTemplates).toBe(false);
    expect(utils.result.current.loading).toBe(true);

    // I20 resolves: only I20's phrases render.
    await act(async () => {
      gateI20.resolve({ data: { templates: [tmpl(20, 'Лечение по I20')] } });
      await flush();
    });
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Лечение по I20');
    });
    expect((utils.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Лечение по I10',
    )).toBe(false);
    // Exactly two GETs were issued (I10 mount + I20 switch) — a queued-but-
    // unconsumed mock here would poison the NEXT test's request mocking.
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('section becoming falsy clears the list immediately and permanently', async () => {
    // A different ICD context than the previous test so the mount cannot be
    // served from the persisted module cache — its GET must really fire.
    const gateJ45 = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateJ45.promise);
    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: 'J45' });

    act(() => {
      utils.rerender({ section: undefined, icd10Code: 'J45' });
    });

    // Immediately: no phrases for a context that no longer exists.
    expect(utils.result.current.templates).toHaveLength(0);
    expect(utils.result.current.hasTemplates).toBe(false);

    // The stale J45 response arrives LAST — for a context with no section the
    // list must stay empty, permanently.
    await act(async () => {
      gateJ45.resolve({ data: { templates: [tmpl(30, 'Лечение по J45')] } });
      await flush();
    });
    expect(utils.result.current.templates).toHaveLength(0);
    expect(utils.result.current.hasTemplates).toBe(false);
    // The queued mount GET was really consumed — no leftovers for the next test.
    expect(apiGet).toHaveBeenCalledTimes(1);
  });
});

describe('RETRO-3953-03: forced refresh after a mutation bypasses the stale pre-mutation promise', () => {
  it('a successful PUT shows the newly persisted text, not the old pending GET\u2019s payload', async () => {
    // A pre-mutation GET is still in flight (slow network).
    const gateOldGet = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOldGet.promise);
    const utils = renderTemplatesHook({ section: 'recommendations', icd10Code: null });

    // The doctor edits template 1; the PUT succeeds.
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    // The forced refresh issues a FRESH GET carrying the new text.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });

    let updateResult: { success: boolean } | undefined;
    utils.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });

    // The stale pre-mutation GET resolves LAST with the OLD text.
    await act(async () => {
      gateOldGet.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });

    // The mutation reported success…
    expect(updateResult?.success).toBe(true);
    // …a real post-mutation GET occurred (not a join of the stale promise)…
    expect(apiGet).toHaveBeenCalledTimes(2);
    // …and the UI shows the newly persisted text, never the old payload.
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
    expect((utils.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Старый текст',
    )).toBe(false);
  });
});

describe('RETRO-3953-04: a failed shared GET surfaces the same failure to every subscriber', () => {
  it('both mounted hooks show the failure; the joiner never sees a false "no templates" success', async () => {
    const gate = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gate.promise);

    const first = renderTemplatesHook({ section: 'anamnesis', icd10Code: null });
    const second = renderTemplatesHook({ section: 'anamnesis', icd10Code: null });

    // The shared GET fails for both.
    await act(async () => {
      gate.reject({ message: '403 Forbidden' });
      await flush();
    });

    // One shared request, no redundant traffic.
    expect(apiGet).toHaveBeenCalledTimes(1);
    // The ORIGINATOR shows the failure.
    expect(first.result.current.error).not.toBeNull();
    expect(first.result.current.templates).toHaveLength(0);
    // The JOINER must not launder the failure into an empty success.
    expect(second.result.current.error).not.toBeNull();
    expect(second.result.current.templates).toHaveLength(0);
    expect(second.result.current.loading).toBe(false);
    expect(second.result.current.hasTemplates).toBe(false);
  });
});
