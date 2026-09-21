/**
 * RQ-18 — public /q/:publicCode route pins (S-15 public half).
 *
 * Critical flow (directive §8 — NO DOUBLE START):
 *   public_code → ONE public start-session → session_token + queue_info
 *   → the EXISTING QueueJoin state machine → existing complete flow.
 *
 * Forbidden and pinned here:
 *  - a second public start-session from React effects/StrictMode/retry;
 *  - the legacy `startQueueJoinSession(session_token)` mis-call (it expects
 *    a QR token, not a join-session token);
 *  - any fallback to the clinic-wide QR-token flow.
 *
 * Refusal semantics (§11): unknown/archived/hidden/tombstoned/retired are
 * ONE anonymous unavailable state — no internal reason is revealed, no
 * fallback.
 *
 * RQ-18 follow-up (owner round-1 review of merged #3360):
 *  - P1-1: the patient sees the DIRECTION (direction.title), never the
 *    clinic-wide sentinel display fields («Клиника» / «Все специалисты» /
 *    «0 в очереди») — the mock below carries the ACTUAL backend response
 *    shape (verified against get_qr_token_info's clinic-wide branch and
 *    the follow-up endpoint override), not a hand-improved payload;
 *  - P1-2: a client-known expired session is transparently renewed BEFORE
 *    the first business attempt with the typed form preserved; the RQ-10
 *    no-auto-renewal-after-complete contract stays pinned; the typed form
 *    draft survives a full remount (per-code storage key);
 *  - P2-1: the single-entry ticket view normalizes entries[0] metrics —
 *    no fabricated «−1 впереди», wait time and direction title shown;
 *  - P2-2: navigating /q/A → /q/B inside one route instance starts B and
 *    drops A's whole client context (code-bound bootstrap guard).
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const queueApiMocks = vi.hoisted(() => ({
    fetchQrTokenInfo: vi.fn(),
    startQueueJoinSession: vi.fn(),
    completeQueueJoinSession: vi.fn(),
}));

vi.mock('../../api/queue', () => queueApiMocks);

const directionApiMocks = vi.hoisted(() => ({
    startPublicDirectionSession: vi.fn(),
}));

vi.mock('../../api/queueDirections', () => directionApiMocks);

import QueueJoin from '../QueueJoin';
import { ROUTE_REGISTRY } from '../../routing/routeRegistry';

const getRouteById = (id: string) => ROUTE_REGISTRY.find((r) => r.id === id);

function renderDirectionRoute(code = 'abcd1234efgh') {
    return render(
        <React.StrictMode>
            <MemoryRouter initialEntries={[`/q/${code}`]}>
                <Routes>
                    <Route path="/q/:publicCode" element={<QueueJoin />} />
                </Routes>
            </MemoryRouter>
        </React.StrictMode>,
    );
}

/**
 * P1-1: the REAL backend response shape. The shared token-info builder
 * runs the clinic-wide branch for the minted is_clinic_wide token; the
 * follow-up endpoint override replaces the sentinel display fields with
 * the direction identity and nulls the sentinel stats. The mock mirrors
 * that contract — NOT a hand-improved queue_info.
 */
const DIRECTION_START_RESPONSE = {
    session_token: 'dir-session-token',
    expires_at: '2099-09-20T00:15:00Z',
    permanent_address: true,
    direction: {
        profile_id: 7,
        key: 'lab-key',
        title: 'Лаборатория',
        public_code: 'abcd1234efgh',
    },
    queue_info: {
        is_clinic_wide: true,
        queue_active: true,
        allowed: true,
        status: 'available',
        message: 'Запись доступна',
        department_name: 'Лаборатория',
        specialist_name: null,
        queue_length: null,
        target_date: '2026-09-20',
        selectable_specialists: [],
    },
};

/** Pre-fix sentinel payload (old merged main) — the UI must stay honest. */
const SENTINEL_START_RESPONSE = {
    ...DIRECTION_START_RESPONSE,
    queue_info: {
        ...DIRECTION_START_RESPONSE.queue_info,
        department_name: 'Клиника',
        specialist_name: 'Все специалисты',
        queue_length: 0,
    },
};

/** The multi-result shape complete_join_session_multiple actually returns. */
const COMPLETE_MULTI_RESPONSE = {
    success: true,
    queue_time: '2026-09-20T09:00:00Z',
    entries: [
        {
            specialist_id: 7,
            queue_entry_id: 101,
            queue_number: 3,
            duplicate: false,
            queue_length: 2,
            estimated_wait_time: 30,
            specialist_name: 'Все специалисты',
            department: 'qdir:lab-key',
        },
    ],
    errors: null,
    message: 'Создано 1 записей, ошибок: 0',
};

