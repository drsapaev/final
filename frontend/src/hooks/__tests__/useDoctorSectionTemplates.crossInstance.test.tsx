/**
 * RETRO-3995-02 (post-merge review window 3969-3996, ledger PR 4000) — fail-first.
 *
 * The section-template cache is MODULE-GLOBAL and shared by every mounted
 * hook instance with the same owner/section/ICD/limit key, while the request
 * epoch is PER INSTANCE. A stale cross-instance GET therefore passes its own
 * epoch check and can (1) replace a newer successful update in the shared
 * map — every future reader (including fresh mounts served from cache)
 * receives the outdated payload, and (2) its catch handler deletes the
 * shared entry unconditionally, destroying a newer instance's successful
 * data or pending promise. A joining subscriber that attached to the stale
 * promise before the newer update repaints the stale payload too.
 *
 * Fix contract: every cache WRITE and every cache DELETE must carry the
 * shared per-key install-token identity; a stale-generation response adopts
 * the newer shared truth (data or pending promise) instead of painting its
 * own payload.
 */
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

describe('RETRO-3995-02: cross-instance cache generations', () => {
  it('a stale cross-instance GET never replaces a newer successful update in the shared cache', async () => {
    // Instance A starts the slow GET whose payload is already outdated.
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'examination', icd10Code: null });

    // Instance C (same key) joins the in-flight GET (no extra traffic), edits
    // a template and the forced post-PUT refresh lands the NEW text.
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });
    const c = renderTemplatesHook({ section: 'examination', icd10Code: null });

    let updateResult: { success: boolean } | undefined;
    c.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);
    expect(apiGet).toHaveBeenCalledTimes(2);

    // A's stale response resolves LAST with the OLD text.
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });

    // Both live instances must converge on the NEWER shared truth…
    await waitFor(() => {
      expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
    expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    // …and a freshly mounted instance must be served from the cache WITHOUT a
    // new network request — the stale responder replaced nothing.
    const d = renderTemplatesHook({ section: 'examination', icd10Code: null });
    expect(apiGet).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect((d.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
  });

  it('a late failed GET keeps the newer shared data and never paints a false failure', async () => {
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'treatment', icd10Code: 'Q99' });

    // C (same key) joins, PUTs successfully and its forced refresh commits NEW.
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });
    const c = renderTemplatesHook({ section: 'treatment', icd10Code: 'Q99' });

    let updateResult: { success: boolean } | undefined;
    c.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);
    expect(apiGet).toHaveBeenCalledTimes(2);

    // The stale GET fails LAST — it must not delete the newer shared entry.
    await act(async () => {
      gateOld.reject({ message: '503 Service Unavailable' });
      await flush();
    });

    // The stale failure must not paint over the newer known truth…
    expect(a.result.current.error).toBeNull();
    expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    // …and the cache must still hold it: a fresh mount reads it with no GET.
    const d = renderTemplatesHook({ section: 'treatment', icd10Code: 'Q99' });
    expect(apiGet).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect((d.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
  });

  it('a joining subscriber converges on the newer shared truth, not the stale payload it joined', async () => {
    // A starts the slow GET; B joins it BEFORE the newer update lands.
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'Q88' });
    const b = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'Q88' });
    expect(apiGet).toHaveBeenCalledTimes(1);

    // C performs the mutation and the post-PUT refresh commits NEW.
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });
    const c = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'Q88' });

    let updateResult: { success: boolean } | undefined;
    c.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);

    // The stale promise B joined resolves with the OLD payload last.
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });

    // B must not repaint the stale payload it joined: the newest successful
    // shared truth wins for every subscriber.
    await waitFor(() => {
      expect((b.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
    expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    expect(apiGet).toHaveBeenCalledTimes(2);
  });
});

describe('RETRO-4014-01: the newest GET fails — a stale success must not read as current', () => {
  it('a stale completion after a newer FAILED refresh surfaces the failure, never its own OLD payload', async () => {
    // A starts the slow GET(OLD) — generation 1.
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });

    // C (same key) joins, PUTs successfully, and its forced post-PUT
    // refresh FAILS (503): the catch deletes the shared entry…
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockRejectedValueOnce({ message: '503 Service Unavailable' });
    const c = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });

    let updateResult: { success: boolean } | undefined;
    c.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);
    // C's own forced refresh paints its honest failure (RETRO-3995-03).
    await waitFor(() => {
      expect(c.result.current.error).toBe('503 Service Unavailable');
    });

    // …generation 2 failed LAST, and now A's stale GET succeeds with OLD.
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });

    // The stale payload must NOT fall through as a successful current
    // response: A surfaces the newer generation's failure instead.
    await waitFor(() => {
      expect(a.result.current.error).toBe('503 Service Unavailable');
    });
    expect(a.result.current.templates).toEqual([]);

    // The shared map holds no stale data: the next ordinary reader issues a
    // REAL network GET (cache miss) instead of being served OLD.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Свежий текст')] } });
    const d = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledTimes(3);
    });
    await waitFor(() => {
      expect((d.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Свежий текст');
    });
    expect((d.result.current.templates as Record<string, unknown>[])[0]?.template_text).not.toBe('Старый текст');
  });

  it('a pending newer read keeps precedence over the failure tombstone — the stale completion chains onto it', async () => {
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'complaints', icd10Code: null });

    // C's forced refresh fails (tombstone generation 2, entry deleted)…
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockRejectedValueOnce({ message: '503 Service Unavailable' });
    const c = renderTemplatesHook({ section: 'complaints', icd10Code: null });
    let updateResult: { success: boolean } | undefined;
    c.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);

    // …and generation 3 (D's ordinary read) is STILL PENDING when A settles.
    const gateD = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateD.promise);
    const d = renderTemplatesHook({ section: 'complaints', icd10Code: null });
    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledTimes(3);
    });

    // A's stale GET resolves while the newer read is in flight: it must
    // CHAIN onto generation 3 (pending truth beats the tombstone)…
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });

    // …and converge on D's eventual NEW data, not on its own OLD payload.
    await act(async () => {
      gateD.resolve({ data: { templates: [tmpl(1, 'Новый текст')] } });
      await flush();
    });
    await waitFor(() => {
      expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
    expect((d.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    expect(a.result.current.error).toBeNull();
  });

  it('a newer SUCCESS clears the failure tombstone — a late stale responder adopts the newer data', async () => {
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'J45' });

    // Generation 2 (C's forced refresh) fails and leaves the tombstone…
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockRejectedValueOnce({ message: '503 Service Unavailable' });
    const c = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'J45' });
    let updateResult: { success: boolean } | undefined;
    c.result.current.updateTemplate('1', 'Новый текст', 'replace').then((r) => {
      updateResult = r as { success: boolean };
    });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);

    // …and generation 3 (D's ordinary read) SUCCEEDS: the tombstone must be
    // cleared and the entry restored with the fresh truth.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });
    const d = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'J45' });
    await waitFor(() => {
      expect((d.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });

    // A's stale GET resolves LAST: the shared truth is generation 3's
    // success — adopt it as ok:true, never fall through to OLD.
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });
    expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    expect(a.result.current.error).toBeNull();

    // The cache serves the fresh truth with no extra traffic.
    const e = renderTemplatesHook({ section: 'anamnesis', icd10Code: 'J45' });
    expect(apiGet).toHaveBeenCalledTimes(3);
    await waitFor(() => {
      expect((e.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
  });
});
