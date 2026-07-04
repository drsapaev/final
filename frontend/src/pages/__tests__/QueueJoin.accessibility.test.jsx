import React from 'react';
import fs from 'node:fs';
import path from 'node:path';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const queueApiMocks = vi.hoisted(() => ({
  fetchQrTokenInfo: vi.fn(),
  startQueueJoinSession: vi.fn(),
  completeQueueJoinSession: vi.fn(),
}));

vi.mock('../../api/queue', () => queueApiMocks);

import QueueJoin from '../QueueJoin';

const queueJoinSourcePath = path.resolve(process.cwd(), 'src/pages/QueueJoin.jsx');
const readQueueJoinSource = () => fs.readFileSync(queueJoinSourcePath, 'utf8');

function setupQueueApiMock({
  selectableSpecialists = [
    { id: 1, specialty: 'cardiology', specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
  ],
  clinicWide = false,
  allowed = true,
  status = 'available',
  message = 'Р—Р°РїРёСЃСЊ РґРѕСЃС‚СѓРїРЅР°',
} = {}) {
  queueApiMocks.fetchQrTokenInfo.mockResolvedValue({
    queue_active: true,
    allowed,
    status,
    message,
    queue_length: 2,
    department_name: 'Кардиология',
    specialist_name: 'Кардиолог',
    target_date: '2026-02-21',
    selectable_specialists: selectableSpecialists,
  });
  queueApiMocks.startQueueJoinSession.mockResolvedValue({
    session_token: 'session-token',
    queue_info: {
      is_clinic_wide: clinicWide,
      queue_active: true,
      allowed,
      status,
      message,
      queue_length: 2,
      department_name: 'Кардиология',
      specialist_name: 'Кардиолог',
      target_date: '2026-02-21',
      selectable_specialists: selectableSpecialists,
    },
  });
  queueApiMocks.completeQueueJoinSession.mockResolvedValue({
    success: true,
    queue_number: 3,
    entries: [{ number: 3, department: 'cardiology' }],
  });
}

function renderQueueJoin(token = 'test-token') {
  return render(
    <MemoryRouter initialEntries={[`/queue/join/${token}`]}>
      <Routes>
        <Route path="/queue/join/:token" element={<QueueJoin />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderBareQueueJoin() {
  return render(
    <MemoryRouter initialEntries={['/queue/join']}>
      <Routes>
        <Route path="/queue/join" element={<QueueJoin />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('QueueJoin Accessibility & UX', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupQueueApiMock();

    const storage = new Map();
    window.localStorage.getItem = vi.fn((key) => (storage.has(key) ? storage.get(key) : null));
    window.localStorage.setItem = vi.fn((key, value) => {
      storage.set(key, String(value));
    });
    window.localStorage.removeItem = vi.fn((key) => {
      storage.delete(key);
    });
    window.localStorage.clear = vi.fn(() => {
      storage.clear();
    });
  });

  it('shows a missing token error for the bare join route without calling queue APIs', async () => {
    renderBareQueueJoin();

    expect(await screen.findByRole('alert')).toHaveTextContent(/QR-код не найден/i);
    expect(queueApiMocks.fetchQrTokenInfo).not.toHaveBeenCalled();
    expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
  });

  it('exposes labeled required fields and announces validation errors', async () => {
    renderQueueJoin();

    fireEvent.click(await screen.findByRole('button', { name: /давом этиш/i }));

    expect(await screen.findByLabelText(/фио/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/телефон рақами/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/фио/i), { target: { value: 'Тест Пациент' } });
    fireEvent.change(screen.getByLabelText(/телефон рақами/i), { target: { value: '+998 (90)' } });
    fireEvent.click(screen.getByRole('button', { name: /қўшилиш/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/телефон указан не полностью/i);

    expect(screen.getByLabelText(/фио/i)).toHaveAttribute('aria-required', 'true');
    expect(screen.getByLabelText(/телефон рақами/i)).toHaveAttribute('aria-required', 'true');
  });

  it('persists in-progress form state for the same QR token', async () => {
    const view = renderQueueJoin('persist-token');

    fireEvent.click(await screen.findByRole('button', { name: /давом этиш/i }));

    const nameInput = await screen.findByLabelText(/фио/i);
    const phoneInput = screen.getByLabelText(/телефон рақами/i);

    fireEvent.change(nameInput, { target: { value: 'Тест Пациент' } });
    fireEvent.change(phoneInput, { target: { value: '+998 (90) 123-45-67' } });

    view.unmount();

    renderQueueJoin('persist-token');
    fireEvent.click(await screen.findByRole('button', { name: /давом этиш/i }));

    expect(await screen.findByLabelText(/фио/i)).toHaveValue('Тест Пациент');
    expect(screen.getByLabelText(/телефон рақами/i)).toHaveValue('+998 (90) 123-45-67');
  });

  it('shows meaningful empty state when no specialists are available for clinic-wide QR', async () => {
    setupQueueApiMock({ selectableSpecialists: [], clinicWide: true });
    renderQueueJoin('clinic-wide-token');

    // UX Audit Registrar #2: UZ text replaced with RU for i18n consistency.
    expect(await screen.findByText(/сейчас нет специалистов для выбора через qr/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /обновить/i })).toBeInTheDocument();
  });

  it('renders backend-provided unavailable message without local queue rule assembly', async () => {
    setupQueueApiMock({
      allowed: false,
      status: 'limit_reached',
      message: 'Backend says registration is full',
    });
    renderQueueJoin('backend-status-token');

    expect(await screen.findByRole('alert')).toHaveTextContent('Backend says registration is full');
    expect(queueApiMocks.startQueueJoinSession).not.toHaveBeenCalled();
  });

  it('does not recreate unavailable queue policy messages from status codes', () => {
    const source = readQueueJoinSource();

    expect(source).not.toContain('QUEUE_JOIN_MESSAGES.registrationClosedAt');
    expect(source).not.toContain('QUEUE_JOIN_MESSAGES.receptionAlreadyOpened');
    expect(source).not.toContain('QUEUE_JOIN_MESSAGES.limitReached');
    expect(source).not.toContain('QUEUE_JOIN_MESSAGES.queueInactive');
    expect(source).toContain('setError(tokenInfo.message || QUEUE_JOIN_MESSAGES.registrationUnavailable)');
  });

  it('submits real doctor ids for clinic-wide QR instead of queue profile ids', async () => {
    setupQueueApiMock({
      selectableSpecialists: [
        { id: 6, specialty: 'cardio', specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
      ],
      clinicWide: true,
    });
    renderQueueJoin('clinic-wide-real-id-token');

    fireEvent.click(await screen.findByLabelText(/кардиолог/i));
    fireEvent.click(screen.getByRole('button', { name: /давом этиш/i }));

    fireEvent.change(await screen.findByLabelText(/фио/i), {
      target: { value: 'Тест Пациент' },
    });
    fireEvent.change(screen.getByLabelText(/телефон рақами/i), {
      target: { value: '+998 (90) 123-45-67' },
    });
    fireEvent.click(screen.getByRole('button', { name: /қўшилиш/i }));

    await screen.findByText(/сиз навбатда!/i);
    expect(queueApiMocks.completeQueueJoinSession).toHaveBeenCalledWith(
      expect.objectContaining({
        specialist_ids: [6],
      })
    );
  });

  it('provides retry action from error state and recovers to info step', async () => {
    queueApiMocks.fetchQrTokenInfo
      .mockRejectedValueOnce(new Error('network fail'))
      .mockResolvedValueOnce({
        queue_active: true,
        allowed: true,
        queue_length: 1,
        department_name: 'Кардиология',
        specialist_name: 'Кардиолог',
        target_date: '2026-02-21',
      });
    queueApiMocks.startQueueJoinSession.mockResolvedValue({
      session_token: 'session-token',
      queue_info: {
        is_clinic_wide: false,
        queue_length: 1,
        department_name: 'Кардиология',
        specialist_name: 'Кардиолог',
        target_date: '2026-02-21',
      },
    });

    renderQueueJoin('retry-token');
    expect(await screen.findByRole('alert')).toHaveTextContent(/qr-токен не найден/i);
    const retryButton = await screen.findByRole('button', { name: /қайта уриниш/i });
    fireEvent.click(retryButton);

    expect(await screen.findByRole('button', { name: /давом этиш/i })).toBeInTheDocument();
  });
});
