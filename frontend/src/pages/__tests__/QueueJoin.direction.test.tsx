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
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

/** Renders the route PLUS navigation/location probes for the round-4
 * canonical-URL pins. `lastQjPath` mirrors the live URL after navigations. */
let lastQjPath = '';
const LocationProbe = () => {
    const location = useLocation();
    lastQjPath = location.pathname;
    return null;
};
const NavButton = ({ to }: { to: string }) => {
    const navigate = useNavigate();
    return (
        <button type="button" data-testid={`nav-${to}`} onClick={() => navigate(to)}>
            go {to}
        </button>
    );
};
function renderDirectionRouteWithNav(initialPath: string) {
    return render(
        <React.StrictMode>
            <MemoryRouter initialEntries={[initialPath]}>
                <LocationProbe />
                <NavButton to={`/q/${CANONICAL_CODE}`} />
                <NavButton to={`/q/${CANONICAL_CODE.toUpperCase()}`} />
                <Routes>
                    <Route path="/q/:publicCode" element={<QueueJoin />} />
                </Routes>
            </MemoryRouter>
        </React.StrictMode>,
    );
}

const CANONICAL_CODE = 'abcd1234efgh';
const DRAFT_PHONE = '+998 (90) 123-45-67';

/** Builds a round-4 draft envelope (the shape an OLDER build stored).
 * Round-5 keeps these pins as backward-compatibility probes: whatever an
 * older build left under the direction key must be discarded, never shown. */
function draftEnvelope(name: string, phone = DRAFT_PHONE, telegramId = '') {
    const digits = phone.replace(/\D/g, '');
    return {
        ts: Date.now(),
        v: { tail4: digits.slice(-4), fails: 0 },
        data: { patientName: name, phone, telegramId },
    };
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
    // Round-6 (P1-3): the server-computed attempt-identity horizon —
    // end of the target queue-day in the clinic timezone + grace.
    target_date: '2026-09-20',
    attempt_expires_at: '2099-09-20T21:59:59Z',
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
    // resetAllMocks (not clearAllMocks): a failed test must not leak a
    // pending mockResolvedValueOnce into the next test — the round-4 head
    // leaked exactly that way when PIN 33 failed mid-flow.
    vi.resetAllMocks();
    window.localStorage.clear();
    // round-6: the attempt-state lives in localStorage (survives the tab),
    // the PHI draft stays sessionStorage-only —
    // full isolation between pins.
    window.sessionStorage.clear();
    lastQjPath = '';
});

