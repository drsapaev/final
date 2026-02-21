import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import QueueJoin from '../QueueJoin';

function createResponse(payload, ok = true, status = 200) {
  return {
    ok,
    status,
    statusText: ok ? 'OK' : 'Error',
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  };
}

function setupFetchMock({
  specialists = [
    { id: 1, specialty: 'cardiology', specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
  ],
  clinicWide = false,
} = {}) {
  global.fetch = vi.fn(async (input, options = {}) => {
    const url = String(input);

    if (url === '/api/v1/queues/profiles/public') {
      return createResponse({
        specialists,
      });
    }

    if (url.includes('/api/v1/queue/qr-tokens/')) {
      return createResponse({
        queue_active: true,
        allowed: true,
        queue_length: 2,
        department_name: 'Кардиология',
        specialist_name: 'Кардиолог',
        target_date: '2026-02-21',
      });
    }

    if (url === '/api/v1/queue/join/start' && options.method === 'POST') {
      return createResponse({
        session_token: 'session-token',
        queue_info: {
          is_clinic_wide: clinicWide,
          queue_length: 2,
          department_name: 'Кардиология',
          specialist_name: 'Кардиолог',
          target_date: '2026-02-21',
        },
      });
    }

    if (url === '/api/v1/queue/join/complete' && options.method === 'POST') {
      return createResponse({
        success: true,
        queue_number: 3,
        entries: [{ number: 3, department: 'cardiology' }],
      });
    }

    return createResponse({ detail: `Unhandled URL: ${url}` }, false, 404);
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

describe('QueueJoin Accessibility & UX', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupFetchMock();

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

  it('exposes labeled required fields and announces validation errors', async () => {
    renderQueueJoin();

    fireEvent.click(await screen.findByRole('button', { name: /давом этиш/i }));

    expect(await screen.findByLabelText(/фио/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/телефон рақами/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/фио/i), { target: { value: 'Тест Пациент' } });
    fireEvent.change(screen.getByLabelText(/телефон рақами/i), { target: { value: '+998 (90)' } });
    fireEvent.click(screen.getByRole('button', { name: /қўшилиш/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/телефон рақами тўлиқ эмас/i);

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
    setupFetchMock({ specialists: [], clinicWide: true });
    renderQueueJoin('clinic-wide-token');

    expect(await screen.findByText(/ҳозирча qr орқали танлаш учун мутахассислар мавжуд эмас/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /янгилаш/i })).toBeInTheDocument();
  });

  it('provides retry action from error state and recovers to info step', async () => {
    let tokenInfoCalls = 0;
    global.fetch = vi.fn(async (input, options = {}) => {
      const url = String(input);

      if (url === '/api/v1/queues/profiles/public') {
        return createResponse({
          specialists: [
            { id: 1, specialty: 'cardiology', specialty_display: 'Кардиолог', icon: '❤️', color: '#FF3B30' },
          ],
        });
      }

      if (url.includes('/api/v1/queue/qr-tokens/')) {
        tokenInfoCalls += 1;
        if (tokenInfoCalls === 1) {
          return createResponse({ detail: 'network fail' }, false, 500);
        }
        return createResponse({
          queue_active: true,
          allowed: true,
          queue_length: 1,
          department_name: 'Кардиология',
          specialist_name: 'Кардиолог',
          target_date: '2026-02-21',
        });
      }

      if (url === '/api/v1/queue/join/start' && options.method === 'POST') {
        return createResponse({
          session_token: 'session-token',
          queue_info: {
            is_clinic_wide: false,
            queue_length: 1,
            department_name: 'Кардиология',
            specialist_name: 'Кардиолог',
            target_date: '2026-02-21',
          },
        });
      }

      if (url === '/api/v1/queue/join/complete' && options.method === 'POST') {
        return createResponse({
          success: true,
          queue_number: 2,
          entries: [{ number: 2, department: 'cardiology' }],
        });
      }

      return createResponse({ detail: `Unhandled URL: ${url}` }, false, 404);
    });

    renderQueueJoin('retry-token');
    const retryButton = await screen.findByRole('button', { name: /қайта уриниш/i });
    fireEvent.click(retryButton);

    expect(await screen.findByRole('button', { name: /давом этиш/i })).toBeInTheDocument();
  });
});
