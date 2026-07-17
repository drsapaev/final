import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ThemeProvider } from '../../../../contexts/ThemeContext.tsx';
import Button from '../Button';
import Typography from '../Typography';

const renderWithTheme = (ui) => render(<ThemeProvider>{ui}</ThemeProvider>);

describe('macOS primitives regressions', () => {
  it('does not expose button CSS as accessible text', () => {
    renderWithTheme(<Button loading>Save</Button>);

    const button = screen.getByRole('button', { name: /save/i });
    expect(button).toHaveTextContent('Save');
    expect(button).not.toHaveTextContent('@keyframes');
    expect(button).not.toHaveTextContent('mac-spin');
  });

  it('renders Typography with the requested semantic component', () => {
    render(
      <Typography variant="h4" component="h1">
        Screen title
      </Typography>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Screen title' })).toBeInTheDocument();
  });
});
