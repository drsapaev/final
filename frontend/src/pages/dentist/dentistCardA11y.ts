import type React from 'react';

/**
 * PR-UI-15-6: keyboard a11y for the dental patient-card grids — verbatim
 * body of the former DentistPanelUnified.handleCardKeyDown (Enter/Space
 * activation), shared by the extracted card-grid views.
 */
export const dentalCardKeyDown = (
  event: React.KeyboardEvent<HTMLElement>,
  action: () => void,
) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    action();
  }
};
