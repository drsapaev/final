import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import QueueProfilesManager from '../QueueProfilesManager';
import { api } from '@/api/client';

// QR-FE-024 — the edit dialog must submit a field-level dirty payload, not
// the full stale form. A full PUT resends is_active/show_on_qr_page captured
// when the dialog opened; the backend (exclude_unset PUT) treats any
// supplied availability field as an availability request, so a title-only
// edit from a stale form can re-publish a profile another admin explicitly
// unpublished, or un-archive an archived one. SYNTHETIC fixtures only.

const syntheticProfile = {
  key: 'synthetic-cardio',
  title: 'Synthetic Cardio Title',
  title_ru: 'Синтетическая кардиология',
  queue_tags: ['cardio', 'ekg'],
  department_key: 'cardiology',
  order: 3,
  is_active: true,
  show_on_qr_page: true,
  icon: 'Heart',
  color: 'synthetic-crimson',
};

vi.mock('@/api/client', () => {
  const apiMock = {
    get: vi.fn((url: string) => {
      if (url.startsWith('/queues/profiles')) {
        return Promise.resolve({ data: { profiles: [{ ...syntheticProfile }] } });
      }
      if (url === '/admin/departments') {
        return Promise.resolve({ data: { data: [{ key: 'cardiology', name_ru: 'Синтетическое отделение' }] } });
      }
      return Promise.resolve({ data: { data: [] } });
    }),
    post: vi.fn(() => Promise.resolve({ data: { success: true } })),
    put: vi.fn(() => Promise.resolve({ data: { success: true } })),
    delete: vi.fn(),
  };
  return {
    default: apiMock,
    api: apiMock,
    apiClient: apiMock,
  };
});

vi.mock('../../../services/notify', () => ({
  notify: { success: vi.fn(), warning: vi.fn() },
}));

const openEditDialog = async () => {
  render(
    <ThemeProvider>
      <QueueProfilesManager />
    </ThemeProvider>
  );
  await screen.findByText('Synthetic Cardio Title');
  const editButton = await screen.findByRole('button', {
    name: 'Редактировать профиль Синтетическая кардиология',
  });
  await userEvent.click(editButton);
  const titleInput = await screen.findByLabelText('Название вкладки очереди на английском');
  expect(titleInput).toHaveValue('Synthetic Cardio Title');
  return titleInput;
};

const boardPutBodies = (): Array<Record<string, unknown>> =>
  (api.put as unknown as ReturnType<typeof vi.fn>).mock.calls
    .filter((call) => String(call[0]).startsWith('/queues/profiles/'))
    .map((call) => call[1] as Record<string, unknown>);

describe('QueueProfilesManager edit dirty payload (QR-FE-024)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('title-only edit sends only title — stale availability flags are omitted', async () => {
    const titleInput = await openEditDialog();

    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, 'Synthetic Cardio Renamed');
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить вкладку очереди' }));

    await waitFor(() => {
      expect(boardPutBodies()).toHaveLength(1);
    });
    const body = boardPutBodies()[0];
    // Only the actually changed field reaches the backend; unchanged
    // is_active/show_on_qr_page cannot undo a concurrent admin's
    // unpublish/archive (backend exclude_unset semantics).
    expect(body).toEqual({ title: 'Synthetic Cardio Renamed' });
    expect(body).not.toHaveProperty('show_on_qr_page');
    expect(body).not.toHaveProperty('is_active');
  });

  it('explicit availability change is still sent as a real request', async () => {
    await openEditDialog();

    const qrCheckbox = screen.getByRole('checkbox', { name: 'Показывать профиль на QR-странице' });
    expect(qrCheckbox).toBeChecked();
    await userEvent.click(qrCheckbox);
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить вкладку очереди' }));

    await waitFor(() => {
      expect(boardPutBodies()).toHaveLength(1);
    });
    const body = boardPutBodies()[0];
    // A deliberate unpublish remains an explicit availability request.
    expect(body).toEqual({ show_on_qr_page: false });
  });

  it('submitting an untouched form performs no PUT at all', async () => {
    await openEditDialog();

    await userEvent.click(screen.getByRole('button', { name: 'Сохранить вкладку очереди' }));

    // Nothing changed → honest no-op: no network command, dialog closes.
    await waitFor(() => {
      expect(screen.queryByLabelText('Название вкладки очереди на английском')).not.toBeInTheDocument();
    });
    expect(boardPutBodies()).toHaveLength(0);
  });
});
