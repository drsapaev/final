import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '../Button';
import { SIZES, VARIANTS } from '../types';

describe('Button', () => {
  it('renders with correct text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('renders as button element', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('calls onClick when clicked', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Button onClick={handleClick}>Click me</Button>);
    
    await user.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('does not call onClick when disabled', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Button disabled onClick={handleClick}>Click me</Button>);
    
    await user.click(screen.getByRole('button'));
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('shows loading state', () => {
    render(<Button loading>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
    // Проверяем наличие спиннера загрузки
    expect(screen.getByRole('button')).toHaveStyle('cursor: not-allowed');
  });

  it('applies correct variant styles', () => {
    const { rerender } = render(<Button variant={VARIANTS.PRIMARY}>Primary</Button>);
    expect(screen.getByRole('button')).toHaveClass('design-system-button');

    rerender(<Button variant={VARIANTS.SECONDARY}>Secondary</Button>);
    expect(screen.getByRole('button')).toHaveClass('design-system-button');
  });

  it('applies correct size styles', () => {
    const { rerender } = render(<Button size={SIZES.SM}>Small</Button>);
    expect(screen.getByRole('button')).toHaveClass('design-system-button');

    rerender(<Button size={SIZES.MD}>Medium</Button>);
    expect(screen.getByRole('button')).toHaveClass('design-system-button');

    rerender(<Button size={SIZES.LG}>Large</Button>);
    expect(screen.getByRole('button')).toHaveClass('design-system-button');
  });

  it('applies fullWidth style when fullWidth is true', () => {
    render(<Button fullWidth>Full Width</Button>);
    expect(screen.getByRole('button')).toHaveStyle('width: 100%');
  });

  it('applies custom className', () => {
    render(<Button className="custom-class">Click me</Button>);
    expect(screen.getByRole('button')).toHaveClass('custom-class');
  });

  it('applies custom style', () => {
    const customStyle = { backgroundColor: 'red' };
    render(<Button style={customStyle}>Click me</Button>);
    expect(screen.getByRole('button')).toHaveStyle('background-color: red');
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef();
    render(<Button ref={ref}>Click me</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  it('handles keyboard events', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Button onClick={handleClick}>Click me</Button>);
    
    screen.getByRole('button').focus();
    await user.keyboard('{Enter}');
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders with icon and text', () => {
    render(
      <Button>
        <span>🚀</span>
        Button with Icon
      </Button>
    );
    expect(screen.getByText('🚀')).toBeInTheDocument();
    expect(screen.getByText('Button with Icon')).toBeInTheDocument();
  });
});
