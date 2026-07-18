import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReactElement } from 'react';

import { ThemeProvider } from '../../../../contexts/ThemeContext';
import Button from '../Button';
import Typography from '../Typography';

// Typography is still implicit-any and its propTypes require `color`
// and `paragraph`. Cast through unknown to a permissive component so
// the test's bare <Typography variant="h4" component="h1"> usage
// compiles without supplying those props.
const TypographyAny = Typography as unknown as React.ComponentType<Record<string, unknown>>;

const renderWithTheme = (ui: ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

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
      <TypographyAny variant="h4" component="h1">
        Screen title
      </TypographyAny>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Screen title' })).toBeInTheDocument();
  });
});
