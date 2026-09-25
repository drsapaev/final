/**
 * Round-2 review P2 (PR 3455): the DepartmentManagement create form must
 * mirror the server-side DepartmentCreate.key contract — lowercase latin
 * identifier `^[a-z][a-z0-9_]*$`, max 50 chars — so a value the UI presents
 * as valid always survives the API boundary (instead of a post-submit 422
 * with no inline format guidance).
 *
 * The update path deliberately does NOT enforce the pattern: the server
 * update schema has no key field (immutable server-side), and legacy keys
 * created before the unified contract must stay savable.
 */
import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import DepartmentManagement from '../DepartmentManagement';
import { api } from '@/api/client';
import { toast } from 'react-toastify';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('react-toastify', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

const mockedGet = vi.mocked(api.get);
const mockedPost = vi.mocked(api.post);
const mockedToastError = vi.mocked(toast.error);

const departmentsFixture = [
  {
    id: 1,
    key: 'cardiology',
    name_ru: 'Кардиология SYNTH',
    name_uz: 'Kardiologiya SYNTH',
    active: true,
    display_order: 1,
    color: '#ffffff',
    icon: '🏥',
    description: '',
    stats: {},
    integrations: {},
  },
  {
    id: 2,
    key: 'dermatology',
    name_ru: 'Дерматология SYNTH',
    name_uz: 'Dermatologiya SYNTH',
    active: false,
    display_order: 2,
    color: '#ffffff',
    icon: '🏥',
    description: '',
    stats: {},
    integrations: {},
  },
];

const renderPanel = () =>
  render(
    <ThemeProvider>
      <DepartmentManagement />
    </ThemeProvider>,
  );

const openAddForm = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(
    await screen.findByRole('button', { name: 'Добавить отделение' }),
  );
};

/** Fill the create form so the KEY is the only field under test. */
const fillCreateForm = async (
  user: ReturnType<typeof userEvent.setup>,
  key: string,
) => {
  await user.type(
    screen.getByPlaceholderText('Название (русский)'),
    'Синтетика',
  );
  await user.type(
    screen.getByPlaceholderText('Ключ (например, cardio)'),
    key,
  );
};

describe('DepartmentManagement create-form key contract (round-2 review P2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGet.mockImplementation(async (url: string) => {
      if (String(url).startsWith('/admin/departments/overview')) {
        return { data: { data: { departments: [], totals: {} } } } as never;
      }
      if (String(url).startsWith('/admin/departments')) {
        return { data: { data: departmentsFixture, count: 2 } } as never;
      }
      return { data: {} } as never;
    });
    mockedPost.mockResolvedValue({ data: { success: true } } as never);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ['cardio-2', 'hyphen'],
    ['Cardio', 'uppercase letter'],
    ['2cardio', 'leading digit'],
    ['cardio lab', 'embedded space'],
    ['c'.repeat(51), 'over the 50-char limit'],
  ])(
    'rejects key "%s" (%s) inline and never calls the API',
    async (key: string) => {
      const user = userEvent.setup();
      renderPanel();
      await openAddForm(user);
      await fillCreateForm(user, key);
      await user.click(screen.getByRole('button', { name: 'Сохранить' }));

      // Inline format guidance (the round-2 P2 ask), not a post-submit 422.
      expect(
        await screen.findByText(/только строчные латинские буквы/),
      ).toBeInTheDocument();
      expect(mockedPost).not.toHaveBeenCalled();
      expect(mockedToastError).toHaveBeenCalledWith('Исправьте ошибки в форме');
    },
  );

  it('accepts a contract-conforming key and submits it to the API', async () => {
    const user = userEvent.setup();
    renderPanel();
    await openAddForm(user);
    await fillCreateForm(user, 'cardio_lab2');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(1));
    expect(mockedPost.mock.calls[0][0]).toBe('/admin/departments');
    expect(mockedPost.mock.calls[0][1]).toMatchObject({ key: 'cardio_lab2' });
  });
});
