import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const managerActions = vi.hoisted(() => ({ discardDraft: vi.fn() }));

vi.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: false }),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string) => ({
      'admin2.asv_tab_catalog': 'Каталог услуг',
      'admin2.asv_tab_queue_profiles': 'Профили очередей',
      'admin2.sdx_title': 'Направления и очереди',
      'registrarPanel.rt_title': 'Вкладки регистратуры',
      'registrarPanel.rt_unsaved_warning': 'Сохранить изменения перед уходом?',
      'registrarPanel.rt_discard_confirm': 'Отменить изменения',
      'common.cancel': 'Остаться',
    })[key] ?? key,
  }),
}));

vi.mock('../RegistrarTabsManager', () => ({
  default: React.forwardRef<{ discardDraft: () => void }, {
    onDirtyChange?: (dirty: boolean) => void;
    onSavingChange?: (saving: boolean) => void;
    defaultOpenProfiles?: boolean;
  }>(function MockRegistrarTabsManager({ onDirtyChange, onSavingChange, defaultOpenProfiles }, ref) {
    React.useImperativeHandle(ref, () => ({ discardDraft: managerActions.discardDraft }));
    return <div data-testid="registrar-tabs-panel">
      Registrar tabs
      <button type="button" onClick={() => onDirtyChange?.(true)}>Edit registrar tabs</button>
      <button type="button" onClick={() => onSavingChange?.(true)}>Start saving registrar tabs</button>
      {defaultOpenProfiles && <span>Profile settings open</span>}
    </div>;
  }),
}));

vi.mock('../ServiceCatalog', () => ({
  default: () => <div data-testid="service-catalog-panel">Service catalog</div>,
}));

import AdminServices from '../AdminServices';

function LocationControls() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div>
      <output data-testid="current-location">{location.pathname}{location.search}</output>
      <button type="button" onClick={() => navigate(-1)}>Back</button>
      <button type="button" onClick={() => navigate(1)}>Forward</button>
      <button
        type="button"
        onClick={() => navigate('/admin/services?servicesTab=queue-profiles&setupReturn=queue-directions-v1&setupSection=resources')}
      >
        Set queue profiles query
      </button>
      <button type="button" onClick={() => navigate('/admin/services?servicesTab=unknown&keep=1')}>
        Set unknown tab query
      </button>
    </div>
  );
}

