/**
 * Fix D (trusted pricing) — targeted tests.
 *
 * Оригинальные дефекты:
 *  - подтверждение сабмита считало totalAmount из несуществующего item.price
 *    → 0 для платных услуг (100000 показывалась как «бесплатно»);
 *  - frontend дублировал правила скидок и считал repeat-консультации
 *    бесплатными, тогда как backend применяет настраиваемый процент;
 *  - отсутствие цены отображалось как 0 сум.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import { buildCartQuoteRequest, type CartQuote } from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const cartStepPath = path.resolve(__dirname, '../CartStepV2.tsx');
const backendCartPath = path.resolve(
  __dirname,
 '../../../../../backend/app/api/v1/endpoints/registrar_wizard/_cart.py'
);
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readCartStepSource = () => fs.readFileSync(cartStepPath, 'utf8');
const readBackendCartSource = () => fs.readFileSync(backendCartPath, 'utf8');

// =====================================================================
// 1. buildCartQuoteRequest (real behavior)
// =====================================================================

describe('Fix D: buildCartQuoteRequest', () => {
  it('builds items with quantity from cart lines', () => {
    const request = buildCartQuoteRequest({
      items: [
        { service_id: 11, quantity: 1 },
        { service_id: 22, quantity: 3 },
      ],
      discount_mode: 'repeat',
      all_free: false,
    });
    expect(request).toEqual({
      items: [
        { service_id: 11, quantity: 1 },
        { service_id: 22, quantity: 3 },
      ],
      discount_mode: 'repeat',
      all_free: false,
    });
  });

  it('returns null for an empty/unresolved cart (nothing to quote)', () => {
    expect(buildCartQuoteRequest({ items: [] })).toBeNull();
    expect(buildCartQuoteRequest({ items: [{ quantity: 2 }] })).toBeNull();
    expect(buildCartQuoteRequest(null)).toBeNull();
  });
});

// =====================================================================
// 2. Source contracts
// =====================================================================

describe('Fix D: trusted pricing contract', () => {
  let source = '';
  let cartStep = '';

  beforeEach(() => {
    source = readWizardSource();
    cartStep = readCartStepSource();
  });

  it('confirmation total comes from the server quote, not from item.price', () => {
    // Прежний баг: reduce по несуществующему item.price
    expect(source).not.toContain('sum + (Number((item as { price?: number | string }).price) || 0), 0)');
    expect(source).toContain('const totalAmount = Number(cartQuote.total_amount) || 0;');
  });

  it('blocks completion while the quote is not ready (no untrustworthy totals)', () => {
    expect(source).toContain("if (cartQuoteStatus !== 'ready' || !cartQuote) {");
    expect(source).toContain("t('misc.aw_quote_calculating')");
    expect(source).toContain("t('misc.aw_quote_error')");
  });

  it('only the latest quote response is applied (stale responses discarded)', () => {
    expect(source).toContain('cartQuoteRequestIdRef.current');
    expect(source).toContain('requestId !== cartQuoteRequestIdRef.current');
  });

  it('quote request is rebuilt on any cart/discount change (old preview invalidated)', () => {
    expect(source).toContain('}, [isOpen, wizardData.cart]);');
  });

  it('CartStepV2 no longer zeroes repeat consultations (backend owns discounts)', () => {
    expect(cartStep).not.toContain("itemPrice = 0;");
    expect(cartStep).toContain('cartQuoteStatus');
    expect(cartStep).toContain('aw_quote_price_not_set');
  });

  it('shows pending approval status for All Free in the confirmation', () => {
    expect(source).toContain("cartQuote.approval_status === 'pending' ? t('misc.aw_quote_pending_approval') : null");
  });

  it('backend quote endpoint reuses the save-path discount SSOT helpers', () => {
    const backend = readBackendCartSource();
    expect(backend).toContain('def quote_cart_prices(');
    // SSOT: те же настройки и тот же хелпер скидок, что и при сохранении
    expect(backend).toContain('_load_registration_discount_settings(db)');
    expect(backend).toContain('_apply_service_discount(');
    // Отсутствие цены — не 0
    expect(backend).toContain('не указана цена');
  });

  it('quote items carry unit price, quantity, discount and final price', () => {
    const backend = readBackendCartSource();
    expect(backend).toContain('service_name=service.name');
    expect(backend).toContain('quantity=item_req.quantity');
    expect(backend).toContain('discount_percent=discount_percent');
    expect(backend).toContain('final_price=final_price');
  });
});

// =====================================================================
// 3. Quote shape sanity (type-level guard for the confirmation rendering)
// =====================================================================

describe('Fix D: quote shape', () => {
  it('confirmation rendering fields exist on CartQuote', () => {
    const quote: CartQuote = {
      items: [
        {
          service_id: 1,
          service_name: 'Консультация',
          unit_price: 100000,
          quantity: 2,
          discount_percent: 50,
          final_price: 100000,
        },
      ],
      total_amount: 100000,
      approval_status: 'approved',
    };
    expect(quote.items[0].final_price).toBe(quote.items[0].unit_price); // 50% от 100000 × 2
    expect(quote.total_amount).toBe(100000);
  });
});
