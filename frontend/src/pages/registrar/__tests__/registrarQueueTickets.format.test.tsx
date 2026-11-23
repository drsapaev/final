/**
 * REG-FE-083 (follow-up audit 2026-11-02): предпросмотр записи показывает
 * ВЫДАННЫЕ НОМЕРА ТАЛОНОВ, а не только метку очереди.
 *
 * Прежде «Очередь» печаталась через formatPreviewList, который выбирает
 * name/service_name/code/queue_name/queue_tag и НИКОГДА не читает `number`:
 * предпросмотр показывал «Кардиология» вместо «№17 — Кардиология», и
 * мульти-очередные записи теряли все номера. Инвариант честности: запись
 * БЕЗ номера показывает «<метка> (без номера)» и никогда не изобретает
 * порядковый номер строки.
 *
 * Red-first (до фикса): formatPreviewQueueTickets не существовал; RecordPreview
 * терял номера (рендерил только queue_name/queue_tag).
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

import { formatPreviewList, formatPreviewQueueTickets } from '../registrarHelpers';
import RecordPreview from '../views/RecordPreview';
import type { Appointment } from '../../../types/domain/clinic';

// RecordPreview требует tI18n-проп (структурный тип).
type RecordPreviewDialogT = (key: string, options?: Record<string, unknown>) => string;

const tI18n = ((key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key) as unknown as RecordPreviewDialogT;

const mkRow = (extra: Record<string, unknown>): Appointment =>
  ({
    id: 1,
    patient_fio: 'Ivanov I.I.',
    queue_numbers: [],
    ...extra,
  }) as unknown as Appointment;

describe('formatPreviewQueueTickets — REG-FE-083 unit', () => {
  it('issued numbers are paired with their queue labels, multi-queue rows keep every numeral', () => {
    const out = formatPreviewQueueTickets(
      [
        { number: 17, queue_tag: 'cardiology', queue_name: 'Кардиология' },
        { number: 22, queue_name: 'Хирургия' },
        { number: 5 },
      ],
      'без номера',
    );
    expect(out).toBe('№17 — Кардиология, №22 — Хирургия, №5');
  });

  it('unallocated entry → honest placeholder, never an invented row ordinal', () => {
    const out = formatPreviewQueueTickets(
      [
        { queue_name: 'Кардиология' },
        { queue_tag: 'cardio' },
      ],
      'без номера',
    );
    expect(out).toBe('Кардиология (без номера), cardio (без номера)');
    expect(out).not.toMatch(/№\d/);
  });

  it('string arrays and non-array values pass through (same convention as formatPreviewList)', () => {
    expect(formatPreviewQueueTickets(['Анализ крови', 'ЭКГ'], 'без номера')).toBe('Анализ крови, ЭКГ');
    expect(formatPreviewQueueTickets(null, 'без номера')).toBe('');
    // Универсальный форматер услуг не изменён (у услуг нет `number`).
    expect(formatPreviewList([{ name: 'Терапия' }, { service_name: 'ЭКГ' }])).toBe('Терапия, ЭКГ');
  });
});

describe('RecordPreview — REG-FE-083 rendered queue field', () => {
  it('queue field renders issued ticket numbers with queue labels', () => {
    render(
      <RecordPreview
        isOpen
        row={mkRow({
          queue_numbers: [
            { number: 17, queue_tag: 'cardiology', queue_name: 'Кардиология' },
            { number: 22, queue_name: 'Хирургия' },
          ],
        })}
        onClose={() => {}}
        onEdit={() => {}}
        tI18n={tI18n}
      />,
    );

    expect(screen.getByText('№17 — Кардиология, №22 — Хирургия')).toBeTruthy();
    // Прежде рендерилось только «Кардиология» (formatPreviewList терял number).
    expect(screen.queryByText(/^Кардиология$/)).toBeNull();
  });

  it('entry without a number renders the honest placeholder (no fabricated №)', () => {
    render(
      <RecordPreview
        isOpen
        row={mkRow({ queue_numbers: [{ queue_name: 'Кардиология' }] })}
        onClose={() => {}}
        onEdit={() => {}}
        tI18n={tI18n}
      />,
    );

    expect(screen.getByText(/Кардиология \(registrarPanel\.rp_queue_no_ticket\)/)).toBeTruthy();
    expect(screen.queryByText(/№\d/)).toBeNull();
  });

  it('services field keeps using the generic formatter (no queue-number logic leakage)', () => {
    render(
      <RecordPreview
        isOpen
        row={mkRow({
          services: [{ name: 'Терапия' }, { service_name: 'ЭКГ' }],
          queue_numbers: [{ number: 9, queue_name: 'Кардиология' }],
        })}
        onClose={() => {}}
        onEdit={() => {}}
        tI18n={tI18n}
      />,
    );

    expect(screen.getByText('Терапия, ЭКГ')).toBeTruthy();
    expect(screen.getByText('№9 — Кардиология')).toBeTruthy();
  });
});
