import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Card from '../Card';

describe('Card', () => {
  it('renders with children', () => {
    render(
      <Card>
        <div>Card content</div>
      </Card>
    );
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  it('renders as div element', () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText('Card content').closest('div')).toBeInTheDocument();
  });

  it('applies correct className', () => {
    render(<Card className="custom-class">Card content</Card>);
    expect(screen.getByText('Card content').closest('div')).toHaveClass('custom-class');
  });

  it('applies custom style', () => {
    const customStyle = { backgroundColor: 'red' };
    render(<Card style={customStyle}>Test card with custom style</Card>);
    expect(screen.getByText('Test card with custom style').closest('div')).toHaveStyle('background-color: rgb(255, 0, 0)');
  });

  it('calls onClick when clicked', async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    
    render(<Card onClick={handleClick}>Card content</Card>);
    
    await user.click(screen.getByText('Card content').closest('div'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef();
    render(<Card ref={ref}>Card content</Card>);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });

  describe('Card.Header', () => {
    it('renders header content', () => {
      render(
        <Card>
          <Card.Header>
            <h3>Header Title</h3>
          </Card.Header>
          <div>Card content</div>
        </Card>
      );
      expect(screen.getByText('Header Title')).toBeInTheDocument();
    });

    it('applies correct className', () => {
      render(
        <Card>
          <Card.Header className="custom-header">Header</Card.Header>
        </Card>
      );
      expect(screen.getByText('Header').closest('div')).toHaveClass('custom-header');
    });
  });

  describe('Card.Content', () => {
    it('renders content', () => {
      render(
        <Card>
          <Card.Content>
            <p>Unique card content test</p>
          </Card.Content>
        </Card>
      );
      expect(screen.getByText('Unique card content test')).toBeInTheDocument();
    });

    it('applies correct className', () => {
      render(
        <Card>
          <Card.Content className="custom-content">Content</Card.Content>
        </Card>
      );
      expect(screen.getByText('Content').closest('div')).toHaveClass('custom-content');
    });
  });

  describe('Card.Footer', () => {
    it('renders footer content', () => {
      render(
        <Card>
          <div>Card content</div>
          <Card.Footer>
            <button>Footer Button</button>
          </Card.Footer>
        </Card>
      );
      expect(screen.getByText('Footer Button')).toBeInTheDocument();
    });

    it('applies correct className', () => {
      render(
        <Card>
          <Card.Footer className="custom-footer">Footer</Card.Footer>
        </Card>
      );
      expect(screen.getByText('Footer').closest('div')).toHaveClass('custom-footer');
    });
  });

  it('renders complete card structure', () => {
    render(
      <Card>
        <Card.Header>
          <h3>Card Title</h3>
        </Card.Header>
        <Card.Content>
          <p>Card content goes here</p>
        </Card.Content>
        <Card.Footer>
          <button>Action</button>
        </Card.Footer>
      </Card>
    );

    expect(screen.getByText('Card Title')).toBeInTheDocument();
    expect(screen.getByText('Card content goes here')).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();
  });
});
