/**
 * Select Stories — canonical Select primitive (plan §PR-UI-18 item 2).
 *
 * Canonical select: options + value + placeholder; `onValueChange` is the
 * preferred value-based handler (the `onChange` event-style one is the
 * deprecated legacy path).
 */
import Select from './Select';

export default {
  title: 'UI/MacOS/Select',
  component: Select,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical Select: options/value/placeholder; onValueChange — ' +
          'предпочтительный обработчик (onChange — legacy-путь).',
      },
    },
  },
};

const specialtyOptions = [
  { value: 'cardiology', label: 'Кардиология' },
  { value: 'dermatology', label: 'Дерматология' },
  { value: 'dentistry', label: 'Стоматология' },
];

export const Basic = {
  args: {
    label: 'Специализация',
    options: specialtyOptions,
    placeholder: 'Выберите специализацию',
  },
};

export const WithValue = {
  args: {
    label: 'Специализация',
    options: specialtyOptions,
    value: 'cardiology',
  },
};

export const Disabled = {
  args: {
    label: 'Кабинет',
    options: [
      { value: '12', label: 'Кабинет 12' },
      { value: '14', label: 'Кабинет 14' },
    ],
    value: '12',
    disabled: true,
  },
};
