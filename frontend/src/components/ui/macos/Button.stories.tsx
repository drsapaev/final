/**
 * Button Stories — canonical macOS-style Button primitive.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers variants × colors, sizes, loading, disabled, icons.
 *
 * Icon-controls audit policy: every interactive control keeps a visible text
 * label (no icon-only buttons) — matches scripts/audit-icon-only-controls.mjs
 * strict gate that scans *.stories.tsx.
 */
import React from 'react';
import { Plus, Download, ChevronRight } from 'lucide-react';
import Button from './Button';

export default {
  title: 'Primitives/Button',
  component: Button,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style Button — Apple HIG button with variants ' +
          '(primary/secondary/ghost/outline/danger/link), semantic colors, ' +
          'sizes, loading and icon slots (startIcon/endIcon).',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

export const Variants = {
  name: 'Варианты',
  args: { children: 'Основная кнопка', variant: 'primary', onClick: () => {} },
};

export const SemanticColors = {
  name: 'Семантические цвета',
  render: () => (
    <>
      <Button color="default">По умолчанию</Button>
      <Button color="success" variant="primary">Сохранить</Button>
      <Button color="warning" variant="primary">Предупреждение</Button>
      <Button color="danger" variant="primary">Удалить</Button>
      <Button color="info" variant="primary">Инфо</Button>
    </>
  ),
};

export const Sizes = {
  name: 'Размеры',
  render: () => (
    <>
      <Button size="small" variant="primary">Малая</Button>
      <Button size="default" variant="primary">Обычная</Button>
      <Button size="large" variant="primary">Крупная</Button>
    </>
  ),
};

export const WithIcons = {
  name: 'С иконками',
  render: () => (
    <>
      <Button variant="primary" startIcon={<Plus size={16} />}>Добавить запись</Button>
      <Button variant="secondary" endIcon={<ChevronRight size={16} />}>Далее</Button>
      <Button variant="outline" startIcon={<Download size={16} />}>Экспорт</Button>
    </>
  ),
};

export const Loading = {
  name: 'Загрузка',
  args: { children: 'Сохранение…', variant: 'primary', loading: true },
};

export const Disabled = {
  name: 'Отключена',
  args: { children: 'Недоступно', variant: 'primary', disabled: true },
};

export const FullWidth = {
  name: 'На всю ширину',
  args: { children: 'Подтвердить запись', variant: 'primary', fullWidth: true },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', width: '320px', background: 'var(--mac-bg-secondary)' }}>
        <Story />
      </div>
    ),
  ],
};
