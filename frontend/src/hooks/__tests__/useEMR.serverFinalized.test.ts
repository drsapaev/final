/**
 * RETRO-4007-01 / RETRO-4007-02 (post-merge re-review of #4007, ledger
 * #4000) — fail-first regressions for the FINALIZED_STATE workflow
 * residuals.
 *
 * 4007-01: after a FINALIZED_STATE 409 (stale-local in_progress, the
 * record was signed on the server), the doctor is told to use
 * «Внести поправку» while the LOCAL isSigned/isAmended flags are still
 * false — the amendment action lives only in the signed/amended toolbar
 * branch, so the designed workflow is unreachable without an explicit
 * refresh that discards the local draft.
 *
 * 4007-02: (a) the deterministic finalized refusal returns without
 * marking any stop condition — useEMR transitions saving → error with
 * isDirty=true, the autosave effect re-arms the debounce and re-issues
 * the known-doomed POST on every window; (b) the legacy signed HTTP 400
 * (`{ signed: true }`) is not checked before the success bookkeeping, so
 * a signed refusal is still stamped as the last successful save.
 *
 * Contract after the fix:
 * - useEMR exposes `serverFinalized` (set by the FINALIZED_STATE 409 and
 *   the legacy signed 400, cleared by a reload/amendment/visit switch);
 * - the local draft (isDirty) is retained — no automatic overwrite, no
 *   discard;
 * - EMRContainerV2 admits the amendment action when serverFinalized
 *   (the toolbar renders the amendment branch instead of the ordinary
 *   Save/Save-and-Sign branch);
 * - the autosave pauses after ONE finalized/signed refusal until the
 *   explicit doctor recovery (resetErrors); a signed outcome is never
 *   stamped as a successful autosave;
 * - genuine optimistic conflicts and stale-visit drops keep their
 *   existing behavior (controls).
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

import { useEMRAutosave } from '../useEMRAutosave';
import { useEMR } from '../useEMR';

const authState = vi.hoisted(() => ({ profile: { id: 1 } as { id: number } | null }));

vi.mock('../../api/client', () => ({
    apiClient: { get: vi.fn(), post: vi.fn() },
    setSessionInvalidationListener: vi.fn(),
}));

vi.mock('../../stores/auth', () => ({
    getState: () => ({ profile: authState.profile }),
}));

import { apiClient } from '../../api/client';

const apiClientMock = vi.mocked(apiClient);

const serverEmr = (visitId: number, overrides: Record<string, unknown> = {}) => ({
    id: 1,
    patient_id: 2,
    visit_id: visitId,
    version: 2,
    row_version: 5,
    status: 'in_progress',
    data: { complaints: `visit-${visitId} text`, specialty: 'therapy' },
    ...overrides,
});

const finalizedRejection = () => ({
    response: {
        status: 409,
        data: {
            detail: {
                error: 'FINALIZED_STATE',
                message: 'Cannot edit signed or amended EMR. Use amend endpoint instead.',
            },
        },
    },
});

const legacySigned400Rejection = () => ({
    response: {
        status: 400,
        data: { detail: 'EMR is signed and cannot be modified' },
    },
});

let visitSeq = 900;
async function renderLoadedHook() {
    const visitId = ++visitSeq;
    apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(visitId) });
    const utils = renderHook((props: { visitId: number }) => useEMR(props.visitId, { specialty: 'therapy' }), {
        initialProps: { visitId },
    });
    await act(async () => {
        await vi.waitFor(() => {
            expect(utils.result.current.isLoading).toBe(false);
        });
    });
    return utils;
}

/** useEMR + useEMRAutosave смонтированы вместе — реальная связка (по acceptance re-review). */
function useRealHarness(visitId: number) {
    const emr = useEMR(visitId, { specialty: 'therapy' });
    const autosave = useEMRAutosave({
        isDirty: emr.isDirty,
        isSaving: emr.isSaving,
        isSigned: emr.isSigned,
        status: emr.status,
        saveEMR: emr.saveEMR,
        debounceMs: 50,
        maxWaitMs: 100,
        enabled: true,
    });
    return { emr, autosave };
}

/** Юнит-харнесс автосейва (прямые моки результата). */
function useAutosaveHarness(saveEMR: (opts?: Record<string, unknown>) => Promise<unknown>, opts: {
    isDirty: boolean;
    isSigned: boolean;
    status: string;
    isSaving?: boolean;
}) {
    return useEMRAutosave({
        isDirty: opts.isDirty,
        isSaving: opts.isSaving ?? false,
        isSigned: opts.isSigned,
        status: opts.status,
        saveEMR,
        debounceMs: 50,
        maxWaitMs: 100,
        enabled: true,
    });
}

beforeEach(() => {
    vi.resetAllMocks();
    authState.profile = { id: 1 };
});

afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
});

