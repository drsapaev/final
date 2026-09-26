import '@testing-library/jest-dom';
import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../../../test/renderWithProviders';
import AppointmentsTab from '../AppointmentsTab';

describe('AppointmentsTab', () => {
  it('shows a load error instead of reporting an empty list', () => {
    renderWithProviders(
      <AppointmentsTab
        appointments={[]}
        appointmentsError
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText(/cardio_appt_empty_title/i)).not.toBeInTheDocument();
  });
});
