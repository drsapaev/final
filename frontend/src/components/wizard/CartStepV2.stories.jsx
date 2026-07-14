/**
 * CartStepV2 Stories
 *
 * UX Audit R-3.3: visual testing for cart step with services grid
 * and cart summary. Shows states: empty cart, with items, with discount.
 */
import CartStepV2 from './CartStepV2';

export default {
  title: 'Wizard/CartStepV2',
  component: CartStepV2,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Step 2 of the appointment wizard. ' +
          'Features: 3-column services grid, quick add to cart, ' +
          'quantity controls, discount mode selector, consultation repeat eligibility. ' +
          'UX Audit R-3.3: inline styles migrated to CSS (38 → 10).',
      },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ padding: '20px', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
  argTypes: {
    cart: {
      control: 'object',
      description: 'Cart state with items',
    },
  },
};

const sampleServices = [
  { id: 101, code: 'C001', name: 'Консультация кардиолога', price: 150000, requires_doctor: true },
  { id: 102, code: 'C002', name: 'ЭКГ', price: 80000, requires_doctor: false },
  { id: 103, code: 'C003', name: 'УЗИ сердца', price: 200000, requires_doctor: true },
];

// Empty cart
export const EmptyCart = {
  args: {
    cart: { items: [], discount_mode: 'none', all_free: false },
    services: sampleServices,
    onAddToCart: () => {},
    onRemoveFromCart: () => {},
    onUpdateQuantity: () => {},
    onUpdateCart: () => {},
    onApplyRepeatSuggestion: () => {},
  },
};

// Cart with items
export const WithItems = {
  args: {
    cart: {
      items: [
        { id: 1, service_id: 101, service_code: 'C001', name: 'Консультация кардиолога', price: 150000, quantity: 1, doctor_id: 1, doctor_name: 'Dr Test' },
        { id: 2, service_id: 102, service_code: 'C002', name: 'ЭКГ', price: 80000, quantity: 1 },
      ],
      discount_mode: 'none',
      all_free: false,
    },
    services: sampleServices,
    onAddToCart: () => {},
    onRemoveFromCart: () => {},
    onUpdateQuantity: () => {},
    onUpdateCart: () => {},
    onApplyRepeatSuggestion: () => {},
  },
};

// Cart with repeat discount
export const WithRepeatDiscount = {
  args: {
    cart: {
      items: [
        { id: 1, service_id: 101, service_code: 'C001', name: 'Консультация кардиолога', price: 150000, quantity: 1, doctor_id: 1, doctor_name: 'Dr Test' },
      ],
      discount_mode: 'repeat',
      all_free: false,
    },
    services: sampleServices,
    onAddToCart: () => {},
    onRemoveFromCart: () => {},
    onUpdateQuantity: () => {},
    onUpdateCart: () => {},
    onApplyRepeatSuggestion: () => {},
    consultationRows: [
      { itemId: 1, serviceName: 'Консультация кардиолога', doctorName: 'Dr Test', eligibility: { eligible: true, reason: 'Повторный визит в течение 30 дней', repeat_discount_percent: 100 } },
    ],
  },
};
