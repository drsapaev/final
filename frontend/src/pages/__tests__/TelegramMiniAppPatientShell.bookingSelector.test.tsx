/**
 * Round-14 regression (owner round-5 review of PR-3386 merge commit bc362d5).
 *
 * P1: the actual Telegram /book entrypoint is PATIENT_BOOKING_ENTRY_ROUTE =
 * /telegram/mini-app/patient?section=appointments, which opens THIS shell —
 * not PatientBookingPanel. The department field here must be the canonical
 * Department.key selector (options from POST /telegram/mini-app/booking/
 * departments, loaded through getTelegramMiniAppAuthPayload so BOTH allowed
 * identity modes work: initData and entryToken). Free text ("Кардиология")
 * is not a Department.key and would be refused with 400 department_unknown.
 *
 * P2: booking reasons arrive as machine codes (department_unknown,
 * doctor_not_eligible, ...). This shell must show the patient-safe wording —
 * not splice the raw reason into 'Черновик записи не подтвержден: {reason}'.
 *
 * These tests render the real shell component at the real /book URL.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '../../i18n';
import uzLocale from '../../i18n/locales/uz-Latn';
import { tInterpolate } from '../../i18n/useTranslation';

// Round-15: the uz-Latn assertions must NOT touch the shared i18n store.
// Loading the lazy bundle here leaks into src/i18n/__tests__/adapter.test.ts
// ("unused locale resources stay unloaded" invariant) through the
// single-fork shared singleton — and a pending lazy backend callback can
// even re-add the bundle AFTER cleanup. So instead of loadLanguages() this
// file spies getFixedT: 'uz-Latn' resolves over the statically imported
// locale module, every other language keeps the real store-backed t().
const realGetFixedT = i18n.getFixedT.bind(i18n) as (
  lng: string,
  ns?: unknown,
  opts?: unknown,
) => ReturnType<typeof i18n.getFixedT>;

function resolveLocaleValue(locale: Record<string, unknown>, key: string): string {
  const value = key
    .split('.')
    .reduce<unknown>((acc, part) => (acc && typeof acc === 'object' ? (acc as Record<string, unknown>)[part] : undefined), locale);
  return typeof value === 'string' ? value : key;
}

beforeAll(() => {
  vi.spyOn(i18n, 'getFixedT').mockImplementation(((lng: string, ns?: string, opts?: Record<string, unknown>) => {
    if (lng === 'uz-Latn') {
      const uzT = (key: string, params?: Record<string, unknown>) =>
        tInterpolate(resolveLocaleValue(uzLocale as unknown as Record<string, unknown>, String(key)), params || {});
      return uzT as unknown as ReturnType<typeof realGetFixedT>;
    }
    return realGetFixedT(lng, ns, opts);
  }) as typeof i18n.getFixedT);
});

afterAll(() => {
  vi.restoreAllMocks();
});

const { apiPost } = vi.hoisted(() => ({ apiPost: vi.fn() }));

vi.mock('../../api/client', () => ({ api: { post: apiPost } }));

import TelegramMiniAppPatientShell from '../TelegramMiniAppPatientShell';

const DEPARTMENTS_URL = '/telegram/mini-app/booking/departments';
const PREVIEW_URL = '/telegram/mini-app/appointments/preview';
const CREATE_URL = '/telegram/mini-app/appointments';
const MANIFEST_URL = '/telegram/mini-app/patient/manifest';

const linkedManifest = {
  scope: { type: 'linked' },
  language: { code: 'ru' },
  capabilities: {
    appointments: { preview_enabled: true, create_enabled: true },
    visits: {},
    queue: {},
    forms: {},
    cabinet: {},
    payments: {},
    results: {},
  },
};

const departmentRows = [
  { key: 'cardio', name: 'Кардиология' },
  { key: 'derma', name: 'Дерматология' },
];

// Round-15 (owner P2): the payload must carry the clinic's own Uzbek name
// so the uz-Latn selector is not stuck on Russian labels.
const departmentRowsUz = [
  { key: 'cardio', name: 'Кардиология', name_uz: 'Kardiologiya' },
];

const uzManifest = {
  ...linkedManifest,
  language: { code: 'uz' },
};

function routeApiPostByUrl(url: string, body: Record<string, any>) {
  if (url === MANIFEST_URL) {
    return Promise.resolve({ data: linkedManifest });
  }
  if (url === DEPARTMENTS_URL) {
    return Promise.resolve({ data: { departments: departmentRows } });
  }
  if (url === PREVIEW_URL) {
    return Promise.resolve({
      data: {
        preview_only: true,
        mutation_allowed: false,
        appointment: {
          appointment_date: body?.appointmentDate || '2026-01-01',
          appointment_time: body?.appointmentTime || '09:30',
          status: 'draft',
          payment_type: 'cash',
          payment_currency: 'UZS',
          department: 'Кардиология',
        },
      },
    });
  }
  if (url === CREATE_URL) {
    return Promise.resolve({
      data: {
        appointment_id: 42,
        preview: {
          appointment: {
            appointment_date: body?.appointmentDate || '2026-01-01',
            appointment_time: body?.appointmentTime || '09:30',
            status: 'draft',
            payment_type: 'cash',
            payment_currency: 'UZS',
            department: 'Кардиология',
          },
        },
      },
    });
  }
  return Promise.resolve({ data: {} });
}

function rejectWithReason(status: number, reason: string) {
  return Promise.reject({
    response: { status, data: { detail: { reason } } },
  });
}

function renderBookSurface(search: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[`/telegram/mini-app/patient${search}`]}>
        <Routes>
          <Route path="/telegram/mini-app/patient" element={<TelegramMiniAppPatientShell />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

async function selectDepartmentByName(label: string, triggerLabel = 'Отделение') {
  // The custom Select renders a trigger button associated to the visible
  // label ('Отделение'), then a portal listbox with role="option" rows.
  const trigger = await screen.findByLabelText(triggerLabel);
  fireEvent.click(trigger);
  const option = await screen.findByRole('option', { name: label });
  fireEvent.click(option);
}

describe('TelegramMiniAppPatientShell booking department selector (P1, round-14)', () => {
  beforeEach(() => {
    apiPost.mockReset();
    apiPost.mockImplementation((url: string, body: Record<string, any>) => routeApiPostByUrl(url, body));
  });

  afterEach(() => {
    delete (window as unknown as { Telegram?: unknown }).Telegram;
  });

  it('loads the department reference through initData and submits the canonical key "cardio" on the real /book surface', async () => {
    (window as unknown as { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'test-init-data-payload' },
    };

    renderBookSurface('?section=appointments');

    // P1: the shell (not PatientBookingPanel) must call the reference
    // endpoint with the same authenticated identity as the booking calls.
    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        DEPARTMENTS_URL,
        expect.objectContaining({ initData: 'test-init-data-payload' }),
        expect.anything(),
      );
    });

    // Visible human label "Кардиология", value picked from the list…
    await selectDepartmentByName('Кардиология');
    expect(screen.getByLabelText('Отделение')).toHaveTextContent('Кардиология');

    // …and the canonical Department.key ("cardio") is what reaches the
    // backend — not the free-text label.
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        PREVIEW_URL,
        expect.objectContaining({ department: 'cardio' }),
        expect.anything(),
      );
    });

    // The department field is no longer a free-text input.
    expect(screen.queryByRole('textbox', { name: 'Отделение' })).not.toBeInTheDocument();
  });

  it('loads the department reference through an entry-token URL and submits the canonical key', async () => {
    // No Telegram WebApp identity — the second allowed entry mode.
    renderBookSurface('?section=appointments&entryToken=tok_appointments_abc123');

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        DEPARTMENTS_URL,
        expect.objectContaining({ entryToken: 'tok_appointments_abc123' }),
        expect.anything(),
      );
    });

    await selectDepartmentByName('Кардиология');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        PREVIEW_URL,
        expect.objectContaining({ department: 'cardio' }),
        expect.anything(),
      );
    });
  });

  it('shows the Uzbek department name on the uz-Latn UI — label comes from the payload name_uz (round-15 P2)', async () => {
    // The uz-Latn display language resolves over the statically imported
    // locale (store untouched — see the getFixedT spy above); the observed
    // divergence was that the SELECTOR stayed Russian even on an Uzbek form.
    (window as unknown as { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'test-init-data-payload' },
    };
    apiPost.mockImplementation((url: string, body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: uzManifest });
      if (url === DEPARTMENTS_URL) return Promise.resolve({ data: { departments: departmentRowsUz } });
      if (url === PREVIEW_URL) return routeApiPostByUrl(PREVIEW_URL, body);
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');

    // The uz-Latn form must list the clinic's own Uzbek name — not the
    // Russian label — while still submitting the canonical key.
    await selectDepartmentByName("Kardiologiya", "Bo'lim");
    expect(screen.getByLabelText("Bo'lim")).toHaveTextContent('Kardiologiya');

    fireEvent.click(screen.getByRole('button', { name: 'Qoralamani tekshirish' }));
    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        PREVIEW_URL,
        expect.objectContaining({ department: 'cardio' }),
        expect.anything(),
      );
    });
  });

  it('clears a stale selected department when the reference refetch fails after a section switch (round-15 P2)', async () => {
    (window as unknown as { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'test-init-data-payload' },
    };
    let departmentsCalls = 0;
    apiPost.mockImplementation((url: string, body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: linkedManifest });
      if (url === DEPARTMENTS_URL) {
        departmentsCalls += 1;
        if (departmentsCalls >= 2) {
          return Promise.reject({ response: { status: 503, data: { detail: { reason: 'bot_token_required' } } } });
        }
        return Promise.resolve({ data: { departments: departmentRows } });
      }
      if (url === PREVIEW_URL) return routeApiPostByUrl(PREVIEW_URL, body);
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');
    await selectDepartmentByName('Кардиология');

    // Leave the booking section (the departments effect is gated to
    // appointments, so no refetch happens there) and come back — the shell
    // refetches the reference list and the second attempt fails (503). The
    // selector renders empty/placeholder now, so the payload must NOT
    // silently carry the previously selected key.
    fireEvent.click(screen.getByLabelText('Открытый раздел: Визиты'));
    fireEvent.click(screen.getByLabelText('Открытый раздел: Запись'));
    await waitFor(() => expect(departmentsCalls).toBe(2));

    await screen.findByText('Список отделений сейчас недоступен — можно отправить заявку без отделения.');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));
    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        PREVIEW_URL,
        expect.objectContaining({ department: undefined }),
        expect.anything(),
      );
    });
  });

  it('degrades gracefully when the department reference endpoint fails — form stays usable without departments', async () => {
    (window as unknown as { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'test-init-data-payload' },
    };
    apiPost.mockImplementation((url: string) => {
      if (url === DEPARTMENTS_URL) {
        return Promise.reject({ response: { status: 503, data: { detail: { reason: 'bot_token_required' } } } });
      }
      return routeApiPostByUrl(url, {});
    });

    renderBookSurface('?section=appointments');

    // Selector renders (with the "no department" escape hatch), submit still works.
    await screen.findByLabelText('Отделение');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));
    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        PREVIEW_URL,
        expect.objectContaining({ department: undefined }),
        expect.anything(),
      );
    });
  });
});

describe('TelegramMiniAppPatientShell patient-safe booking errors (P2, round-14)', () => {
  beforeEach(() => {
    apiPost.mockReset();
    (window as unknown as { Telegram?: unknown }).Telegram = {
      WebApp: { initData: 'test-init-data-payload' },
    };
  });

  afterEach(() => {
    delete (window as unknown as { Telegram?: unknown }).Telegram;
  });

  it('maps preview department_unknown to the patient-safe wording instead of the machine reason', async () => {
    apiPost.mockImplementation((url: string, _body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: linkedManifest });
      if (url === DEPARTMENTS_URL) return Promise.resolve({ data: { departments: departmentRows } });
      if (url === PREVIEW_URL) return rejectWithReason(400, 'department_unknown');
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');
    await screen.findByLabelText('Отделение');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    await waitFor(() => {
      expect(screen.getByText('Выберите отделение из списка и попробуйте ещё раз.')).toBeInTheDocument();
    });
    expect(screen.queryByText(/department_unknown/)).not.toBeInTheDocument();
  });

  it('maps create doctor_not_eligible to the patient-safe wording instead of the machine reason', async () => {
    apiPost.mockImplementation((url: string, body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: linkedManifest });
      if (url === DEPARTMENTS_URL) return Promise.resolve({ data: { departments: departmentRows } });
      if (url === PREVIEW_URL) return routeApiPostByUrl(PREVIEW_URL, body);
      if (url === CREATE_URL) return rejectWithReason(400, 'doctor_not_eligible');
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');
    await screen.findByLabelText('Отделение');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    // After a successful preview the create action becomes available.
    const createButton = await screen.findByRole('button', { name: 'Отправить заявку' });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText('Этот врач сейчас недоступен для записи. Выберите другого врача.')).toBeInTheDocument();
    });
    expect(screen.queryByText(/doctor_not_eligible/)).not.toBeInTheDocument();
  });

  it('maps preview telegram_link_inactive to the patient-safe wording instead of the machine reason (round-15 P2)', async () => {
    apiPost.mockImplementation((url: string, _body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: linkedManifest });
      if (url === DEPARTMENTS_URL) return Promise.resolve({ data: { departments: departmentRows } });
      if (url === PREVIEW_URL) return rejectWithReason(403, 'telegram_link_inactive');
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');
    await screen.findByLabelText('Отделение');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    await waitFor(() => {
      expect(screen.getByText('Ваша привязка к Telegram отключена. Свяжитесь с клиникой, чтобы восстановить доступ.')).toBeInTheDocument();
    });
    expect(screen.queryByText(/telegram_link_inactive/)).not.toBeInTheDocument();
  });

  it('maps create telegram_link_blocked to the patient-safe wording instead of the machine reason (round-15 P2)', async () => {
    apiPost.mockImplementation((url: string, body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: linkedManifest });
      if (url === DEPARTMENTS_URL) return Promise.resolve({ data: { departments: departmentRows } });
      if (url === PREVIEW_URL) return routeApiPostByUrl(PREVIEW_URL, body);
      if (url === CREATE_URL) return rejectWithReason(403, 'telegram_link_blocked');
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');
    await screen.findByLabelText('Отделение');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    const createButton = await screen.findByRole('button', { name: 'Отправить заявку' });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText('Доступ через Telegram сейчас заблокирован. Свяжитесь с клиникой.')).toBeInTheDocument();
    });
    expect(screen.queryByText(/telegram_link_blocked/)).not.toBeInTheDocument();
  });

  it('keeps the reason visible for genuinely unknown backend codes (diagnostics preserved)', async () => {
    apiPost.mockImplementation((url: string, _body: Record<string, any>) => {
      if (url === MANIFEST_URL) return Promise.resolve({ data: linkedManifest });
      if (url === DEPARTMENTS_URL) return Promise.resolve({ data: { departments: departmentRows } });
      if (url === PREVIEW_URL) return rejectWithReason(400, 'brand_new_future_reason');
      return Promise.resolve({ data: {} });
    });

    renderBookSurface('?section=appointments');
    await screen.findByLabelText('Отделение');
    fireEvent.click(screen.getByRole('button', { name: 'Проверить черновик' }));

    await waitFor(() => {
      expect(screen.getByText('Черновик записи не подтвержден: brand_new_future_reason')).toBeInTheDocument();
    });
  });
});
