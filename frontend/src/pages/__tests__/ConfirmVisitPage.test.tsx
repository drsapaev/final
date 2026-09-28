/**
 * ConfirmVisitPage — the destination of the PWA/SMS visit-confirmation
 * deep link /confirm-visit#token=… (PR 3390 review round, P1).
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
import { BrowserRouter, MemoryRouter, useNavigate } from 'react-router-dom';

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
  window.history.replaceState(null, '', '/');
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
    expect(screen.getByText('final.cv_loading')).toBeTruthy();

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
    fireEvent.click(await screen.findByText('final.cv_confirm'));

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

  it('sends both public POSTs with credentials so the CSRF cookie travels cross-origin', async () => {
    // PR 3390 review P1: in the documented split-origin deployment
    // (VITE_API_BASE_URL, e.g. clinic.example.com + api.clinic.example.com)
    // the backend CSRFMiddleware requires BOTH the X-CSRF-Token header and
    // the csrf_token cookie. Without withCredentials the browser omits the
    // cookie on the cross-origin POST -> 403 missing_cookie. The bootstrap
    // GET already sends credentials; both page POSTs must do the same.
    apiMock
      .mockResolvedValueOnce(ok(VISIT_INFO))
      .mockResolvedValueOnce(ok(CONFIRM_OK));

    renderAt(`#token=${TOKEN}`);
    fireEvent.click(await screen.findByText('final.cv_confirm'));

    expect(await screen.findByText('Визит подтвержден')).toBeTruthy();
    const infoCall = apiMock.mock.calls.find(([url]) => url === '/visits/info');
    const confirmCall = apiMock.mock.calls.find(
      ([url]) => url === '/patient/visits/confirm',
    );
    expect(infoCall?.[2]).toEqual({ withCredentials: true });
    expect(confirmCall?.[2]).toEqual({ withCredentials: true });
  });

  it.each([
    [404, 'Визит не найден или уже подтвержден'],
    [400, 'Срок подтверждения истек'],
  ])('read failure %i is terminal, with no retry button', async (status, detail) => {
    apiMock.mockRejectedValueOnce({ response: { status, data: { detail } } });

    renderAt('?token=unknown-token-999');
    expect(await screen.findByText(detail)).toBeTruthy();
    expect(screen.queryByText('final.cv_btn_retry')).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['rate limit', { response: { status: 429, data: { detail: 'Попробуйте позже' } } }],
    ['server failure', { response: { status: 503, data: { detail: 'Сервис временно недоступен' } } }],
    ['network failure', new Error('synthetic network failure')],
  ])('retry after %s reads the card once more', async (_cause, error) => {
    apiMock.mockRejectedValueOnce(error).mockResolvedValueOnce(ok(VISIT_INFO));

    renderAt(`#token=${TOKEN}`);
    fireEvent.click(await screen.findByText('final.cv_btn_retry'));

    expect(await screen.findByText('SYNTHETIC Test Doctor')).toBeTruthy();
    expect(apiMock.mock.calls.filter(([url]) => url === '/visits/info')).toHaveLength(2);
    expect(apiMock.mock.calls.every(([url]) => !String(url).includes(TOKEN))).toBe(true);
  });

  it.each([
    ['fragment', `#token=${TOKEN}`, '/confirm-visit'],
    ['fragment with extra parameter', `#token=${TOKEN}&source=sms`, '/confirm-visit#source=sms'],
    ['legacy query', `?token=${TOKEN}&source=sms`, '/confirm-visit?source=sms'],
  ])('cleans the %s token from browser history before the first API call', async (
    _source, suffix, expectedPath,
  ) => {
    window.history.replaceState(null, '', `/confirm-visit${suffix}`);
    apiMock.mockImplementationOnce(async () => {
      expect(window.location.pathname + window.location.search + window.location.hash)
        .toBe(expectedPath);
      expect(window.location.href).not.toContain(TOKEN);
      return ok(VISIT_INFO);
    });

    render(<BrowserRouter><ConfirmVisitPage /></BrowserRouter>);

    expect(await screen.findByText('SYNTHETIC Test Doctor')).toBeTruthy();
    expect(apiMock).toHaveBeenCalledTimes(1);
    expect(apiMock.mock.calls[0]?.[1]).toEqual({ token: TOKEN });
  });

  it('an empty fragment token stays invalid even beside a legacy query token', () => {
    window.history.replaceState(null, '', `/confirm-visit?token=${TOKEN}#token=`);
    render(<BrowserRouter><ConfirmVisitPage /></BrowserRouter>);

    expect(screen.getByText('final.cv_invalid_link')).toBeTruthy();
    expect(window.location.pathname + window.location.search + window.location.hash)
      .toBe('/confirm-visit');
    expect(apiMock).not.toHaveBeenCalled();
  });

  it('keeps BrowserRouter token switches single-read and cleans each address', async () => {
    const nextToken = 'synthetic-next-fragment-token';
    window.history.replaceState(null, '', `/confirm-visit#token=${TOKEN}`);
    apiMock.mockImplementation(async (_url, body) => {
      expect(window.location.href).not.toContain('token=');
      return ok({
        ...VISIT_INFO,
        doctor_name: body.token === nextToken
          ? 'SYNTHETIC Second Doctor'
          : 'SYNTHETIC Test Doctor',
      });
    });
    const NavigateToNextToken = () => {
      const navigate = useNavigate();
      return (
        <button onClick={() => navigate(`/confirm-visit#token=${nextToken}`)}>
          next fragment
        </button>
      );
    };

    render(
      <BrowserRouter>
        <NavigateToNextToken />
        <ConfirmVisitPage />
      </BrowserRouter>,
    );
    expect(await screen.findByText('SYNTHETIC Test Doctor')).toBeTruthy();
    fireEvent.click(screen.getByText('next fragment'));
    expect(await screen.findByText('SYNTHETIC Second Doctor')).toBeTruthy();
    expect(window.location.pathname + window.location.search + window.location.hash)
      .toBe('/confirm-visit');
    expect(apiMock.mock.calls.map(([, body]) => body)).toEqual([
      { token: TOKEN }, { token: nextToken },
    ]);
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
    expect(screen.getByText('final.cv_invalid_link')).toBeTruthy();
    expect(apiMock).not.toHaveBeenCalled();
  });

  it('transient confirm failure (429) keeps the card and shows the server detail', async () => {
    apiMock
      .mockResolvedValueOnce(ok(VISIT_INFO))
      .mockRejectedValueOnce({
        response: { status: 429, data: { detail: 'Слишком много попыток' } },
      });

    renderAt(`?token=${TOKEN}`);
    fireEvent.click(await screen.findByText('final.cv_confirm'));

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
    fireEvent.click(await screen.findByText('final.cv_confirm'));

    expect(await screen.findByText('Срок подтверждения истек')).toBeTruthy();
  });
});
