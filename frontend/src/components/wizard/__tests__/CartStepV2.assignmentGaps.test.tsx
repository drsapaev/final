/**
 * PR #3511 round-3 (P2, owner review): пустой список врачей в мастере.
 *
 * Дефект: `collectDoctorAssignmentGaps` выходил ранним `[]` при пустом
 * roster — закреплённая услуга (Service.doctor_id) исчезала без объяснения
 * причины, а блок instructions администратору не показывался вовсе.
 *
 * Новый контракт (поведенческие тесты, SYNTHETIC-метаданные):
 *   - roster УСПЕШНО загружен и ПУСТОЙ ('loaded') + закреплённая услуга →
 *     блок `.cart-step-v2__assignment-gaps` виден: точная причина
 *     (doctor_missing) и путь администратора;
 *   - запрос врачей не завершён ('loading') или упал ('error') → блока НЕТ:
 *     сбой загрузки не выдаётся за конфиг-ошибку каталога;
 *   - проп не передан (legacy-вызовы) → переданный массив по-прежнему
 *     достоверен: непустой roster с отсутствующим назначенным врачом
 *     показывает блок как раньше.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import CartStepV2, { type CartStepV2Props } from '../CartStepV2';
import type { DoctorsRequestStatus } from '../wizardUtils';

const SYNTHETIC_PINNED_ECHO = {
  id: 30,
  name: 'ЭхоКГ закреплённая (синтетика)',
  category_code: 'K',
  service_code: 'K11',
  is_consultation: false,
  price: 120000,
  doctor_id: 7,
  department_key: 'cardiology',
  accepted_specialties: ['cardiology'],
};

const buildProps = (
  doctors: CartStepV2Props['doctorsData'],
  doctorsRequestStatus?: DoctorsRequestStatus,
): CartStepV2Props => ({
  cart: { items: [], visit_date: '', discount_mode: 'none', all_free: false },
  onAddToCart: vi.fn(),
  onRemoveFromCart: vi.fn(),
  servicesData: [SYNTHETIC_PINNED_ECHO] as CartStepV2Props['servicesData'],
  doctorsData: doctors,
  doctorsRequestStatus,
  errors: undefined,
  activeCategory: 'all',
  searchQuery: '',
  editMode: false,
  getServiceName: (itemOrService: { name?: string }) => itemOrService.name || '',
  onUpdateItem: vi.fn(),
  cartQuoteStatus: 'idle',
  cartQuoteTotal: null,
  cartQuoteMessage: undefined,
});

describe('PR #3511 round-3 (P2): assignment-gap блок при пустом roster', () => {
  it("показывает причину, когда roster успешно загружен и ПУСТ (doctor_missing)", () => {
    render(<CartStepV2 {...buildProps([], 'loaded')} />);

    expect(
      screen.getByText('Услуги с назначенным врачом недоступны для записи'),
    ).toBeInTheDocument();
    // Точная причина: услуга + ID отсутствующего назначенного врача.
    expect(
      screen.getByText(/ЭхоКГ закреплённая \(синтетика\)» назначлена врачу \(ID 7\)/),
    ).toBeInTheDocument();
  });

  it("не показывает блок, пока запрос врачей в полёте ('loading')", () => {
    const { container } = render(<CartStepV2 {...buildProps([], 'loading')} />);
    expect(container.querySelector('.cart-step-v2__assignment-gaps')).toBeNull();
  });

  it("не показывает блок при упавшем запросе врачей ('error') — нет ложной конфиг-ошибки", () => {
    const { container } = render(<CartStepV2 {...buildProps([], 'error')} />);
    expect(container.querySelector('.cart-step-v2__assignment-gaps')).toBeNull();
  });

  it('legacy-вызов без пропа: непустой roster с отсутствующим врачом показывает блок', () => {
    render(
      <CartStepV2
        {...buildProps([{ id: 101, user: { full_name: 'Синтетический Врач' }, specialty: 'cardiology', active: true }])}
      />,
    );
    expect(
      screen.getByText(/назначлена врачу \(ID 7\), которого нет среди активных врачей/),
    ).toBeInTheDocument();
  });

  it("успешно загруженный пустой roster без закреплённых услуг — блока нет", () => {
    const props = buildProps([], 'loaded');
    props.servicesData = [{ id: 31, name: 'Обычная консультация (синтетика)', category_code: 'K', service_code: 'K01', is_consultation: true, price: 50000, doctor_id: null }] as CartStepV2Props['servicesData'];
    const { container } = render(<CartStepV2 {...props} />);
    expect(container.querySelector('.cart-step-v2__assignment-gaps')).toBeNull();
  });
});
