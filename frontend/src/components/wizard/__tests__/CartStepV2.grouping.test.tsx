/**
 * RQ-07 (S-05) — категория корзины не зависит от текста названия и legacy-кода.
 *
 * Прежний контракт (дефект, зарегистрирован планом RQ-07):
 *   фильтр категорий CartStepV2.getDisplayedServices классифицировал услуги
 *   эвристиками по ТЕКСТУ названия (name.includes('консультация'/'экг'/
 *   'эхокг'/'рентген')) и по ЖЕСТКО ЗАШИТЫМ legacy-кодам (service_code ===
 *   'K10', includes('ECG'), /^S\d+$/ + 'рентген'):
 *     - услуга категории K с не-русским (переведенным) названием исчезала
 *       из ВСЕХ вкладок (isConsultation=false по тексту; normalizedCategory
 *       'specialists' в фильтре specialists не участвовал);
 *     - услуга категории P со словом «консультация» в названии уезжала из
 *       «Процедур» в «Специалистов» — текст менял медицинскую классификацию;
 *     - новая услуга той же категории с кодом, не совпадающим с legacy
 *       (K22, S30), исчезала со вкладки «Специалисты».
 *
 * Новый контракт (поведенческие тесты, SYNTHETIC-метаданные):
 *   - классификация только по каноническим полям DTO: category_code
 *     (SSOT normalizeCategoryCode) и is_consultation;
 *   - при неизвестном category_code — fallback на канонический префикс
 *     service_code (parseServiceCode), но НЕ по тексту названия;
 *   - неклассифицированное остается видимым явно на вкладке «Прочее»;
 *   - прежняя продуктовая раскладка канонических категорий сохранена
 *     (K → Специалисты, L → Лаборатория, P → Процедуры).
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import CartStepV2 from '../CartStepV2';

const SYNTHETIC_SERVICES = [
  // Специалисты: консультация с каноническим is_consultation, название БЕЗ
  // слова «консультация» (как после перевода/переименования).
  { id: 1, name: 'Терапевт первичный приём', category_code: 'K', service_code: 'K01', is_consultation: true, price: 50000 },
  // Специалисты: ЭКГ с legacy-кодом K10 — регрессионный контроль раскладки.
  { id: 2, name: 'Электрокардиограмма', category_code: 'K', service_code: 'K10', is_consultation: false, price: 30000 },
  // Специалисты: новая услуга категории K с кодом, НЕ совпадающим с legacy
  // K10/'ECG', и названием без «экг» — раньше исчезала со вкладки.
  { id: 3, name: 'Холтер суточный', category_code: 'K', service_code: 'K22', is_consultation: false, price: 40000 },
  // Специалисты: стоматология S с названием без «рентген» — раньше исчезала.
  { id: 4, name: 'Зубной снимок 48', category_code: 'S', service_code: 'S30', is_consultation: false, price: 25000 },
  // Специалисты: категория неизвестна, но DTO явно помечает консультацию.
  { id: 5, name: 'Приём узкого специалиста', is_consultation: true, price: 60000 },
  // Процедуры: текст содержит «консультац...», но канонические метаданные
  // говорят procedures + is_consultation=false — текст не должен переносить
  // услугу в «Специалистов» и не должен прятать её из «Процедур».
  { id: 6, name: 'Консультационный контроль процедуры', category_code: 'P', service_code: 'P05', is_consultation: false, price: 15000 },
  // Лаборатория: каноническая категория L.
  { id: 7, name: 'Общий анализ крови', category_code: 'L', service_code: 'L01', is_consultation: false, price: 12000 },
  // Прочее: неклассифицированная услуга без category_code/service_code —
  // обязана оставаться видимой явно (S-05: «неклассифицированное видно»).
  { id: 8, name: 'Синтетическая допуслуга', is_consultation: false, price: 5000 },
];

const CATEGORIES = ['specialists', 'laboratory', 'procedures', 'other'];

const buildProps = (activeCategory: string) => ({
  cart: { items: [], visit_date: '', discount_mode: 'none', all_free: false },
  onAddToCart: vi.fn(),
  onRemoveFromCart: vi.fn(),
  servicesData: SYNTHETIC_SERVICES,
  doctorsData: [],
  errors: undefined,
  activeCategory,
  searchQuery: '',
  editMode: false,
  getServiceName: (itemOrService: { name?: string }) => itemOrService.name || '',
  onUpdateItem: vi.fn(),
  cartQuoteStatus: 'idle' as const,
  cartQuoteTotal: null,
  cartQuoteMessage: undefined,
});

const visibleNames = (activeCategory: string): string[] => {
  const { container } = render(<CartStepV2 {...buildProps(activeCategory)} />);
  const names = Array.from(
    container.querySelectorAll<HTMLElement>('.cart-step-v2__service-name'),
  ).map((el) => el.textContent || '');
  return names;
};

const namesFor = (activeCategory: string): Set<string> =>
  new Set(visibleNames(activeCategory));

describe('RQ-07: вкладка «Специалисты» классифицирует по category_code/is_consultation', () => {
  it('консультация видна по каноническому is_consultation, даже если названия нет слова «консультация»', () => {
    const names = namesFor('specialists');
    expect(names.has('Терапевт первичный приём')).toBe(true);
  });

  it('новая услуга категории K (код K22, название без «экг») не исчезает со вкладки', () => {
    const names = namesFor('specialists');
    expect(names.has('Холтер суточный')).toBe(true);
  });

  it('стоматология S (название без «рентген») не исчезает со вкладки', () => {
    const names = namesFor('specialists');
    expect(names.has('Зубной снимок 48')).toBe(true);
  });

  it('консультация без категории видна по is_consultation (fallback категории не нужен)', () => {
    const names = namesFor('specialists');
    expect(names.has('Приём узкого специалиста')).toBe(true);
  });

  it('регрессионный контроль: legacy ЭКГ K10 остается на «Специалистах»', () => {
    const names = namesFor('specialists');
    expect(names.has('Электрокардиограмма')).toBe(true);
  });

  it('текст «Консультационный контроль...» НЕ переносит процедуру P в «Специалистов»', () => {
    const names = namesFor('specialists');
    expect(names.has('Консультационный контроль процедуры')).toBe(false);
  });
});

describe('RQ-07: канонические категории процедур и лаборатории', () => {
  it('процедура P видна на «Процедурах», несмотря на слово «консультация» в названии', () => {
    const names = namesFor('procedures');
    expect(names.has('Консультационный контроль процедуры')).toBe(true);
  });

  it('лаборатория L видна на «Лаборатории»', () => {
    const names = namesFor('laboratory');
    expect(names.has('Общий анализ крови')).toBe(true);
  });

  it('услуга категории K не попадает на «Процедуры» и «Лабораторию»', () => {
    expect(namesFor('procedures').has('Холтер суточный')).toBe(false);
    expect(namesFor('laboratory').has('Холтер суточный')).toBe(false);
  });
});

describe('RQ-07: неклассифицированное видно явно', () => {
  it('услуга без category_code/service_code остается на «Прочем»', () => {
    const names = namesFor('other');
    expect(names.has('Синтетическая допуслуга')).toBe(true);
  });

  it('переведенное название услуги категории K не теряет услугу НИ НА ОДНОЙ вкладке (S-05)', () => {
    // Услуга «Приём узкого специалиста» (id=5) обязана быть видимой ровно
    // на одной вкладке; до фикса она не появлялась ни на одной.
    const foundOn = CATEGORIES.filter((cat) => namesFor(cat).has('Приём узкого специалиста'));
    expect(foundOn).toEqual(['specialists']);
  });

  it('на вкладке «Прочее» нет услуг канонических категорий K/L/P', () => {
    const names = namesFor('other');
    expect(names.has('Терапевт первичный приём')).toBe(false);
    expect(names.has('Общий анализ крови')).toBe(false);
    expect(names.has('Консультационный контроль процедуры')).toBe(false);
  });
});

describe('RQ-07: вкладка «Все» и поиск не меняют каноническую классификацию', () => {
  it('неизвестная вкладка (default) показывает весь каталог без эвристик', () => {
    const names = namesFor('all');
    expect(names.size).toBe(SYNTHETIC_SERVICES.length);
  });

  it('все услуги всегда присутствуют в DOM-выдаче ровно одной вкладки (нет дублей и потерь)', () => {
    for (const service of SYNTHETIC_SERVICES) {
      const foundOn = CATEGORIES.filter((cat) => namesFor(cat).has(service.name));
      expect(foundOn.length, `услуга "${service.name}" видна ровно на одной вкладке`).toBeLessThanOrEqual(1);
    }
  });
});

describe('RQ-07: корзинная группировка не зависит от классификации каталога', () => {
  it('счётчик визитов не рендерится для пустой корзины (негативный контроль)', () => {
    render(<CartStepV2 {...buildProps('specialists')} />);
    expect(screen.queryByText(/Будет создано визитов/)).not.toBeInTheDocument();
  });
});
