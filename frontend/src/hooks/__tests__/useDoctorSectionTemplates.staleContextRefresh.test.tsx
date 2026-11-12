/**
 * RETRO-3995-01 (post-merge review of the #3969–#3996 wave, dossier of
 * merged PR #3995) — fail-first.
 *
 * P2: the mutation callbacks (updateTemplate / pinTemplate / unpinTemplate /
 * deleteTemplate) called their CLOSURE-CAPURED fetchTemplates(true). When a
 * mutation completed after the doctor switched the section/ICD context, that
 * stale-context forced refresh took the NEWEST request epoch for the OLD
 * context and:
 *   - committed the previous diagnosis's phrases into the panel rendered for
 *     the NEW diagnosis (the phrases are actionable — Apply inserts their
 *     text into the EMR field), while
 *   - the live context's own in-flight response was discarded by the epoch
 *     guard AND never written to the module cache.
 *
 * Post-fix contract:
 *  - the post-mutation refresh targets the LIVE context (latest-ref), so a
 *    mutation completing after a context switch re-reads what the doctor is
 *    looking at NOW;
 *  - defense in depth: ANY stale-closure request (e.g. a captured
 *    refetch(true)) may still fetch its old context, but can never paint it
 *    under the live context — the commit guards require the request's
 *    cacheKey to still be the hook's live cacheKey.
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

const texts = (hook: { result: { current: { templates: unknown[] } } }) =>
  (hook.result.current.templates as Array<{ template_text: string }>).map((t) => t.template_text);

beforeEach(() => {
  vi.clearAllMocks();
  authState.profile = { id: 1 };
  // URL-routed GETs: an I10 request can only ever answer with I10 phrases,
  // an I20 request with I20 phrases — the mock mirrors the real contract.
  apiGet.mockImplementation((url: string) => {
    if (String(url).includes('icd10_code=I10')) {
      return Promise.resolve({ data: { templates: [tmpl(1, 'Лечение по I10')] } });
    }
    if (String(url).includes('icd10_code=I20')) {
      return Promise.resolve({ data: { templates: [tmpl(2, 'Лечение по I20')] } });
    }
    return Promise.resolve({ data: { templates: [] } });
  });
});

describe('RETRO-3995-01: a mutation completing after a context switch refreshes the LIVE context', () => {
  it('an updateTemplate PUT resolving after the ICD switch re-reads I20, never repaints I10 phrases', async () => {
    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I10'));

    // The doctor edits an I10 phrase; the PUT is slow.
    const gatePut = deferred<{ data: { id: number } }>();
    apiPut.mockImplementationOnce(() => gatePut.promise);
    utils.result.current.updateTemplate('1', 'Новый текст', 'replace');

    // While the PUT is pending, the doctor changes the diagnosis to I20.
    act(() => {
      utils.rerender({ section: 'treatment', icd10Code: 'I20' });
    });
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I20'));
    const getsBefore = apiGet.mock.calls.length;

    // The PUT resolves — the post-mutation refresh must target the LIVE
    // context (I20), never the captured I10 closure.
    await act(async () => {
      gatePut.resolve({ data: { id: 1 } });
      await flush();
    });
    await waitFor(() => expect(apiGet.mock.calls.length).toBeGreaterThan(getsBefore));

    const lastUrl = String(apiGet.mock.calls.at(-1)?.[0]);
    expect(lastUrl).toContain('icd10_code=I20');
    expect(lastUrl).not.toContain('icd10_code=I10');

    // THE core regression: the previous diagnosis's phrases must not be
    // rendered (nor actionable) under the new diagnosis.
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I20'));
    expect(texts(utils)).not.toContain('Лечение по I10');
  });

  it('a deleteTemplate resolving after the ICD switch refreshes the live context too', async () => {
    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I10'));

    const gateDelete = deferred<{ data: unknown }>();
    vi.mocked(apiClient.delete).mockImplementationOnce(() => gateDelete.promise);
    utils.result.current.deleteTemplate('1');

    act(() => {
      utils.rerender({ section: 'treatment', icd10Code: 'I20' });
    });
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I20'));

    await act(async () => {
      gateDelete.resolve({ data: {} });
      await flush();
    });
    await waitFor(() => {
      const lastUrl = String(apiGet.mock.calls.at(-1)?.[0]);
      expect(lastUrl).toContain('icd10_code=I20');
    });
    expect(texts(utils)).not.toContain('Лечение по I10');
  });
});

describe('RETRO-3995-01 (defense in depth): a stale-closure refetch can never paint the previous context', () => {
  it('a captured refetch(true) from the I10 context does not repaint I10 phrases under I20', async () => {
    const utils = renderTemplatesHook({ section: 'treatment', icd10Code: 'I10' });
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I10'));

    // Any external caller may hold the I10-era refetch handle (the public
    // `refetch` return, captured before the switch).
    const staleRefetch = utils.result.current.refetch;

    act(() => {
      utils.rerender({ section: 'treatment', icd10Code: 'I20' });
    });
    await waitFor(() => expect(texts(utils)).toContain('Лечение по I20'));

    // The stale handle forces a refresh of its captured I10 context. The
    // request itself may happen (its cacheKey is I10) — but its response may
    // never commit under the live I20 context (pre-fix: it took the newest
    // epoch and repainted I10's phrases).
    await act(async () => {
      await staleRefetch(true);
      await flush();
    });

    expect(texts(utils)).not.toContain('Лечение по I10');
    expect(texts(utils)).toContain('Лечение по I20');
  });
});
