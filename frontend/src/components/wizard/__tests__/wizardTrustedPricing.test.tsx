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
      pricing_mode: 'cart',
    });
  });

  it('returns null for an empty/unresolved cart (nothing to quote)', () => {
    expect(buildCartQuoteRequest({ items: [] })).toBeNull();
    expect(buildCartQuoteRequest({ items: [{ quantity: 2 }] })).toBeNull();
    expect(buildCartQuoteRequest(null)).toBeNull();
  });

  it('mirrors custom_price into the quote request (Codex R1 P2)', () => {
    // Квота обязана учитывать врачебную переопределённую цену так же, как
    // это делает /registrar/cart при выставлении инвойса.
    const request = buildCartQuoteRequest({
      items: [{ service_id: 11, quantity: 2, custom_price: 80000 }],
    });
    expect(request).toEqual({
      items: [{ service_id: 11, quantity: 2, custom_price: 80000 }],
      discount_mode: 'none',
      all_free: false,
      pricing_mode: 'cart',
    });
    // custom_price отсутствует → поле не добавляется
    const plain = buildCartQuoteRequest({ items: [{ service_id: 12, quantity: 1 }] });
    expect(plain?.items[0]).not.toHaveProperty('custom_price', expect.anything());
    expect(Object.prototype.hasOwnProperty.call(plain?.items[0] ?? {}, 'custom_price')).toBe(false);
  });

  it('mirrors the selected doctor into quote specialist_id like the save command (Codex R12 P2)', () => {
    // Команда сохранения шлёт specialist_id = item.doctor_id (newServices),
    // поэтому команда создаст очередь выбранного врача, когда у услуги нет
    // default-врача и нет активной очереди дня. Квота и save-ревалидация
    // токена обязаны видеть ТОТ ЖЕ specialist_id — иначе квота 400
    // "specialist_id is required" навсегда блокирует завершение.
    const request = buildCartQuoteRequest({
      items: [{ service_id: 11, quantity: 2, doctor_id: 45 }],
    }, { pricingMode: 'edit_delta', patientId: 7, targetDate: '2026-09-09' });
    expect(request?.items[0]).toEqual({ service_id: 11, quantity: 2, specialist_id: 45 });

    // doctor_id отсутствует/некорректен → поле не добавляется (зеркало
    // newServicesWithoutDoctor: specialist_id: null)
    const noDoctor = buildCartQuoteRequest({ items: [{ service_id: 12, quantity: 1 }] });
    expect(Object.prototype.hasOwnProperty.call(noDoctor?.items[0] ?? {}, 'specialist_id')).toBe(false);
    const badDoctor = buildCartQuoteRequest({ items: [{ service_id: 12, quantity: 1, doctor_id: Number.NaN }] });
    expect(Object.prototype.hasOwnProperty.call(badDoctor?.items[0] ?? {}, 'specialist_id')).toBe(false);
  });

  it('edit-mode quote carries pricing_mode=edit_delta over the delta items (Codex R1 P1)', () => {
    // /registrar/cart/edit-delta выставляет ТОЛЬКО новые услуги и по своим
    // правилам (без repeat/benefit скидок). Квота edit-режима обязана
    // запрашивать именно дельту с pricing_mode='edit_delta'.
    const delta = buildCartQuoteRequest(
      { items: [{ service_id: 1, quantity: 1 }, { service_id: 2, quantity: 3 }] },
      { pricingMode: 'edit_delta', itemsOverride: [{ service_id: 2, quantity: 3 }] }
    );
    expect(delta).toEqual({
      items: [{ service_id: 2, quantity: 3 }],
      discount_mode: 'none',
      all_free: false,
      pricing_mode: 'edit_delta',
    });
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
    // Codex R1 PR 3095: в edit-режиме квота дополнительно зависит от identity
    // (edit-дельта) и справочника услуг; Codex R2 PR 3095: ещё и от маршрута
    // команды (fullUpdateQuoteRoute — QR-записи квотируются по full-update);
    // Codex R6 PR 3095: и от пациента (edit-контекст дельты: patient_id +
    // target_date + preferred entries входят в запрос квоты)
    expect(source).toContain('}, [isOpen, editMode, wizardData.cart, servicesData, editOriginalServiceIdentity, fullUpdateQuoteRoute, quoteRefreshNonce, wizardData.patient?.id]);');
    expect(source).toContain('patientId: wizardData.patient?.id ?? null');
    expect(source).toContain('targetDate: getLocalISODate()');
    expect(source).toContain('preferredEntryIds: Array.from(editOriginalServiceIdentity.queueIds)');
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
    // Codex R6 PR 3095 (P2): edit_delta биллит дельту (priced_qty = billable),
    // cart/full_update — полное запрошенное количество
    expect(backend).toContain('quantity=priced_qty');
    expect(backend).toContain('priced_qty = billable_qty if quote_req.pricing_mode == "edit_delta" else item_req.quantity');
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

// =====================================================================
// 4. Codex R2 PR 3095
// =====================================================================

describe('Fix D Codex R2: quote contract follows the actual command route', () => {
  let source = '';

  beforeEach(() => {
    source = readWizardSource();
  });

  it('full_update route is detected by the same predicate as the submit (Codex R2 P1)', () => {
    // QR-записи (online_queue + source=online + queueEntryId) сабмятся через
    // /queue/online-entry/{id}/full-update — квота обязана использовать
    // pricing_mode='full_update' и ПОЛНУЮ корзину, а не edit_delta.
    expect(source).toContain('const fullUpdateQuoteRoute = useMemo(() => {');
    expect(source).toContain("recordKind === 'online_queue' && effectiveSource === 'online'");
    expect(source).toContain('resolveOnlineQueueEntryId(initialData, recordKind, effectiveSource)');
    // выбор контракта: edit_delta только НЕ для full-update маршрута
    expect(source).toContain("if (isEditModeQuote && !fullUpdateQuoteRoute) {");
    expect(source).toContain("quotePricingMode = 'full_update';");
  });

  it('empty edit delta is a valid zero-cost quote, not a blocked idle state (Codex R2 P1)', () => {
    // Изменили только данные пациента / удалили услуги → квотировать нечего,
    // но сабмит обязан проходить: в edit-режиме ставится нулевая ready-квота.
    expect(source).toContain("setCartQuote({ items: [], total_amount: 0, approval_status: 'approved' });");
    expect(source).toContain('Codex R2 PR 3095 (P1): пустая дельта');
    // вне edit-режима поведение прежнее (idle)
    expect(source).toContain("setCartQuoteStatus('idle');");
  });

  it('backend quote endpoint accepts full_update and mirrors the full-update route', () => {
    const backend = readBackendCartSource();
    // Ветка зеркалит _full_update_create_single_independent_entry
    expect(backend).toContain('elif quote_req.pricing_mode == "full_update":');
    expect(backend).toContain('service.is_consultation and effective_discount_mode in ("repeat", "benefit")');
    // edit_delta → approved (команда пишет approved); full_update + all_free
    // → pending (Codex R3 #3095: _full_update_handle_all_free_visit пишет
    // approval_status="pending" и для нового, и для неоплаченного визита)
    expect(backend).toContain('if quote_req.pricing_mode == "edit_delta":');
    expect(backend).toContain('"pending" if effective_discount_mode == "all_free" else "approved"');
    // cart-режим: custom_price спасает от 409 при пустом каталог-прайсе
    expect(backend).toContain('if service.price is None and item_req.custom_price is None:');
  });
});
