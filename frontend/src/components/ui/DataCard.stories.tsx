/**
 * DataCard Stories — canonical DataCard primitive (plan §PR-UI-18 item 2).
 *
 * PR-UI-11-1 introduced DataCard as the canonical titled data panel
 * (data-first surfaces: lists / timelines / summaries). The body states
 * mirror the canonical async trio: loading / error+retry / empty, each
 * rendered through the AppEmpty/AppSkeleton machinery.
 */
import DataCard from './DataCard';
import Button from './macos/Button';
import { CalendarDays } from 'lucide-react';

export default {
  title: 'UI/DataCard',
  component: DataCard,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical DataCard (PR-UI-11-1): titled data panel with ' +
          'canonical loading/error/empty body states.',
      },
    },
  },
};

export const Basic = {
  args: {
    title: 'Приёмы на сегодня',
    description: 'Кардиология · кабинет 12',
    children: 'Список приёмов отображается здесь — данные-first поверхность без лишнего декора.',
  },
};

export const WithBadgeAndAction = {
  render: () => (
    <DataCard
      title="Приёмы на сегодня"
      icon={<CalendarDays size={16} />}
      badge={7}
      action={<Button variant="secondary" size="sm">Все записи</Button>}
    >
      Заголовок с иконкой, счётчиком-бейджем и действием справа.
    </DataCard>
  ),
};

export const Loading = {
  args: {
    title: 'Приёмы на сегодня',
    loading: true,
    children: 'Не отображается при loading',
  },
};

export const ErrorState = {
  args: {
    title: 'Приёмы на сегодня',
    error: 'Сервер недоступен',
    onRetry: () => {},
    retryLabel: 'Повторить',
  },
};

export const Empty = {
  args: {
    title: 'Приёмы на сегодня',
    empty: 'Записей нет',
  },
};

export const FilledCompact = {
  args: {
    title: 'Сводка смены',
    variant: 'filled',
    density: 'compact',
    children: 'Вариант filled с компактной плотностью (density=compact).',
  },
};
