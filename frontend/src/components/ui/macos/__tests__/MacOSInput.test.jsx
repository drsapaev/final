import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import MacOSInput from '../MacOSInput';

describe('MacOSInput', () => {
  it('renders a clear button for controlled clearable inputs and calls onClear', () => {
    const onClear = vi.fn();

    render(
      <MacOSInput
        value="hello"
        onChange={() => {}}
        clearable
        onClear={onClear}
      />,
    );

    const clearButton = screen.getByRole('button', { name: /clear input/i });
    expect(clearButton).toBeInTheDocument();

    fireEvent.click(clearButton);
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('does not render a clear button when there is no value', () => {
    render(
      <MacOSInput
        value=""
        onChange={() => {}}
        clearable
        onClear={() => {}}
      />,
    );

    expect(screen.queryByRole('button', { name: /clear input/i })).not.toBeInTheDocument();
  });
});
