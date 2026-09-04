/**
 * Checkbox a11y contract — PR-UI-18-5 (axe aria-toggle-field-name fix).
 *
 * The wrapper exposes role="checkbox" but historically carried NO accessible
 * name: a plain <label> sibling does not label a non-form-control element,
 * so screen readers announced an unnamed toggle. These tests lock the fix:
 *   1. explicit aria-label prop → applied to the role="checkbox" wrapper;
 *   2. label prop → aria-labelledby association via useId;
 *   3. keyboard toggle (Space/Enter) still works — the fix must not alter
 *      interaction behavior.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import Checkbox from '../Checkbox';

describe('Checkbox accessible name (PR-UI-18-5)', () => {
  it('applies an explicit aria-label to the role="checkbox" wrapper', () => {
    render(<Checkbox checked={false} onChange={() => {}} aria-label="Запомнить меня" />);
    expect(screen.getByRole('checkbox', { name: 'Запомнить меня' })).toBeInTheDocument();
  });

  it('associates the label prop through aria-labelledby', () => {
    render(<Checkbox checked={false} onChange={() => {}} label="Согласен с условиями" />);
    expect(screen.getByRole('checkbox', { name: 'Согласен с условиями' })).toBeInTheDocument();
  });

  it('renders without a name when neither aria-label nor label is given (legacy callers unchanged)', () => {
    render(<Checkbox checked={false} onChange={() => {}} />);
    const el = screen.getByRole('checkbox');
    expect(el).not.toHaveAttribute('aria-label');
    expect(el).not.toHaveAttribute('aria-labelledby');
  });
});

describe('Checkbox interaction contract (unchanged by the a11y fix)', () => {
  it('toggles via keyboard Space', () => {
    const onChange = vi.fn();
    render(<Checkbox checked={false} onChange={onChange} aria-label="Тест" />);
    fireEvent.keyDown(screen.getByRole('checkbox'), { key: ' ' });
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('toggles via keyboard Enter', () => {
    const onChange = vi.fn();
    render(<Checkbox checked onChange={onChange} aria-label="Тест" />);
    fireEvent.keyDown(screen.getByRole('checkbox'), { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it('reflects checked state in aria-checked', () => {
    const { rerender } = render(<Checkbox checked={false} onChange={() => {}} aria-label="Тест" />);
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-checked', 'false');
    rerender(<Checkbox checked onChange={() => {}} aria-label="Тест" />);
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-checked', 'true');
  });
});
