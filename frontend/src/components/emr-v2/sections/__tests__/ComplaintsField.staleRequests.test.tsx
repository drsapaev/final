/**
 * EMRCOMPLAINT-FE-001 (audit 3886, round 27) — fail-first.
 *
 * ComplaintsField launched onRequestAI(debouncedValue) and, after the await,
 * unconditionally setAiSuggestions(result) with no epoch, abort or effect
 * cleanup. The [value] effect cleared local suggestions on text change, but
 * an OLDER request could resolve after that clear and repopulate the panel
 * with past-complaint text — accept-capable against the current complaint.
 * The loading spinner likewise belonged to whichever request resolved last.
 *
 * Contract after the fix: every value/editability change invalidates the
 * in-flight request (epoch guard); a late response neither displays nor
 * re-enables acceptance, and the spinner resets with the owning request.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ComplaintsField from '../ComplaintsField';

function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => { resolve = res; });
    return { promise, resolve };
}

async function flushMicrotasks() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
    });
}

type Suggestion = { id: number; text: string };

describe('EMRCOMPLAINT-FE-001: late complaint-history responses cannot repopulate the panel', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    function focusTextarea() {
        const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
        fireEvent.focus(ta);
        return ta;
    }

    it('R16: a response for text A resolved after the doctor switched to text B is not displayed', async () => {
        const request = deferred<Suggestion[]>();
        // one stable callback identity across every rerender (as a real parent)
        const onRequestAI = vi.fn(() => request.promise);
        const props = { value: '', onChange: vi.fn(), onRequestAI };
        const { rerender } = render(<ComplaintsField {...props} />);
        focusTextarea();

        // doctor types text A (≥5 chars) and the 1.5s debounce elapses
        rerender(<ComplaintsField {...props} value="боль в груди" />);
        await act(async () => { vi.advanceTimersByTime(1500); });
        expect(onRequestAI).toHaveBeenCalledTimes(1);
        expect(onRequestAI).toHaveBeenCalledWith('боль в груди');

        // doctor edits to text B — the A request is still in flight
        rerender(<ComplaintsField {...props} value="боль в спине" />);

        // the A response resolves LATE
        await act(async () => {
            request.resolve([{ id: 1, text: 'старая жалоба' }]);
        });
        await flushMicrotasks();

        expect(screen.queryByText('старая жалоба')).not.toBeInTheDocument();
    });

    it('R17: a late response cannot reappear after the editor was disabled and re-enabled', async () => {
        const request = deferred<Suggestion[]>();
        const onRequestAI = vi.fn(() => request.promise);
        const props = { value: '', onChange: vi.fn(), onRequestAI };
        const { rerender } = render(<ComplaintsField {...props} />);
        focusTextarea();

        rerender(<ComplaintsField {...props} value="боль в груди" />);
        await act(async () => { vi.advanceTimersByTime(1500); });
        expect(onRequestAI).toHaveBeenCalledTimes(1);

        // editor becomes read-only while the request is in flight
        rerender(<ComplaintsField {...props} value="боль в груди" isEditable={false} />);
        await act(async () => {
            request.resolve([{ id: 1, text: 'старая жалоба' }]);
        });
        await flushMicrotasks();

        // editor is re-enabled — the stale result must not resurface
        rerender(<ComplaintsField {...props} value="боль в груди" />);
        expect(screen.queryByText('старая жалоба')).not.toBeInTheDocument();
    });

    it('R18: the spinner resets when the owning text changes, not when the stale request settles', async () => {
        const request = deferred<Suggestion[]>();
        const onRequestAI = vi.fn(() => request.promise);
        const props = { value: '', onChange: vi.fn(), onRequestAI };
        const { rerender } = render(<ComplaintsField {...props} />);
        focusTextarea();

        rerender(<ComplaintsField {...props} value="боль в груди" />);
        await act(async () => { vi.advanceTimersByTime(1500); });
        expect(screen.getByText(/Ищу похожие записи/i)).toBeInTheDocument();

        // the doctor keeps typing — the in-flight request is obsolete
        rerender(<ComplaintsField {...props} value="боль в груди и спине" />);
        expect(screen.queryByText(/Ищу похожие записи/i)).not.toBeInTheDocument();

        // the obsolete response resolving late must not re-light the spinner
        await act(async () => {
            request.resolve([{ id: 1, text: 'старая жалоба' }]);
        });
        await flushMicrotasks();
        expect(screen.queryByText(/Ищу похожие записи/i)).not.toBeInTheDocument();
        expect(screen.queryByText('старая жалоба')).not.toBeInTheDocument();
    });

    it('R19: clearing the text below the request threshold kills the pending result', async () => {
        const request = deferred<Suggestion[]>();
        const onRequestAI = vi.fn(() => request.promise);
        const props = { value: '', onChange: vi.fn(), onRequestAI };
        const { rerender } = render(<ComplaintsField {...props} />);
        focusTextarea();

        rerender(<ComplaintsField {...props} value="боль в груди" />);
        await act(async () => { vi.advanceTimersByTime(1500); });
        expect(onRequestAI).toHaveBeenCalledTimes(1);

        // doctor clears the field entirely
        rerender(<ComplaintsField {...props} value="" />);
        await act(async () => {
            request.resolve([{ id: 1, text: 'старая жалоба' }]);
        });
        await flushMicrotasks();

        expect(screen.queryByText('старая жалоба')).not.toBeInTheDocument();
    });

    it('C20 (control): a timely response for the current text is displayed and accept-capable', async () => {
        const onChange = vi.fn();
        const onRequestAI = vi.fn(async () => [{ id: 1, text: 'ангина' }] as Suggestion[]);
        const props = { value: '', onChange, onRequestAI };
        const { rerender } = render(<ComplaintsField {...props} />);
        const ta = focusTextarea();

        rerender(<ComplaintsField {...props} value="боль в груди" />);
        await act(async () => { vi.advanceTimersByTime(1500); });
        await flushMicrotasks();

        expect(screen.getByText('ангина')).toBeInTheDocument();

        // Alt+Enter accepts the selected suggestion into the complaint
        fireEvent.keyDown(ta, { key: 'Enter', altKey: true });
        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange.mock.calls[0][0]).toContain('ангина');
    });

    it('C21 (control): Escape dismisses the visible suggestion panel', async () => {
        const onRequestAI = vi.fn(async () => [{ id: 1, text: 'ангина' }] as Suggestion[]);
        const props = { value: '', onChange: vi.fn(), onRequestAI };
        const { rerender } = render(<ComplaintsField {...props} />);
        const ta = focusTextarea();

        rerender(<ComplaintsField {...props} value="боль в груди" />);
        await act(async () => { vi.advanceTimersByTime(1500); });
        await flushMicrotasks();
        expect(screen.getByText('ангина')).toBeInTheDocument();

        fireEvent.keyDown(ta, { key: 'Escape' });
        expect(screen.queryByText('ангина')).not.toBeInTheDocument();
    });
});
