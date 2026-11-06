/**
 * QR-FE-028/029/030 (audit 3886, ledger group 1 — QR patient join):
 *
 * 028: legacy /queue/join/:token accepts late cross-token responses — a
 *      deferred info/start of token A resolves AFTER the user switched to
 *      token B on the same mounted route and overwrites B's live
 *      UI/session with A's context (no epoch/ownership guard on the
 *      legacy path; the direction path already has directionEpochRef).
 * 029: the legacy UNKNOWN envelope always persists attemptExpiresAt:
 *      null, dropping the backend attempt_expires_at (target queue-day +
 *      grace) for the SAME /queue/join/start response — a next-day QR
 *      attempt is discarded after the fixed 24h TTL fallback.
 * 030: an unguarded localStorage.setItem('lastQueueJoin') runs AFTER the
 *      recovery envelope is deleted and BEFORE setStep('success'); a
 *      storage quota/security failure turns a committed successful join
 *      into an error/UNKNOWN screen.
 *
 * Red-first: on pre-fix source every test below fails for the exact
 * documented reason; each is unrolled in the PR body evidence table.
 */
import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const queueApiMocks = vi.hoisted(() => ({
  fetchQrTokenInfo: vi.fn(),
  startQueueJoinSession: vi.fn(),
  completeQueueJoinSession: vi.fn(),
  probeQueueJoinSession: vi.fn(),
}));

vi.mock('../../api/queue', () => queueApiMocks);

import QueueJoin from '../QueueJoin';

const TOKEN_A = 'legacy-qr-token-a';
const TOKEN_B = 'legacy-qr-token-b';

const SPECIALISTS_A = [
  { id: 6, specialty: 'cardio', specialty_display: 'Кардиолог Альфа' },
];
const SPECIALISTS_B = [
  { id: 9, specialty: 'derma', specialty_display: 'Дерматолог Бета' },
];

function tokenInfo(specialists: typeof SPECIALISTS_A, department: string) {
  return {
    queue_active: true,
    allowed: true,
    status: 'available',
    message: 'Запись доступна',
    queue_length: 2,
    department_name: department,
    specialist_name: specialists[0].specialty_display,
    target_date: '2026-11-05',
    is_clinic_wide: true,
    selectable_specialists: specialists,
  };
}

/** In-route navigation control: switches the mounted route to another
 * legacy token WITHOUT remounting the QueueJoin route element. */
function NavTo({ to }: { to: string }) {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(to)}>
      switch-token
    </button>
  );
}

