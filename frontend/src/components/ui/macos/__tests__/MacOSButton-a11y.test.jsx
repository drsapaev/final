import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MacOSButton from '../MacOSButton';

describe('MacOSButton A11y', () => {
  it('receives focus when tabbed to', () => {
    const handleFocus = vi.fn();
    const handleBlur = vi.fn();
    render(
      <MacOSButton onFocus={handleFocus} onBlur={handleBlur}>
        Focus me
      </MacOSButton>
    );

    const button = screen.getByRole('button');
    button.focus();
    expect(handleFocus).toHaveBeenCalled();

    button.blur();
    expect(handleBlur).toHaveBeenCalled();
  });

  it('applies aria-label if provided', () => {
    render(<MacOSButton aria-label="custom label">Button</MacOSButton>);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'custom label');
  });
});
