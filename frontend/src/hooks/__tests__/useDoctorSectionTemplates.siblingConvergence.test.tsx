/**
 * RETRO-4014-01 sibling convergence contract (ledger PR 4000, comment 19 /
 * id 6798655747) — fail-first.
 *
 * The tombstone fix (7c3459ef6) made stale READS converge on the newer
 * shared truth, but an ALREADY-PAINTED mounted instance had no cache
 * subscription at all: after a sibling's successful mutation + forced
 * refresh installs a newer shared truth into sectionTemplateCache, the
 * quiet sibling kept showing its stale list (and an instance stranded in
 * its own error state stayed stranded). The contract pinned here:
 *
 * 1. SUCCESSFUL shared-map installs fan out to every mounted same-key
 *    instance — repaint the newer truth, clear a stranded error, no extra
 *    network request.
 * 2. FAILURE outcomes fan out NOTHING — the failure tombstone governs
 *    reads; a painted sibling keeps its last known good list.
 * 3. An instance's own in-flight request always owns its paint.
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
  // mockReset, not clearAllMocks: queued mock*Once implementations must not
  // leak across tests (clearAllMocks keeps them).
  for (const m of [apiMocks.get, apiMocks.post, apiMocks.put, apiMocks.delete]) {
    (m as ReturnType<typeof vi.fn>).mockReset();
  }
  authState.profile = { id: 1 };
});

describe('RETRO-4014-01: already-rendered sibling convergence (fan-out contract)', () => {
  it('a quiet sibling repaints the newer shared truth after a successful mutation — with zero extra GETs', async () => {
    // A: the first GET resolves OLD and PAINTS — A is now a rendered sibling.
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'treatment', icd10Code: null });
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });
    expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Старый текст');

    // C: same key — mounts, cache-hit paints OLD without extra traffic.
    const c = renderTemplatesHook({ section: 'treatment', icd10Code: null });
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Старый текст');

    // C edits: PUT ok, the forced post-PUT refresh installs the NEW truth.
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });
    let updateResult: { success: boolean } | undefined;
    c.result.current
      .updateTemplate('1', 'Новый текст', 'replace')
      .then((r) => {
        updateResult = r as { success: boolean };
      });
    await act(async () => {
      await flush();
    });
    expect(updateResult?.success).toBe(true);
    expect(apiGet).toHaveBeenCalledTimes(2);
    expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');

    // THE CONTRACT: A — still mounted, never re-fetched — converges on the
    // newer shared truth through the fan-out subscription, not its own read.
    await waitFor(() => {
      expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('a sibling stranded in its own error state recovers when the shared truth advances', async () => {
    // A paints OLD, then its own forced refresh FAILS (tombstone installs).
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'examination', icd10Code: null });
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });
    apiGet.mockRejectedValueOnce(new Error('503 Service Unavailable'));
    let refreshFailure: unknown;
    await act(async () => {
      refreshFailure = await a.result.current.refetch(true);
    });
    expect((refreshFailure as { ok: boolean }).ok).toBe(false);
    expect(a.result.current.error).toBeTruthy();
    // The instance's OWN failure empties its own list (typed failure paint).
    expect(a.result.current.templates).toEqual([]);

    // C: same key — its ordinary read finds no entry (the failure deleted
    // it), issues a fresh GET that resolves the NEW truth and installs it.
    apiGet.mockResolvedValueOnce({ data: { templates: [tmpl(1, 'Новый текст')] } });
    const c = renderTemplatesHook({ section: 'examination', icd10Code: null });
    expect(apiGet).toHaveBeenCalledTimes(3);
    await waitFor(() => {
      expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    });

    // THE CONTRACT: A's stranded error is cleared by the fan-out repaint —
    // the shared truth moved past A's last painted generation.
    await waitFor(() => {
      expect(a.result.current.error).toBeFalsy();
    });
    expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Новый текст');
    expect(apiGet).toHaveBeenCalledTimes(3);
  });

  it('a failed fresh read fans out NOTHING — the painted sibling keeps its last known good list', async () => {
    // A paints OLD; C cache-hits the same OLD.
    const gateOld = deferred<{ data: { templates: Record<string, unknown>[] } }>();
    apiGet.mockImplementationOnce(() => gateOld.promise);
    const a = renderTemplatesHook({ section: 'recommendations', icd10Code: null });
    await act(async () => {
      gateOld.resolve({ data: { templates: [tmpl(1, 'Старый текст')] } });
      await flush();
    });
    const c = renderTemplatesHook({ section: 'recommendations', icd10Code: null });
    expect((c.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Старый текст');

    // C's mutation succeeds but its forced fresh read FAILS — the shared
    // latest outcome is the tombstone, never a data payload.
    apiPut.mockResolvedValueOnce({ data: { id: 1, template_text: 'Новый текст' } });
    apiGet.mockRejectedValueOnce(new Error('503 Service Unavailable'));
    await act(async () => {
      // The mutation's own result stays success:true (the PUT succeeded);
      // the failed fresh read surfaces through the error state + tombstone.
      await c.result.current.updateTemplate('1', 'Новый текст', 'replace');
    });
    await waitFor(() => {
      expect(c.result.current.error).toBeTruthy();
    });

    // A: no repaint, no error — its painted list stays the last known good.
    expect((a.result.current.templates as Record<string, unknown>[])[0]?.template_text).toBe('Старый текст');
    expect(a.result.current.error).toBeFalsy();
  });
});
