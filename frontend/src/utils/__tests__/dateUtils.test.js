import { describe, expect, it } from 'vitest';

import { parseRegistrarTimestamp, REGISTRAR_TIME_ZONE } from '../dateUtils';

describe('parseRegistrarTimestamp', () => {
  it('keeps timezone-aware timestamps stable', () => {
    const parsed = parseRegistrarTimestamp('2026-04-16T09:30:00+05:00');

    expect(parsed).not.toBeNull();
    expect(parsed.toISOString()).toBe('2026-04-16T04:30:00.000Z');
  });

  it('treats naive timestamps as Asia/Tashkent local time', () => {
    const parsed = parseRegistrarTimestamp('2026-04-16T09:30:00');

    expect(parsed).not.toBeNull();
    expect(parsed.toISOString()).toBe('2026-04-16T04:30:00.000Z');
  });

  it('exposes the clinic timezone constant used for rendering', () => {
    expect(REGISTRAR_TIME_ZONE).toBe('Asia/Tashkent');
  });
});

