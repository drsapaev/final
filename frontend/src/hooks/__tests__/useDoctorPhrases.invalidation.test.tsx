/**
 * EMRPHRASE-FE-001 (audit 3886, round 27) — fail-first.
 *
 * useDoctorPhrases only aborted the previous request when a NEW request
 * started. Shortening the text below minQueryLength cleared the suggestions
 * state but left the in-flight request alive — its success handler then
 * called setSuggestions(...) unconditionally, resurrecting suggestions for
 * text the doctor had already cleared or changed. lastQueryRef compared
 * TEXT ONLY, so switching doctor/field/specialty with the same text skipped
 * the new context's authorized query entirely.
 *
 * Contract after the fix: any invalidation (short text, context identity
 * change) aborts the in-flight request and generation-guards its result;
 * the query memo is keyed by doctor+field+specialty+text and resets on
 * identity change so the new context always fetches.
 */
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
    get: vi.fn(),
    post: vi.fn(),
}));

vi.mock('../../api/client', () => ({
    api: {
        get: apiMocks.get,
        post: apiMocks.post,
    },
}));

import { useDoctorPhrases } from '../useDoctorPhrases';

function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => { resolve = res; });
    return { promise, resolve };
}

function mockReady() {
    apiMocks.get.mockImplementation(async (url: string) => {
        if (url.includes('/emr/readiness/')) {
            return { data: { ready: true, progress: 100, message: null } };
        }
        throw new Error(`unexpected GET ${url}`);
    });
}

type HookProps = { doctorId: number; currentText: string; field?: string };

function renderPhrases(initial: HookProps) {
    return renderHook(
        ({ doctorId, currentText, field = 'diagnosis' }: HookProps) =>
            useDoctorPhrases({
                doctorId,
                field,
                specialty: 'cardiology',
                currentText,
                cursorPosition: currentText.length,
                config: { debounceMs: 50, minQueryLength: 3, maxSuggestions: 5 },
            }),
        { initialProps: initial },
    );
}

describe('EMRPHRASE-FE-001: phrase suggestions are invalidated with their context', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        apiMocks.get.mockReset();
        apiMocks.post.mockReset();
        mockReady();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    async function settleReadiness() {
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
    }

    it('R22: shortening below minQueryLength aborts the in-flight request — its late result never appears', async () => {
        const request = deferred<{ data: { suggestions: unknown[] } }>();
        apiMocks.post.mockReturnValueOnce(request.promise);

        const { rerender, result } = renderPhrases({ doctorId: 201, currentText: '' });
        await settleReadiness();

        rerender({ doctorId: 201, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(50); });
        expect(apiMocks.post).toHaveBeenCalledTimes(1);

        // the doctor shortens the text below the query threshold
        rerender({ doctorId: 201, currentText: 'го' });
        await act(async () => { vi.advanceTimersByTime(50); });

        // the OLD request resolves late
        await act(async () => {
            request.resolve({ data: { suggestions: [{ id: 1, text: 'старая фраза' }] } });
        });
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(result.current.suggestions).toEqual([]);
    });

    it('R23: switching doctor with the same text issues a context-scoped fetch for the new doctor', async () => {
        const first = deferred<{ data: { suggestions: unknown[] } }>();
        const second = deferred<{ data: { suggestions: unknown[] } }>();
        apiMocks.post.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);

        const { rerender, result } = renderPhrases({ doctorId: 202, currentText: '' });
        await settleReadiness();

        rerender({ doctorId: 202, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(50); });
        expect(apiMocks.post).toHaveBeenCalledTimes(1);
        expect(apiMocks.post.mock.calls[0][0]).toBe('/emr/phrase-suggest');
        expect(apiMocks.post.mock.calls[0][1].doctorId).toBe(202);

        // SAME text, DIFFERENT doctor — the memo must not skip this query
        rerender({ doctorId: 203, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(50); });

        expect(apiMocks.post).toHaveBeenCalledTimes(2);
        expect(apiMocks.post.mock.calls[1][1].doctorId).toBe(203);

        // the first doctor's late response must not leak into doctor 203's UI
        await act(async () => {
            first.resolve({ data: { suggestions: [{ id: 1, text: 'фраза врача 202' }] } });
        });
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(result.current.suggestions).toEqual([]);
    });

    it('R24: switching field with the same text issues a fetch for the new field', async () => {
        apiMocks.post.mockResolvedValue({ data: { suggestions: [] } });

        const { rerender } = renderHook(
            ({ doctorId, currentText, field }: { doctorId: number; currentText: string; field: string }) =>
                useDoctorPhrases({
                    doctorId,
                    field,
                    specialty: 'cardiology',
                    currentText,
                    cursorPosition: currentText.length,
                    config: { debounceMs: 50, minQueryLength: 3 },
                }),
            { initialProps: { doctorId: 204, currentText: '', field: 'diagnosis' } },
        );
        await settleReadiness();

        rerender({ doctorId: 204, currentText: 'головная боль', field: 'diagnosis' });
        await act(async () => { vi.advanceTimersByTime(50); });
        expect(apiMocks.post).toHaveBeenCalledTimes(1);

        rerender({ doctorId: 204, currentText: 'головная боль', field: 'treatment' });
        await act(async () => { vi.advanceTimersByTime(50); });

        expect(apiMocks.post).toHaveBeenCalledTimes(2);
        expect(apiMocks.post.mock.calls[1][1].field).toBe('treatment');
    });

    it('R25: pausing the field kills the in-flight request — its late result never appears', async () => {
        const request = deferred<{ data: { suggestions: unknown[] } }>();
        apiMocks.post.mockReturnValueOnce(request.promise);

        const { rerender, result } = renderPhrases({ doctorId: 207, currentText: '' });
        await settleReadiness();

        rerender({ doctorId: 207, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(50); });
        expect(apiMocks.post).toHaveBeenCalledTimes(1);

        // doctor pauses autocomplete for this field while the request runs
        await act(async () => { result.current.togglePause(); });

        await act(async () => {
            request.resolve({ data: { suggestions: [{ id: 1, text: 'старая фраза' }] } });
        });
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(result.current.suggestions).toEqual([]);
    });

    it('C25 (control): a timely response for the current context is exposed', async () => {
        apiMocks.post.mockResolvedValueOnce({ data: { suggestions: [{ id: 1, text: 'мигрень' }] } });

        const { rerender, result } = renderPhrases({ doctorId: 205, currentText: '' });
        await settleReadiness();

        rerender({ doctorId: 205, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(50); });
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(result.current.suggestions).toEqual([{ id: 1, text: 'мигрень' }]);
    });

    it('C26 (control): unchanged text in the same context does not refetch (memo intact)', async () => {
        apiMocks.post.mockResolvedValue({ data: { suggestions: [] } });

        const { rerender } = renderPhrases({ doctorId: 206, currentText: '' });
        await settleReadiness();

        rerender({ doctorId: 206, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(50); });
        expect(apiMocks.post).toHaveBeenCalledTimes(1);

        // cursor moves but text and context stay the same — no new request
        rerender({ doctorId: 206, currentText: 'головная боль' });
        await act(async () => { vi.advanceTimersByTime(200); });
        expect(apiMocks.post).toHaveBeenCalledTimes(1);
    });
});
