function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown): string {
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '';
  return typeof value === 'string' ? value.trim() : '';
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
