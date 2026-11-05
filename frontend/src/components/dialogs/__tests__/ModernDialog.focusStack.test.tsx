/**
 * REG-FE-075/076/077/080 (follow-up audit 2026-11-02): доступность и
 * владение жизненным циклом ModernDialog.
 *
 * 075: customHeader-композиция без строкового title оставляла диалог
 *      БЕЗ доступного имени (aria-labelledby не проставлялся).
 * 076: ловушка фокуса считала disabled/скрытые элементы tabbable —
 *      Tab с последней ЖИВОЙ кнопки выпадал из диалога.
 * 077: каждый экземпляр вешал глобальный keydown и безусловно чистил
 *      body.overflow — внутренний диалог закрывался вместе с внешним
 *      (Escape), а скролл разблокировался за ещё открытым.
 * 080: фокус не возвращался на триггер после закрытия.
 *
 * Red-first: все четыре падали на префиксном исходнике.
 */
import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ModernDialog from '../ModernDialog';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

beforeEach(() => {
  document.body.style.overflow = '';
});

afterEach(() => {
  vi.useRealTimers();
  document.body.style.overflow = '';
});

describe('REG-FE-075: dialog accessible name', () => {
  it('customHeader composition without title gets a name via ariaLabel', () => {
    render(
      <ModernDialog
        isOpen
        onClose={vi.fn()}
        customHeader={<div className="custom">Свой заголовок</div>}
        ariaLabel="Регистрация пациента"
      />,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog.getAttribute('aria-label')).toBe('Регистрация пациента');
  });

  it('string title keeps naming the dialog (aria-label, customHeader case)', () => {
    render(
      <ModernDialog
        isOpen
        onClose={vi.fn()}
        title="Изменение цены"
        customHeader={<div className="custom">header</div>}
      />,
    );
    expect(screen.getByRole('dialog').getAttribute('aria-label')).toBe('Изменение цены');
  });

  it('plain title keeps aria-labelledby (unchanged legacy contract)', () => {
    render(<ModernDialog isOpen onClose={vi.fn()} title="Обычный заголовок" />);
    const dialog = screen.getByRole('dialog');
    expect(dialog.getAttribute('aria-labelledby')).toBe('dialog-title');
  });
});

describe('REG-FE-076: focus trap counts only real candidates', () => {
  it('Tab from the last LIVE button wraps when the trailing action is disabled', async () => {
    vi.useFakeTimers();
    try {
      render(
        <ModernDialog
          isOpen
          onClose={vi.fn()}
          title="Отмена записи"
          actions={[
            { label: 'Отмена', onClick: vi.fn(), variant: 'secondary' },
            { label: 'Подтвердить', onClick: vi.fn(), disabled: true, variant: 'primary' },
          ]}
        />,
      );
      // Первоначальный фокус (100ms) — на первый ДОСТУПНЫЙ элемент.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      // Первый tabbable — close-кнопка (X): disabled-действие не получает
      // ни стартового фокуса, ни места в таб-порядке.
      // У close-кнопки и backdrop-кнопки одинаковый aria-label — берём
      // именно close-кнопку заголовка.
      const closeButton = document.querySelector('.modern-dialog-close') as HTMLElement;
      expect(closeButton).not.toBeNull();
      expect(document.activeElement).toBe(closeButton);

      // «Отмена» — последняя ЖИВАЯ кнопка: Tab с неё заворачивает на
      // первый элемент, а не «застревает» на disabled-«Подтвердить».
      const cancelButton = screen.getByRole('button', { name: 'Отмена' });
      cancelButton.focus();
      await act(async () => {
        fireEvent.keyDown(document, { key: 'Tab' });
      });
      expect(document.activeElement).toBe(closeButton);
      expect(document.activeElement).not.toBe(screen.getByRole('button', { name: 'Подтвердить' }));
      expect(document.activeElement).not.toBe(document.body);
    } finally {
      vi.useRealTimers();
    }
  }, 10000);
});

describe('REG-FE-077: dialog stack owns Escape and body scroll', () => {
  const NestedDialogs = ({
    closeOuter,
    closeInner,
  }: {
    closeOuter: () => void;
    closeInner: () => void;
  }) => (
    <>
      <ModernDialog
        isOpen
        onClose={closeOuter}
        title="Внешний диалог"
        actions={[{ label: 'Внешнее действие', onClick: () => undefined }]}
      />
      <ModernDialog isOpen onClose={closeInner} title="Внутренний диалог" />
    </>
  );

  it('Escape closes only the TOP dialog', async () => {
    const closeOuter = vi.fn();
    const closeInner = vi.fn();
    vi.useFakeTimers();
    try {
      render(<NestedDialogs closeOuter={closeOuter} closeInner={closeInner} />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await act(async () => {
        fireEvent.keyDown(document, { key: 'Escape' });
      });

      expect(closeInner).toHaveBeenCalledTimes(1);
      expect(closeOuter).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  }, 10000);

  it('body scroll is restored only when the LAST dialog closes', async () => {
    vi.useFakeTimers();
    try {
      const first = render(<ModernDialog isOpen onClose={vi.fn()} title="Первый" />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });
      expect(document.body.style.overflow).toBe('hidden');

      const second = render(<ModernDialog isOpen onClose={vi.fn()} title="Второй" />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      // Первый закрылся — второй ещё открыт.
      first.unmount();
      expect(document.body.style.overflow).toBe('hidden');

      // Последний закрылся — скролл возвращён.
      second.unmount();
      expect(document.body.style.overflow).toBe('');
    } finally {
      vi.useRealTimers();
    }
  }, 10000);
});

describe('REG-FE-080: focus returns to the trigger', () => {
  it('focus is restored to the element that opened the dialog', async () => {
    vi.useFakeTimers();
    try {
      const trigger = document.createElement('button');
      trigger.textContent = 'Открыть';
      document.body.appendChild(trigger);
      trigger.focus();
      expect(document.activeElement).toBe(trigger);

      const { unmount } = render(
        <ModernDialog isOpen onClose={vi.fn()} title="Диалог" />,
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });
      expect(document.activeElement).not.toBe(trigger);

      unmount();
      expect(document.activeElement).toBe(trigger);

      trigger.remove();
    } finally {
      vi.useRealTimers();
    }
  }, 10000);
});
