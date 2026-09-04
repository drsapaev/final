/**
 * Modal Stories — canonical macOS-style Modal primitive.
 *
 * PR-UI-18 item 2 (plan §PR-UI-18): Storybook stories for all canonical
 * primitives. Covers sizes, variants and composed header/content/actions
 * layout. Uses a stateful wrapper because Modal visibility is controlled.
 */
import React, { useState } from 'react';
import Modal from './Modal';
import Button from './Button';

export default {
  title: 'Primitives/Modal',
  component: Modal,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'macOS-style Modal dialog — controlled via isOpen, with ' +
          'backdrop, escape/backdrop-close policies, sizes and actions slot.',
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

/** Stateful wrapper: Modal is controlled — story button toggles isOpen. */
const ModalDemo = ({
  size,
  variant,
}: {
  size?: string;
  variant?: string;
}) => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>Открыть диалог</Button>
      <Modal
        isOpen={open}
        onClose={() => setOpen(false)}
        title="Подтверждение записи"
        size={size}
        variant={variant}
        actions={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Отмена</Button>
            <Button variant="primary" onClick={() => setOpen(false)}>Подтвердить</Button>
          </>
        }
      >
        <p style={{ margin: 0, color: 'var(--mac-text-primary)' }}>
          Пациент А. А. будет записан на приём. Демо-содержимое диалога
          показывает базовый макет модального окна.
        </p>
      </Modal>
    </>
  );
};

export const DefaultSize = {
  name: 'Стандартный размер',
  render: () => <ModalDemo />,
};

export const Sizes = {
  name: 'Размеры (small / large)',
  render: () => (
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
      <ModalDemo size="small" />
      <ModalDemo size="large" />
    </div>
  ),
};

export const CompactVariant = {
  name: 'Компактный вариант',
  render: () => <ModalDemo variant="compact" />,
};
