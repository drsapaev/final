import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import CartStepV2 from '../CartStepV2';

const buildProps = () => ({
  cart: {
    items: [
      {
        id: 'item-1',
        service_id: 10,
        service_name: 'Консультация',
        service_price: 50000,
        quantity: 1,
        doctor_id: null,
      },
    ],
    visit_date: '',
    discount_mode: 'none',
    all_free: false,
  },
  onAddToCart: vi.fn(),
  onRemoveFromCart: vi.fn(),
  servicesData: [
    {
      id: 10,
      name: 'Консультация',
      requires_doctor: true,
      accepted_specialties: null,
      price: 50000,
    },
  ],
  doctorsData: [
    {
      id: 7,
      user: { full_name: 'Доктор Тестов' },
      specialty: 'cardiology',
      cabinet: '12',
    },
    {
      id: 8,
      specialty: 'dermatology',
      cabinet: '14',
    },
  ],
  errors: undefined,
  activeCategory: 'all',
  searchQuery: '',
  editMode: false,
  getServiceName: () => 'Консультация',
  onUpdateItem: vi.fn(),
  cartQuoteStatus: 'idle' as const,
  cartQuoteTotal: null,
  cartQuoteMessage: undefined,
});

describe('CartStepV2 doctor options', () => {
  it('renders only real doctors with interpolated fallback and cabinet labels', () => {
    render(<CartStepV2 {...buildProps()} />);

    const select = screen.getByRole('combobox');
    const options = within(select).getAllByRole('option');

    expect(options).toHaveLength(3);
    expect(options[1]).toHaveTextContent('Доктор Тестов · cardiology · каб. 12');
    expect(options[2]).toHaveTextContent('Врач #8 · dermatology · каб. 14');
    expect(select.textContent).not.toMatch(/\{doctor\.|\$\{doctor\.|total_doctors|by_specialty/);
  });
});
