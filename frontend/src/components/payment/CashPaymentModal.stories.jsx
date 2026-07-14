/**
 * CashPaymentModal Stories
 *
 * UX Audit R-1.2: visual testing for cash payment modal with quick denominations.
 * Shows states: default (cash method), with change due, insufficient funds.
 */
import CashPaymentModal from './CashPaymentModal';

export default {
  title: 'Payment/CashPaymentModal',
  component: CashPaymentModal,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Modal for processing cash/card payments. ' +
          'Features: quick cash denominations (50k/100k/200k/500k UZS), ' +
          '"Без сдачи" button, change-due calculation, insufficient funds validation.',
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
    appointment: {
      control: 'object',
      description: 'Appointment data',
    },
  },
};

// Default cash payment
export const DefaultCash = {
  args: {
    appointment: {
      id: 1001,
      patient_name: 'Иванов Иван Иванович',
      patient_id: 101,
      department: 'Кардиология',
      appointment_date: '2026-07-14',
      appointment_time: '10:00',
      total_amount: 150000,
      remaining_amount: 150000,
      payment_amount: 150000,
    },
    onProcessPayment: () => alert('Payment processed'),
    onClose: () => alert('Modal closed'),
  },
};

// Large amount
export const LargeAmount = {
  args: {
    appointment: {
      id: 1002,
      patient_name: 'Петров Петр Петрович',
      patient_id: 102,
      department: 'Стоматология',
      appointment_date: '2026-07-14',
      appointment_time: '11:30',
      total_amount: 850000,
      remaining_amount: 850000,
      payment_amount: 850000,
    },
    onProcessPayment: () => {},
    onClose: () => {},
  },
};
