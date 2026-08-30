/**
 * StatCard Stories — canonical StatCard primitive (plan §PR-UI-18 item 2).
 *
 * PR-UI-06: StatCard is the canonical name (MacOSStatCard kept as a
 * backward-compat alias). StatCard renders a KPI: label + value + trend
 * (positive / negative / neutral) + optional icon.
 */
import StatCard from './StatCard';
import { Users, TrendingUp, TrendingDown } from 'lucide-react';

export default {
  title: 'UI/MacOS/StatCard',
  component: StatCard,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical StatCard (PR-UI-06): KPI-плитка label/value/trend ' +
          '+ icon; MacOSStatCard — backward-compat алиас.',
      },
    },
  },
};

export const Neutral = {
  args: {
    label: 'Пациентов сегодня',
    value: '42',
  },
};

export const PositiveTrend = {
  args: {
    label: 'Записей создано',
    value: '128',
    trend: '+12% к прошлой неделе',
    trendType: 'positive',
    trendLabel: <TrendingUp size={14} />,
  },
};

export const NegativeTrend = {
  args: {
    label: 'Отмены',
    value: '7',
    trend: '-3 за неделю',
    trendType: 'negative',
    trendLabel: <TrendingDown size={14} />,
  },
};

export const WithIcon = {
  args: {
    label: 'Активные пациенты',
    value: '1 204',
    icon: Users,
  },
};

export const Small = {
  args: {
    label: 'Размер sm',
    value: '99',
    size: 'sm',
  },
};
