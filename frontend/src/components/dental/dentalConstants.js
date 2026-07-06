/**
 * dentalConstants — Single Source of Truth for dental clinical dictionaries.
 *
 * H6 fix: previously TOOTH_STATUS / TOOTH_PROCEDURES / MATERIALS were defined
 * in 3 different files (DentalChart.jsx, TeethChart.jsx, ToothModal.jsx) with
 * subtle drift between them. Now every consumer imports from here.
 *
 * All values are intentionally lowercase snake_case strings — they persist
 * into the EMR v2 `specialty_data.tooth_status[toothNumber]` JSONB field
 * and must remain stable across backend versions.
 *
 * NOTE: prices are baseline defaults used for UI display; actual visit
 * charges go through the price-override / cashier flow. Do NOT treat these
 * as authoritative — they're a UI convenience only.
 */

// =============================================================================
// Tooth status — visual state of a tooth on the chart
// =============================================================================
export const TOOTH_STATUS = Object.freeze({
  HEALTHY: 'healthy',
  CARIES: 'caries',
  FILLED: 'filled',
  CROWN: 'crown',
  IMPLANT: 'implant',
  MISSING: 'missing',
  ROOT: 'root',
  BRIDGE: 'bridge',
});

export const TOOTH_STATUS_LIST = Object.freeze(
  Object.values(TOOTH_STATUS),
);

export const TOOTH_STATUS_COLORS = Object.freeze({
  [TOOTH_STATUS.HEALTHY]: '#4caf50',
  [TOOTH_STATUS.CARIES]: '#f44336',
  [TOOTH_STATUS.FILLED]: '#2196f3',
  [TOOTH_STATUS.CROWN]: '#ff9800',
  [TOOTH_STATUS.IMPLANT]: '#9c27b0',
  [TOOTH_STATUS.MISSING]: 'var(--mac-text-tertiary)',
  [TOOTH_STATUS.ROOT]: 'var(--mac-text-tertiary)',
  [TOOTH_STATUS.BRIDGE]: 'var(--mac-accent-blue-light)',
});

export const TOOTH_STATUS_LABELS = Object.freeze({
  [TOOTH_STATUS.HEALTHY]: 'Здоров',
  [TOOTH_STATUS.CARIES]: 'Кариес',
  [TOOTH_STATUS.FILLED]: 'Пломба',
  [TOOTH_STATUS.CROWN]: 'Коронка',
  [TOOTH_STATUS.IMPLANT]: 'Имплант',
  [TOOTH_STATUS.MISSING]: 'Отсутствует',
  [TOOTH_STATUS.ROOT]: 'Корень',
  [TOOTH_STATUS.BRIDGE]: 'Мост',
});

// =============================================================================
// Tooth procedures — what was done to a tooth during a visit
// =============================================================================
// `isProsthetic` flag marks procedures that involve prosthetic work and
// therefore trigger the extra prosthetic-fields UI (shade / fit_quality /
// warranty_period / patient_satisfaction) in ToothModal.
export const TOOTH_PROCEDURES = Object.freeze({
  EXAMINATION: { id: 'examination', name: 'Осмотр', price: 20000, isProsthetic: false },
  CLEANING:    { id: 'cleaning',    name: 'Чистка', price: 50000, isProsthetic: false },
  FILLING:     { id: 'filling',     name: 'Пломба', price: 150000, isProsthetic: false },
  ROOT_CANAL:  { id: 'root_canal',  name: 'Лечение каналов', price: 300000, isProsthetic: false },
  CROWN:       { id: 'crown',       name: 'Коронка', price: 500000, isProsthetic: true },
  EXTRACTION:  { id: 'extraction',  name: 'Удаление', price: 100000, isProsthetic: false },
  IMPLANT:     { id: 'implant',     name: 'Имплантация', price: 1500000, isProsthetic: true },
  BRIDGE:      { id: 'bridge',      name: 'Мостовидный протез', price: 800000, isProsthetic: true },
  VENEER:      { id: 'veneer',      name: 'Винир', price: 600000, isProsthetic: true },
});

export const TOOTH_PROCEDURE_LIST = Object.freeze(
  Object.values(TOOTH_PROCEDURES),
);

export const PROSTHETIC_PROCEDURE_IDS = Object.freeze(
  TOOTH_PROCEDURE_LIST.filter((p) => p.isProsthetic).map((p) => p.id),
);

export const isProstheticProcedure = (procedureId) =>
  PROSTHETIC_PROCEDURE_IDS.includes(procedureId);

