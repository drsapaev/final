import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import CartStepV2 from '../CartStepV2';
import { ThemeProvider } from '../../../contexts/ThemeContext';

const consultation = {
  id: 10,
  name: 'Консультация кардиолога',
  category_code: 'K',
  is_consultation: true,
  doctor_selection_required: true,
  doctor_booking_available: true,
  requires_doctor: false,
  department_key: 'cardiology',
  accepted_specialties: ['cardiology'],
  price: 50000,
};

const doctors = [
  { id: 7, user: { full_name: 'Иванов Иван' }, specialty: 'cardiology', cabinet: '12' },
  { id: 8, user: { full_name: 'Петров Пётр' }, specialty: 'cardiology', cabinet: '14' },
  { id: 9, user: { full_name: 'Неактивный Врач' }, specialty: 'cardiology', is_active: false },
  { id: 11, user: { full_name: 'Сидоров Сергей' }, specialty: 'dermatology' },
];

const buildProps = () => ({
  cart: { items: [], discount_mode: 'none' },
  onAddToCart: vi.fn(),
  onRemoveFromCart: vi.fn(),
  servicesData: [consultation],
  doctorsData: doctors,
  activeCategory: 'specialists',
  searchQuery: '',
  getServiceName: () => consultation.name,
  onUpdateItem: vi.fn(),
  cartQuoteStatus: 'idle' as const,
});

describe('CartStepV2 doctor cards', () => {
  it('shows each active doctor by full name with eligible services, including an empty doctor card', () => {
    render(<CartStepV2 {...buildProps()} />);

    const ivanov = screen.getByRole('region', { name: 'Иванов Иван' });
    const petrov = screen.getByRole('region', { name: 'Петров Пётр' });
    const sidorov = screen.getByRole('region', { name: 'Сидоров Сергей' });
    expect(within(ivanov).getByRole('button', { name: /Консультация кардиолога/ })).toBeInTheDocument();
    expect(within(petrov).getByRole('button', { name: /Консультация кардиолога/ })).toBeInTheDocument();
    expect(within(sidorov).getByText('Услуги не найдены')).toBeInTheDocument();
    expect(screen.queryByText('Неактивный Врач')).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('submits the service with the doctor from the clicked card', () => {
    const props = buildProps();
    render(<CartStepV2 {...props} />);
    fireEvent.click(within(screen.getByRole('region', { name: 'Петров Пётр' }))
      .getByRole('button', { name: /Консультация кардиолога/ }));
    expect(props.onAddToCart).toHaveBeenCalledWith(consultation, doctors[1]);
  });

  it('searches doctor names and retains the matching doctor service', () => {
    render(<CartStepV2 {...buildProps()} searchQuery="Петров" />);
    expect(screen.getByRole('region', { name: 'Петров Пётр' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Иванов Иван' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Петров Пётр' }))
      .getByRole('button', { name: /Консультация кардиолога/ })).toBeInTheDocument();
  });

  it('shows but disables a consultation whose doctor queue is not configured', () => {
    const props = buildProps();
    render(<CartStepV2 {...props} servicesData={[{ ...consultation, doctor_booking_available: false }]} />);
    const card = screen.getByRole('region', { name: 'Иванов Иван' });
    const button = within(card).getByRole('button', { name: /Консультация кардиолога/ });
    expect(button).toBeDisabled();
    expect(within(card).getByText('Очередь для этой консультации не настроена')).toBeInTheDocument();
    fireEvent.click(button);
    expect(props.onAddToCart).not.toHaveBeenCalled();
  });

  it('locks QR edits to the original doctor and keeps the cart assignment read-only', () => {
    render(<ThemeProvider><CartStepV2 {...buildProps()} lockedDoctorId={7} cart={{
      items: [{ id: 'original', service_id: 10, service_name: consultation.name, doctor_id: 7, quantity: 1 }],
      discount_mode: 'none',
    }} /></ThemeProvider>);
    expect(screen.getByRole('region', { name: 'Иванов Иван' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Петров Пётр' })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.getAllByText('Врач: Иванов Иван')).toHaveLength(2);
  });
});
