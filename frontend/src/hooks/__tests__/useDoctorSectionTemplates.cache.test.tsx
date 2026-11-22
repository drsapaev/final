/**
 * EMRTMPL-FE-001/002/003 (audit 3886, round 23) — fail-first.
 *
 * - EMRTMPL-FE-001 (P1): the module-global section-template cache was keyed
 *   only by section/ICD/limit — no principal. In one SPA runtime doctor B
 *   could be served doctor A's cached personal clinical phrases, even though
 *   the backend scopes every query to the authenticated doctor.
 * - EMRTMPL-FE-002 (P2): a second hook that joined an in-flight request
 *   received the shared promise but never a setTemplates commit — it stayed
 *   empty («Нет сохранённых шаблонов») while the first instance showed the
 *   list.
 * - EMRTMPL-FE-003 (P2): no request-generation guard — a slow response for
 *   the previous ICD could overwrite the current diagnosis's template list.
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
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
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

describe('EMRTMPL-FE-001: principal-scoped template cache', () => {
  it('doctor B never receives doctor A\u2019s cached templates (fresh authorized GET)', async () => {
    // Doctor A loads their personal complaints templates.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Жалобы врача А')] } });
    const first = renderTemplatesHook({ section: 'complaints', icd10Code: null });
    await waitFor(() => {
      expect((first.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Жалобы врача А');
    });
    first.unmount();

    // Same JS runtime: logout + login as doctor B.
    authState.profile = { id: 2 };
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(2, 'Жалобы врача Б')] } });
    const second = renderTemplatesHook({ section: 'complaints', icd10Code: null });
    await waitFor(() => {
      expect((second.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Жалобы врача Б');
    });

    // B's list came from a fresh authorized request, not A's cache entry.
    expect(apiGet).toHaveBeenCalledTimes(2);
    expect((second.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Жалобы врача А',
    )).toBe(false);
  });

  it('anonymous state bypasses the cache entirely (no personal templates without a principal)', async () => {
    authState.profile = null;
    apiGet.mockResolvedValue({ data: { templates: [tmpl(3, 'Анонимный запрос')] } });

    const first = renderTemplatesHook({ section: 'recommendations', icd10Code: null });
    await waitFor(() => {
      expect(first.result.current.hasTemplates).toBe(true);
    });
    first.unmount();

    const second = renderTemplatesHook({ section: 'recommendations', icd10Code: null });
    await waitFor(() => {
      expect(second.result.current.hasTemplates).toBe(true);
    });

    // No cache means every mount queries the server.
    expect(apiGet).toHaveBeenCalledTimes(2);
  });
});

describe('EMRTMPL-FE-002: joining an in-flight request delivers the result to every subscriber', () => {
  it('a second mounted hook receives the shared result (single GET)', async () => {
    const gate = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gate.promise);

    const first = renderTemplatesHook({ section: 'anamnesis', icd10Code: null });
    const second = renderTemplatesHook({ section: 'anamnesis', icd10Code: null });

    await act(async () => {
      gate.resolve({ data: { templates: [tmpl(9, 'Общий анамнез')] } });
      await flush();
    });

    // BOTH instances show the fetched authorized list.
    expect((first.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Общий анамнез');
    expect((second.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Общий анамнез');
    // One shared request, no redundant traffic.
    expect(apiGet).toHaveBeenCalledTimes(1);
  });

  it('the joiner still receives the result when the original hook unmounts first', async () => {
    const gate = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gate.promise);

    const first = renderTemplatesHook({ section: 'examination', icd10Code: null });
    const second = renderTemplatesHook({ section: 'examination', icd10Code: null });
    first.unmount();

    await act(async () => {
      gate.resolve({ data: { templates: [tmpl(11, 'Осмотр без патологии')] } });
      await flush();
    });

    expect((second.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Осмотр без патологии');
    expect(second.result.current.loading).toBe(false);
  });
});

describe('EMRTMPL-FE-003: a late response of the previous ICD never overwrites the current list', () => {
  it('slow I10 response resolved after I20 must not replace the I20 templates', async () => {
    // Slow GET for I10 (the previous diagnosis).
    const gateI10 = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateI10.promise);

    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });

    // The doctor switches the diagnosis to I20; its request resolves fast.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(21, 'Лечение по I20')] } });
    act(() => {
      utils.rerender({ section: 'treatment', icd10Code: 'I20' });
    });
    await waitFor(() => {
      expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Лечение по I20');
    });

    // The stale I10 response arrives LAST.
    await act(async () => {
      gateI10.resolve({ data: { templates: [tmpl(10, 'Лечение по I10')] } });
      await flush();
    });

    // Only the current diagnosis's templates may be displayed.
    expect((utils.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Лечение по I20');
    expect((utils.result.current.templates as Record<string, unknown>[]).some(
      (t) => t.template_text === 'Лечение по I10',
    )).toBe(false);
  });
});
