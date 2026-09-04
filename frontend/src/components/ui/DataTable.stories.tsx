/**
 * DataTable Stories — canonical DataTable primitive (PR-UI-09a foundation).
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers column API, visual variants (striped/hoverable/density),
 * async states (loading/empty) and pagination.
 *
 * PII policy (AGENTS.md §PII fields L377/L388): patient identifiers in
 * committed fixtures use INITIALS ONLY — no full names anywhere below.
 */
import React from 'react';
import DataTable, { type DataTableColumn } from './DataTable';

export default {
  title: 'Primitives/DataTable',
  component: DataTable,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'DataTable — canonical table primitive (PR-UI-09a): ' +
          'column API with render/sortable/align, async states, pagination, ' +
          'virtualization and mobile scroll behavior (ruling P7).',
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

interface VisitRow {
  id: number;
  patient: string;
  specialty: string;
  time: string;
  status: string;
}

const columns: DataTableColumn<VisitRow>[] = [
  { key: 'patient', title: 'Пациент', sortable: true },
  { key: 'specialty', title: 'Отделение' },
  { key: 'time', title: 'Время', align: 'right' },
  {
    key: 'status',
    title: 'Статус',
    render: (value: unknown) => {
      const text = String(value);
      const color = text === 'завершён'
        ? 'var(--mac-text-secondary)'
        : 'var(--mac-accent)';
      return <span style={{ color }}>{text}</span>;
    },
  },
];

const visits: VisitRow[] = [
  { id: 1, patient: 'А. А.', specialty: 'Кардиология', time: '09:00', status: 'завершён' },
  { id: 2, patient: 'Б. Б.', specialty: 'Дерматология', time: '09:30', status: 'ожидает' },
  { id: 3, patient: 'В. В.', specialty: 'Стоматология', time: '10:15', status: 'ожидает' },
  { id: 4, patient: 'Г. Г.', specialty: 'Кардиология', time: '11:00', status: 'отменён' },
  { id: 5, patient: 'Д. Д.', specialty: 'Дерматология', time: '11:45', status: 'ожидает' },
];

export const Default = {
  name: 'Базовая таблица',
  args: {
    columns,
    data: visits,
    ariaLabel: 'Таблица визитов — демо',
  },
};

export const StripedAndHoverable = {
  name: 'Полосатая с подсветкой строк',
  args: {
    columns,
    data: visits,
    striped: true,
    hoverable: true,
    ariaLabel: 'Таблица визитов — полосатая',
  },
};

export const Loading = {
  name: 'Загрузка',
  args: {
    columns,
    data: [],
    loading: true,
    ariaLabel: 'Таблица визитов — загрузка',
  },
};

export const EmptyState = {
  name: 'Нет данных',
  args: {
    columns,
    data: [],
    emptyState: 'Визитов на выбранную дату нет',
    ariaLabel: 'Таблица визитов — пусто',
  },
};

export const Pagination = {
  name: 'С пагинацией',
  args: {
    columns,
    data: visits,
    pagination: true,
    pageSize: 3,
    totalItems: 5,
    currentPage: 1,
    ariaLabel: 'Таблица визитов — пагинация',
  },
};
