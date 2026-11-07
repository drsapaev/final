/**
 * DERMSCHED-FE-001 / DERMSCHED-FE-002 (audit 3892, post-merge group 9
 * «schedule-next wiring») — fail-first regressions for ScheduleNextModal:
 *
 * - DERMSCHED-FE-001: the modal must issue its patient/service/schedule
 *   requests through the shared authenticated API client with the
 *   configured API base — not raw `fetch('patients/')`-style SPA-relative
 *   URLs that resolve under the panel route and dead-code the feature.
 * - DERMSCHED-FE-002: when a queue-row-shaped patient is supplied, the
 *   form must preselect the canonical `patient_id`, never the queue/visit
 *   record `id` — the backend resolves `Patient.id`.
 *
 * Red-first: on the pre-fix source every bug-case assertion fails (raw
 * fetch is used, the shared client is never called, and the preselect
 * takes the record id); the positive controls pass on both.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ScheduleNextModal from '../ScheduleNextModal';
import { api } from '../../../api/client';

vi.mock('../../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: vi.fn(() => 'synthetic-doctor-token') },
}));
vi.mock('../../../utils/logger', () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);

const QUEUE_ROW_PATIENT = {
  // Queue-row semantics: `id` is the visit/queue record id, `patient_id`
  // is the canonical Patient.id the backend resolves.
  id: 101,
  patient_id: 9,
  patient_name: 'SYNTHETIC QUEUE PATIENT',
};

function jsonResponse(data: unknown, status = 200) {
  return { data, status } as never;
}

const PATIENTS = [
  { id: 9, first_name: 'Ann', last_name: 'Ayn', phone: '100' },
  { id: 12, first_name: 'Bo', last_name: 'Li', phone: '200' },
];
const SERVICES = [{ id: 5, name: 'Derma service', category: 'derma', code: 'D1', price: 100 }];

beforeEach(() => {
  vi.clearAllMocks();
  // A working raw-fetch stub: the PRE-FIX code path (raw fetch) must be
  // able to load its lists so the positive controls stay green pre-fix;
  // the bug cases are about WHICH transport and WHICH identity is used.
  global.fetch = vi.fn(async (input: unknown) => {
    const url = String(input);
    if (url.includes('patients')) {
      return { ok: true, status: 200, json: async () => PATIENTS } as never;
    }
    if (url.includes('services')) {
      return { ok: true, status: 200, json: async () => SERVICES } as never;
    }
    return { ok: true, status: 200, json: async () => ({ visit_id: 55, confirmation: { channel: 'telegram', token: 'tok-1' } }) } as never;
  }) as unknown as typeof fetch;
  mockedGet.mockImplementation(async (url: unknown) => {
    const path = String(url);
    if (path === '/patients') return jsonResponse(PATIENTS);
    if (path === '/services') return jsonResponse(SERVICES);
    throw new Error(`unexpected GET ${path}`);
  });
});

describe('DERMSCHED-FE-001 — schedule-next uses the shared API client and the configured base', () => {
  it('loads patients and services through the shared client (pre-fix: raw SPA-relative fetch)', async () => {
    render(<ScheduleNextModal isOpen patient={QUEUE_ROW_PATIENT} />);

    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/patients'));
    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/services'));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('submits schedule-next through the shared client with an absolute API path (pre-fix: raw fetch POST)', async () => {
    mockedPost.mockResolvedValue(jsonResponse({
      visit_id: 55,
      confirmation: { channel: 'telegram', token: 'tok-1' },
    }));

    const { container } = render(<ScheduleNextModal isOpen patient={QUEUE_ROW_PATIENT} />);

    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/services'));
    fireEvent.change(screen.getByLabelText('Schedule next visit date'), { target: { value: '2030-01-01' } });
    fireEvent.change(screen.getByLabelText('Schedule next visit service 1'), { target: { value: '5' } });
    // Submit the form element directly (jsdom's interactive validation on
    // submit-button clicks is unreliable in this environment).
    fireEvent.submit(container.querySelector('form') as HTMLFormElement);

    await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(1));
    const [postUrl, postBody] = mockedPost.mock.calls[0];
    expect(String(postUrl)).toBe('/doctor/visits/schedule-next');
    expect(String((postBody as { patient_id: unknown }).patient_id)).toBe('9');
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('DERMSCHED-FE-002 — schedule-next preselects the canonical patient_id', () => {
  it('preselects patient.patient_id for a queue-row-shaped patient (pre-fix: record id 101)', async () => {
    render(<ScheduleNextModal isOpen patient={QUEUE_ROW_PATIENT} />);

    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith('/patients'));
    expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe('9');
  });

  it('positive control: a genuine patient object still preselects its own id', async () => {
    render(<ScheduleNextModal isOpen patient={{ id: 12, first_name: 'Bo', last_name: 'Li' }} />);

    await waitFor(() => {
      expect((screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement).value).toBe('12');
    });
  });
});
