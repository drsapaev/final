/**
 * AppState Stories — canonical loading/empty/error primitives
 * (plan §PR-UI-18 item 2).
 *
 * PR-UI-07 / PR-UI-07a series: AppLoading / AppEmpty / AppError are the
 * canonical async-state trio that replaced MacOSEmptyState (physically
 * decommissioned in #2836). AppEmpty renders the internalized
 * `variant="minimal"` framing accepted as canonical.
 */
import { AppLoading, AppEmpty, AppError } from './AppState';
import Button from './Button';

export default {
  title: 'UI/MacOS/AppState',
  component: AppEmpty,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical async states (PR-UI-07/07a): AppLoading, ' +
          'AppEmpty, AppError. MacOSEmptyState decommissioned #2836.',
      },
    },
  },
};

export const Loading = {
  render: () => <AppLoading title="Загрузка очереди…" description="Обновляем данные за сегодня" />,
};

export const Empty = {
  render: () => (
    <AppEmpty
      title="Записей нет"
      description="На сегодня приёмов не запланировано"
    />
  ),
};

export const EmptyWithAction = {
  render: () => (
    <AppEmpty
      title="Пациенты не найдены"
      description="Измените параметры поиска или добавьте нового пациента"
      action={<Button variant="primary" size="sm">Добавить пациента</Button>}
    />
  ),
};

export const ErrorState = {
  render: () => (
    <AppError
      title="Не удалось загрузить данные"
      description="Проверьте соединение и повторите попытку"
    />
  ),
};
