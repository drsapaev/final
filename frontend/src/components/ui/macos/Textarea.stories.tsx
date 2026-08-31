/**
 * Textarea Stories — canonical macOS-style Textarea primitive.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers label + hint, error state, auto-resize with row bounds
 * and disabled state.
 */
import React from 'react';
import Textarea from './Textarea';

export default {
  title: 'Primitives/Textarea',
  component: Textarea,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style Textarea — label, hint, error state, ' +
          'character counter (maxLength) and auto-resize with min/max rows.',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', display: 'grid', gap: '24px', maxWidth: '420px', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

export const Default = {
  name: 'Базовое поле',
  args: {
    label: 'Жалобы пациента',
    placeholder: 'Опишите жалобы своими словами…',
    rows: 4,
  },
};

export const WithCounter = {
  name: 'Счётчик символов',
  args: {
    label: 'Заключение',
    placeholder: 'Краткое заключение по визиту…',
    maxLength: 200,
    rows: 4,
    hint: 'До 200 символов',
  },
};

export const ErrorState = {
  name: 'Ошибка валидации',
  args: {
    label: 'Причина отмены',
    placeholder: 'Укажите причину отмены визита…',
    error: true,
    rows: 3,
    defaultValue: 'Пациент',
  },
};

export const AutoResize = {
  name: 'Авто-рост',
  args: {
    label: 'Протокол приёма',
    placeholder: 'Текст будет расширять поле по мере ввода…',
    autoResize: true,
    minRows: 2,
    maxRows: 8,
  },
};

export const Disabled = {
  name: 'Отключено',
  args: {
    label: 'Служебное примечание',
    defaultValue: 'Поле доступно только администратору',
    rows: 3,
    disabled: true,
  },
};
