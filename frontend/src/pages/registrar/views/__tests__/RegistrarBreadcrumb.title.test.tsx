/**
 * RQ-20 (срез RQ-20.a): RegistrarBreadcrumb department-crumb title contract.
 *
 * Pins the plan §RQ-20 result "произвольный профиль показывает свое название"
 * for the breadcrumb: the crumb must show the SAME title the tab button
 * shows (the loaded queue profile label from the Tabs SSOT). The previous
 * implementation looked up `p.title` on the TabItem objects passed by the
 * panel — those carry `label` — so every backend-driven tab fell back to the
 * raw profile key in the wayfinding crumb.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import RegistrarBreadcrumb from '../RegistrarBreadcrumb';

const baseProps = {
  searchQuery: '',
  wizardEditMode: false,
  showWizard: false,
  onNavigateToWelcome: vi.fn(),
  onNavigateToAppointments: vi.fn(),
  onNavigateToQueue: vi.fn(),
  onNavigateToPatients: vi.fn(),
  tI18n: (key: string) => key,
};

describe('RegistrarBreadcrumb department title (RQ-20)', () => {
  it('shows the loaded profile label for an arbitrary profile key', () => {
    render(
      <RegistrarBreadcrumb
        {...baseProps}
        activeTab="synthetic-diagnostics"
        queueProfiles={[{ key: 'synthetic-diagnostics', label: 'Синтетическая диагностика' }]}
      />,
    );
    expect(screen.getByText('Синтетическая диагностика')).toBeInTheDocument();
  });

  it('falls back to the raw key when the profile is not loaded', () => {
    render(
      <RegistrarBreadcrumb
        {...baseProps}
        activeTab="synthetic-diagnostics"
        queueProfiles={[]}
      />,
    );
    expect(screen.getByText('synthetic-diagnostics')).toBeInTheDocument();
  });

  it('keeps supporting the title-shaped profile objects', () => {
    render(
      <RegistrarBreadcrumb
        {...baseProps}
        activeTab="cardiology"
        queueProfiles={[{ key: 'cardiology', title: 'Кардиолог' }]}
      />,
    );
    expect(screen.getByText('Кардиолог')).toBeInTheDocument();
  });

  it('does not render a department crumb without an active tab', () => {
    render(
      <RegistrarBreadcrumb
        {...baseProps}
        activeTab={null}
        queueProfiles={[{ key: 'cardiology', label: 'Кардиолог' }]}
      />,
    );
    expect(screen.queryByText('Кардиолог')).not.toBeInTheDocument();
  });
});
