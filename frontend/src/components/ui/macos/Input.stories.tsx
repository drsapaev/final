/**
 * Input Stories — canonical macOS-style Input primitive.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers label + hint, error state, clearable, disabled and
 * icon slot.
 */
import React from 'react';
import { Search, Calendar } from 'lucide-react';
import Input from './Input';

export default {
  title: 'Primitives/Input',
  component: Input,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style text Input — label, hint, error state, ' +
          'clearable mode, icon slot and sizes.',
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

export const Default = {
  name: 'Базовое поле',
  args: {
    placeholder: 'Иван',
    label: 'Имя пациента',
  },
};

export const WithHint = {
  name: 'С подсказкой',
  args: {
    label: 'Номер карты',
    placeholder: 'КА-000123',
    hint: 'Номер указан на обложке медицинской карты',
  },
};

export const ErrorState = {
  name: 'Ошибка валидации',
  args: {
    label: 'Телефон',
    placeholder: '+998 90 000-00-00',
    error: 'Введите телефон в международном формате',
    defaultValue: '90123',
  },
};

export const Clearable = {
  name: 'С очисткой',
  args: {
    label: 'Поиск',
    placeholder: 'Начните вводить фамилию…',
    clearable: true,
    defaultValue: 'Ива',
  },
};

export const WithIcon = {
  name: 'С иконкой',
  args: {
    label: 'Поиск пациента',
    placeholder: 'Идентификатор или инициалы…',
    icon: Search,
  },
};

export const Disabled = {
  name: 'Отключено',
  args: {
    label: 'Дата регистрации',
    defaultValue: '2026-08-30',
    disabled: true,
    icon: Calendar,
  },
};
