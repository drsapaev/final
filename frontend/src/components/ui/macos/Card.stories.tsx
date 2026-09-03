/**
 * Card Stories — canonical macOS-style Card primitive and its composable
 * parts (CardHeader / CardTitle / CardDescription / CardContent / CardFooter).
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers variants, paddings, interactive state and the parts API.
 */
import React from 'react';
import Card, { CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './Card';
import Button from './Button';

export default {
  title: 'Primitives/Card',
  component: Card,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style Card surface — variants ' +
          '(default/elevated/outlined/filled), paddings, shadows and the ' +
          'composable parts API used across panels.',
      },
    },
  },
  decorators: [
    (Story: () => React.ReactElement) => (
      <div style={{ padding: '20px', display: 'flex', flexWrap: 'wrap', gap: '16px', background: 'var(--mac-bg-secondary)', minHeight: '100vh' }}>
        <Story />
      </div>
    ),
  ],
};

const CardBody = ({ text }: { text: string }) => (
  <p style={{ margin: 0, color: 'var(--mac-text-primary)' }}>{text}</p>
);

export const Variants = {
  name: 'Варианты',
  render: () => (
    <>
      <Card variant="default"><CardBody text="Default" /></Card>
      <Card variant="elevated"><CardBody text="Elevated" /></Card>
      <Card variant="outlined"><CardBody text="Outlined" /></Card>
      <Card variant="filled"><CardBody text="Filled" /></Card>
    </>
  ),
};

export const Paddings = {
  name: 'Отступы',
  render: () => (
    <>
      <Card padding="small" variant="outlined"><CardBody text="Small" /></Card>
      <Card padding="default" variant="outlined"><CardBody text="Default" /></Card>
      <Card padding="large" variant="outlined"><CardBody text="Large" /></Card>
      <Card padding="none" variant="outlined"><CardBody text="None" /></Card>
    </>
  ),
};

export const ComposedParts = {
  name: 'Составной макет (parts API)',
  render: () => (
    <Card style={{ width: '360px' }}>
      <CardHeader>
        <CardTitle>Приём пациента</CardTitle>
        <CardDescription>Карточка визита — демо-данные</CardDescription>
      </CardHeader>
      <CardContent>
        <CardBody text="Раздел содержимого карточки: основная информация о визите отображается здесь." />
      </CardContent>
      <CardFooter>
        <Button variant="secondary">Отмена</Button>
        <Button variant="primary">Сохранить</Button>
      </CardFooter>
    </Card>
  ),
};

export const Interactive = {
  name: 'Интерактивная',
  args: {
    variant: 'elevated',
    interactive: true,
    onClick: () => {},
    children: 'Кликабельная карточка — hover-подсветка и cursor: pointer',
    style: { width: '320px', padding: '16px', color: 'var(--mac-text-primary)' },
  },
};
