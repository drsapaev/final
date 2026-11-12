/**
 * CARDSVC-FE-001 / CARDSVC-FE-002 (audit 3886, ledger group "cardiology
 * services tab", round 28) — fail-first regressions.
 *
 * CARDSVC-FE-001 (P1/P2 candidate): DoctorServiceSelector loaded the
 * doctor services catalog with a browser-relative
 * `fetch(`/doctor/${specialty}/services`)` — on a separately hosted
 * frontend (VITE_API_BASE_URL) this targets the FRONTEND origin (404 /
 * SPA fallback HTML) and bypasses the shared client's auth handling,
 * although the canonical route lives under the configured
 * `/api/v1` API origin.
 *
 * CARDSVC-FE-002 (P2): the cardiology ServicesTab mounts the selector
 * without `onServicesChange` (documented read-only catalog), yet every
 * service was rendered as role="button", tabIndex=0, pointer cursor with
 * click/Enter/Space handlers that computed a new selection and silently
 * discarded it — a misleading pseudo-selection affordance.
 *
 * Red-first: on the pre-fix source the transport test fails (browser
 * fetch used, shared client not called) and the read-only test fails
 * (activatable button roles rendered).
 */
import React from 'react';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function SnackbarProviderMock({ children }: { children?: React.ReactNode }) {
  return <div>{children}</div>;
}

vi.mock('notistack', () => ({
  SnackbarProvider: SnackbarProviderMock,
  useSnackbar: () => ({ enqueueSnackbar: vi.fn() })
}));

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'light' })
}));

const apiMocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../../api/client', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    api: { get: apiMocks.get, post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  };
});

import DoctorServiceSelector from '../DoctorServiceSelector';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SERVICE_A = {
  id: 'svc-consult-1',
  name: 'Приём кардиолога',
  code: 'CONS-CARD-01',
  price: 120000,
  currency: 'UZS',
  duration_minutes: 30,
};

const SERVICES_BY_CATEGORY = {
  'consultation.cardiology': {
    category: { name_ru: 'Консультация кардиолога' },
    services: [SERVICE_A],
  },
};

describe('CARDSVC-FE-001: the services catalog loads through the configured shared API client', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.get.mockResolvedValue({ data: { services_by_category: SERVICES_BY_CATEGORY } });
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((() => Promise.resolve(new Response('{}'))) as typeof fetch);
  });

  it('requests /doctor/cardiology/services via the versioned client, never a browser-relative fetch', async () => {
    render(
      <DoctorServiceSelector
        specialty="cardiology"
        selectedServices={[]}
        canEditPrices={false}
      />
    );

    await waitFor(() => expect(apiMocks.get).toHaveBeenCalledTimes(1));
    expect(apiMocks.get).toHaveBeenCalledWith('/doctor/cardiology/services');
    expect(fetchSpy).not.toHaveBeenCalled();

    // Category content from the backend DTO is rendered.
    expect(await screen.findByText('Приём кардиолога')).toBeInTheDocument();
    expect(screen.getByText(/CONS-CARD-01/)).toBeInTheDocument();
  });

  it('surfaces the catalog error state when the shared client rejects (control)', async () => {
    apiMocks.get.mockRejectedValueOnce(new Error('network down'));
    const { container } = render(
      <DoctorServiceSelector specialty="cardiology" selectedServices={[]} canEditPrices={false} />
    );
    await waitFor(() =>
      expect(container.textContent).toContain('Ошибка загрузки услуг')
    );
  });
});

describe('CARDSVC-FE-002: a read-only catalog exposes no pseudo-selection affordances', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.get.mockResolvedValue({ data: { services_by_category: SERVICES_BY_CATEGORY } });
  });

  it('renders rows as plain non-interactive information without onServicesChange (ServicesTab shape)', async () => {
    const { container } = render(
      <DoctorServiceSelector
        specialty="cardiology"
        selectedServices={[]}
        canEditPrices={false}
      />
    );
    await screen.findByText('Приём кардиолога');

    // No activatable button roles and no focusable pseudo-buttons.
    expect(container.querySelectorAll('[role="button"]')).toHaveLength(0);
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0);
    expect(screen.queryByRole('button', { name: /приём кардиолога/i })).not.toBeInTheDocument();
  });

  it('the explicit readOnly prop suppresses selection even when a change callback exists', async () => {
    const { container } = render(
      <DoctorServiceSelector
        specialty="cardiology"
        selectedServices={[]}
        canEditPrices={false}
        readOnly
        onServicesChange={vi.fn()}
      />
    );
    await screen.findByText('Приём кардиолога');
    expect(container.querySelectorAll('[role="button"]')).toHaveLength(0);
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0);
  });

  it('interactive mode (onServicesChange provided, not read-only) still selects services (control)', async () => {
    const onServicesChange = vi.fn();
    const { container } = render(
      <DoctorServiceSelector
        specialty="cardiology"
        selectedServices={[]}
        canEditPrices
        onServicesChange={onServicesChange}
      />
    );
    const row = await screen.findByText('Приём кардиолога');
    const rowButton = row.closest('[role="button"]');
    expect(rowButton).not.toBeNull();
    fireEvent.click(rowButton as HTMLElement);

    await waitFor(() => expect(onServicesChange).toHaveBeenCalledTimes(1));
    const emitted = onServicesChange.mock.calls[0][0] as Array<Record<string, unknown>>;
    expect(emitted).toHaveLength(1);
    expect(emitted[0]).toMatchObject({ id: 'svc-consult-1', name: 'Приём кардиолога', quantity: 1 });
  });
});


describe('RETRO-3970-02 — the empty-catalog fallback is localized like the error state', () => {
  it('the hardcoded Russian literals left the component; the empty state goes through t()', () => {
    const source = fs.readFileSync(path.resolve(__dirname, '../DoctorServiceSelector.tsx'), 'utf8');
    expect(source).not.toContain('Услуги не найдены');
    expect(source).not.toContain('в админ панели');
    expect(source).toContain('t(\'misc.dss_uslugi_ne_naydeny\')');
    expect(source).toContain('t(\'misc.dss_dobavte_uslugi_admin_paneli\'');
  });

  it('an empty catalog still renders the empty-state card with its texts', async () => {
    apiMocks.get.mockResolvedValueOnce({ data: {} });
    render(<DoctorServiceSelector specialty="cardiology" />);
    await waitFor(() => {
      expect(apiMocks.get).toHaveBeenCalledWith('/doctor/cardiology/services');
    });
    // The ru locale value of misc.dss_uslugi_ne_naydeny — UX unchanged in ru.
    expect(screen.getByText('Услуги не найдены')).toBeInTheDocument();
    expect(screen.getByText(/Добавьте услуги для специальности/)).toBeInTheDocument();
  });
});
