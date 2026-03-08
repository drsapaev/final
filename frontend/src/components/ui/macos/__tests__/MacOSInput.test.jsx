import { render, screen, fireEvent } from '@testing-library/react';
import React, { useState } from 'react';
import MacOSInput from '../MacOSInput';

describe('MacOSInput', () => {
  it('renders correctly', () => {
    render(<MacOSInput placeholder="Enter something" />);
    expect(screen.getByPlaceholderText('Enter something')).toBeInTheDocument();
  });

  it('shows clear button when clearable is true and has value', () => {
    render(<MacOSInput clearable defaultValue="test value" />);
    expect(screen.getByRole('button', { name: 'Clear input' })).toBeInTheDocument();
  });

  it('clears value when clear button is clicked (uncontrolled)', () => {
    const handleChange = vi.fn();
    render(<MacOSInput clearable defaultValue="test value" onChange={handleChange} />);
    const button = screen.getByRole('button', { name: 'Clear input' });
    fireEvent.click(button);
    expect(handleChange).toHaveBeenCalled();
  });

  it('clears value when clear button is clicked (controlled)', () => {
    const Wrapper = () => {
      const [val, setVal] = useState('test');
      return <MacOSInput clearable value={val} onChange={(e) => setVal(e.target.value)} />;
    };
    render(<Wrapper />);

    expect(screen.getByDisplayValue('test')).toBeInTheDocument();
    const button = screen.getByRole('button', { name: 'Clear input' });

    fireEvent.click(button);

    expect(screen.queryByDisplayValue('test')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Clear input' })).not.toBeInTheDocument();
  });
});
