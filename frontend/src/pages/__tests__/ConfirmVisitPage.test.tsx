/**
 * ConfirmVisitPage — the destination of the PWA/SMS visit-confirmation
 * deep link /confirm-visit?token=… (PR 3390 review round, P1).
 *
 * Pins:
 *  - the public /confirm-visit route exists in the registry (the SMS
 *    invitation must not land on the /not-found wildcard);
 *  - the visit card loads via POST /visits/info with token in the body;
 *  - confirmation goes through POST /patient/visits/confirm and surfaces
 *    the same-day queue number;
 *  - terminal failures (404/400, incl. "already confirmed"/"expired")
 *    show the server reason on the invalid screen;
 *  - transient read failures offer explicit retry.
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router-dom';

const { apiMock } = vi.hoisted(() => ({
  apiMock: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  api: Object.assign(apiMock, {
    get: apiMock,
    post: apiMock,
  }),
}));

vi.mock('../../i18n/useTranslation', () => ({
  // The real hook creates a fresh t closure on every render.
  useTranslation: () => ({ t: (key: string) => key }),
}));

import ConfirmVisitPage from '../ConfirmVisitPage';
import { ROUTE_REGISTRY } from '../../routing/routeRegistry';

const ok = (data: unknown) => ({ status: 200, data });

// Synthetic fixtures only (AGENTS.md policy): 00-operator phone does not
// exist in the +998 numbering plan, names carry SYNTHETIC markers.
const VISIT_INFO = {
  success: true,
  visit_id: 7,
  status: 'pending_confirmation',
  patient_name: 'Синтетик SYNTHETIC-Testpatient',
  doctor_name: 'SYNTHETIC Test Doctor',
  visit_date: '2026-09-25',
  visit_time: '10:30',
  department: null,
  discount_mode: 'none',
  services: [
    {
      name: 'Приём SYNTHETIC-кардиолога',
      code: 'CARDIO',
      quantity: 1,
      price: 150000,
      total: 150000,
    },
  ],
  total_amount: 150000,
  currency: 'UZS',
  confirmation_expires_at: null,
  notes: null,
};

const CONFIRM_OK = {
  success: true,
  message: 'Визит подтвержден',
  visit_id: 7,
  status: 'confirmed',
  patient_name: 'Синтетик SYNTHETIC-Testpatient',
  visit_date: '2026-09-25',
  visit_time: '10:30',
  queue_numbers: [{ queue_tag: 'cardiology_common', number: 12, queue_id: 3 }],
  print_tickets: null,
};

const TOKEN = 'visit-confirm-token-123';

afterEach(() => {
  cleanup();
  apiMock.mockReset();
});

const renderAt = (search: string) =>
  render(
    <MemoryRouter initialEntries={[`/confirm-visit${search}`]}>
      <ConfirmVisitPage />
    </MemoryRouter>,
  );

describe('ConfirmVisitPage — /confirm-visit public screen', () => {
  it('PIN: registry carries the public /confirm-visit route wired to ConfirmVisitPage', () => {
    const route = ROUTE_REGISTRY.find((r) => r.id === 'confirm-visit') as
      | { path?: string; auth?: string; component?: string; nav?: boolean }
      | undefined;
    expect(route).toBeTruthy();
    expect(route?.path).toBe('/confirm-visit');
    expect(route?.auth).toBe('public');
    expect(route?.component).toBe('ConfirmVisitPage');
    expect(route?.nav).toBe(false);
  });

  it('loads one visit card via POST /visits/info without the token in the URL', async () => {
    apiMock.mockResolvedValueOnce(ok(VISIT_INFO));

    renderAt(`?token=${TOKEN}`);
    expect(screen.getByText('cv_loading')).toBeTruthy();

    expect(await screen.findByText('SYNTHETIC Test Doctor')).toBeTruthy();
    expect(screen.getByText('Синтетик SYNTHETIC-Testpatient')).toBeTruthy();
    expect(screen.getByText(/25\.09\.2026/)).toBeTruthy();
    expect(screen.getByText('Приём SYNTHETIC-кардиолога')).toBeTruthy();

    await act(async () => { await Promise.resolve(); });
    const infoCalls = apiMock.mock.calls.filter(([url]) => url === '/visits/info');
    expect(infoCalls).toHaveLength(1);
    expect(infoCalls[0]?.[1]).toEqual({ token: TOKEN });
    expect(apiMock.mock.calls.every(([url]) => !String(url).includes(TOKEN))).toBe(true);
  });

  it('confirms via POST /patient/visits/confirm and shows the queue number', async () => {
    apiMock
      .mockResolvedValueOnce(ok(VISIT_INFO))
      .mockResolvedValueOnce(ok(CONFIRM_OK));

    renderAt(`?token=${TOKEN}`);
    fireEvent.click(await screen.findByText('cv_confirm'));

    expect(await screen.findByText('Визит подтвержден')).toBeTruthy();
    const confirmCall = apiMock.mock.calls.find(([url]) =>
      String(url).includes('/patient/visits/confirm'),
    );
    expect(confirmCall?.[0]).toBe('/patient/visits/confirm');
    expect(confirmCall?.[1]).toEqual({ token: TOKEN });
    // Same-day confirmation issued a queue ticket.
    expect(screen.getByText('№12')).toBeTruthy();
    expect(screen.getByText('cardiology_common')).toBeTruthy();
  });

  it.each([
    [404, 'Визит не найден или уже подтвержден'],
    [400, 'Срок подтверждения истек'],
  ])('read failure %i is terminal, with no retry button', async (status, detail) => {
    apiMock.mockRejectedValueOnce({ response: { status, data: { detail } } });

    renderAt('?token=unknown-token-999');
    expect(await screen.findByText(detail)).toBeTruthy();
    expect(screen.queryByText('btn_retry')).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['rate limit', { response: { status: 429, data: { detail: 'Попробуйте позже' } } }],
    ['server failure', { response: { status: 503, data: { detail: 'Сервис временно недоступен' } } }],
    ['network failure', new Error('synthetic network failure')],
  ])('retry after %s reads the card once more', async (_cause, error) => {
    apiMock.mockRejectedValueOnce(error).mockResolvedValueOnce(ok(VISIT_INFO));

    renderAt(`?token=${TOKEN}`);
    fireEvent.click(await screen.findByText('btn_retry'));

    expect(await screen.findByText('SYNTHETIC Test Doctor')).toBeTruthy();
    expect(apiMock.mock.calls.filter(([url]) => url === '/visits/info')).toHaveLength(2);
    expect(apiMock.mock.calls.every(([url]) => !String(url).includes(TOKEN))).toBe(true);
  });

  it('ignores an old token response after navigating to a new token', async () => {
    const newToken = 'synthetic-new-token';
    let resolveFirst!: (value: ReturnType<typeof ok>) => void;
    const firstRead = new Promise<ReturnType<typeof ok>>((resolve) => {
      resolveFirst = resolve;
    });
    apiMock.mockReturnValueOnce(firstRead).mockResolvedValueOnce(ok({
      ...VISIT_INFO,
      doctor_name: 'SYNTHETIC Second Doctor',
    }));

    const NavigateToNextToken = () => {
      const navigate = useNavigate();
      return <button onClick={() => navigate(`?token=${newToken}`)}>next token</button>;
    };
    render(
      <MemoryRouter initialEntries={[`/confirm-visit?token=${TOKEN}`]}>
        <NavigateToNextToken />
        <ConfirmVisitPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText('next token'));
    expect(await screen.findByText('SYNTHETIC Second Doctor')).toBeTruthy();
    await act(async () => { resolveFirst(ok(VISIT_INFO)); });
    expect(screen.queryByText('SYNTHETIC Test Doctor')).toBeNull();
    await waitFor(() => expect(apiMock).toHaveBeenCalledTimes(2));
    expect(apiMock.mock.calls.map(([, body]) => body)).toEqual([
      { token: TOKEN }, { token: newToken },
    ]);
  });

  it('missing token — invalid state, no API call', () => {
    renderAt('');
    expect(screen.getByText('cv_invalid_link')).toBeTruthy();
    expect(apiMock).not.toHaveBeenCalled();
  });

  it('transient confirm failure (429) keeps the card and shows the server detail', async () => {
    apiMock
      .mockResolvedValueOnce(ok(VISIT_INFO))
      .mockRejectedValueOnce({
        response: { status: 429, data: { detail: 'Слишком много попыток' } },
      });

    renderAt(`?token=${TOKEN}`);
    fireEvent.click(await screen.findByText('cv_confirm'));

    expect(await screen.findByText('Слишком много попыток')).toBeTruthy();
    // The card is still on screen — the patient can retry.
    expect(screen.getByText('SYNTHETIC Test Doctor')).toBeTruthy();
  });

  it('terminal confirm failure (400, expired) moves to the invalid state with the reason', async () => {
    apiMock
      .mockResolvedValueOnce(ok(VISIT_INFO))
      .mockRejectedValueOnce({
        response: { status: 400, data: { detail: 'Срок подтверждения истек' } },
      });

    renderAt(`?token=${TOKEN}`);
    fireEvent.click(await screen.findByText('cv_confirm'));

    expect(await screen.findByText('Срок подтверждения истек')).toBeTruthy();
  });
});