afterEach(() => {
    // PIN 26 enables Date-only fake timers inside the test — restore them
    // here so no mocked clock leaks into any other test (lint rule
    // no-fake-timers-without-cleanup; a no-op when nothing was mocked).
    vi.useRealTimers();
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

    it('PIN 16 (round-5 P1-1): the direction draft is GONE — a reload never restores the typed PHI and the device keeps nothing', async () => {
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
        // Round-5: NOTHING about the typed patient was persisted under the
        // shared permanent code — the round-4 phone-tail challenge verified
        // nothing for families sharing one number, so the draft is gone.
        expect(
            window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh'),
        ).toBeNull();
        first.unmount();
        // same browser session reload: an EMPTY form, no banner, no PHI
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        expect(screen.queryByTestId('qj-draft-challenge-input')).toBeNull();
        expect((screen.getByLabelText(/фио пациента/i) as HTMLInputElement).value).toBe('');
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
    });

    it('PIN 21 (red on 569d15f5): a NEW browser session never sees the previous patient PHI', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        const first = renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
            target: { value: 'Пациент А' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: '+998 (90) 555-11-22' },
        });
        first.unmount();
        // NEW browser session on the SHARED device: sessionStorage does not
        // survive it — and the draft must not live in long-lived localStorage.
        window.sessionStorage.clear();
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        // no confirmation banner (nothing found) and no prefill
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        const nameInput = (screen.getByLabelText(/фио пациента/i) as HTMLInputElement);
        expect(nameInput.value).toBe('');
        // the permanent shared code never carries PHI in long-lived storage
        expect(window.localStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
    });

    it('PIN 22 (red on 569d15f5): a stale draft past the TTL is discarded, not restored', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        window.sessionStorage.setItem(
            'queue_join_form_qdir_abcd1234efgh',
            JSON.stringify({
                ts: Date.now() - 16 * 60 * 1000, // past the 15-minute TTL
                data: { patientName: 'Старый Пациент', phone: '+998 (90) 111-00-00', telegramId: '' },
            }),
        );
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        expect((screen.getByLabelText(/фио пациента/i) as HTMLInputElement).value).toBe('');
        // the expired draft is erased from the device
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
    });

    it('PIN 23 (round-5 P1-1): a legacy-build draft is discarded, never shown — typing persists nothing', async () => {
        window.sessionStorage.setItem(
            'queue_join_form_qdir_abcd1234efgh',
            JSON.stringify(draftEnvelope('Черновик Пациент', '+998 (90) 222-33-44')),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        // no banner, no challenge, empty form — the stored draft is erased
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        expect(screen.queryByTestId('qj-draft-challenge-input')).toBeNull();
        expect((screen.getByLabelText(/фио пациента/i) as HTMLInputElement).value).toBe('');
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
        // typing the NEW patient's identity persists NOTHING under the
        // shared permanent code (round-5: no PHI draft at all)
        fireEvent.change(screen.getByLabelText(/фио пациента/i), {
            target: { value: 'Новый Пациент' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: DRAFT_PHONE },
        });
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
    });

    it('PIN 24 (round-2 P1): leaving to the home page discards the draft — no PHI survives the exit', async () => {
        window.sessionStorage.setItem(
            'queue_join_form_qdir_abcd1234efgh',
            JSON.stringify({
                ts: Date.now(),
                data: { patientName: 'Уходящий Пациент', phone: '+998 (90) 333-44-55', telegramId: '' },
            }),
        );
        directionApiMocks.startPublicDirectionSession.mockRejectedValue({
            response: { status: 500, data: { detail: 'boom' } },
        });
        renderDirectionRoute();
        // a non-404 start failure renders the generic error screen (with the
        // home button) — not the unified refusal marker (that one is 404-only)
        await waitFor(() => {
            expect(screen.getByRole('button', { name: /главная/i })).toBeTruthy();
        });
        fireEvent.click(screen.getByRole('button', { name: /главная/i }));
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
        expect(window.localStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
    });

    it('PIN 19 (red on 569d15f5): a LATE start answer for /q/A never overwrites the booted /q/B', async () => {
        const CODE_A = 'aaaa1111bbbb';
        const CODE_B = 'cccc2222dddd';
        let resolveA: (value: unknown) => void = () => {};
        const pendingA = new Promise((resolve) => {
            resolveA = resolve;
        });
        directionApiMocks.startPublicDirectionSession.mockImplementation((code: string) =>
            code === CODE_A
                ? pendingA
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

        // A is still pending — navigate to B; B boots first
        fireEvent.click(screen.getByTestId('nav-to-b'));
        await screen.findByText('Направление Б');
        // NOW the slow A response arrives out of order
        await React.act(async () => {
            resolveA({
                ...DIRECTION_START_RESPONSE,
                session_token: 'session-A',
                direction: { ...DIRECTION_START_RESPONSE.direction, title: 'Направление А', public_code: CODE_A },
            });
        });
        // the page/session MUST still belong to B
        expect(screen.getByText('Направление Б')).toBeTruthy();
        expect(screen.queryByText('Направление А')).toBeNull();
        // a submit under B's URL uses B's session, not the late A session
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), { target: { value: 'Пациент Б' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        await React.act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
        });
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].session_token).toBe('session-B');
    });

    it('PIN 20 (red on 569d15f5): a LATE complete answer for A never renders A\'s ticket under /q/B', async () => {
        const CODE_A = 'aaaa1111bbbb';
        const CODE_B = 'cccc2222dddd';
        let resolveStartA: (value: unknown) => void = () => {};
        let resolveCompleteA: (value: unknown) => void = () => {};
        const pendingStartA = new Promise((resolve) => {
            resolveStartA = resolve;
        });
        const pendingCompleteA = new Promise((resolve) => {
            resolveCompleteA = resolve;
        });
        directionApiMocks.startPublicDirectionSession.mockImplementation((code: string) =>
            code === CODE_A
                ? pendingStartA
                : Promise.resolve({
                      ...DIRECTION_START_RESPONSE,
                      session_token: 'session-B',
                      direction: { ...DIRECTION_START_RESPONSE.direction, title: 'Направление Б', public_code: CODE_B },
                  }),
        );
        queueApiMocks.completeQueueJoinSession.mockReturnValue(pendingCompleteA as never);

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

        // A's START resolves (reaching the form), the COMPLETE stays pending
        await React.act(async () => {
            resolveStartA({
                ...DIRECTION_START_RESPONSE,
                session_token: 'session-A',
                direction: { ...DIRECTION_START_RESPONSE.direction, title: 'Направление А', public_code: CODE_A },
            });
        });
        await screen.findByText('Направление А');
        // fill A's form and submit — complete(A) stays pending
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), { target: { value: 'Пациент А' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        await React.act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
        });
        // navigate to B while A's complete is still in flight; B boots
        fireEvent.click(screen.getByTestId('nav-to-b'));
        await screen.findByText('Направление Б');
        // the LATE A complete resolves — its ticket must NOT render under /q/B
        await React.act(async () => {
            resolveCompleteA(COMPLETE_MULTI_RESPONSE);
        });
        await React.act(async () => {});
        expect(screen.getByText('Направление Б')).toBeTruthy();
        expect(screen.queryByText(/ваш номер/i)).toBeNull();
        expect(screen.queryByText('№3')).toBeNull();
    });

    it('PIN 25 (red on 569d15f5): «перед вами» uses the backend queue_length — 100/0 shows 0, never 99', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockResolvedValue({
            ...COMPLETE_MULTI_RESPONSE,
            entries: [
                {
                    specialist_id: 7,
                    queue_entry_id: 101,
                    queue_number: 100,
                    duplicate: false,
                    queue_length: 0,
                    estimated_wait_time: 0,
                    specialist_name: 'Все специалисты',
                    department: 'qdir:lab-key',
                },
            ],
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(screen.getByText(/ваш номер/i)).toBeTruthy();
        });
        expect(screen.getByText('№100')).toBeTruthy();
        // the LIVE waiting count (0), not ticket-number − 1 (99)
        expect(screen.getByText('0 к.')).toBeTruthy();
        expect(screen.queryByText('99 к.')).toBeNull();
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

    it('PIN 26 (round-3 P1): a lost complete response NEVER auto-renews — the retry reuses the SAME session', async () => {
        // Date-only fake timers: the retry must happen AFTER the locally
        // known expiry (repro: network error → time passes expires_at →
        // resubmit). Only Date is faked — promises/waitFor stay real.
        vi.useFakeTimers({ toFake: ['Date'] });
        try {
            directionApiMocks.startPublicDirectionSession
                .mockResolvedValueOnce({
                    ...DIRECTION_START_RESPONSE,
                    session_token: 'session-X',
                    expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
                })
                // a WOULD-BE renewal must never fire — a distinct token if it does
                .mockResolvedValue({
                    ...DIRECTION_START_RESPONSE,
                    session_token: 'session-Y',
                    expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
                });
            queueApiMocks.completeQueueJoinSession
                .mockRejectedValueOnce({ response: { status: 0 } }) // network class: response lost
                .mockResolvedValue(COMPLETE_MULTI_RESPONSE);
            renderDirectionRoute();
            await screen.findByText(/заполните форму/i);
            await fillAndSubmit();
            await waitFor(() => {
                expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
            });
            // RQ-10 honesty: the lost response is flagged as result-unknown
            await screen.findByText(/результат отправки неизвестен/i);
            // time moves past expires_at
            vi.setSystemTime(Date.now() + 15 * 60_000);
            await React.act(async () => {
                fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
            });
            await waitFor(() => {
                expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(2);
            });
            // no NEW session was minted: the boot start is still the only one
            expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
            // the retry reused the SAME (possibly consumed) session — a safe
            // server-side reconcile, never a second business attempt
            expect(queueApiMocks.completeQueueJoinSession.mock.calls[1][0].session_token).toBe('session-X');
        } finally {
            vi.useRealTimers();
        }
    });

    it('PIN 27 (round-3 P1): a legacy ?token= never hijacks the direction draft identity — no PHI across directions', async () => {
        const CODE_A = 'aaaa1111bbbb';
        const CODE_B = 'cccc2222dddd';
        directionApiMocks.startPublicDirectionSession.mockImplementation((code: string) =>
            Promise.resolve({
                ...DIRECTION_START_RESPONSE,
                session_token: code === CODE_A ? 'session-A' : 'session-B',
                direction: {
                    ...DIRECTION_START_RESPONSE.direction,
                    title: code === CODE_A ? 'Направление А' : 'Направление Б',
                    public_code: code,
                },
            }),
        );
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);

        function NavigateToB() {
            const navigate = useNavigate();
            return (
                <button type="button" data-testid="nav-to-b" onClick={() => navigate(`/q/${CODE_B}?token=shared`)}>
                    go-b
                </button>
            );
        }

        render(
            <React.StrictMode>
                <MemoryRouter initialEntries={[`/q/${CODE_A}?token=shared`]}>
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

        // patient A types PHI under /q/A?token=shared
        await screen.findByText('Направление А');
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), { target: { value: 'Пациент А' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        // SPA transition to /q/B carrying the SAME legacy token
        fireEvent.click(screen.getByTestId('nav-to-b'));
        await screen.findByText('Направление Б');
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        // form B starts EMPTY — A's in-memory PHI must not survive the switch
        const nameInput = (await screen.findByLabelText(/фио пациента/i)) as HTMLInputElement;
        expect(nameInput.value).toBe('');
        // no token-keyed draft exists in either store — the legacy query
        // never becomes the draft identity of a permanent address
        expect(window.sessionStorage.getItem('queue_join_form_shared')).toBeNull();
        expect(window.localStorage.getItem('queue_join_form_shared')).toBeNull();
        expect(window.sessionStorage.getItem(`queue_join_form_qdir_${CODE_A}`)).toBeNull();
        // B's own submit carries only B's data under B's session
        fireEvent.change(nameInput, { target: { value: 'Пациент Б' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        await React.act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
        });
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].patient_name).toBe('Пациент Б');
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].session_token).toBe('session-B');
    });

    it('PIN 28 (round-3 P1): a double-click performs exactly ONE renewal and ONE complete', async () => {
        directionApiMocks.startPublicDirectionSession
            .mockResolvedValueOnce({
                ...DIRECTION_START_RESPONSE,
                session_token: 'expired-token',
                expires_at: new Date(Date.now() - 60_000).toISOString(), // expired at submit time
            })
            .mockResolvedValue({
                ...DIRECTION_START_RESPONSE,
                session_token: 'fresh-token',
                expires_at: new Date(Date.now() + 600_000).toISOString(),
            });
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        fireEvent.change(screen.getByLabelText(/фио пациента/i), { target: { value: 'Тест Пациент' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        // two FAST clicks inside one act — the second must hit the attempt
        // lock (the disabled attribute alone cannot protect the submit)
        await React.act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
        });
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalled();
        });
        // boot start + exactly ONE transparent renewal
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(2);
        // exactly ONE business complete
        expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        expect(queueApiMocks.completeQueueJoinSession.mock.calls[0][0].session_token).toBe('fresh-token');
    });

    it('PIN 29 (round-3 P1): the submit lock is epoch-scoped — a hung A neither blocks nor unlocks B', async () => {
        const CODE_A = 'aaaa1111bbbb';
        const CODE_B = 'cccc2222dddd';
        directionApiMocks.startPublicDirectionSession.mockImplementation((code: string) =>
            Promise.resolve({
                ...DIRECTION_START_RESPONSE,
                session_token: code === CODE_A ? 'session-A' : 'session-B',
                direction: {
                    ...DIRECTION_START_RESPONSE.direction,
                    title: code === CODE_A ? 'Направление А' : 'Направление Б',
                    public_code: code,
                },
            }),
        );
        let resolveCompleteA: (value: unknown) => void = () => {};
        const pendingCompleteA = new Promise((resolve) => {
            resolveCompleteA = resolve;
        });
        queueApiMocks.completeQueueJoinSession.mockImplementation((body: { session_token: string }) =>
            body.session_token === 'session-A'
                ? pendingCompleteA
                : new Promise(() => {}), // B's complete stays in flight
        );

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

        await screen.findByText('Направление А');
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), { target: { value: 'Пациент А' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        await React.act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /присоединиться/i }));
        });
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        });
        // A's complete hangs → navigate to B while it is in flight
        fireEvent.click(screen.getByTestId('nav-to-b'));
        await screen.findByText('Направление Б');
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        // (i) B's submit is AVAILABLE — the hung A must not keep it disabled
        const submitB = screen.getByRole('button', { name: /присоедин/i }) as HTMLButtonElement;
        expect(submitB.disabled).toBe(false);
        // (ii) B's own attempt starts
        fireEvent.change(screen.getByLabelText(/фио пациента/i), { target: { value: 'Пациент Б' } });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '+998 (90) 123-45-67' } });
        await React.act(async () => {
            fireEvent.click(submitB);
        });
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(2);
        });
        expect(submitB.disabled).toBe(true);
        // (iii) the LATE resolution of A's complete must not unlock B's button
        await React.act(async () => {
            resolveCompleteA(COMPLETE_MULTI_RESPONSE);
        });
        await React.act(async () => {});
        expect(submitB.disabled).toBe(true);
        // and A's late ticket never renders under /q/B
        expect(screen.queryByText(/ваш номер/i)).toBeNull();
    });

    it('PIN 30 (round-5 P1-1): nothing draft-like survives remounts — the device is left clean every time', async () => {
        window.sessionStorage.setItem(
            'queue_join_form_qdir_abcd1234efgh',
            JSON.stringify(draftEnvelope('Ожидающий Пациент', '+998 (90) 444-55-66')),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        const first = renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        // first boot already discarded the legacy draft: empty form, no banner
        await screen.findByLabelText(/фио пациента/i);
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
        first.unmount();
        // a reload / crash / second visit — the same clean state, and the
        // typed context does NOT reappear (nothing was stored)
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        expect((screen.getByLabelText(/фио пациента/i) as HTMLInputElement).value).toBe('');
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
    });

    it('PIN 32 (round-5 P1-1): the owner-verification challenge is GONE — an anonymous shared device neither stores nor reveals PHI', async () => {
        window.sessionStorage.setItem(
            'queue_join_form_qdir_abcd1234efgh',
            JSON.stringify(draftEnvelope('Пациент А')),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        await screen.findByLabelText(/фио пациента/i);
        // the round-4 challenge UI no longer exists — there is nothing to
        // verify ownership of (the family-shared phone made the 4-digit
        // tail worthless as a factor)
        expect(screen.queryByTestId('qj-draft-confirm')).toBeNull();
        expect(screen.queryByTestId('qj-draft-challenge-input')).toBeNull();
        expect(screen.queryByTestId('qj-draft-restore')).toBeNull();
        // the stored PHI was erased on boot; the form is empty for the
        // next person at the device
        expect(window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh')).toBeNull();
        expect((screen.getByLabelText(/фио пациента/i) as HTMLInputElement).value).toBe('');
    });

    it('PIN 32b (round-5 P1-1): sessionStorage under the direction key never contains patient PHI', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
            target: { value: 'Пациент С Секретным Именем' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: '+998 (90) 777-88-99' },
        });
        await React.act(async () => {});
        // fail-closed by construction: the shared permanent code keeps NO
        // patient data in ANY form (round-4 stored ciphertext-free PHI with
        // a 4-digit gate — reviewed as insufficient)
        const stored = window.sessionStorage.getItem('queue_join_form_qdir_abcd1234efgh');
        expect(stored).toBeNull();
        let phiLeaked = false;
        for (let i = 0; i < window.sessionStorage.length; i += 1) {
            const value = window.sessionStorage.getItem(window.sessionStorage.key(i) as string) ?? '';
            if (/Пациент С|998|777-88-99/.test(value)) {
                phiLeaked = true;
            }
        }
        expect(phiLeaked).toBe(false);
    });

    it('PIN 33 (round-4 P1-2): a lost complete response survives the reload — NO new session, the retry re-uses the ORIGINAL attempt identity', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValueOnce({
            response: { status: 502, data: { detail: 'bad gateway' } },
        });
        const first = renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        // the response was lost — the honest unknown banner is up
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        });
        expect(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh'),
        ).toBeTruthy();
        first.unmount();

        // THE RELOAD: the attempt state is hydrated, outcome UNKNOWN —
        // the mount must NOT mint a new session and must NOT run the
        // legacy flow; the reconcile panel engages instead.
        queueApiMocks.completeQueueJoinSession.mockResolvedValueOnce(COMPLETE_MULTI_RESPONSE);
        renderDirectionRoute();
        await screen.findByTestId('qj-reconcile-banner');
        // the public start-session was NOT called again (1 call from the
        // first mount only) — a new session would bypass the one-shot
        // complete contract for the still-unknown attempt
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();

        // the patient RE-TYPES their identity (the draft is gone — round-5
        // P1-1) and re-checks the attempt; the payload-bound replay accepts
        // the same identity (P1-3)
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
            target: { value: 'Тест Пациент' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: '+998 (90) 123-45-67' },
        });
        fireEvent.click(screen.getByTestId('qj-reconcile-check'));
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(2);
        });
        // the retry carries the ORIGINAL session token — the same attempt
        // identity, never a second business attempt under a new token
        const retryPayload = queueApiMocks.completeQueueJoinSession.mock.calls[1][0] as {
            session_token?: string;
        };
        expect(retryPayload.session_token).toBe('dir-session-token');
        // the joined session replayed the saved ticket → the success step
        await waitFor(() => {
            expect(screen.getByText(/ваш номер/i)).toBeTruthy();
        });
        // the attempt envelope is consumed
        expect(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh'),
        ).toBeNull();
    });

    it('PIN 34 (round-4 P1-2): a non-canonical (uppercase) URL uses the canonical lowercase identity and replaces itself', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRouteWithNav('/q/ABCD1234EFGH');
        await screen.findByText(/заполните форму/i);
        // the start call used the CANONICAL code — the backend resolves
        // strip().lower(), and so must the client identity
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledWith('abcd1234efgh');
        // the URL was replaced with the canonical variant
        expect(lastQjPath).toBe('/q/abcd1234efgh');
    });

    it('PIN 34b (round-4 P1-2): an unknown attempt survives the case-alias navigation — no new session for /q/ABCD after /q/abcd', async () => {
        window.localStorage.setItem(
            `queue_join_attempt_qdir_${CANONICAL_CODE}`,
            JSON.stringify({
                ts: Date.now(),
                publicCode: CANONICAL_CODE,
                sessionToken: 'dir-session-token',
                profileId: 7,
                directionTitle: 'Лаборатория',
                completeAttempted: true,
                outcomeUnknown: true,
            }),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRouteWithNav(`/q/${CANONICAL_CODE}`);
        // unknown attempt → reconcile instead of an automatic start
        await screen.findByTestId('qj-reconcile-banner');
        expect(directionApiMocks.startPublicDirectionSession).not.toHaveBeenCalled();
        // navigating to the UPPERCASE alias of the SAME address must not
        // reset the guard or mint a session (the pre-fix second bypass)
        fireEvent.click(screen.getByTestId(`nav-/q/${CANONICAL_CODE.toUpperCase()}`));
        await React.act(async () => {});
        await screen.findByTestId('qj-reconcile-banner');
        expect(directionApiMocks.startPublicDirectionSession).not.toHaveBeenCalled();
        expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
    });

    it('PIN 35 (round-4 P2-1): a CONFIRMED pre-execution refusal offers the explicit start-over — a new session only after the deliberate action', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: {
                status: 400,
                data: { detail: { reason: 'join_session_expired', message: 'Сессия истекла' } },
            },
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        // the confirmed refusal surfaces the honest recovery offer
        await screen.findByTestId('qj-preexec-refusal');
        expect(screen.getByTestId('qj-start-over')).toBeTruthy();
        // no blind retry loop: the submit did not auto-renew anything
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        // the machine-reason refusal updated the persisted attempt outcome —
        // a reload boots a FRESH session safely (nothing was created)
        const attemptState = JSON.parse(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh') as string,
        );
        expect(attemptState.outcomeUnknown).toBe(false);

        // THE EXPLICIT START-OVER: mints a new session on the deliberate click
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);
        fireEvent.click(screen.getByTestId('qj-start-over'));
        await waitFor(() => {
            expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(2);
        });
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit('Второй Пациент');
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(2);
        });
        await waitFor(() => {
            expect(screen.getByText(/ваш номер/i)).toBeTruthy();
        });
    });

    it('PIN 38 (round-5 P1-4): a join_session_processing refusal keeps the outcome UNKNOWN — no start-over on the reconcile panel', async () => {
        // The first bypass from the review: the processing claim (400 with a
        // machine reason) is NOT a network error and NOT a proven
        // pre-execution refusal — a parallel claim may still commit the
        // ticket. Fail-closed: UNKNOWN stays, the reconcile panel offers
        // ONLY the server-verdict check (the start-over escape is gone).
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: {
                status: 400,
                data: {
                    detail: {
                        reason: 'join_session_processing',
                        message: 'Сессия обрабатывается',
                    },
                },
            },
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        });
        // the honest-unknown hint is up right after the refused submit
        await screen.findByText(/результат отправки неизвестен/i);
        // reload: the UNKNOWN attempt hydrates the reconcile panel —
        // with ONLY the check button, never a start-over
        renderDirectionRoute();
        await screen.findByTestId('qj-reconcile-banner');
        expect(screen.getByTestId('qj-reconcile-check')).toBeTruthy();
        expect(screen.queryByTestId('qj-reconcile-start-over')).toBeNull();
        // the persisted attempt state stays UNKNOWN
        const attemptState = JSON.parse(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh') as string,
        );
        expect(attemptState.outcomeUnknown).toBe(true);
    });

    it('PIN 38b (round-5 P1-4): an undescribed 500 after submit stays UNKNOWN — the attempt may be committed', async () => {
        // The second bypass: an HTTP 500 can arrive AFTER the business
        // commit (post-commit side effects) — marking it «known» invited a
        // duplicating fresh session. Fail-closed: UNKNOWN.
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: { status: 500, data: { detail: 'Internal server error' } },
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        });
        await screen.findByText(/результат отправки неизвестен/i);
        const attemptState = JSON.parse(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh') as string,
        );
        expect(attemptState.outcomeUnknown).toBe(true);
        // no start-over escape anywhere in the unknown state
        expect(screen.queryByTestId('qj-reconcile-start-over')).toBeNull();
        expect(screen.queryByTestId('qj-start-over')).toBeNull();
    });

    it('PIN 39 (round-5 P1-3): a payload-bound replay conflict swaps the panel to the honest mismatch message with the start-over', async () => {
        // The review's wrong-patient scenario: the patient retypes a
        // DIFFERENT identity and re-checks the attempt — the server
        // refuses with join_session_payload_mismatch (409). The reconcile
        // panel is replaced by the conflict message; the start-over is
        // available (decisive verdict) and mints a fresh session only on
        // the deliberate click.
        // Pre-seed the UNKNOWN attempt (as a lost response would).
        window.localStorage.setItem(
            `queue_join_attempt_qdir_${CANONICAL_CODE}`,
            JSON.stringify({
                ts: Date.now(),
                publicCode: CANONICAL_CODE,
                sessionToken: 'dir-session-token',
                profileId: 7,
                directionTitle: 'Лаборатория',
                completeAttempted: true,
                outcomeUnknown: true,
            }),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: {
                status: 409,
                data: {
                    detail: {
                        reason: 'join_session_payload_mismatch',
                        message: 'Попытка принадлежит другому набору данных',
                    },
                },
            },
        });
        renderDirectionRoute();
        await screen.findByTestId('qj-reconcile-banner');
        // the reconcile boot lands directly on the form (no info step) —
        // the patient re-types a DIFFERENT identity and re-checks
        fireEvent.change(await screen.findByLabelText(/фио пациента/i), {
            target: { value: 'Другой Пациент' },
        });
        fireEvent.change(screen.getByLabelText(/номер телефона/i), {
            target: { value: '+998 (90) 123-45-67' },
        });
        fireEvent.click(screen.getByTestId('qj-reconcile-check'));
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        });
        // the conflict panel replaces the reconcile panel
        await screen.findByTestId('qj-payload-mismatch');
        // decisive → the attempt state is consumed (a reload boots fresh)
        expect(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh'),
        ).toBeNull();
        // the deliberate start-over mints a NEW session (a different token)
        queueApiMocks.completeQueueJoinSession.mockResolvedValue(COMPLETE_MULTI_RESPONSE);
        directionApiMocks.startPublicDirectionSession.mockResolvedValue({
            ...DIRECTION_START_RESPONSE,
            session_token: 'dir-session-token-2',
        });
        fireEvent.click(screen.getAllByTestId('qj-reconcile-start-over')[0]);
        await waitFor(() => {
            expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        });
        await screen.findByText(/заполните форму/i);
        // and the retry submit carries the NEW attempt identity — the
        // previous attempt's token was never re-used
        await fillAndSubmit('Другой Пациент');
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(2);
        });
        const secondPayload = queueApiMocks.completeQueueJoinSession.mock.calls[1][0] as {
            session_token?: string;
        };
        expect(secondPayload.session_token).toBe('dir-session-token-2');
    });
    // ── Round-6 (PR #3362 review, P1-3 + P2-1) ───────────────────────────

    it('PIN 40 (round-6 P1-3): the attempt horizon outruns the fixed 24h TTL — a tomorrow-targeting attempt stays recoverable past submit+24h', async () => {
        // The review scenario: the session started after the cutoff targets
        // TOMORROW; a fixed 24h TTL dropped the reconcile identity while the
        // target queue-day was still running. The server horizon decides now.
        const ts = Date.now() - 25 * 60 * 60 * 1000; // older than the fixed TTL
        const horizon = new Date(Date.now() + 30 * 60 * 60 * 1000).toISOString();
        window.localStorage.setItem(
            `queue_join_attempt_qdir_${CANONICAL_CODE}`,
            JSON.stringify({
                ts,
                publicCode: CANONICAL_CODE,
                sessionToken: 'dir-session-token',
                profileId: 7,
                directionTitle: 'Лаборатория',
                completeAttempted: true,
                outcomeUnknown: true,
                attemptExpiresAt: horizon,
            }),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        // the attempt is STILL hydratable — the reconcile panel comes up,
        // no fresh session is minted behind the patient's back
        await screen.findByTestId('qj-reconcile-banner');
        expect(directionApiMocks.startPublicDirectionSession).not.toHaveBeenCalled();
    });

    it('PIN 40b (round-6 P1-3): an attempt past its horizon is dropped — a fresh start becomes possible again', async () => {
        window.localStorage.setItem(
            `queue_join_attempt_qdir_${CANONICAL_CODE}`,
            JSON.stringify({
                ts: Date.now(),
                publicCode: CANONICAL_CODE,
                sessionToken: 'dir-session-token',
                profileId: 7,
                directionTitle: 'Лаборатория',
                completeAttempted: true,
                outcomeUnknown: true,
                attemptExpiresAt: new Date(Date.now() - 60 * 1000).toISOString(),
            }),
        );
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        renderDirectionRoute();
        // the horizon is over → the identity is gone → the normal start runs
        await screen.findByText(/заполните форму/i);
        expect(directionApiMocks.startPublicDirectionSession).toHaveBeenCalledTimes(1);
        expect(
            window.localStorage.getItem(`queue_join_attempt_qdir_${CANONICAL_CODE}`),
        ).toBeNull();
    });

    it('PIN 41 (round-6 P2-1): a rollback-proven join_session_not_executed refusal offers the honest start-over instead of the UNKNOWN loop', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: {
                status: 400,
                data: {
                    detail: {
                        reason: 'join_session_not_executed',
                        message: 'Очередь заполнена',
                        details: [{ specialist_id: 7, error: 'Очередь заполнена' }],
                    },
                },
            },
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        // the PROVEN refusal (rollback confirmed) → the explicit start-over
        await screen.findByTestId('qj-preexec-refusal');
        expect(screen.getByTestId('qj-start-over')).toBeTruthy();
        // the outcome is KNOWN — no UNKNOWN reconcile loop on reload
        const attemptState = JSON.parse(
            window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh') as string,
        );
        expect(attemptState.outcomeUnknown).toBe(false);
    });

    it('PIN 42 (round-6 P1-3): the attempt envelope is written to localStorage and survives a tab close', async () => {
        directionApiMocks.startPublicDirectionSession.mockResolvedValue(DIRECTION_START_RESPONSE);
        queueApiMocks.completeQueueJoinSession.mockRejectedValue({
            response: { status: 0 },
        });
        renderDirectionRoute();
        await screen.findByText(/заполните форму/i);
        await fillAndSubmit();
        await waitFor(() => {
            expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledTimes(1);
        });
        // written to localStorage (tab-close proof)…
        const stored = window.localStorage.getItem('queue_join_attempt_qdir_abcd1234efgh');
        expect(stored).not.toBeNull();
        const envelope = JSON.parse(stored as string);
        expect(envelope.outcomeUnknown).toBe(true);
        // …carries the server horizon when the start provided one…
        expect(envelope.attemptExpiresAt).toBeTruthy();
        // …and nothing PHI-shaped ever entered the envelope.
        expect(JSON.stringify(envelope)).not.toMatch(/пациент|patient_name|phone.*\d{3}/i);
    });
});

