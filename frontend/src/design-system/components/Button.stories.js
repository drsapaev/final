import React from 'react';
import { Button } from './Button';
import { SIZES, VARIANTS } from './types';

// More on how to set up stories at: https://storybook.js.org/docs/writing-stories#default-export
export default {
  title: 'Design System/Button',
  component: Button,
  parameters: {
    // Optional parameter to center the component in the Canvas. More info: https://storybook.js.org/docs/configure/story-layout
    layout: 'centered',
    docs: {
      description: {
        component: 'Кнопка для действий и взаимодействий в интерфейсе. Поддерживает различные варианты, размеры и состояния.'
      }
    }
  },
  // This component will have an automatically generated Autodocs entry: https://storybook.js.org/docs/writing-docs/autodocs
  tags: ['autodocs'],
  // More on argTypes: https://storybook.js.org/docs/api/argtypes
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: Object.values(VARIANTS),
      description: 'Вариант кнопки'
    },
    size: {
      control: { type: 'select' },
      options: Object.values(SIZES),
      description: 'Размер кнопки'
    },
    disabled: {
      control: { type: 'boolean' },
      description: 'Отключена ли кнопка'
    },
    loading: {
      control: { type: 'boolean' },
      description: 'Состояние загрузки'
    },
    fullWidth: {
      control: { type: 'boolean' },
      description: 'Занимает ли кнопка всю ширину'
    },
    children: {
      control: { type: 'text' },
      description: 'Содержимое кнопки'
    }
  },
  // Use `fn` to spy on the onClick arg, which will appear in the actions panel once invoked: https://storybook.js.org/docs/essentials/actions#action-args
  args: { onClick: () => {} }
};

// More on writing stories with args: https://storybook.js.org/docs/writing-stories/args
export const Primary = {
  args: {
    variant: VARIANTS.PRIMARY,
    children: 'Primary Button'
  }
};

export const Secondary = {
  args: {
    variant: VARIANTS.SECONDARY,
    children: 'Secondary Button'
  }
};

export const Success = {
  args: {
    variant: VARIANTS.SUCCESS,
    children: 'Success Button'
  }
};

export const Danger = {
  args: {
    variant: VARIANTS.DANGER,
    children: 'Danger Button'
  }
};

export const Warning = {
  args: {
    variant: VARIANTS.WARNING,
    children: 'Warning Button'
  }
};

export const Info = {
  args: {
    variant: VARIANTS.INFO,
    children: 'Info Button'
  }
};

export const Ghost = {
  args: {
    variant: VARIANTS.GHOST,
    children: 'Ghost Button'
  }
};

export const Small = {
  args: {
    size: SIZES.SM,
    children: 'Small Button'
  }
};

export const Medium = {
  args: {
    size: SIZES.MD,
    children: 'Medium Button'
  }
};

export const Large = {
  args: {
    size: SIZES.LG,
    children: 'Large Button'
  }
};

export const Disabled = {
  args: {
    disabled: true,
    children: 'Disabled Button'
  }
};

export const Loading = {
  args: {
    loading: true,
    children: 'Loading Button'
  }
};

export const FullWidth = {
  args: {
    fullWidth: true,
    children: 'Full Width Button'
  },
  parameters: {
    layout: 'padded'
  }
};

export const WithIcon = {
  args: {
    children: (
      <>
        <span>🚀</span>
        Button with Icon
      </>
    )
  }
};

export const AllVariants = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <Button variant={VARIANTS.PRIMARY}>Primary</Button>
        <Button variant={VARIANTS.SECONDARY}>Secondary</Button>
        <Button variant={VARIANTS.SUCCESS}>Success</Button>
        <Button variant={VARIANTS.DANGER}>Danger</Button>
        <Button variant={VARIANTS.WARNING}>Warning</Button>
        <Button variant={VARIANTS.INFO}>Info</Button>
        <Button variant={VARIANTS.GHOST}>Ghost</Button>
      </div>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <Button size={SIZES.SM}>Small</Button>
        <Button size={SIZES.MD}>Medium</Button>
        <Button size={SIZES.LG}>Large</Button>
      </div>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <Button disabled>Disabled</Button>
        <Button loading>Loading</Button>
      </div>
    </div>
  ),
  parameters: {
    layout: 'padded'
  }
};
