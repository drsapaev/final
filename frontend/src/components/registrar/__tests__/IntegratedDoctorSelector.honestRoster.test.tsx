/**
 * REG-FE-071 / REG-FE-072 / REG-FE-074 (follow-up audit 2026-11-02):
 * честность IntegratedDoctorSelector.
 *
 * 071: prop `specialty` прежде принимался, но НЕ фильтровал ни запрос, ни
 *      рендер — при specialty="cardiology" оставались видимыми дерматологи
 *      и дантисты.
 * 072: отображаемый «диапазон онлайн-очереди №N-M» строился из АГРЕГАТА
 *      СПЕЦИАЛЬНОСТИ (бэкенд /queue-settings) — выдуманный диапазон, не
 *      фактические номера талонов врача. Теперь показываются только лимиты.
 * 074: сбой ОПЦИОНАЛЬНЫХ настроек очереди прежде «валил» весь компонент
 *      (Promise.all под общим try/catch) — список врачей, загрузившийся
 *      успешно, прятался за глобальной ошибкой.
 *
 * Red-first (до фикса): все три сценария проваливались.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Doctor } from '../../../types/domain/clinic';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

const apiMocks = vi.hoisted(() => ({
  fetchRegistrarDoctors: vi.fn(),
  fetchRegistrarQueueSettings: vi.fn(),
}));

vi.mock('../../../hooks/useRegistrarApi', () => ({
  useRegistrarApi: () => apiMocks,
}));

import IntegratedDoctorSelector from '../IntegratedDoctorSelector';
import { ThemeProvider } from '../../../contexts/ThemeContext';

/** macOS Card требует ThemeProvider. */
const renderSelector = (ui: React.ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

const mkDoctor = (id: number, specialty: string, fullName: string): Doctor =>
  ({
    id,
    specialty,
    user: { full_name: fullName },
    schedules: [],
  }) as unknown as Doctor;

const ROSTER = {
  doctors: [
    mkDoctor(1, 'cardiology', 'Doc Cardio'),
    mkDoctor(2, 'dermatology', 'Doc Derma'),
    mkDoctor(3, 'dentistry', 'Doc Dental'),
  ],
};

const QUEUE_SETTINGS = {
  specialties: {
    cardiology: { start_number: 100, max_per_day: 20 },
    dermatology: { start_number: 200, max_per_day: 15 },
  },
};

beforeEach(() => {
  apiMocks.fetchRegistrarDoctors.mockReset();
  apiMocks.fetchRegistrarQueueSettings.mockReset();
  apiMocks.fetchRegistrarDoctors.mockResolvedValue(ROSTER);
  apiMocks.fetchRegistrarQueueSettings.mockResolvedValue(QUEUE_SETTINGS);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('REG-FE-074 — optional queue-settings failure no longer hides the roster', () => {
  it('doctors OK + settings 500 → doctors stay selectable + separate warning, no queue limits', async () => {
    apiMocks.fetchRegistrarQueueSettings.mockRejectedValue(new Error('settings 500'));
    renderSelector(<IntegratedDoctorSelector />);

    await waitFor(() => {
      expect(screen.getByText('Doc Cardio')).toBeTruthy();
      expect(screen.getByText('Doc Derma')).toBeTruthy();
    });
    // Отдельное предупреждение вместо глобальной ошибки.
    expect(screen.getByTestId('ids-settings-warning')).toBeTruthy();
    // Прежде: глобальная ошибка «ids_oshibka_zagruzki_dannyh_vrac» и НИОДНОГО врача.
    expect(screen.queryByText(/ids_oshibka_zagruzki_dannyh_vrac/)).toBeNull();
    // Лимиты очереди опущены (нет данных) — и нет выдуманного диапазона.
    expect(screen.queryByText(/Лимит онлайн-записи/)).toBeNull();
    expect(screen.queryByText(/Онлайн-очередь/)).toBeNull();
  });

  it('doctors failure is still a global error (primary resource)', async () => {
    apiMocks.fetchRegistrarDoctors.mockRejectedValue(new Error('doctors down'));
    apiMocks.fetchRegistrarQueueSettings.mockResolvedValue(QUEUE_SETTINGS);
    renderSelector(<IntegratedDoctorSelector />);

    await waitFor(() => {
      expect(screen.getByText(/ids_oshibka_zagruzki_dannyh_vrac/)).toBeTruthy();
    });
    expect(screen.queryByText('Doc Cardio')).toBeNull();
  });
});

describe('REG-FE-071 — specialty prop actually filters the rendered roster', () => {
  it('specialty="cardiology" → only the cardiologist is selectable', async () => {
    renderSelector(<IntegratedDoctorSelector specialty="cardiology" />);

    await waitFor(() => expect(screen.getByText('Doc Cardio')).toBeTruthy());
    expect(screen.queryByText('Doc Derma')).toBeNull();
    expect(screen.queryByText('Doc Dental')).toBeNull();
  });

  it('specialty="dentistry" (roster has one) → only the dentist', async () => {
    renderSelector(<IntegratedDoctorSelector specialty="dentistry" />);
    await waitFor(() => expect(screen.getByText('Doc Dental')).toBeTruthy());
    expect(screen.queryByText('Doc Cardio')).toBeNull();
  });

  it('specialty with no matches → honest empty state mentioning the specialty', async () => {
    renderSelector(<IntegratedDoctorSelector specialty="neurosurgery" />);
    await waitFor(() => {
      expect(screen.getByText(/ids_net_vrachey_spetsialnosti_sp/)).toBeTruthy();
    });
    expect(screen.queryByText('Doc Cardio')).toBeNull();
  });

  it('no specialty prop → full roster (unchanged)', async () => {
    renderSelector(<IntegratedDoctorSelector />);
    await waitFor(() => {
      expect(screen.getByText('Doc Cardio')).toBeTruthy();
      expect(screen.getByText('Doc Derma')).toBeTruthy();
      expect(screen.getByText('Doc Dental')).toBeTruthy();
    });
  });
});

describe('REG-FE-072 — honest specialty limits instead of a fabricated ticket range', () => {
  it('renders ONLY the per-day limit — no invented «№start-end» range', async () => {
    renderSelector(<IntegratedDoctorSelector specialty="cardiology" />);
    await waitFor(() => expect(screen.getByText('Doc Cardio')).toBeTruthy());

    // Честные лимиты специальности.
    expect(screen.getByText(/Лимит онлайн-записи по специальности: макс\. 20\/день/)).toBeTruthy();
    // Прежде — выдуманный диапазон «Онлайн-очередь: №100-119 (макс. 20/день)».
    expect(screen.queryByText(/Онлайн-очередь/)).toBeNull();
    expect(screen.queryByText(/№100-119/)).toBeNull();
    expect(screen.queryByText(/№100/)).toBeNull();
  });

  it('two doctors sharing a specialty show the SAME honest aggregate limit (no per-doctor ranges)', async () => {
    const roster = {
      doctors: [
        mkDoctor(1, 'cardiology', 'Doc Cardio A'),
        mkDoctor(4, 'cardiology', 'Doc Cardio B'),
      ],
    };
    apiMocks.fetchRegistrarDoctors.mockResolvedValue(roster);
    renderSelector(<IntegratedDoctorSelector specialty="cardiology" />);

    await waitFor(() => expect(screen.getByText('Doc Cardio A')).toBeTruthy());
    expect(screen.getByText('Doc Cardio B')).toBeTruthy();
    // Один и тот же агрегат специальности — без выдуманных per-doctor диапазонов.
    const limitNodes = screen.getAllByText(/Лимит онлайн-записи по специальности: макс\. 20\/день/);
    expect(limitNodes.length).toBe(2);
    expect(screen.queryByText(/№\d+-\d+/)).toBeNull();
  });
});