describe('RETRO-4007-01: the amendment workflow is reachable after a stale-local FINALIZED_STATE response', () => {
    it('a FINALIZED_STATE save rejection exposes serverFinalized while retaining the local draft', async () => {
        const utils = await renderLoadedHook();

        apiClientMock.post.mockRejectedValueOnce(finalizedRejection());
        act(() => {
            utils.result.current.setField('complaints', 'late edit over a server-signed EMR');
        });
        let outcome: Record<string, unknown> | undefined;
        await act(async () => {
            outcome = await utils.result.current.saveEMR({ isDraft: true }) as Record<string, unknown>;
        });

        expect(outcome?.finalized).toBe(true);
        // THE residual: the amendment affordance is gated behind LOCAL
        // isSigned/isAmended (both false here) — the server-finalized marker
        // must reach the consumer so the amendment branch can open.
        expect(utils.result.current.serverFinalized).toBe(true);
        // unsaved edits retained: no automatic overwrite, no discard
        expect(utils.result.current.isDirty).toBe(true);
        expect(utils.result.current.error).toContain('подписана');
    });

    it('a legacy signed HTTP 400 rejection exposes the same serverFinalized marker', async () => {
        const utils = await renderLoadedHook();

        apiClientMock.post.mockRejectedValueOnce(legacySigned400Rejection());
        act(() => {
            utils.result.current.setField('complaints', 'late edit over a signed EMR');
        });
        let outcome: Record<string, unknown> | undefined;
        await act(async () => {
            outcome = await utils.result.current.saveEMR({ isDraft: true }) as Record<string, unknown>;
        });

        expect(outcome?.signed).toBe(true);
        expect(utils.result.current.serverFinalized).toBe(true);
        expect(utils.result.current.isDirty).toBe(true);
        expect(utils.result.current.error).toContain('подписана');
    });

    it('reloading the server record clears the marker (the explicit refresh path)', async () => {
        const utils = await renderLoadedHook();

        apiClientMock.post.mockRejectedValueOnce(finalizedRejection());
        act(() => {
            utils.result.current.setField('complaints', 'late edit');
        });
        await act(async () => {
            await utils.result.current.saveEMR({ isDraft: true });
        });
        expect(utils.result.current.serverFinalized).toBe(true);

        // The doctor explicitly refreshes the signed server record.
        apiClientMock.get.mockResolvedValueOnce({
            status: 200,
            data: serverEmr(visitSeq, { status: 'signed', row_version: 6 }),
        });
        await act(async () => {
            await utils.result.current.reloadFromServer();
        });

        expect(utils.result.current.serverFinalized).toBe(false);
        expect(utils.result.current.isSigned).toBe(true);
    });

    it('a visit switch clears the marker (no cross-visit leakage)', async () => {
        const utils = await renderLoadedHook();

        apiClientMock.post.mockRejectedValueOnce(finalizedRejection());
        act(() => {
            utils.result.current.setField('complaints', 'late edit');
        });
        await act(async () => {
            await utils.result.current.saveEMR({ isDraft: true });
        });
        expect(utils.result.current.serverFinalized).toBe(true);

        const nextVisit = visitSeq + 1;
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(nextVisit) });
        await act(async () => {
            utils.rerender({ visitId: nextVisit });
            await vi.waitFor(() => {
                expect(utils.result.current.isLoading).toBe(false);
            });
        });

        expect(utils.result.current.serverFinalized).toBe(false);
    });
});

