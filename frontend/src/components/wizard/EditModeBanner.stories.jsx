/**
 * EditModeBanner Stories
 *
 * UX Audit R-3.3: visual testing for edit mode banner with QR/Desk source badge.
 * Shows 2 states: online source (QR badge), desk source (Desk badge).
 */
import EditModeBanner from './EditModeBanner';

export default {
  title: 'Wizard/EditModeBanner',
  component: EditModeBanner,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Banner shown when wizard is in edit mode. ' +
          'Displays source badge: QR (online, purple) or Desk (registrar, secondary). ' +
          'CSS migrated from inline styles (UX Audit R-3.3).',
      },
    },
  },
  argTypes: {
    editMode: {
      control: 'boolean',
      description: 'Whether wizard is in edit mode',
    },
    initialData: {
      control: 'object',
      description: 'Initial data with source field',
    },
  },
};

// Edit mode with online (QR) source
export const OnlineSource = {
  args: {
    editMode: true,
    initialData: {
      source: 'online',
      source_kind: 'online',
      patient_fio: 'Иванов Иван Иванович',
    },
  },
};

// Edit mode with desk (registrar) source
export const DeskSource = {
  args: {
    editMode: true,
    initialData: {
      source: 'desk',
      patient_fio: 'Петров Петр Петрович',
    },
  },
};

// Not in edit mode — banner hidden
export const NotInEditMode = {
  args: {
    editMode: false,
    initialData: null,
  },
};
