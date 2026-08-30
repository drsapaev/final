/**
 * Button Stories — canonical Button primitive (plan §PR-UI-18 item 2).
 *
 * PR-UI-05 narrowed the variant set to 6 canonical variants
 * (primary/secondary/ghost/outline/danger/link); semantic coloring on
 * secondary goes through the `color` prop. These stories cover the full
 * canonical matrix so visual review of the primitive happens in Storybook.
 */
import Button from './Button';
import { Plus } from 'lucide-react';

export default {
  title: 'UI/MacOS/Button',
  component: Button,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical Button (PR-UI-05): 6 variants, 3 sizes, ' +
          'loading/disabled/fullWidth/icon states. Semantic coloring via `color` on secondary.',
      },
    },
  },
};

export const Primary = {
  args: { children: 'Основная кнопка', variant: 'primary' },
};

export const Secondary = {
  args: { children: 'Вторичная кнопка', variant: 'secondary' },
};

export const Ghost = {
  args: { children: 'Прозрачная кнопка', variant: 'ghost' },
};

export const Outline = {
  args: { children: 'Контурная кнопка', variant: 'outline' },
};

export const Danger = {
  args: { children: 'Удалить', variant: 'danger' },
};

export const Link = {
  args: { children: 'Показать все', variant: 'link' },
};

export const Sizes = {
  render: () => (
    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
      <Button size="sm" variant="primary">Малая</Button>
      <Button size="md" variant="primary">Средняя</Button>
      <Button size="lg" variant="primary">Крупная</Button>
    </div>
  ),
};

export const WithIcon = {
  args: { children: 'Добавить услугу', variant: 'primary', icon: <Plus size={16} /> },
};

export const Loading = {
  args: { children: 'Сохранение…', variant: 'primary', loading: true },
};

export const Disabled = {
  args: { children: 'Недоступно', variant: 'primary', disabled: true },
};

export const FullWidth = {
  args: { children: 'Во всю ширину', variant: 'primary', fullWidth: true },
};
