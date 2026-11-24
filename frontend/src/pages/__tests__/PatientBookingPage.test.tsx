import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../api/client')>(),
  getAuthSessionGeneration: vi.fn(),
}));

vi.mock('../../api/publicBooking', async () => {
  const actual = await vi.importActual<typeof import('../../api/publicBooking')>('../../api/publicBooking');
  return {
    ...actual,
    getPublicBookingOptions: vi.fn(),
    getPublicBookingAvailability: vi.fn(),
    createPatientConfirmedPublicBookingAppointment: vi.fn(),
    createPatientPublicBookingRequest: vi.fn(),
    resubmitPatientPublicBookingRequest: vi.fn(),
  };
});

vi.mock('../../stores/auth', () => ({
  getState: vi.fn(() => ({ token: 'patient-token', profile: { role: 'Patient' } })),
}));

import { getAuthSessionGeneration } from '../../api/client';
import {
  clearPendingPublicBookingSelection,
  createPatientConfirmedPublicBookingAppointment,
  createPatientPublicBookingRequest,
  resubmitPatientPublicBookingRequest,
  getPendingPublicBookingLocale,
  getPublicBookingAvailability,
  getPublicBookingOptions,
  PUBLIC_BOOKING_SELECTION_TTL_MS,
  savePublicBookingSelection,
} from '../../api/publicBooking';
import { getState } from '../../stores/auth';
import PatientBookingPage from '../PatientBookingPage';

const mockedOptions = vi.mocked(getPublicBookingOptions);
const mockedAvailability = vi.mocked(getPublicBookingAvailability);
const mockedCreateAppointment = vi.mocked(createPatientConfirmedPublicBookingAppointment);
const mockedCreateRequest = vi.mocked(createPatientPublicBookingRequest);
const mockedResubmitRequest = vi.mocked(resubmitPatientPublicBookingRequest);
const mockedAuthState = vi.mocked(getState);
const mockedAuthSessionGeneration = vi.mocked(getAuthSessionGeneration);

const OPTIONS = {
  settings_version: 1,
  available: true,
  mode: 'registrar_request' as const,
  booking_horizon_days: 90,
  services: [{ slug: 'cardiology', name: 'Кардиология' }],
  doctors: [
    { slug: 'doctor-one', name: 'Врач Один' },
    { slug: 'doctor-two', name: 'Врач Два' },
  ],
  compatible_pairs: [{ service_slug: 'cardiology', doctor_slug: 'doctor-one' }],
};

