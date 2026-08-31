/**
 * Select Stories — canonical macOS-style Select primitive.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers options API (value/label pairs), placeholder, selected
 * value, label + error and disabled state. The dropdown opens on click —
 * portal-positioned menu.
 */
import React from 'react';
import Select from './Select';

export default {
  title: 'Primitives/Select',
  component: Select,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style Select — button-triggered dropdown with ' +
          'portal menu, keyboard navigation, label and error slots. ' +
          'New code should prefer onValueChange over the legacy onChange.',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', display: 'grid', gap: '20px', maxWidth: '360px', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

const doctorOptions = [
  { value: 'cardiology', label: 'Кардиология' },
  { value: 'dermatology', label: 'Дерматология' },
  { value: 'dentistry', label: 'Стоматология' },
];

export const Default = {
  name: 'Базовый выбор',
  args: {
    options: doctorOptions,
    placeholder: 'Выберите отделение…',
    label: 'Отделение',
  },
};

export const Selected = {
  name: 'С выбранным значением',
  args: {
    options: doctorOptions,
    value: 'dentistry',
    label: 'Отделение',
  },
};

export const ErrorState = {
  name: 'Ошибка валидации',
  args: {
    options: doctorOptions,
    placeholder: 'Выберите врача…',
    label: 'Врач',
    error: 'Поле обязательно для заполнения',
  },
};

export const Disabled = {
  name: 'Отключено',
  args: {
    options: doctorOptions,
    value: 'cardiology',
    label: 'Отделение',
    disabled: true,
  },
};
