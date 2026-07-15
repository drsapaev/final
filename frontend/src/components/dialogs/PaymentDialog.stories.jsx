/**
 * PaymentDialog Stories
 *
 * UX Audit R-4.3: visual testing for payment dialog with backend-driven methods.
 */
import PaymentDialog from './PaymentDialog';
import { useTranslation } from '../../i18n/adapter';

export default {
  title: 'Dialogs/PaymentDialog',
  component: PaymentDialog,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Dialog for processing payments. ' +
          'Uses usePaymentMethods() hook (Phase 2 backend-driven). ' +
          'Features: 4 payment methods with unique icons, amount input, payment processing.',
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
};

export const DefaultPayment = {
  args: {
    appointment: {
      id: 1001,
      patient_name: 'Иванов Иван Иванович',
      patient_id: 101,
      department: 'Кардиология',
      appointment_date: '2026-07-14',
      appointment_time: '10:00',
      total_amount: 150000,
    },
    isPaid: false,
    onClose: () => {},
    onConfirmPayment: () => {},
  },
};

export const AlreadyPaid = {
  args: {
    appointment: {
      id: 1002,
      patient_name: 'Петров Петр Петрович',
      patient_id: 102,
      department: 'Стоматология',
      appointment_date: '2026-07-14',
      appointment_time: '11:30',
      total_amount: 350000,
      payment_status: 'paid',
    },
    isPaid: true,
    onClose: () => {},
    onConfirmPayment: () => {},
  },
};
