/**
 * DataTable Stories — canonical DataTable primitive (plan §PR-UI-18 item 2).
 *
 * PR-UI-09 series (09a-09e) made DataTable THE canonical table: row
 * virtualization (09e-1), sticky header under a bounded viewport (12-4),
 * selectable rows, sorting and the canonical empty state.
 *
 * PII policy (AGENTS.md §PII): fixtures use synthetic initials only.
 */
import DataTable from './DataTable';
import type { DataTableColumn } from './DataTable';

interface ServiceRow {
  id: number;
  code: string;
  name: string;
  price: number;
}

const columns: DataTableColumn<ServiceRow>[] = [
  { key: 'code', title: 'Код', sortable: true, width: '90px' },
  { key: 'name', title: 'Услуга', sortable: true },
  { key: 'price', title: 'Цена', sortable: true, align: 'right' },
];

// Synthetic service catalog — no patient data at all.
const services: ServiceRow[] = [
  { id: 1, code: 'K01', name: 'Консультация кардиолога', price: 150000 },
  { id: 2, code: 'D01', name: 'Первичный осмотр дерматолога', price: 120000 },
  { id: 3, code: 'S02', name: 'Гигиена полости рта', price: 90000 },
  { id: 4, code: 'K05', name: 'ЭКГ с расшифровкой', price: 180000 },
  { id: 5, code: 'L01', name: 'Общий анализ крови', price: 45000 },
];

export default {
  title: 'UI/DataTable',
  component: DataTable,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical DataTable (PR-UI-09a..09e): virtualized rows, ' +
          'sticky header, selection, sorting, canonical empty state.',
      },
    },
  },
};

export const Basic = {
  args: {
    columns,
    data: services,
    getRowId: (row: ServiceRow) => row.id,
  },
};

export const Sortable = {
  args: {
    columns,
    data: services,
    getRowId: (row: ServiceRow) => row.id,
    sortable: true,
  },
};

export const Selectable = {
  args: {
    columns,
    data: services,
    getRowId: (row: ServiceRow) => row.id,
    selectable: true,
  },
};

export const Empty = {
  args: {
    columns,
    data: [],
    getRowId: (row: ServiceRow) => row.id,
  },
};