describe('RETRO-4007-02: the autosave pauses after a deterministic finalized/signed refusal', () => {
    it('a finalized refusal issues exactly ONE rejected POST until the explicit doctor recovery (real useEMR + useEMRAutosave)', async () => {
        vi.useFakeTimers();
        const visitId = ++visitSeq;
        apiClientMock.get.mockResolvedValueOnce({ status: 200, data: serverEmr(visitId) });
        // КАЖДЫЙ POST визита получает финализед-409 (сервер детерминистичен).
        apiClientMock.post.mockRejectedValue(finalizedRejection());
        const { result } = renderHook(() => useRealHarness(visitId));
        await act(async () => {
            await vi.waitFor(() => {
                expect(result.current.emr.isLoading).toBe(false);
            });
        });

        // Доктор печатает в черновике поверх сервер-подписанной записи.
        act(() => {
            result.current.emr.setField('complaints', 'late edit over a server-signed EMR');
        });
        // Первое debounce-окно: обречённый POST №1.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(60);
        });
        expect(apiClientMock.post).toHaveBeenCalledTimes(1);
        expect(result.current.emr.serverFinalized).toBe(true);

        // Дальнейшие debounce-окна: автосейв остаётся на паузе — никаких
        // повторных обречённых POST (без паузы редьюсерный статус-флип
        // saving→error пересоздаёт canSave-замыкание и ре-армит цикл).
        for (let i = 0; i < 4; i += 1) {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(80);
            });
        }
        expect(apiClientMock.post).toHaveBeenCalledTimes(1);
        // Восстановление (resetErrors + последующее редактирование) покрыто
        // юнит-кейсом ниже: здесь достаточно доказательства детерминированной
        // паузы в реальной связке useEMR + useEMRAutosave.
    });

    it('the explicit recovery (resetErrors) re-arms the autosave for the next edit', async () => {
        vi.useFakeTimers();
        const saveEMR: Mock<(opts?: Record<string, unknown>) => Promise<unknown>> =
            vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>(async () => ({ finalized: true, error: 'FINALIZED_STATE' }));
        const { result, rerender } = renderHook(
            ({ isDirty }: { isDirty: boolean }) => useAutosaveHarness(saveEMR, {
                isDirty,
                isSigned: false,
                status: 'draft',
            }),
            { initialProps: { isDirty: true } },
        );

        await act(async () => {
            await vi.advanceTimersByTimeAsync(60);
        });
        expect(saveEMR).toHaveBeenCalledTimes(1);

        // Пауза: окно за окном — ни одного нового POST.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(200);
        });
        expect(saveEMR).toHaveBeenCalledTimes(1);

        // Явное восстановление доктора + новое редактирование (флип dirty)
        // — автосейв снова работает.
        act(() => {
            result.current.resetErrors();
        });
        rerender({ isDirty: false });
        rerender({ isDirty: true });
        await act(async () => {
            await vi.advanceTimersByTimeAsync(60);
        });
        expect(saveEMR).toHaveBeenCalledTimes(2);
    });

    it('a legacy { signed: true } result is never stamped as a successful autosave', async () => {
        const saveEMR: Mock<(opts?: Record<string, unknown>) => Promise<unknown>> =
            vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>(async () => ({ signed: true }));
        const onAutosaveError: Mock<(error: unknown) => void> = vi.fn<(error: unknown) => void>();
        const onAutosaveSuccess: Mock<(result: unknown) => void> = vi.fn<(result: unknown) => void>();

        const { result, rerender } = renderHook(() => useEMRAutosave({
            isDirty: true,
            isSaving: false,
            isSigned: false,
            status: 'draft',
            saveEMR,
            debounceMs: 60_000,
            maxWaitMs: 120_000,
            onAutosaveError,
            onAutosaveSuccess,
        }));

        await act(async () => {
            await result.current.forceSave();
        });
        // Снимок хука обновляется только на ререндере (refs меняются внутри
        // act, но без диспатча ре-рендера нет).
        rerender();

        // THE residual: a signed refusal previously stamped
        // lastSaveTimeRef = Date.now() and called onAutosaveSuccess.
        expect(result.current.lastAutosave).toBeNull();
        expect(onAutosaveSuccess).not.toHaveBeenCalled();
        expect(onAutosaveError).toHaveBeenCalledTimes(1);
        expect((onAutosaveError.mock.calls[0][0] as { type?: string }).type).toBe('signed');
        // and it is a stop condition, not a per-window retry loop
        expect(result.current.isPausedDueToErrors).toBe(true);
    });

    it('a genuine optimistic conflict outcome does not install the pause (control)', async () => {
        vi.useFakeTimers();
        const saveEMR: Mock<(opts?: Record<string, unknown>) => Promise<unknown>> =
            vi.fn<(opts?: Record<string, unknown>) => Promise<unknown>>(async () => ({ conflict: true, current_version: 9, your_version: 5 }));
        const { rerender } = renderHook(
            ({ isDirty }: { isDirty: boolean }) => useAutosaveHarness(saveEMR, {
                isDirty,
                isSigned: false,
                status: 'draft',
            }),
            { initialProps: { isDirty: true } },
        );

        await act(async () => {
            await vi.advanceTimersByTimeAsync(60);
        });
        expect(saveEMR).toHaveBeenCalledTimes(1);

        // Врач продолжает редактировать поверх конфликта (флип dirty):
        // конфликт разрешим врачом (диалог + статус), это НЕ детерминированная
        // пауза — автосейв продолжает работать после нового редактирования.
        rerender({ isDirty: false });
        rerender({ isDirty: true });
        await act(async () => {
            await vi.advanceTimersByTimeAsync(60);
        });
        expect(saveEMR).toHaveBeenCalledTimes(2);
    });
});

describe('RETRO-4007-01: EMRContainerV2 renders the amendment branch in the server-finalized window (source contract)', () => {
    it('amendAllowed admits the serverFinalized marker and the toolbar branches on it', () => {
        const fs = require('node:fs') as typeof import('node:fs');
        const path = require('node:path') as typeof import('node:path');
        const source = fs.readFileSync(
            path.join(__dirname, '../../components/emr-v2/EMRContainerV2.tsx'),
            'utf8',
        );
        // The amendment affordance opens for the stale-local finalized window:
        // the LOCAL isSigned/isAmended are false exactly there.
        expect(source).toMatch(/amendAllowed = \(isSigned \|\| isAmended \|\| serverFinalized\)/);
        // The ordinary Save / Save-and-Sign branch is replaced by the signed
        // branch when the server finalized the record.
        expect(source).toMatch(/: !isSigned && !isAmended && !serverFinalized \? \(/);
        // The container destructures the marker from the hook.
        expect(source).toMatch(/\bserverFinalized,\n/);
    });
});