function todayInTashkent() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function nextCalendarDay(date: string) {
  const next = new Date(`${date}T00:00:00.000Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return next.toISOString().slice(0, 10);
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

function renderPage(path = '/ru/booking', state?: unknown) {
  const LocationProbe = () => {
    const location = useLocation();
    return <output data-testid="current-path">{location.pathname + location.search}</output>;
  };
  return render(
    <MemoryRouter initialEntries={[state ? { pathname: path, state } : path]}>
      <LocationProbe />
      <PatientBookingPage />
    </MemoryRouter>,
  );
}

async function chooseSlot(locale: 'ru' | 'uz-Latn' = 'ru') {
  const labels = locale === 'ru'
    ? { service: 'Услуга', doctor: 'Врач', date: 'Дата' }
    : { service: 'Xizmat', doctor: 'Shifokor', date: 'Sana' };
  await screen.findByLabelText(labels.service);
  fireEvent.change(screen.getByLabelText(labels.service), { target: { value: 'cardiology' } });
  fireEvent.change(screen.getByLabelText(labels.doctor), { target: { value: 'doctor-one' } });
  fireEvent.change(screen.getByLabelText(labels.date), { target: { value: todayInTashkent() } });
  fireEvent.click(await screen.findByLabelText('09:00'));
}

describe('PatientBookingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAuthSessionGeneration.mockReturnValue(1);
    clearPendingPublicBookingSelection();
    mockedAuthState.mockReturnValue({ token: 'patient-token', profile: { role: 'Patient' } } as never);
    mockedOptions.mockResolvedValue(OPTIONS as never);
    mockedAvailability.mockImplementation(async ({ date }) => ({
      date,
      timezone: 'Asia/Tashkent',
      settings_version: 1,
      slots: ['09:00:00'],
    }) as never);
    mockedCreateRequest.mockResolvedValue({ id: 'request-id' } as never);
    mockedCreateAppointment.mockResolvedValue({
      id: 42,
      appointment_date: todayInTashkent(),
      appointment_time: '09:00:00',
      status: 'scheduled',
      timezone: 'Asia/Tashkent',
    } as never);
    mockedResubmitRequest.mockResolvedValue({ id: 'request-id', status: 'pending' } as never);
  });

  it.each([
    { path: '/ru/booking', locale: 'ru', serviceLabel: 'Услуга' },
    { path: '/booking', locale: 'uz-Latn', serviceLabel: 'Xizmat' },
  ])('sets $locale as the document language on $path and restores the previous language on unmount', async ({
    path, locale, serviceLabel,
  }) => {
    const root = document.documentElement;
    const originalLanguage = root.getAttribute('lang');
    root.setAttribute('lang', 'en');
    try {
      const page = renderPage(path);
      try {
        await screen.findByLabelText(serviceLabel);
        expect(root).toHaveAttribute('lang', locale);
      } finally {
        page.unmount();
      }
      expect(root).toHaveAttribute('lang', 'en');
    } finally {
      if (originalLanguage === null) root.removeAttribute('lang');
      else root.setAttribute('lang', originalLanguage);
    }
  });

  it('shows only service/doctor pairs approved by the current public policy', async () => {
    renderPage();
    await screen.findByLabelText('Услуга');
    fireEvent.change(screen.getByLabelText('Услуга'), { target: { value: 'cardiology' } });

    const doctorSelect = screen.getByLabelText('Врач') as HTMLSelectElement;
    expect(Array.from(doctorSelect.options).map((option) => option.value)).toEqual(['', 'doctor-one']);
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });

  it('revalidates settings and slots before submitting a non-reserving request', async () => {
    renderPage();
    await chooseSlot();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));

    await screen.findByRole('heading', { name: /Заявка отправлена регистратору/ });
    expect(mockedCreateRequest).toHaveBeenCalledTimes(1);
    const [body, key, sessionGeneration] = mockedCreateRequest.mock.calls[0];
    expect(body).toEqual({
      service_slug: 'cardiology',
      doctor_slug: 'doctor-one',
      appointment_date: todayInTashkent(),
      appointment_time: '09:00',
      expected_settings_version: 1,
    });
    expect(key).toMatch(/^[0-9a-f-]{36}$/i);
    expect(sessionGeneration).toBe(1);
    expect(body).not.toHaveProperty('patient_id');
    expect(screen.getByText(/не резервирует время/i)).toBeInTheDocument();
  });

  it('creates and confirms an appointment when the current policy selects that mode', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, mode: 'confirmed_appointment' } as never);
    renderPage();
    await chooseSlot();

    expect(screen.getByText(/после заключительной проверки свободного времени/i)).toBeInTheDocument();
    expect(screen.queryByText(/не резервирует время/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить запись' }));

    expect(await screen.findByRole('heading', { name: 'Запись подтверждена.' })).toBeInTheDocument();
    expect(mockedCreateAppointment).toHaveBeenCalledTimes(1);
    expect(mockedCreateAppointment.mock.calls[0][0]).toEqual({
      service_slug: 'cardiology',
      doctor_slug: 'doctor-one',
      appointment_date: todayInTashkent(),
      appointment_time: '09:00',
      expected_settings_version: 1,
    });
    expect(mockedCreateAppointment.mock.calls[0][1]).toMatch(/^[0-9a-f-]{36}$/i);
    expect(mockedCreateAppointment.mock.calls[0][2]).toBe(1);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
    expect(screen.getByText(/вы записаны на выбранное время/i)).toBeInTheDocument();
    expect(screen.getByText(/Врач Один/)).toBeInTheDocument();
  });

  it('explains the five future appointment limit returned by the server', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, mode: 'confirmed_appointment' } as never);
    mockedCreateAppointment.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: { code: 'booking_active_appointment_limit' } },
      },
    });
    renderPage();
    await chooseSlot();
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить запись' }));

    expect(await screen.findByText(/5 активных записей на будущие даты/i)).toBeInTheDocument();
    expect(mockedCreateAppointment).toHaveBeenCalledTimes(1);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('requires explicit acknowledgement before switching from request to confirmed appointment mode', async () => {
    renderPage();
    await chooseSlot();
    mockedOptions.mockResolvedValue({
      ...OPTIONS,
      mode: 'confirmed_appointment',
      settings_version: 2,
    } as never);
    mockedAvailability.mockImplementation(async ({ date }) => ({
      date,
      timezone: 'Asia/Tashkent',
      settings_version: 2,
      slots: ['09:00:00'],
    }) as never);

    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));

    expect(await screen.findByLabelText(/Я проверил/)).toBeInTheDocument();
    expect(mockedCreateAppointment).not.toHaveBeenCalled();
    expect(mockedCreateRequest).not.toHaveBeenCalled();

    fireEvent.click(screen.getByLabelText(/Я проверил/));
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить запись' }));

    await screen.findByRole('heading', { name: 'Запись подтверждена.' });
    expect(mockedCreateAppointment).toHaveBeenCalledTimes(1);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('retries an ambiguous confirmed booking with the exact same payload and key', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, mode: 'confirmed_appointment' } as never);
    mockedCreateAppointment.mockRejectedValueOnce({ isAxiosError: true, request: {} });
    renderPage();
    await chooseSlot();
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить запись' }));

    expect(await screen.findByText(/не удалось подтвердить результат/i)).toBeInTheDocument();
    const firstAttempt = mockedCreateAppointment.mock.calls[0];
    fireEvent.click(screen.getByRole('button', { name: 'Повторить ту же отправку' }));

    await screen.findByRole('heading', { name: 'Запись подтверждена.' });
    expect(mockedCreateAppointment).toHaveBeenCalledTimes(2);
    expect(mockedCreateAppointment.mock.calls[1]).toEqual(firstAttempt);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('resubmits a changed time against the existing request instead of creating another one', async () => {
    const requestId = '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab';
    mockedResubmitRequest.mockRejectedValueOnce({ isAxiosError: true, request: {} });
    renderPage('/ru/booking', {
      publicBookingResubmit: {
        requestId,
        expectedVersion: 4,
        serviceSlug: 'cardiology',
        doctorSlug: 'doctor-one',
      },
    });

    const date = todayInTashkent();
    fireEvent.change(await screen.findByLabelText('Дата'), { target: { value: date } });
    fireEvent.click(await screen.findByLabelText('09:00'));
    expect(screen.getByLabelText('Услуга')).toBeDisabled();
    expect(screen.getByLabelText('Врач')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить новое время' }));

    const retry = await screen.findByRole('button', { name: 'Повторить ту же отправку' });
    const firstAttempt = mockedResubmitRequest.mock.calls[0];
    fireEvent.click(retry);
    await screen.findByRole('heading', { name: /Новое время отправлено регистратору/ });
    expect(mockedResubmitRequest).toHaveBeenCalledTimes(2);
    expect(mockedResubmitRequest.mock.calls[0][0]).toBe(requestId);
    expect(mockedResubmitRequest.mock.calls[0][1]).toEqual({
      expected_version: 4,
      appointment_date: date,
      appointment_time: '09:00',
      expected_settings_version: 1,
    });
    expect(mockedResubmitRequest.mock.calls[0][2]).toMatch(/^[0-9a-f-]{36}$/i);
    expect(mockedResubmitRequest.mock.calls[0][3]).toBe(1);
    expect(mockedResubmitRequest.mock.calls[1]).toEqual(firstAttempt);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('retries the same uncertain resubmission after its handoff expires and the booking language changes', async () => {
    const requestId = '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab';
    const startedAt = Date.now();
    const clock = vi.spyOn(Date, 'now').mockReturnValue(startedAt);
    try {
      mockedResubmitRequest.mockRejectedValueOnce({ isAxiosError: true, request: {} });
      renderPage('/ru/booking', {
        publicBookingResubmitRequired: true,
        publicBookingLocale: 'ru',
        publicBookingResubmit: {
          requestId,
          expectedVersion: 4,
          serviceSlug: 'cardiology',
          doctorSlug: 'doctor-one',
          locale: 'ru',
          createdAt: startedAt,
        },
      });

      const date = todayInTashkent();
      fireEvent.change(await screen.findByLabelText('Дата'), { target: { value: date } });
      fireEvent.click(await screen.findByLabelText('09:00'));
      const submit = screen.getByRole('button', { name: 'Отправить новое время' });
      await waitFor(() => expect(submit).toBeEnabled());
      fireEvent.click(submit);

      expect(await screen.findByRole('button', { name: 'Повторить ту же отправку' })).toBeEnabled();
      expect(mockedResubmitRequest).toHaveBeenCalledTimes(1);
      const firstAttempt = mockedResubmitRequest.mock.calls[0];
      expect(firstAttempt).toEqual([requestId, {
        expected_version: 4,
        appointment_date: date,
        appointment_time: '09:00',
        expected_settings_version: 1,
      }, expect.stringMatching(/^[0-9a-f-]{36}$/i), 1]);

      clock.mockReturnValue(startedAt + PUBLIC_BOOKING_SELECTION_TTL_MS + 1);
      fireEvent.click(screen.getByRole('link', { name: 'O‘zbekcha' }));
      expect(screen.getByTestId('current-path')).toHaveTextContent(/^\/booking$/);

      const retry = await screen.findByRole('button', { name: 'Ayni yuborishni takrorlash' });
      expect(screen.getByRole('alert')).toHaveTextContent(/Yuborish natijasini tasdiqlab bo‘lmadi/);
      expect(screen.queryByRole('button', { name: 'Yangi vaqtni yuborish' })).not.toBeInTheDocument();
      expect(mockedResubmitRequest).toHaveBeenCalledTimes(1);
      fireEvent.click(retry);

      await screen.findByRole('heading', { name: /Yangi vaqt avvalgi so‘rovingiz doirasida/ });
      expect(mockedResubmitRequest).toHaveBeenCalledTimes(2);
      expect(mockedResubmitRequest.mock.calls[1]).toEqual(firstAttempt);
      expect(mockedCreateRequest).not.toHaveBeenCalled();
      expect(mockedCreateAppointment).not.toHaveBeenCalled();
    } finally {
      clock.mockRestore();
    }
  });

  it('does not resend a retained attempt after the patient session generation changes', async () => {
    mockedCreateRequest.mockRejectedValueOnce({ isAxiosError: true, request: {} });
    renderPage();
    await chooseSlot();

    const submit = screen.getByRole('button', { name: 'Отправить заявку' });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);
    const retry = await screen.findByRole('button', { name: 'Повторить ту же отправку' });
    expect(mockedCreateRequest).toHaveBeenCalledTimes(1);

    mockedAuthSessionGeneration.mockReturnValue(2);
    await act(async () => {
      fireEvent.click(retry);
    });

    expect(mockedCreateRequest).toHaveBeenCalledTimes(1);
    expect(mockedCreateAppointment).not.toHaveBeenCalled();
    expect(mockedResubmitRequest).not.toHaveBeenCalled();
    expect(screen.queryByRole('heading', { name: /Заявка отправлена регистратору/ })).not.toBeInTheDocument();
  });

  it('preserves the original request when the patient switches booking language', async () => {
    const requestId = '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab';
    renderPage('/ru/booking', {
      publicBookingResubmit: {
        requestId,
        expectedVersion: 4,
        serviceSlug: 'cardiology',
        doctorSlug: 'doctor-one',
      },
    });

    const switchLanguage = await screen.findByRole('link', { name: 'O‘zbekcha' });
    expect(document.documentElement).toHaveAttribute('lang', 'ru');
    expect(switchLanguage).toHaveAttribute('lang', 'uz-Latn');
    fireEvent.click(switchLanguage);
    const date = await screen.findByLabelText('Sana');
    expect(document.documentElement).toHaveAttribute('lang', 'uz-Latn');
    fireEvent.change(date, { target: { value: todayInTashkent() } });
    fireEvent.click(await screen.findByLabelText('09:00'));
    fireEvent.click(screen.getByRole('button', { name: 'Yangi vaqtni yuborish' }));

    await waitFor(() => expect(mockedResubmitRequest).toHaveBeenCalledTimes(1));
    expect(mockedResubmitRequest.mock.calls[0][0]).toBe(requestId);
    expect(mockedResubmitRequest.mock.calls[0][1].expected_version).toBe(4);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('fails closed when the resubmit handoff has expired', async () => {
    renderPage('/ru/booking', {
      publicBookingResubmitRequired: true,
      publicBookingLocale: 'ru',
      publicBookingResubmit: {
        requestId: '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab',
        expectedVersion: 4,
        serviceSlug: 'cardiology',
        doctorSlug: 'doctor-one',
        locale: 'ru',
        createdAt: Date.now() - PUBLIC_BOOKING_SELECTION_TTL_MS - 1,
      },
    });

    expect(await screen.findByText(/данные для изменения прежней заявки устарели или потеряны/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Услуга')).not.toBeInTheDocument();
    expect(mockedResubmitRequest).not.toHaveBeenCalled();
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('restores the same resubmit request from the short-lived tab handoff if route state is missing', async () => {
    const requestId = '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab';
    const date = todayInTashkent();
    savePublicBookingSelection({
      locale: 'ru',
      serviceSlug: 'cardiology',
      doctorSlug: 'doctor-one',
      date,
      time: '09:00',
      settingsVersion: 1,
      createdAt: Date.now(),
      resubmit: {
        requestId,
        expectedVersion: 5,
        serviceSlug: 'cardiology',
        doctorSlug: 'doctor-one',
      },
    });
    renderPage();

    const submitButton = await screen.findByRole('button', { name: 'Отправить новое время' });
    await waitFor(() => expect(submitButton).toBeEnabled());
    fireEvent.click(submitButton);
    await waitFor(() => expect(mockedResubmitRequest).toHaveBeenCalledTimes(1));
    await screen.findByRole('heading', { name: /Новое время отправлено регистратору/ });

    expect(mockedResubmitRequest).toHaveBeenCalledTimes(1);
    expect(mockedResubmitRequest.mock.calls[0][0]).toBe(requestId);
    expect(mockedResubmitRequest.mock.calls[0][1].expected_version).toBe(5);
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('shows patient-card guidance for the backend detail.reason response', async () => {
    mockedCreateRequest.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 404, data: { detail: { reason: 'patient_profile_required' } } },
    });
    renderPage();
    await chooseSlot();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));

    expect(await screen.findByText(/нужна собственная карточка пациента/i)).toBeInTheDocument();
  });

  it('ignores a manual availability response after the selected date changes', async () => {
    const staleRetry = deferred<Awaited<ReturnType<typeof getPublicBookingAvailability>>>();
    mockedAvailability
      .mockRejectedValueOnce(new Error('Initial availability failure'))
      .mockImplementationOnce(() => staleRetry.promise)
      .mockImplementationOnce(async ({ date }) => ({
        date,
        timezone: 'Asia/Tashkent',
        settings_version: 1,
        slots: ['10:00:00'],
      }) as never);
    renderPage();
    await screen.findByLabelText('Услуга');
    fireEvent.change(screen.getByLabelText('Услуга'), { target: { value: 'cardiology' } });
    fireEvent.change(screen.getByLabelText('Врач'), { target: { value: 'doctor-one' } });
    const originalDate = todayInTashkent();
    fireEvent.change(screen.getByLabelText('Дата'), { target: { value: originalDate } });
    const refreshButton = await screen.findByRole('button', { name: 'Проверить актуальные варианты' });
    fireEvent.click(refreshButton);
    expect(mockedAvailability).toHaveBeenCalledTimes(2);

    fireEvent.change(screen.getByLabelText('Дата'), { target: { value: nextCalendarDay(originalDate) } });
    expect(await screen.findByLabelText('10:00')).toBeInTheDocument();

    await act(async () => {
      staleRetry.resolve({
        date: originalDate,
        timezone: 'Asia/Tashkent',
        settings_version: 1,
        slots: ['09:30:00'],
      });
      await staleRetry.promise;
    });

    expect(screen.getByLabelText('10:00')).toBeInTheDocument();
    expect(screen.queryByLabelText('09:30')).not.toBeInTheDocument();
  });

  it('requires explicit reconfirmation when booking settings changed after selection', async () => {
    renderPage();
    await chooseSlot();
    mockedOptions.mockResolvedValue({ ...OPTIONS, settings_version: 2 } as never);
    mockedAvailability.mockImplementation(async ({ date }) => ({
      date,
      timezone: 'Asia/Tashkent',
      settings_version: 2,
      slots: ['09:00:00'],
    }) as never);
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));

    expect(await screen.findByLabelText(/Я проверил/)).toBeInTheDocument();
    expect(mockedCreateRequest).not.toHaveBeenCalled();
    const acknowledgement = screen.getByLabelText(/Я проверил/);
    fireEvent.click(acknowledgement);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Отправить заявку|Проверяем и отправляем/ })).toBeEnabled();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));

    await screen.findByRole('heading', { name: /Заявка отправлена регистратору/ });
    expect(mockedCreateRequest).toHaveBeenCalledTimes(1);
    expect(mockedCreateRequest.mock.calls[0][0].expected_settings_version).toBe(2);
  });

  it('retries an ambiguous send with the exact same body and idempotency key', async () => {
    mockedCreateRequest.mockRejectedValueOnce({ isAxiosError: true, request: {} });
    renderPage();
    await chooseSlot();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));

    const retry = await screen.findByRole('button', { name: 'Повторить ту же отправку' });
    expect(screen.getByLabelText('Услуга')).toBeDisabled();
    const firstAttempt = mockedCreateRequest.mock.calls[0];
    fireEvent.click(retry);
    await screen.findByRole('heading', { name: /Заявка отправлена регистратору/ });

    expect(mockedCreateRequest).toHaveBeenCalledTimes(2);
    expect(mockedCreateRequest.mock.calls[1]).toEqual(firstAttempt);
  });

  it('keeps an uncertain request locked through a local cooldown until the same attempt is retried', async () => {
    mockedCreateRequest
      .mockRejectedValueOnce({ isAxiosError: true, request: {} })
      .mockRejectedValueOnce({
        isAxiosError: true,
        clientRateLimit: true,
        response: { status: 429, data: { detail: 'Client-side cooldown active after HTTP 429' } },
      });
    renderPage();
    await chooseSlot();
    const submit = screen.getByRole('button', { name: 'Отправить заявку' });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);

    const retry = await screen.findByRole('button', { name: 'Повторить ту же отправку' });
    const firstAttempt = mockedCreateRequest.mock.calls[0];
    await act(async () => {
      fireEvent.click(retry);
    });

    expect(mockedCreateRequest).toHaveBeenCalledTimes(2);
    expect(mockedCreateRequest.mock.calls[1]).toEqual(firstAttempt);
    expect(screen.getByLabelText('Услуга')).toBeDisabled();
    expect(screen.getByLabelText('Дата')).toBeDisabled();
    expect(screen.getByText(/подождите и попробуйте позже/i)).toBeVisible();
    expect(screen.queryByRole('heading', { name: /Заявка отправлена регистратору/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Повторить ту же отправку' }));
    await screen.findByRole('heading', { name: /Заявка отправлена регистратору/ });
    expect(mockedCreateRequest).toHaveBeenCalledTimes(3);
    expect(mockedCreateRequest.mock.calls[2]).toEqual(firstAttempt);
    expect(mockedCreateAppointment).not.toHaveBeenCalled();
    expect(mockedResubmitRequest).not.toHaveBeenCalled();
  });

  it('keeps the selected route out of the URL while handing off to patient login', async () => {
    mockedAuthState.mockReturnValue({ token: null, profile: null } as never);
    renderPage('/booking');
    await chooseSlot('uz-Latn');
    fireEvent.click(screen.getByRole('button', { name: 'Bemor sifatida kirish' }));

    expect(screen.getByTestId('current-path')).toHaveTextContent('/patient/login');
    expect(screen.getByTestId('current-path')).not.toHaveTextContent('cardiology');
    expect(getPendingPublicBookingLocale()).toBe('uz-Latn');
  });

  it('fails closed when the server reports an unsupported booking mode', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, mode: 'future_mode' as never } as never);
    renderPage();
    expect(await screen.findByText(/Этот способ записи пока не подключён/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Услуга')).not.toBeInTheDocument();
    expect(mockedCreateRequest).not.toHaveBeenCalled();
    expect(mockedCreateAppointment).not.toHaveBeenCalled();
  });

  it('does not convert a resubmission into a new confirmed appointment', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, mode: 'confirmed_appointment' } as never);
    renderPage('/ru/booking', {
      publicBookingResubmit: {
        requestId: '3d7bdb53-c26e-46ed-81ec-9e7bdebd12ab',
        expectedVersion: 4,
        serviceSlug: 'cardiology',
        doctorSlug: 'doctor-one',
      },
    });

    expect(await screen.findByText(/этот вариант нельзя использовать для изменения прежней заявки/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Услуга')).not.toBeInTheDocument();
    expect(mockedCreateAppointment).not.toHaveBeenCalled();
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });

  it('fails closed when the server has not configured a booking horizon', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, booking_horizon_days: null } as never);
    renderPage();

    expect(await screen.findByRole('heading', { name: /Онлайн-запись сейчас недоступна/ })).toBeInTheDocument();
    expect(screen.queryByLabelText('Услуга')).not.toBeInTheDocument();
    expect(mockedAvailability).not.toHaveBeenCalled();
    expect(mockedCreateRequest).not.toHaveBeenCalled();
  });
});