/** Fills the form and submits (form step reached by the caller). */
async function fillAndSubmit(name = 'Тест Пациент') {
    fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
    fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
        target: { value: name },
    });
    fireEvent.change(screen.getByLabelText(/номер телефона/i), {
        target: { value: '+998 (90) 123-45-67' },
    });
    await React.act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
    });
}

beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
});

describe('RQ-18 — /q/:publicCode public route', () => {
    it('PIN 7 (red on main): registry carries a public /q/:publicCode route into the QueueJoin experience', () => {
        const route = getRouteById('queue-join-direction') as
            | { path?: string; auth?: string; nav?: boolean; component?: string }
            | undefined;
        expect(route).toBeTruthy();
        expect(route?.path).toBe('/q/:publicCode');
        expect(route?.auth).toBe('public');
        expect(route?.component).toBe('QueueJoin');
        expect(route?.nav).toBe(false);
    });

    it('PIN 8: mount performs EXACTLY ONE public start-session (StrictMode-safe)', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        await waitFor(() => {
            expect(screen.getByText(/заполните форму/i)).toBeTruthy();
        });
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledWith('abcd1234efgh');
    });

    it('PIN 9: the session response feeds the EXISTING QueueJoin state (info step reached, form opens)', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        // info step reached through the existing state machine
        await waitFor(() => {
            expect(screen.getByText(/заполните форму/i)).toBeTruthy();
        });
        // continue into the existing form step
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        expect(await screen.findByLabelText(/фио пациента/i)).toBeTruthy();
    });

    it('PIN 10: legacy QR-token machinery is never invoked in direction mode', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        await waitFor(() => {
            expect(screen.getByText(/заполните форму/i)).toBeTruthy();
        });
        expect(queueApiMocks.fetchQrTokenInfo).not.toHaveBeenCalled();
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
    });

    it('PIN 11: anonymous refusal renders ONE unified unavailable state — no internal reasons', async () => {
        directionApiMocks.startPublicDirectionSession.mockRejectedValue({
            response: { status: 404, data: { detail: 'Направление недоступно' } },
        });
        renderDirectionRoute();
        await waitFor(() => {
            expect(screen.getByTestId('qj-direction-unavailable')).toBeTruthy();
        });
        // no internal profile keys / codes / reasons leak to the anonymous patient
        expect(screen.queryByText(/lab-key/i)).toBeNull();
        expect(screen.queryByText(/abcd1234efgh/)).toBeNull();
        expect(screen.queryByText(/архив|удал|скрыт|retired/i)).toBeNull();
    });

    it('PIN 12: refusal never falls back to the clinic-wide QR flow', async () => {
        directionApiMocks.startPublicDirectionSession.mockRejectedValue({
            response: { status: 404, data: { detail: 'Направление недоступно' } },
        });
        renderDirectionRoute();
        await waitFor(() => {
            expect(screen.getByTestId('qj-direction-unavailable')).toBeTruthy();
        });
        expect(queueApiMocks.fetchQrTokenInfo).not.toHaveBeenCalled();
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
    });

    it('PIN 10b: lost session at submit-time uses ONE safe session-start retry — never the legacy token start', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
    });

    it('PIN 13 (red on merged main): the patient sees the DIRECTION — title shown, clinic sentinels and fabricated stats never', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        // direction identity from the direction object
        expect(screen.getByText('Лаборатория')).toBeTruthy();
        // clinic-wide sentinel display fields are never rendered
        expect(screen.queryByText('Клиника')).toBeNull();
        expect(screen.queryByText('Все специалисты')).toBeNull();
        // no fabricated «0 в очереди / ~0 мин» stat cards in direction mode
        expect(screen.queryByText(/^в очереди$/)).toBeNull();
        expect(screen.queryByText('~0')).toBeNull();
    });

    it('PIN 13b: pre-fix sentinel payload still renders the direction — no «Клиника», no fake stats', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(SENTINEL_START_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        expect(screen.getByText('Лаборатория')).toBeTruthy();
        expect(screen.queryByText('Клиника')).toBeNull();
        expect(screen.queryByText('Все специалисты')).toBeNull();
        expect(screen.queryByText(/^в очереди$/)).toBeNull();
        expect(screen.queryByText('~0')).toBeNull();
    });

    it('PIN 14 (red on merged main): client-known expired session is renewed BEFORE submit — form preserved, 2 starts', async () => {
        directionApiMocks.startPublicDirectionSession
            .mockResolvedValueOnce({
                ...DIRECTION_START_RESPONSE,
                session_token: 'expired-token',
                expires_at: new Date(Date.now() - 60_000).toISOString(),
            })
            .mockResolvedValueOnce({
                ...DIRECTION_START_RESPONSE,
                session_token: 'fresh-token',
                expires_at: new Date(Date.now() + 600_000).toISOString(),
            });
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        // mount start + transparent pre-submit renewal — exactly 2 starts
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(2);
        // the completed attempt used the RENEWED session token
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].session_token).toBe('fresh-token');
        // the typed form context survived the renewal
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].patient_name).toBe('Тест Пациент');
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
    });

    it('PIN 15 (RQ-10 regression guard): a complete-attempt rejection NEVER auto-renews the session', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: { status: 400, data: { detail: 'Сессия не найдена или истекла' } },
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        // the first attempt's result may be unknown — no automatic renewal
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
    });

    it('PIN 16 (red on merged main): the typed draft survives a full remount on the same /q/:code', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        const first = renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
            target: { value: 'Иванов Иван' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: '+998 (90) 123-45-67' },
        });
        first.unmount();
        // full page reload equivalent: fresh mount, session expired long ago
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        const nameInput = await screen.findByLabelText(/фио пациента/i);
        expect((nameInput as HTMLInputElement).value).toBe('Иванов Иван');
    });

    it('PIN 17 (red on merged main): /q/A → /q/B inside one mount starts B and drops A entirely', async () => {
        const CODE_A = 'aaaa1111bbbb';
        const CODE_B = 'cccc2222dddd';
        directionApiMocks.startPublicDirectionSession.mockImplementation((code: string) =>
            code === CODE_A
                ? Promise.resolve({
                      ...DIRECTION_START_RESPONSE,
                      session_token: 'session-A',
                      direction: { ...DIRECTION_START_RESPONSE.direction, title: 'Направление А', public_code: CODE_A },
                  })
                : Promise.resolve({
                      ...DIRECTION_START_RESPONSE,
                      session_token: 'session-B',
                      direction: { ...DIRECTION_START_RESPONSE.direction, title: 'Направление Б', public_code: CODE_B },
                  }),
        );
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);

        function NavigateToB() {
            const navigate = useNavigate();
            return (
                <button type="button" data-testid="nav-to-b" onClick={() => navigate(`/q/${CODE_B}`)}>
                    go-b
                </button>
            );
        }

        render(
            <React.StrictMode>
                <MemoryRouter initialEntries={[`/q/${CODE_A}`]}>
                    <Routes>
                        <Route
                            path="/q/:publicCode"
                            element={
                                <>
                                    <QueueJoin />
                                    <NavigateToB />
                                </>
                            }
                        />
                    </Routes>
                </MemoryRouter>
            </React.StrictMode>,
        );

        // A booted
        await screen.findByText('Направление А');
        // same route instance navigates to B (param change, NO remount)
        fireEvent.click(screen.getByTestId('nav-to-b'));
        await screen.findByText('Направление Б');

        // B's start happened exactly once (A once, B once)
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(2);
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenNthCalledWith(1, CODE_A);
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenNthCalledWith(2, CODE_B);

        // A's form context did not leak into B
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
            target: { value: 'Пациент Б' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: '+998 (90) 123-45-67' },
        });
        await React.act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
        });
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        // the submit under URL B used B's session, not A's stale one
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].session_token).toBe('session-B');
    });

    it('PIN 18 (red on merged main): direction ticket result normalizes entries[0] — no «−1», real wait and direction title', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(screen.getByText(/ваш номер/i)).toBeTruthy();
        });
        // ticket number from entries[0]
        expect(screen.getByText('№3')).toBeTruthy();
        // «перед вами» = number − 1 = 2, never the fabricated −1
        expect(screen.getByText('2 к.')).toBeTruthy();
        expect(screen.queryByText('-1 к.')).toBeNull();
        expect(screen.queryByText(/−1/)).toBeNull();
        // wait time from entries[0] is now visible
        expect(screen.getByText('30 мин')).toBeTruthy();
        // the ticket is labelled with the DIRECTION title, not the raw
        // internal department code (qdir:lab-key) or the sentinel name
        expect(screen.getAllByText('Лаборатория').length).toBeGreaterThan(0);
        expect(screen.queryByText('qdir:lab-key')).toBeNull();
        expect(screen.queryByText('Все специалисты')).toBeNull();
    });
});
