/**
 * Modal Stories — canonical Modal primitive (plan §PR-UI-18 item 2).
 *
 * Modal is the canonical dialog surface (the duplicate components/common/
 * Modal was dead code slated for removal). Compound parts:
 * ModalHeader / ModalTitle / ModalContent / ModalFooter.
 */
import React from 'react';
import Modal from './Modal';
import Button from './Button';

export default {
  title: 'UI/MacOS/Modal',
  component: Modal,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical Modal: isOpen/onClose + title/children/actions, ' +
          'sizes and variants; backdrop/escape behaviour controlled by props.',
      },
    },
  },
};

export const ConfirmDialog = {
  args: {
    isOpen: true,
    title: 'Отменить приём?',
    children: 'Приём пациента А. А. (кардиология, кабинет 12) будет отменён. Действие нельзя отменить.',
    actions: (
      <>
        <Button variant="secondary">Отмена</Button>
        <Button variant="danger">Отменить приём</Button>
      </>
    ),
  },
};

export const Informational = {
  args: {
    isOpen: true,
    title: 'Чек отправлен на печать',
    children: 'Документ добавлен в очередь печати. Заберите чек в регистратуре.',
    actions: <Button variant="primary">Понятно</Button>,
  },
};
