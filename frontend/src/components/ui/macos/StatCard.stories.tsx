/**
 * StatCard Stories — canonical macOS-style StatCard primitive.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers trend directions (positive/negative/neutral), sizes,
 * loading state and clickable detail mode.
 */
import React from 'react';
import { Users, CalendarDays, Stethoscope } from 'lucide-react';
import MacOSStatCard from './StatCard';

export default {
  title: 'Primitives/StatCard',
  component: MacOSStatCard,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style StatCard — metric tile with icon, value, ' +
          'subtitle and trend indicator (positive/negative/neutral).',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'stretch', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

export const TrendPositive = {
  name: 'Рост показателя',
  args: {
    title: 'Пациентов сегодня',
    value: '42',
    subtitle: 'на 30.08.2026',
    icon: Users,
    trend: '+12%',
    trendType: 'positive',
    trendLabel: 'к прошлой неделе',
  },
};

export const TrendNegative = {
  name: 'Падение показателя',
  args: {
    title: 'Отмены записей',
    value: '7',
    subtitle: 'за неделю',
    icon: CalendarDays,
    trend: '−18%',
    trendType: 'negative',
    trendLabel: 'к прошлой неделе',
  },
};

export const TrendNeutral = {
  name: 'Без изменений',
  args: {
    title: 'Врачи на смене',
    value: '12',
    subtitle: 'текущая смена',
    icon: Stethoscope,
    trend: '0%',
    trendType: 'neutral',
    trendLabel: 'стабильно',
  },
};

export const Sizes = {
  name: 'Размеры',
  render: () => (
    <>
      <MacOSStatCard size="sm" title="Малая" value="12" icon={Users} />
      <MacOSStatCard size="md" title="Обычная" value="128" icon={Users} />
      <MacOSStatCard size="lg" title="Крупная" value="1 024" icon={Users} />
    </>
  ),
};

export const Loading = {
  name: 'Загрузка',
  args: {
    title: 'Загрузка метрики',
    icon: Users,
    loading: true,
  },
};