function renderAdminServices(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <LocationControls />
      <Routes>
        <Route path="/admin/services" element={<AdminServices />} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockLegacySavedTab() {
  vi.spyOn(localStorage, 'getItem').mockImplementation((key) =>
    key === 'servicesTab' ? 'queue-profiles' : null,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  managerActions.discardDraft.mockClear();
  localStorage.clear();
});

describe('AdminServices URL-backed tab navigation', () => {
  it('opens the queue-profile compatibility URL without redirecting the services route', async () => {
    renderAdminServices('/admin/services?servicesTab=queue-profiles');

    expect(await screen.findByTestId('registrar-tabs-panel')).toBeInTheDocument();
    expect(screen.getByTestId('current-location')).toHaveTextContent(
      '/admin/services?servicesTab=queue-profiles',
    );
    expect(screen.queryByTestId('service-catalog-panel')).not.toBeInTheDocument();
  });

  it('keeps the catalog as the safe start for an unknown servicesTab value', async () => {
    mockLegacySavedTab();
    renderAdminServices('/admin/services?servicesTab=unknown&keep=1');

    expect(await screen.findByTestId('service-catalog-panel')).toBeInTheDocument();
    await waitFor(() => {
      const current = new URL(screen.getByTestId('current-location').textContent ?? '', 'http://local');
      expect(current.pathname).toBe('/admin/services');
      expect(current.searchParams.get('servicesTab')).toBe('catalog');
      expect(current.searchParams.get('keep')).toBe('1');
    });
    expect(screen.queryByTestId('registrar-tabs-panel')).not.toBeInTheDocument();
  });

  it('normalizes repeated servicesTab parameters to the safe catalog tab', async () => {
    renderAdminServices('/admin/services?servicesTab=queue-profiles&servicesTab=catalog&keep=2');

    expect(await screen.findByTestId('service-catalog-panel')).toBeInTheDocument();
    await waitFor(() => {
      const current = new URL(screen.getByTestId('current-location').textContent ?? '', 'http://local');
      expect(current.searchParams.getAll('servicesTab')).toEqual(['catalog']);
      expect(current.searchParams.get('keep')).toBe('2');
    });
  });

  it('synchronizes direct query changes and preserves tab selection through Back and Forward', async () => {
    const user = userEvent.setup();
    renderAdminServices('/admin/services?servicesTab=catalog');

    expect(await screen.findByTestId('service-catalog-panel')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Профили очередей' }));
    expect(await screen.findByTestId('registrar-tabs-panel')).toBeInTheDocument();
    expect(screen.getByTestId('current-location')).toHaveTextContent('servicesTab=queue-profiles');
    expect(managerActions.discardDraft).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(await screen.findByTestId('service-catalog-panel')).toBeInTheDocument();
    expect(screen.getByTestId('current-location')).toHaveTextContent('servicesTab=catalog');

    await user.click(screen.getByRole('button', { name: 'Forward' }));
    expect(await screen.findByTestId('registrar-tabs-panel')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Set queue profiles query' }));
    expect(await screen.findByTestId('registrar-tabs-panel')).toBeInTheDocument();
    expect(screen.getByTestId('queue-setup-return')).toHaveTextContent('Направления и очереди');
  });

  it('serializes the legacy local tab preference into the URL on direct entry', async () => {
    mockLegacySavedTab();
    renderAdminServices('/admin/services');

    expect(await screen.findByTestId('registrar-tabs-panel')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId('current-location')).toHaveTextContent(
        '/admin/services?servicesTab=queue-profiles',
      );
    });
  });

  it('keeps the edited registrar tab list when the administrator cancels navigation', async () => {
    const user = userEvent.setup();
    renderAdminServices('/admin/services?servicesTab=queue-profiles&keep=1');
    await screen.findByTestId('registrar-tabs-panel');
    await user.click(screen.getByRole('button', { name: 'Edit registrar tabs' }));
    await user.click(screen.getByRole('button', { name: 'Каталог услуг' }));

    expect(await screen.findByRole('dialog')).toHaveTextContent('Сохранить изменения перед уходом?');
    await user.click(screen.getByRole('button', { name: 'Остаться' }));

    expect(screen.getByTestId('registrar-tabs-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('service-catalog-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('current-location')).toHaveTextContent('servicesTab=queue-profiles');
    expect(managerActions.discardDraft).not.toHaveBeenCalled();
  });

  it('leaves the registrar editor only after explicit discard confirmation', async () => {
    const user = userEvent.setup();
    renderAdminServices('/admin/services?servicesTab=queue-profiles&keep=2');
    await screen.findByTestId('registrar-tabs-panel');
    await user.click(screen.getByRole('button', { name: 'Edit registrar tabs' }));
    await user.click(screen.getByRole('button', { name: 'Каталог услуг' }));

    await screen.findByRole('dialog');
    await user.click(screen.getByRole('button', { name: 'Отменить изменения' }));

    expect(await screen.findByTestId('service-catalog-panel')).toBeInTheDocument();
    const current = new URL(screen.getByTestId('current-location').textContent ?? '', 'http://local');
    expect(current.searchParams.get('servicesTab')).toBe('catalog');
    expect(current.searchParams.get('keep')).toBe('2');
    expect(managerActions.discardDraft).toHaveBeenCalledTimes(1);
  });

  it('disables tab navigation while the registrar configuration is being saved', async () => {
    const user = userEvent.setup();
    renderAdminServices('/admin/services?servicesTab=queue-profiles');
    await screen.findByTestId('registrar-tabs-panel');
    await user.click(screen.getByRole('button', { name: 'Start saving registrar tabs' }));

    expect(screen.getByRole('button', { name: 'Каталог услуг' })).toBeDisabled();
    expect(screen.getByTestId('current-location')).toHaveTextContent('servicesTab=queue-profiles');
  });
});