function renderQueueJoin(initialToken: string) {
  return render(
    <MemoryRouter initialEntries={[`/queue/join/${initialToken}`]}>
      {/* In-route switch control: mounted NEXT to the route outlet so it
       * stays clickable while QueueJoin shows its loading screen. */}
      <NavTo
        to={`/queue/join/${
          initialToken === TOKEN_A ? TOKEN_B : TOKEN_A
        }`}
      />
      <Routes>
        <Route path="/queue/join/:token" element={<QueueJoin />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Drives the shared clinic-wide flow up to a submitted form. */
async function driveToSubmittedForm() {
  fireEvent.click(await screen.findByLabelText(/дерматолог бета/i));
  fireEvent.click(screen.getByRole('button', { name: /продолжить/i }));
  const nameInput = await screen.findByLabelText(/фио/i);
  fireEvent.change(nameInput, { target: { value: 'Тестов Тест Тестович' } });
  fireEvent.change(screen.getByLabelText(/номер телефона/i), { target: { value: '998901234567' } });
  await act(async () => {
    fireEvent.submit(nameInput.closest('form') ?? nameInput);
  });
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

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  queueApiMocks.fetchQrTokenInfo.mockReset();
  queueApiMocks.startQueueJoinSession.mockReset();
  queueApiMocks.completeQueueJoinSession.mockReset();
  queueApiMocks.probeQueueJoinSession.mockReset();
});

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

describe('QR-FE-028: a late legacy A response must not overwrite token B', () => {
  it('deferred A info/start is dropped after the in-route switch to B', async () => {
    const infoA = deferred<ReturnType<typeof tokenInfo>>();
    // A hangs; B answers immediately with its own context.
    queueApiMocks.fetchQrTokenInfo.mockImplementation((token: string) =>
      token === TOKEN_A ? infoA.promise : Promise.resolve(tokenInfo(SPECIALISTS_B, 'Отделение Беты')),
    );
    queueApiMocks.startQueueJoinSession.mockImplementation((token: string) =>
      Promise.resolve({
        session_token: `session-${token}`,
        queue_info: { is_clinic_wide: true, selectable_specialists: token === TOKEN_A ? SPECIALISTS_A : SPECIALISTS_B },
      }),
    );

    renderQueueJoin(TOKEN_A);

    // Switch to B while A's token-info is still in flight.
    fireEvent.click(await screen.findByRole('button', { name: 'switch-token' }));

    // B boot completed: B's specialist is on screen.
    expect(await screen.findByLabelText(/дерматолог бета/i)).toBeInTheDocument();
    await act(async () => {
      await Promise.resolve();
    });
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledTimes(1);
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledWith(TOKEN_B);

    // The late A info/start resolves now — it must NOT paint A over B.
    await act(async () => {
      infoA.resolve(tokenInfo(SPECIALISTS_A, 'Отделение Альфы'));
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    // B's context is still what the user sees…
    expect(screen.getByLabelText(/дерматолог бета/i)).toBeInTheDocument();
    // …and NO A-scoped session was ever minted or adopted.
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText(/кардиолог альфа/i)).toBeNull();
  });

  it('a token switch resets the previous token\u2019s reconcile guard — B still starts its session', async () => {
    // Token A has an outstanding UNKNOWN envelope: A's boot engages the
    // reconcile guard and skips A's auto-start.
    window.localStorage.setItem(
      `queue_join_attempt_qr_${TOKEN_A}__session-a`,
      JSON.stringify({
        ts: Date.now(),
        publicCode: TOKEN_A,
        sessionToken: 'session-a',
        profileId: null,
        directionTitle: null,
        completeAttempted: true,
        outcomeUnknown: true,
        attemptExpiresAt: null,
      }),
    );
    queueApiMocks.fetchQrTokenInfo.mockImplementation((token: string) =>
      token === TOKEN_A
        ? Promise.resolve(tokenInfo(SPECIALISTS_A, 'Отделение Альфы'))
        : Promise.resolve(tokenInfo(SPECIALISTS_B, 'Отделение Беты')),
    );
    queueApiMocks.startQueueJoinSession.mockImplementation((token: string) =>
      Promise.resolve({
        session_token: `session-${token}`,
        queue_info: { is_clinic_wide: true, selectable_specialists: token === TOKEN_A ? SPECIALISTS_A : SPECIALISTS_B },
      }),
    );

    renderQueueJoin(TOKEN_A);
    // A boots with its UNKNOWN envelope — no session minted for A.
    expect(await screen.findByLabelText(/кардиолог альфа/i)).toBeInTheDocument();
    await act(async () => {
      await Promise.resolve();
    });
    expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();

    // In-place switch to the FRESH token B (no envelope of its own):
    fireEvent.click(screen.getByRole('button', { name: 'switch-token' }));

    // B has no UNKNOWN envelope — its boot MUST mint B's own session
    // (pre-fix the stale reconcile guard of A suppressed B's start).
    expect(await screen.findByLabelText(/дерматолог бета/i)).toBeInTheDocument();
    await act(async () => {
      await Promise.resolve();
    });
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledTimes(1);
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledWith(TOKEN_B);
  });
});

describe('QR-FE-029: the legacy envelope keeps the server queue-day horizon', () => {
  it('submit persists attempt_expires_at from /queue/join/start, surviving past the 24h TTL fallback', async () => {
    // 48h server horizon: a legitimate next-day QR attempt window.
    const realNow = Date.now();
    const HORIZON = new Date(realNow + 48 * 60 * 60 * 1000).toISOString();
    queueApiMocks.fetchQrTokenInfo.mockResolvedValue(tokenInfo(SPECIALISTS_B, 'Отделение Беты'));
    queueApiMocks.startQueueJoinSession.mockResolvedValue({
      session_token: 'fresh-session-token',
      queue_info: { is_clinic_wide: true, selectable_specialists: SPECIALISTS_B },
      attempt_expires_at: HORIZON,
    });
    // The complete response is LOST — the exact UNKNOWN-precondition of
    // the recovery envelope. Deferred, never resolved in this mount.
    const lostComplete = deferred<Record<string, unknown>>();
    queueApiMocks.completeQueueJoinSession.mockReturnValue(lostComplete.promise as never);

    const view = renderQueueJoin(TOKEN_B);
    await driveToSubmittedForm();

    // The envelope must carry the SERVER horizon, not the null fallback.
    const raw = window.localStorage.getItem(`queue_join_attempt_qr_${TOKEN_B}__fresh-session-token`);
    expect(raw).not.toBeNull();
    const envelope = JSON.parse(raw as string) as { attemptExpiresAt: string | null };
    expect(envelope.attemptExpiresAt).toBe(HORIZON);

    // Reload AFTER the 24h fallback TTL but BEFORE the server horizon:
    // the original attempt identity must survive (no new session minted).
    const dateSpy = vi.spyOn(Date, 'now').mockReturnValue(realNow + 25 * 60 * 60 * 1000);
    view.unmount();
    renderQueueJoin(TOKEN_B);

    expect(await screen.findByLabelText(/дерматолог бета/i)).toBeInTheDocument();
    await act(async () => {
      await Promise.resolve();
    });
    // Boot with a live envelope must NOT mint a new session: the counter
    // stays at the FIRST boot's single start (a TTL-discarded envelope
    // would have minted a second one — the pre-fix red).
    expect(queueApiMocks.startQueueJoinSession).toHaveBeenCalledTimes(1);
    dateSpy.mockRestore();
  });
});

describe('QR-FE-030: a storage failure after success must not reclassify the join', () => {
  it('throwing lastQueueJoin persistence keeps the success screen and drops the envelope', async () => {
    queueApiMocks.fetchQrTokenInfo.mockResolvedValue(tokenInfo(SPECIALISTS_B, 'Отделение Беты'));
    queueApiMocks.startQueueJoinSession.mockResolvedValue({
      session_token: 'fresh-session-token',
      queue_info: { is_clinic_wide: true, selectable_specialists: SPECIALISTS_B },
    });
    queueApiMocks.completeQueueJoinSession.mockResolvedValue({
      success: true,
      queue_number: 7,
      queue_length: 3,
      estimated_wait_time: 15,
      specialist_name: 'Дерматолог Бета',
      department: 'Дерматология',
    });

    // The ONLY failing write is the nonclinical lastQueueJoin flag.
    const realSetItem = window.localStorage.setItem.bind(window.localStorage);
    let lastQueueJoinThrew = 0;
    Object.defineProperty(window.localStorage, 'setItem', {
      configurable: true,
      value: (key: string, value: string) => {
        if (key === 'lastQueueJoin') {
          lastQueueJoinThrew += 1;
          throw new DOMException('quota exceeded', 'QuotaExceededError');
        }
        realSetItem(key, value);
      },
    });

    try {
      renderQueueJoin(TOKEN_B);
      await driveToSubmittedForm();

      // The failure REALLY happened (not a vacuum run).
      expect(lastQueueJoinThrew).toBeGreaterThan(0);

      // The confirmed business result is still rendered as success…
      expect(await screen.findByText(/7/)).toBeInTheDocument();
      // …and the outcome was never reclassified as unknown/error.
      expect(window.localStorage.getItem(`queue_join_attempt_qr_${TOKEN_B}__fresh-session-token`)).toBeNull();
    } finally {
      Object.defineProperty(window.localStorage, 'setItem', {
        configurable: true,
        value: realSetItem,
      });
    }
  });
});
