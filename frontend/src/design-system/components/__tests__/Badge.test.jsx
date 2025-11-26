import React from 'react';
import { render, screen } from '@testing-library/react';
import Badge from '../Badge';
import { SIZES, VARIANTS } from '../types';

describe('Badge', () => {
  it('renders with correct text', () => {
    render(<Badge>Badge text</Badge>);
    expect(screen.getByText('Badge text')).toBeInTheDocument();
  });

  it('renders as span element', () => {
    render(<Badge>Badge text</Badge>);
    expect(screen.getByText('Badge text').tagName).toBe('SPAN');
  });

  it('applies correct className', () => {
    render(<Badge className="custom-class">Badge with className</Badge>);
    expect(screen.getByText('Badge with className')).toHaveClass('custom-class');
  });

  it('applies custom style', () => {
    const customStyle = { backgroundColor: 'red' };
    render(<Badge style={customStyle}>Badge with custom style</Badge>);
    expect(screen.getByText('Badge with custom style')).toHaveStyle('background-color: rgb(255, 0, 0)');
  });

  it('applies different variants', () => {
    const { rerender } = render(<Badge variant={VARIANTS.PRIMARY}>Primary</Badge>);
    expect(screen.getByText('Primary')).toHaveClass('design-system-badge');

    rerender(<Badge variant={VARIANTS.SUCCESS}>Success</Badge>);
    expect(screen.getByText('Success')).toHaveClass('design-system-badge');

    rerender(<Badge variant={VARIANTS.DANGER}>Danger</Badge>);
    expect(screen.getByText('Danger')).toHaveClass('design-system-badge');

    rerender(<Badge variant={VARIANTS.WARNING}>Warning</Badge>);
    expect(screen.getByText('Warning')).toHaveClass('design-system-badge');

    rerender(<Badge variant={VARIANTS.INFO}>Info</Badge>);
    expect(screen.getByText('Info')).toHaveClass('design-system-badge');
  });

  it('applies different sizes', () => {
    const { rerender } = render(<Badge size={SIZES.SM}>Small</Badge>);
    expect(screen.getByText('Small')).toHaveClass('design-system-badge');

    rerender(<Badge size={SIZES.MD}>Medium</Badge>);
    expect(screen.getByText('Medium')).toHaveClass('design-system-badge');

    rerender(<Badge size={SIZES.LG}>Large</Badge>);
    expect(screen.getByText('Large')).toHaveClass('design-system-badge');
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef();
    render(<Badge ref={ref}>Badge text</Badge>);
    expect(ref.current).toBeInstanceOf(HTMLSpanElement);
  });

  it('renders with default variant when no variant specified', () => {
    render(<Badge>Default Badge</Badge>);
    expect(screen.getByText('Default Badge')).toHaveClass('design-system-badge');
  });

  it('renders with default size when no size specified', () => {
    render(<Badge>Default Size</Badge>);
    expect(screen.getByText('Default Size')).toHaveClass('design-system-badge');
  });

  it('renders with number content', () => {
    render(<Badge>42</Badge>);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders with icon content', () => {
    render(<Badge>🚀</Badge>);
    expect(screen.getByText('🚀')).toBeInTheDocument();
  });
});
