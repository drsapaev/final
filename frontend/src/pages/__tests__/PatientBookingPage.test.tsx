import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/publicBooking', async () => {
  const actual = await vi.importActual<typeof import('../../api/publicBooking')>('../../api/publicBooking');
  return {
    ...actual,
    getPublicBookingOptions: vi.fn(),
    getPublicBookingAvailability: vi.fn(),
    createPatientPublicBookingRequest: vi.fn(),
    resubmitPatientPublicBookingRequest: vi.fn(),
  };
});

vi.mock('../../stores/auth', () => ({
  getState: vi.fn(() => ({ token: 'patient-token', profile: { role: 'Patient' } })),
}));

import {
  clearPendingPublicBookingSelection,
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
const mockedCreateRequest = vi.mocked(createPatientPublicBookingRequest);
const mockedResubmitRequest = vi.mocked(resubmitPatientPublicBookingRequest);
const mockedAuthState = vi.mocked(getState);

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
    mockedResubmitRequest.mockResolvedValue({ id: 'request-id', status: 'pending' } as never);
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
    const [body, key] = mockedCreateRequest.mock.calls[0];
    expect(body).toEqual({
      service_slug: 'cardiology',
      doctor_slug: 'doctor-one',
      appointment_date: todayInTashkent(),
      appointment_time: '09:00',
      expected_settings_version: 1,
    });
    expect(key).toMatch(/^[0-9a-f-]{36}$/i);
    expect(body).not.toHaveProperty('patient_id');
    expect(screen.getByText(/не резервирует время/i)).toBeInTheDocument();
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

    const retry = await screen.findByRole('button', { name: 'Повторно проверить ту же заявку' });
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
    expect(mockedResubmitRequest.mock.calls[1]).toEqual(firstAttempt);
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

    const retry = await screen.findByRole('button', { name: 'Повторно проверить ту же заявку' });
    expect(screen.getByLabelText('Услуга')).toBeDisabled();
    const firstAttempt = mockedCreateRequest.mock.calls[0];
    fireEvent.click(retry);
    await screen.findByRole('heading', { name: /Заявка отправлена регистратору/ });

    expect(mockedCreateRequest).toHaveBeenCalledTimes(2);
    expect(mockedCreateRequest.mock.calls[1]).toEqual(firstAttempt);
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

  it('fails closed when the selected mode requires a different booking API', async () => {
    mockedOptions.mockResolvedValue({ ...OPTIONS, mode: 'confirmed_appointment' } as never);
    renderPage();
    expect(await screen.findByText(/Этот способ записи пока не подключён/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Услуга')).not.toBeInTheDocument();
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
