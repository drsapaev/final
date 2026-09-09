/**
 * Codex R10 PR 3118 (P2) — quote-ошибка должна быть ВИДНА в блоке ошибок.
 *
 * Дефект: сообщение в блоке ошибок приоритизирует `errors.quote`, но условие
 * рендера проверяло только `cart || doctors || repeat`. Когда сабмит
 * блокировался из-за простаивающей/загружающейся квоты и выставлена ТОЛЬКО
 * quote-ошибка, блок оставался скрытым — кнопка выглядела «нажатой в
 * пустоту».
 *
 * Поведенческий рендер-тест: пустая корзина, минимальные props, только
 * errors.quote → текст ошибки обязан присутствовать в DOM.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import CartStepV2 from '../CartStepV2';

const buildProps = (errors?: Record<string, unknown>) => ({
  cart: { items: [], visit_date: '', discount_mode: 'none', all_free: false },
  onAddToCart: vi.fn(),
  onRemoveFromCart: vi.fn(),
  servicesData: [],
  doctorsData: [],
  errors,
  activeCategory: 'all',
  searchQuery: '',
  editMode: false,
  getServiceName: () => '',
  onUpdateItem: vi.fn(),
  cartQuoteStatus: 'idle' as const,
  cartQuoteTotal: null,
  cartQuoteMessage: undefined,
});

describe('Codex R10 PR 3118: quote-only ошибка рендерится', () => {
  it('блок ошибок виден, когда выставлена ТОЛЬКО errors.quote', () => {
    render(
      <CartStepV2
        {...buildProps({ quote: 'Корзина изменилась — обновите квоту' })}
      />,
    );
    expect(screen.getByText('Корзина изменилась — обновите квоту')).toBeInTheDocument();
  });

  it('без ошибок блок ошибок не рендерится (негативный контроль)', () => {
    const { container } = render(<CartStepV2 {...buildProps(undefined)} />);
    expect(container.querySelector('.cart-step-v2__footer-hint')).toBeInTheDocument(); // «Корзина пуста»
    expect(screen.queryByText('Корзина изменилась — обновите квоту')).not.toBeInTheDocument();
  });
});
