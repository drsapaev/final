import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const completionButtonName = 'finish visit';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../../ui/macos', () => ({
  Button: ({ children, disabled, onClick }: {
    children: React.ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }) => <button disabled={disabled} onClick={onClick}>{children}</button>,
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AppEmpty: () => <div />,
}));

vi.mock('../../emr-v2/EMRContainerV2', () => ({
  EMRContainerV2: ({
    isReadOnly,
    onComplete,
  }: {
    isReadOnly?: boolean;
    onComplete?: (savedData: Record<string, unknown>) => Promise<void> | void;
  }) => (
    <div data-testid="emr-container" data-read-only={String(Boolean(isReadOnly))}>
      {onComplete && !isReadOnly && (
        <button onClick={() => { void onComplete({ complaints: 'saved complaint' }); }}>
          {completionButtonName}
        </button>
      )}
    </div>
  ),
}));

import { VisitTab } from '../VisitTab';

describe('VisitTab completion ownership', () => {
  const getColor = (key: string) => key;
  const getFontSize = (key: string) => key;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('routes completion through EMRContainer for an active visit', async () => {
    const onComplete = vi.fn();
    render(
      <VisitTab
        selectedPatient={{ visit_id: 17, patient_id: 23, status: 'in_progress' }}
        onCancel={vi.fn()}
        onComplete={onComplete}
        onGoToAppointments={vi.fn()}
        getColor={getColor}
        getFontSize={getFontSize}
      />,
    );

    expect(screen.getByTestId('emr-container')).toHaveAttribute('data-read-only', 'false');
    fireEvent.click(screen.getByRole('button', { name: completionButtonName }));
    expect(onComplete).toHaveBeenCalledWith({ complaints: 'saved complaint' });
  });

  it('opens completed visits read-only and removes completion action', () => {
    render(
      <VisitTab
        selectedPatient={{ visit_id: 17, patient_id: 23, status: 'served' }}
        onCancel={vi.fn()}
        onComplete={vi.fn()}
        onGoToAppointments={vi.fn()}
        getColor={getColor}
        getFontSize={getFontSize}
      />,
    );

    expect(screen.getByTestId('emr-container')).toHaveAttribute('data-read-only', 'true');
    expect(screen.queryByRole('button', { name: completionButtonName })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'cardio.cardio_visit_back_to_queue' })).toBeInTheDocument();
  });
});
