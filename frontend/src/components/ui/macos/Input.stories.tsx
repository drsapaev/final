/**
 * Input Stories — canonical Input primitive (plan §PR-UI-18 item 2).
 *
 * Canonical form text input: label / hint / error / disabled / clearable /
 * icon states. PR-UI-05/06 established the macos form family as canonical;
 * the duplicate forms/Modern* files were dead code (removed in PR-UI-17).
 */
import Input from './Input';
import { Search } from 'lucide-react';

export default {
  title: 'UI/MacOS/Input',
  component: Input,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical Input: label/hint/error/disabled/clearable/icon. ' +
          'Формы Modern* — мёртвые дубликаты (удалены в PR-UI-17).',
      },
    },
  },
};

export const Basic = {
  args: {
    label: 'ФИО пациента',
    placeholder: 'Иванов И. И.',
  },
};

export const WithHint = {
  args: {
    label: 'Номер телефона',
    placeholder: '+998 90 000 00 00',
    hint: 'Формат: узбекский мобильный номер',
  },
};

export const ErrorState = {
  args: {
    label: 'Стоимость услуги',
    placeholder: '150 000',
    error: 'Введите положительное число',
  },
};

export const Disabled = {
  args: {
    label: 'ID записи',
    value: 'A-0042',
    disabled: true,
  },
};

export const WithIcon = {
  args: {
    placeholder: 'Поиск пациента…',
    icon: Search,
  },
};

export const Clearable = {
  args: {
    label: 'Поиск',
    value: 'Тестов',
    clearable: true,
  },
};
