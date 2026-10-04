import React from 'react';
import '@testing-library/jest-dom';
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import i18n from '@/i18n';
import StatCard from '../StatCard';

describe('StatCard loading accessibility', () => {
  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });
  });

  it('exposes a polite busy status and hides decorative skeletons', async () => {
    await act(async () => {
      await i18n.changeLanguage('ru');
    });

    render(<StatCard loading title="Patients" value="42" />);

    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAccessibleName('Загрузка…');

    const decorativeSkeletons = status.querySelectorAll('[aria-hidden="true"]');
    expect(decorativeSkeletons).toHaveLength(3);
  });
});
