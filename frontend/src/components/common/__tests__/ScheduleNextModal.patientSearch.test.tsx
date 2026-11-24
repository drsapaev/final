/**
 * DERMSCHED-FE-003 (owner registry #4063; review-group audit comment
 * 6690288950) — the patient picker silently omits patients outside the
 * first default page.
 *
 * The modal loads a bare `/patients` with no `q`, `limit` or search and
 * renders only the returned rows as options; the canonical patient-list
 * API defaults to `limit=100` and supports `q` server-side search. A
 * doctor needing a follow-up for a permitted patient beyond the first
 * 100 rows cannot select them — even a parent-supplied valid patient id
 * that is not among the returned options renders a falsely blank
 * selection.
 *
 * Contract after the repair (both repair options from the red-first
 * combined):
 * 1. The default load uses the canonical API surface explicitly
 *    (`params: { limit: 100 }`), and a search input drives server-side
 *    search (`params: { q, limit: 50 }`).
 * 2. A parent-supplied patient outside the loaded rows keeps a
 *    canonical selected-patient option — the select shows the identity
 *    instead of a false blank.
 * 3. Identity validation: a patient selected through search keeps its
 *    option (with its label) when the search list is cleared or replaced;
 *    an empty search result with nothing selected shows no false option.
 *
 * Red-first: on the pre-fix source cases 1–3 fail (bare request, no
 * search input, no canonical option) while the empty-result control
 * (no patient prop, empty search answer → only the placeholder option)
 * stays green.
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

function jsonResponse(data: unknown, status = 200) {
  return { data, status } as never;
}

// Exactly the audit scenario: the default first page holds patients 1..100
// and patient 150 is only reachable through server-side search.
const FIRST_PAGE = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  first_name: `P${i + 1}`,
  last_name: 'Synth',
  phone: String(1000 + i),
}));
const PATIENT_150 = { id: 150, first_name: 'Pat', last_name: 'OneFifty', phone: '1500' };
const SERVICES = [{ id: 5, name: 'Derma service', category: 'derma', code: 'D1', price: 100 }];

beforeEach(() => {
  vi.clearAllMocks();
  mockedGet.mockImplementation(async (url: unknown, config?: unknown) => {
    const params = (config as { params?: { q?: string; limit?: number } } | undefined)?.params;
    const path = String(url);
    if (path === '/services') return jsonResponse(SERVICES);
    if (path === '/patients') {
      const q = params?.q;
      if (q !== undefined) {
        if (String(q).includes('150')) return jsonResponse([PATIENT_150]);
        return jsonResponse([]);
      }
      return jsonResponse(FIRST_PAGE);
    }
    throw new Error(`unexpected GET ${path}`);
  });
});

function patientSelect(): HTMLSelectElement {
  return screen.getByLabelText('Schedule next visit patient') as HTMLSelectElement;
}

function optionValues(): string[] {
  return Array.from(patientSelect().options).map((o) => o.value);
}

describe('DERMSCHED-FE-003 — the patient picker reaches beyond the first default page', () => {
  it('the default load calls the canonical patient-list surface with an explicit limit', async () => {
    render(<ScheduleNextModal isOpen />);

    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith(
      '/patients',
      expect.objectContaining({ params: expect.objectContaining({ limit: 100 }) }),
    ));
  });

  it('a parent-supplied patient beyond the first page keeps its canonical selected option (no false blank)', async () => {
    render(<ScheduleNextModal isOpen patient={{ patient_id: 150, first_name: 'Pat', last_name: 'OneFifty' }} />);

    await waitFor(() => expect(patientSelect().options.length).toBeGreaterThan(1));
    expect(optionValues()).toContain('150');
    expect(patientSelect().value).toBe('150');
    // The option renders the supplied identity, not a bare id only.
    expect(patientSelect().textContent).toContain('Pat');
  });

  it('typing in the search field drives server-side search and surfaces patient 150', async () => {
    render(<ScheduleNextModal isOpen />);

    await waitFor(() => expect(patientSelect().options.length).toBeGreaterThan(50));
    fireEvent.change(screen.getByLabelText('Schedule next visit patient search'), { target: { value: '150' } });
    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith(
      '/patients',
      expect.objectContaining({ params: expect.objectContaining({ q: '150', limit: 50 }) }),
    ));
    await waitFor(() => expect(optionValues()).toContain('150'));
  });

  it('identity validation: a patient chosen through search keeps its option after the search is cleared', async () => {
    render(<ScheduleNextModal isOpen />);

    await waitFor(() => expect(patientSelect().options.length).toBeGreaterThan(50));
    fireEvent.change(screen.getByLabelText('Schedule next visit patient search'), { target: { value: '150' } });
    await waitFor(() => expect(optionValues()).toContain('150'));
    fireEvent.change(patientSelect(), { target: { value: '150' } });
    // Clearing the search replaces the result list with the first page —
    // the chosen identity must survive as a canonical option.
    fireEvent.change(screen.getByLabelText('Schedule next visit patient search'), { target: { value: '' } });
    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith(
      '/patients',
      expect.objectContaining({ params: expect.objectContaining({ limit: 100 }) }),
    ));
    expect(optionValues()).toContain('150');
    expect(patientSelect().value).toBe('150');
    expect(patientSelect().textContent).toContain('Pat');
  });

  it('control: an empty search result with nothing selected shows no false option', async () => {
    render(<ScheduleNextModal isOpen />);

    await waitFor(() => expect(patientSelect().options.length).toBeGreaterThan(50));
    fireEvent.change(screen.getByLabelText('Schedule next visit patient search'), { target: { value: 'zzz' } });
    await waitFor(() => expect(mockedGet).toHaveBeenCalledWith(
      '/patients',
      expect.objectContaining({ params: expect.objectContaining({ q: 'zzz' }) }),
    ));
    await waitFor(() => expect(optionValues()).toEqual(['']));
    expect(patientSelect().value).toBe('');
  });
});
