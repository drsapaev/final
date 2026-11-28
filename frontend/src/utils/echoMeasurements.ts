function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '';
  return typeof value === 'string' ? value.trim() : '';
}

export const ADULT_TTE_MEASUREMENTS = {
  lvef: { unit: '%', group: 'core' },
  lvedv: { unit: 'mL', group: 'core' },
  lvesv: { unit: 'mL', group: 'core' },
  lavi: { unit: 'mL/m²', group: 'core' },
  lvedd: { unit: 'cm', group: 'extended' },
  lvesd: { unit: 'cm', group: 'extended' },
  ivsd: { unit: 'cm', group: 'extended' },
  pwd: { unit: 'cm', group: 'extended' },
  lvedvi: { unit: 'mL/m²', group: 'extended' },
  lvesvi: { unit: 'mL/m²', group: 'extended' },
  rv_basal_diameter: { unit: 'cm', group: 'extended' },
  tapse: { unit: 'cm', group: 'extended' },
  rv_s_prime: { unit: 'cm/s', group: 'extended' },
  rv_fac: { unit: '%', group: 'extended' },
  aov_vmax: { unit: 'm/s', group: 'extended' },
  aov_mean_gradient: { unit: 'mmHg', group: 'extended' },
  ava_continuity: { unit: 'cm²', group: 'extended' },
} as const;

export type AdultTteMeasurementKey = keyof typeof ADULT_TTE_MEASUREMENTS;
export const ADULT_TTE_MEASUREMENT_KEYS = Object.keys(ADULT_TTE_MEASUREMENTS) as AdultTteMeasurementKey[];
export const ADULT_TTE_EF_METHODS = [
  'biplane_simpson_2d', 'volumetric_3d', 'visual_estimate', 'linear_2d', 'other',
] as const;
export type AdultTteEfMethod = typeof ADULT_TTE_EF_METHODS[number];

export function parseAdultTteMeasurement(value: unknown): number | null {
  if (typeof value === 'string' && /^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(value.trim())) {
    value = Number(value.trim().replace(',', '.'));
  }
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}

/** Read only explicitly entered values in the adult TTE definition. */
export function echoAdultTteFacts(source: unknown) {
  const adultTte = record(record(source).adult_tte);
  if (adultTte.version !== 2) return [];
  const measurements = record(adultTte.measurements);
  const method = ADULT_TTE_EF_METHODS.find(code => code === adultTte.ef_method) ?? null;
  const sourceVisitId = adultTte.source_visit_id;

  return ADULT_TTE_MEASUREMENT_KEYS.flatMap(key => {
    const fact = record(measurements[key]);
    const { unit } = ADULT_TTE_MEASUREMENTS[key];
    if (typeof fact.value !== 'number' || parseAdultTteMeasurement(fact.value) === null || fact.unit !== unit) return [];
    return [{
      key, value: fact.value, unit, methodCode: key === 'lvef' ? method : null,
      measuredAt: text(adultTte.measured_at) || null,
      recordedAt: text(adultTte.recorded_at) || null,
      sourceVisitId: typeof sourceVisitId === 'string' || typeof sourceVisitId === 'number' ? sourceVisitId : null,
      definitionVersion: 2 as const,
    }];
  });
}

/** The nested value wins even when a physician explicitly cleared it. */
export function selectEchoMeasurements(source: unknown) {
  const echo = record(source);
  const leftVentricle = record(echo.leftVentricle);
  const atria = record(echo.atria);
  const aortic = record(record(echo.valves).aortic);
  return {
    edd: text(leftVentricle.edd ?? echo.edd),
    esd: text(leftVentricle.esd ?? echo.esd),
    ef: text(leftVentricle.ef ?? echo.ef),
    la: text(atria.la ?? echo.la),
    aorticPeakVelocity: text(aortic.peak_velocity ?? record(echo.aortic).peak_velocity),
    conclusion: text(echo.conclusion),
  };
}

/** Hydrate the canonical form from both document generations, retaining extra fields. */
export function normalizeEchoForEditor(source: unknown): Record<string, unknown> {
  const echo = record(source);
  const { edd, esd, ef, la, aorticPeakVelocity } = selectEchoMeasurements(echo);
  const valves = record(echo.valves);
  return {
    ...echo,
    leftVentricle: { ...record(echo.leftVentricle), edd, esd, ef },
    atria: { ...record(echo.atria), la },
    valves: {
      ...valves,
      aortic: { ...record(echo.aortic), ...record(valves.aortic), peak_velocity: aorticPeakVelocity },
    },
  };
}

export function echoMeasurementFacts(source: unknown) {
  const echo = record(source);
  const metadata = record(echo.measurement_metadata);
  const selected = selectEchoMeasurements(echo);
  const units = { edd: 'mm', esd: 'mm', ef: '%', la: 'mm', aorticPeakVelocity: 'm/s' } as const;
  return (Object.keys(units) as Array<keyof typeof units>).flatMap(key => {
    const raw = selected[key];
    const value = Number(raw.replace(',', '.'));
    if (!raw || !Number.isFinite(value)) return [];
    return [{
      key, value, unit: units[key],
      method: key === 'ef' ? text(metadata.ef_method) || null : null,
      measuredAt: text(metadata.measured_at) || null,
      recordedAt: text(metadata.recorded_at) || null,
      sourceVisitId: metadata.source_visit_id ?? null,
      definitionVersion: metadata.definition_version ?? null,
    }];
  });
}
