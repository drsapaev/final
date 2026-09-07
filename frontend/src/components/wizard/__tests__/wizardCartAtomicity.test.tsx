/**
 * Fix C (cart atomicity + duplicate submit protection) — targeted tests.
 *
 * Оригинальные дефекты:
 *  - create_visit() коммитил внутри, cart endpoint вызывал его в цикле —
 *    частичный сбой оставлял уже закоммиченные визиты (backend-тесты в
 *    backend/tests/test_registrar_cart_atomicity.py);
 *  - IdempotencyMiddleware на backend'e был opt-in, но frontend никогда
 *    не отправлял Idempotency-Key — сетевые ретраи могли создать вторую корзину;
 *  - повторный Enter во время обработки дважды запускал handleComplete.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import { createIdempotencyKey } from '../wizardUtils';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const patientsApiPath = path.resolve(__dirname, '../../../api/patients.ts');
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readPatientsApiSource = () => fs.readFileSync(patientsApiPath, 'utf8');

// =====================================================================
// 1. Idempotency key helper (real behavior)
// =====================================================================

describe('Fix C: createIdempotencyKey', () => {
  it('produces unique, non-empty keys', () => {
    const a = createIdempotencyKey();
    const b = createIdempotencyKey();
    expect(a).toBeTruthy();
    expect(b).toBeTruthy();
    expect(a).not.toBe(b);
  });
});

// =====================================================================
// 2. Source contracts
// =====================================================================

describe('Fix C: wizard duplicate-submit contract', () => {
  let source = '';

  beforeEach(() => {
    source = readWizardSource();
  });

  it('ignores Enter/Ctrl+Enter while processing (no duplicate submit via keyboard)', () => {
    const keydownBlock = source.slice(
      source.indexOf('=====', source.indexOf('ГОРЯЧИЕ КЛАВИШИ') - 100),
      source.indexOf('===================== ЗАВЕРШЕНИЕ')
    );
    expect(keydownBlock).toContain('if (isProcessing) return;');
    expect(keydownBlock).toContain('[isOpen, currentStep, totalSteps, isProcessing]');
  });

  it('guards handleComplete against re-entrant invocation', () => {
    expect(source).toContain('if (submitLockRef.current) {');
    expect(source).toContain('submitLockRef.current = true;');
    expect(source).toContain('submitLockRef.current = false;');
  });

  it('sends Idempotency-Key with the cart submission and reuses it on retry', () => {
    expect(source).toContain('createRegistrarCart(cartData, { idempotencyKey: cartIdempotencyKeyRef.current })');
    // Ключ генерируется один раз и живёт до успеха
    expect(source).toContain('if (!cartIdempotencyKeyRef.current) {');
    // Успех сбрасывает ключ (следующая корзина = новая операция)
    expect(source).toContain('cartIdempotencyKeyRef.current = null;');
  });

  it('refuses to resend a CHANGED payload under the already-bound key (Codex R2 P2)', () => {
    // Codex R2 #3092 (P1): ключ привязан к payload первой попытки; изменив
    // врача/услугу/дату после сбоя, нельзя повторно отправить изменённые
    // данные со старым ключом — backend вернёт 409, а фронт откажется
    // отправлять раньше времени, чтобы не выдавать оригинальный успех за
    // сохранение новых данных.
    expect(source).toContain('cartIdempotencyPayloadRef = useRef<string | null>(null);');
    expect(source).toContain('cartIdempotencyPayloadRef.current = JSON.stringify(cartData);');
    expect(source).toContain("JSON.stringify(cartData) !== cartIdempotencyPayloadRef.current");
    expect(source).toContain("t('misc.aw_cart_retry_payload_changed')");
    // Успех очищает и payload-снимок; сброс ключа при закрытии/очистке — тоже
    expect(source).toContain('cartIdempotencyPayloadRef.current = null;');
    // i18n-ключ существует во всех 5 локалях (правило Codex R1 #3088)
    const locales = ['en', 'ru', 'kk', 'uz-Cyrl', 'uz-Latn'];
    for (const loc of locales) {
      const localeSource = fs.readFileSync(
        path.resolve(__dirname, `../../../i18n/locales/${loc}.ts`),
        'utf8'
      );
      expect(localeSource).toContain('aw_cart_retry_payload_changed:');
    }
  });

  it('api client forwards the Idempotency-Key header', () => {
    const apiSource = readPatientsApiSource();
    expect(apiSource).toContain("options: { idempotencyKey?: string } = {}");
    expect(apiSource).toContain("'Idempotency-Key': options.idempotencyKey");
  });
});
