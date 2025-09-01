import React from 'react';
import { Card } from './Card';
import { Button } from './Button';
import { VARIANTS } from './types';

export default {
  title: 'Design System/Card',
  component: Card,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'Карточка для группировки связанного контента. Поддерживает заголовок, контент и футер.'
      }
    }
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: ['default', 'elevated', 'outlined'],
      description: 'Вариант карточки'
    },
    hover: {
      control: { type: 'boolean' },
      description: 'Включить эффект при наведении'
    },
    onClick: {
      action: 'clicked',
      description: 'Обработчик клика'
    }
  }
};

export const Default = {
  args: {
    children: (
      <div>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          Заголовок карточки
        </h3>
        <p style={{ margin: '0 0 16px 0', color: '#64748b' }}>
          Это содержимое карточки. Здесь может быть любой контент.
        </p>
        <Button variant={VARIANTS.PRIMARY} size="sm">
          Действие
        </Button>
      </div>
    )
  }
};

export const WithHeader = {
  args: {
    children: (
      <>
        <Card.Header>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
            Заголовок
          </h3>
          <p style={{ margin: '8px 0 0 0', color: '#64748b', fontSize: '14px' }}>
            Подзаголовок
          </p>
        </Card.Header>
        <Card.Content>
          <p style={{ margin: 0, color: '#64748b' }}>
            Основное содержимое карточки.
          </p>
        </Card.Content>
        <Card.Footer>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant={VARIANTS.SECONDARY} size="sm">
              Отмена
            </Button>
            <Button variant={VARIANTS.PRIMARY} size="sm">
              Сохранить
            </Button>
          </div>
        </Card.Footer>
      </>
    )
  }
};

export const Elevated = {
  args: {
    variant: 'elevated',
    children: (
      <div>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          Приподнятая карточка
        </h3>
        <p style={{ margin: 0, color: '#64748b' }}>
          Эта карточка имеет более выраженную тень.
        </p>
      </div>
    )
  }
};

export const Outlined = {
  args: {
    variant: 'outlined',
    children: (
      <div>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          Карточка с рамкой
        </h3>
        <p style={{ margin: 0, color: '#64748b' }}>
          Эта карточка имеет только рамку без фона.
        </p>
      </div>
    )
  }
};

export const NoHover = {
  args: {
    hover: false,
    children: (
      <div>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          Без эффекта наведения
        </h3>
        <p style={{ margin: 0, color: '#64748b' }}>
          Эта карточка не реагирует на наведение мыши.
        </p>
      </div>
    )
  }
};

export const Clickable = {
  args: {
    onClick: () => alert('Карточка нажата!'),
    children: (
      <div>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
          Кликабельная карточка
        </h3>
        <p style={{ margin: 0, color: '#64748b' }}>
          Нажмите на эту карточку, чтобы увидеть действие.
        </p>
      </div>
    )
  }
};

export const AllVariants = {
  render: () => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
      <Card variant="default">
        <div>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
            Default
          </h3>
          <p style={{ margin: 0, color: '#64748b' }}>
            Стандартная карточка с фоном и тенью.
          </p>
        </div>
      </Card>
      
      <Card variant="elevated">
        <div>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
            Elevated
          </h3>
          <p style={{ margin: 0, color: '#64748b' }}>
            Карточка с более выраженной тенью.
          </p>
        </div>
      </Card>
      
      <Card variant="outlined">
        <div>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '600' }}>
            Outlined
          </h3>
          <p style={{ margin: 0, color: '#64748b' }}>
            Карточка только с рамкой.
          </p>
        </div>
      </Card>
    </div>
  ),
  parameters: {
    layout: 'padded'
  }
};
