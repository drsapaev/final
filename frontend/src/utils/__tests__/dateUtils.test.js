import { describe, expect, it } from 'vitest';

import {
  formatRegistrarDate,
  formatRegistrarTime,
  getRegistrarTimestampDisplay,
  parseRegistrarTimestamp,
  REGISTRAR_TIME_ZONE,
} from '../dateUtils';

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

  it('formats UTC timestamps in clinic local time', () => {
    expect(formatRegistrarDate('2026-05-31T19:00:00Z')).toBe('01.06.2026');
    expect(formatRegistrarTime('2026-05-31T19:00:00Z')).toBe('00:00');
  });

  it('reports changed timestamps separately from queue time', () => {
    const display = getRegistrarTimestampDisplay({
      queue_time: '2026-05-31T09:15:00+05:00',
      updated_at: '2026-05-31T09:45:00+05:00',
    });

    expect(display.primaryLabel).toBe('Очередь');
    expect(display.primaryTime).toBe('09:15:00');
    expect(display.showChanged).toBe(true);
    expect(display.changedTime).toBe('09:45:00');
  });

  it('honors backend display_time_kind when queue_time is only a fallback value', () => {
    const display = getRegistrarTimestampDisplay({
      display_time_kind: 'created_at',
      queue_time: '2026-06-02T00:28:48+05:00',
      created_at: '2026-06-02T00:28:48+05:00',
    });

    expect(display.primaryKind).toBe('created_at');
    expect(display.primaryLabel).toBe('Создано');
    expect(display.primaryDate).toBe('02.06.2026');
    expect(display.primaryTime).toBe('00:28:48');
  });

  it('does not show changed timestamp for immediate post-create system updates', () => {
    const display = getRegistrarTimestampDisplay({
      display_time_kind: 'created_at',
      created_at: '2026-06-02T00:28:48+05:00',
      updated_at: '2026-06-02T00:28:54+05:00',
    });

    expect(display.showChanged).toBe(false);
    expect(display.changedDate).toBe('');
    expect(display.changedTime).toBe('');
  });
});
