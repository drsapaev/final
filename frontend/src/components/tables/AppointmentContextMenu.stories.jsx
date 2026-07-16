/**
 * AppointmentContextMenu Stories
 *
 * UX Audit R-2.7: visual testing for context menu with force_majeure tooltip.
 */
import AppointmentContextMenu from './AppointmentContextMenu';
import { useTranslation } from '../../i18n/useTranslation';

export default {
  title: 'Tables/AppointmentContextMenu',
  component: AppointmentContextMenu,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Context menu for appointment row actions. ' +
          'UX Audit R-2.7: force_majeure has tooltip explaining the action. ' +
          'UX Audit R-2.5: tel: uses native anchor instead of window.open().',
      },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ padding: '20px', background: 'var(--mac-bg-secondary)', minHeight: '100vh', position: 'relative' }}>
        <Story />
      </div>
    ),
  ],
};

export const RegistrarView = {
  args: {
    row: {
      id: 1001,
      patient_fio: 'Иванов Иван Иванович',
      patient_phone: '+998901234567',
      doctor_name: 'Dr Test',
      department: 'cardiology',
    },
    position: { x: 100, y: 100 },
    onAction: () => {},
    onClose: () => {},
    isDoctorView: false,
  },
};

export const DoctorView = {
  args: {
    row: {
      id: 1001,
      patient_fio: 'Иванов Иван Иванович',
      patient_phone: '+998901234567',
      doctor_name: 'Dr Test',
      department: 'cardiology',
    },
    position: { x: 100, y: 100 },
    onAction: () => {},
    onClose: () => {},
    isDoctorView: true,
  },
};