// =============================================================================
// Materials — used for fillings, crowns, bridges, veneers
// =============================================================================
export const MATERIALS = Object.freeze({
  COMPOSITE:      { id: 'composite',      name: 'Композит',         price: 50000 },
  CERAMIC:        { id: 'ceramic',        name: 'Керамика',         price: 200000 },
  METAL_CERAMIC:  { id: 'metal_ceramic',  name: 'Металлокерамика',  price: 150000 },
  ZIRCONIA:       { id: 'zirconia',       name: 'Цирконий',         price: 300000 },
  GOLD:           { id: 'gold',           name: 'Золото',           price: 500000 },
});

export const MATERIAL_LIST = Object.freeze(
  Object.values(MATERIALS),
);

export const MATERIAL_LABELS = Object.freeze(
  Object.fromEntries(MATERIAL_LIST.map((m) => [m.id, m.name])),
);

// =============================================================================
// FDI tooth numbering — international standard
// =============================================================================
export const ADULT_TEETH = Object.freeze({
  upperRight: [18, 17, 16, 15, 14, 13, 12, 11],
  upperLeft:  [21, 22, 23, 24, 25, 26, 27, 28],
  lowerLeft:  [38, 37, 36, 35, 34, 33, 32, 31],
  lowerRight: [41, 42, 43, 44, 45, 46, 47, 48],
});

export const DECIDUOUS_TEETH = Object.freeze({
  upperRight: [55, 54, 53, 52, 51],
  upperLeft:  [61, 62, 63, 64, 65],
  lowerLeft:  [75, 74, 73, 72, 71],
  lowerRight: [81, 82, 83, 84, 85],
});

// Human-readable tooth names keyed by FDI base number (1x = upper right,
// 2x = upper left, 3x = lower left, 4x = lower right). Name is the same
// for any quadrant — only the FDI prefix differs.
export const TOOTH_NAMES_BY_POSITION = Object.freeze({
  1: 'Центральный резец',
  2: 'Боковой резец',
  3: 'Клык',
  4: 'Первый премоляр',
  5: 'Второй премоляр',
  6: 'Первый моляр',
  7: 'Второй моляр',
  8: 'Третий моляр (зуб мудрости)',
});

/**
 * Resolve a human-readable name for a tooth by its FDI number.
 * Falls back to `Зуб №{number}` for unknown positions (e.g. deciduous teeth).
 */
export const getToothName = (fdiNumber) => {
  const position = parseInt(String(fdiNumber).slice(-1), 10);
  return TOOTH_NAMES_BY_POSITION[position] || `Зуб №${fdiNumber}`;
};

/**
 * Resolve the quadrant (1-4) of an FDI tooth number.
 * 1 = upper right, 2 = upper left, 3 = lower left, 4 = lower right.
 */
export const getToothQuadrant = (fdiNumber) =>
  parseInt(String(fdiNumber).slice(0, -1), 10);

// =============================================================================
// Currency helpers
// =============================================================================
export const DENTAL_CURRENCY_SUFFIX = 'сум';

export const formatDentalPrice = (amount) => {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return '0';
  }
  return new Intl.NumberFormat('ru-RU').format(amount);
};

// Compact format for buttons/lists: "150k сум" instead of "150 000 сум"
export const formatDentalPriceCompact = (amount) => {
  if (!amount) return `0 ${DENTAL_CURRENCY_SUFFIX}`;
  const kValue = Math.round(amount / 1000);
  return `${kValue}k ${DENTAL_CURRENCY_SUFFIX}`;
};

// =============================================================================
// Aggregate helpers
// =============================================================================
/**
 * Compute the total price for a tooth given its procedures + material.
 * Pure function, used by ToothModal.
 */
export const computeToothTotalPrice = ({ procedures = [], materialId = '' }) => {
  const proceduresTotal = procedures.reduce(
    (sum, proc) => sum + (proc.price || 0),
    0,
  );
  const material = MATERIALS[materialId?.toUpperCase?.()];
  const materialPrice = material ? material.price : 0;
  return proceduresTotal + materialPrice;
};

export default {
  TOOTH_STATUS,
  TOOTH_STATUS_LIST,
  TOOTH_STATUS_COLORS,
  TOOTH_STATUS_LABELS,
  TOOTH_PROCEDURES,
  TOOTH_PROCEDURE_LIST,
  PROSTHETIC_PROCEDURE_IDS,
  isProstheticProcedure,
  MATERIALS,
  MATERIAL_LIST,
  MATERIAL_LABELS,
  ADULT_TEETH,
  DECIDUOUS_TEETH,
  TOOTH_NAMES_BY_POSITION,
  getToothName,
  getToothQuadrant,
  DENTAL_CURRENCY_SUFFIX,
  formatDentalPrice,
  formatDentalPriceCompact,
  computeToothTotalPrice,
};
