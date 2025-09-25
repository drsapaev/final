import React from 'react';
import Badge from './Badge';
import { SIZES, VARIANTS } from './types';

export default {
  title: 'Design System/Badge',
  component: Badge,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'Бейдж для отображения статусов, меток и другой краткой информации.'
      }
    }
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: ['default', ...Object.values(VARIANTS)],
      description: 'Вариант бейджа'
    },
    size: {
      control: { type: 'select' },
      options: Object.values(SIZES),
      description: 'Размер бейджа'
    },
    children: {
      control: { type: 'text' },
      description: 'Содержимое бейджа'
    }
  }
};

export const Default = {
  args: {
    children: 'Default'
  }
};

export const Primary = {
  args: {
    variant: VARIANTS.PRIMARY,
    children: 'Primary'
  }
};

export const Success = {
  args: {
    variant: VARIANTS.SUCCESS,
    children: 'Success'
  }
};

export const Danger = {
  args: {
    variant: VARIANTS.DANGER,
    children: 'Danger'
  }
};

export const Warning = {
  args: {
    variant: VARIANTS.WARNING,
    children: 'Warning'
  }
};

export const Info = {
  args: {
    variant: VARIANTS.INFO,
    children: 'Info'
  }
};

export const Small = {
  args: {
    size: SIZES.SM,
    children: 'Small'
  }
};

export const Medium = {
  args: {
    size: SIZES.MD,
    children: 'Medium'
  }
};

export const Large = {
  args: {
    size: SIZES.LG,
    children: 'Large'
  }
};

export const StatusBadges = {
  render: () => (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      <Badge variant={VARIANTS.SUCCESS}>Активен</Badge>
      <Badge variant={VARIANTS.DANGER}>Неактивен</Badge>
      <Badge variant={VARIANTS.WARNING}>Ожидает</Badge>
      <Badge variant={VARIANTS.INFO}>В процессе</Badge>
      <Badge variant={VARIANTS.PRIMARY}>Новый</Badge>
    </div>
  )
};

export const SizeComparison = {
  render: () => (
    <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
      <Badge size={SIZES.SM}>Small</Badge>
      <Badge size={SIZES.MD}>Medium</Badge>
      <Badge size={SIZES.LG}>Large</Badge>
    </div>
  )
};

export const AllVariants = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <Badge variant="default">Default</Badge>
        <Badge variant={VARIANTS.PRIMARY}>Primary</Badge>
        <Badge variant={VARIANTS.SECONDARY}>Secondary</Badge>
        <Badge variant={VARIANTS.SUCCESS}>Success</Badge>
        <Badge variant={VARIANTS.DANGER}>Danger</Badge>
        <Badge variant={VARIANTS.WARNING}>Warning</Badge>
        <Badge variant={VARIANTS.INFO}>Info</Badge>
      </div>
    </div>
  )
};
