import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getVisitMock, rescheduleVisitMock } = vi.hoisted(() => ({
  getVisitMock: vi.fn(),
  rescheduleVisitMock: vi.fn(),
}));

vi.mock('../../api', () => ({
  getVisit: getVisitMock,
  rescheduleVisit: rescheduleVisitMock,
}));

vi.mock('../../components/RescheduleDialog', () => ({
  default: () => null,
}));

// PR #1913 bugfix: VisitDetails теперь использует MacOSCard который требует
// ThemeProvider (useTheme). Добавляем mock для useTheme, чтобы тест рендерился.
vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    getColor: (key) => {
      const colors = {
        textPrimary: '#1d1d1f',
        textSecondary: '#86868b',
        textTertiary: '#aeaeb2',
        cardBg: '#ffffff',
        bgPrimary: '#ffffff',
        bgSecondary: '#f5f5f7',
        bgTertiary: '#e5e5ea',
        border: '#d1d1d6',
        accent: '#007aff',
        success: '#34c759',
        warning: '#ff9500',
        error: '#ff3b30',
      };
      return colors[key] || '#000000';
    },
  }),
  ThemeProvider: ({ children }) => children,
}));

import VisitDetails from '../VisitDetails.jsx';

function renderVisitDetails() {
  return render(
    <MemoryRouter initialEntries={['/clinical/visits/1']}>
      <Routes>
        <Route path="/clinical/visits/:id" element={<VisitDetails />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('VisitDetails contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders backend visit detail wrapper with patient and doctor display fields', async () => {
    getVisitMock.mockResolvedValue({
      visit: {
        id: 1,
        patient_id: 1,
        patient_name: 'Karimov Aziz',
        doctor_id: 2,
        doctor_name: 'Demo Cardiologist',
        room: '201',
        status: 'open',
        visit_date: '2026-05-25',
      },
      services: [{ name: 'Consultation', price: 125000, qty: 1 }],
    });

    renderVisitDetails();

    expect(await screen.findByText('Karimov Aziz')).toBeInTheDocument();
    expect(screen.getByText('Demo Cardiologist / 201')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
    expect(getVisitMock).toHaveBeenCalledWith('1');
  });
});
