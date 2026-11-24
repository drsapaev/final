import { describe, expect, it } from 'vitest';
import { normalizeEchoForEditor, selectEchoMeasurements } from '@/utils/echoMeasurements';

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
});
