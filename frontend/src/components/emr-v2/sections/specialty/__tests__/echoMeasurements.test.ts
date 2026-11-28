import { describe, expect, it } from 'vitest';
import { echoMeasurementFacts, normalizeEchoForEditor, selectEchoMeasurements } from '@/utils/echoMeasurements';

describe('echo measurement compatibility', () => {
  it('reads nested measurements and preserves a zero without requiring a conclusion', () => {
    const view = selectEchoMeasurements({
      leftVentricle: { esd: '32,5', ef: 0 },
      atria: { la: '36' },
      valves: { aortic: { peak_velocity: '1,2' } },
    });
    expect(view).toEqual({
      edd: '', esd: '32,5', ef: '0', la: '36', aorticPeakVelocity: '1,2', conclusion: '',
    });
  });

  it('uses the old shape only when the corresponding nested value is absent', () => {
    const old = { edd: 44, ef: '61', leftVentricle: { ef: '' }, conclusion: 'SYNTHETIC' };
    expect(normalizeEchoForEditor(old).leftVentricle).toEqual({ edd: '44', esd: '', ef: '' });
    expect(selectEchoMeasurements({ conclusion: 'SYNTHETIC' }).conclusion).toBe('SYNTHETIC');
  });

  it('represents a decimal measurement with its method, date and visit without fabricating missing values', () => {
    const facts = echoMeasurementFacts({
      leftVentricle: { ef: '60,5', esd: '' },
      measurement_metadata: { ef_method: 'SYNTHETIC method', measured_at: '2026-11-23', source_visit_id: 7 },
    });
    expect(facts).toEqual([{
      key: 'ef', value: 60.5, unit: '%', method: 'SYNTHETIC method',
      measuredAt: '2026-11-23', recordedAt: null, sourceVisitId: 7, definitionVersion: null,
    }]);
  });
});
