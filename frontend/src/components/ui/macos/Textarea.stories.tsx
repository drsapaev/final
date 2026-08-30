/**
 * Textarea Stories — canonical Textarea primitive (plan §PR-UI-18 item 2).
 *
 * Canonical multiline input: label / error / disabled / autoResize with
 * min/max rows.
 */
import Textarea from './Textarea';

export default {
  title: 'UI/MacOS/Textarea',
  component: Textarea,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical Textarea: label/error/disabled/autoResize (minRows/maxRows).',
      },
    },
  },
};

export const Basic = {
  args: {
    label: 'Жалобы пациента',
    placeholder: 'Опишите жалобы и симптомы…',
    rows: 4,
  },
};

export const ErrorState = {
  args: {
    label: 'Заключение',
    placeholder: 'Заключение врача…',
    error: true,
    rows: 4,
  },
};

export const Disabled = {
  args: {
    label: 'Протокол (только чтение)',
    value: 'Осмотр завершён. Назначений нет.',
    disabled: true,
    rows: 3,
  },
};

export const AutoResize = {
  args: {
    label: 'Динамическая высота',
    placeholder: 'Текст растёт до maxRows…',
    autoResize: true,
    minRows: 2,
    maxRows: 8,
  },
};
