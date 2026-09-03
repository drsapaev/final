/**
 * DataCard Stories — canonical data-first Card wrapper (PR-UI-11-1).
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers the four async body states (content / loading / error /
 * empty), variants and density. Fixtures use initials only per AGENTS.md
 * §PII (L377/L388) — no real names in committed test fixtures.
 */
import React from 'react';
import { Activity } from 'lucide-react';
import DataCard from './DataCard';
import Button from './macos/Button';

export default {
  title: 'Primitives/DataCard',
  component: DataCard,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'DataCard — data-first wrapper (PR-UI-11-1): header ' +
          '(title/description/icon/action/badge) + body with async states ' +
          '(loading skeleton, error + retry, empty) over the Card primitive.',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-start', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

export const Content = {
  name: 'Содержимое',
  args: {
    title: 'Последние визиты',
    description: 'Обновлено сегодня',
    icon: <Activity size={18} />,
    badge: '24',
    action: <Button variant="secondary">Обновить</Button>,
    children: (
      <ul style={{ margin: 0, paddingLeft: '18px', color: 'var(--mac-text-primary)' }}>
        <li>А. А. — кардиология, 09:00</li>
        <li>Б. Б. — дерматология, 09:30</li>
        <li>В. В. — стоматология, 10:15</li>
      </ul>
    ),
  },
};

export const Loading = {
  name: 'Загрузка (скелетон)',
  args: {
    title: 'Последние визиты',
    loading: true,
    children: null,
  },
};

export const ErrorState = {
  name: 'Ошибка + повтор',
  args: {
    title: 'Последние визиты',
    error: 'Сервер недоступен',
    onRetry: () => {},
    children: null,
  },
};

export const Empty = {
  name: 'Пусто',
  args: {
    title: 'Последние визиты',
    empty: 'Записей пока нет',
    children: null,
  },
};

export const VariantsAndDensity = {
  name: 'Варианты и плотность',
  render: () => (
    <>
      <DataCard variant="default" density="compact" title="Default / compact" style={{ width: '240px' }}>
        <span>Компактное содержимое</span>
      </DataCard>
      <DataCard variant="outlined" density="default" title="Outlined / default" style={{ width: '240px' }}>
        <span>Обычное содержимое</span>
      </DataCard>
      <DataCard variant="filled" density="comfortable" title="Filled / comfortable" style={{ width: '240px' }}>
        <span>Просторное содержимое</span>
      </DataCard>
    </>
  ),
};
