import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import { ThemeProvider } from '@/contexts/ThemeContext';
import { CircularProgress } from '../Progress';

it('exposes the progress value and hides its decorative ring', () => {
  render(
    <ThemeProvider>
      <CircularProgress value={3} max={5} showValue />
    </ThemeProvider>
  );

  const progress = screen.getByRole('progressbar', {
    name: 'Progress: 60%',
    value: { min: 0, max: 5, now: 3 },
  });
  const ring = progress.querySelector('svg');
  expect(ring).toHaveAttribute('aria-hidden', 'true');
  expect(ring).toHaveAttribute('focusable', 'false');
});
