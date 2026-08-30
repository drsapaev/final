/**
 * AppState Stories — canonical loading / empty / error primitives.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers AppLoading (sizes), AppEmpty (with action) and AppError
 * (severity levels) — the three async-state building blocks used by panels.
 */
import React from 'react';
import { CalendarX } from 'lucide-react';
import { AppLoading, AppEmpty, AppError } from './AppState';
import Button from './Button';

export default {
  title: 'Primitives/AppState',
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Async-state primitives: AppLoading (spinner + titles), ' +
          'AppEmpty (zero-data guidance) and AppError (severity-toned ' +
          'failure states with optional retry action).',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

export const Loading = {
  name: 'AppLoading — загрузка',
  render: () => (
    <AppLoading
      title="Загружаем расписание…"
      description="Обычно это занимает пару секунд"
      size="md"
      ariaLabel="Загрузка расписания"
    />
  ),
};

export const Empty = {
  name: 'AppEmpty — нет данных',
  render: () => (
    <AppEmpty
      title="Записей на сегодня нет"
      description="Создайте первую запись, и она появится здесь"
      icon={CalendarX}
      action={<Button variant="primary">Создать запись</Button>}
    />
  ),
};

export const ErrorState = {
  name: 'AppError — ошибка загрузки',
  render: () => (
    <AppError
      title="Не удалось загрузить данные"
      description="Проверьте соединение и попробуйте снова"
      severity="error"
      action={<Button variant="primary">Повторить</Button>}
    />
  ),
};

export const ErrorSeverities = {
  name: 'AppError — уровни серьёзности',
  render: () => (
    <div style={{ display: 'grid', gap: '16px' }}>
      <AppError title="Информационное сообщение" severity="info" />
      <AppError title="Предупреждение" severity="warning" />
      <AppError title="Критическая ошибка" severity="error" />
    </div>
  ),
};
