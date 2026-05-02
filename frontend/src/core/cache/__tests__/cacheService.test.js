import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { cacheService } from '../cacheService';
import { CACHE_TAGS } from '../cacheConfig';

describe('cacheService', () => {
  beforeEach(() => {
    cacheService.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('stores and retrieves values', () => {
    cacheService.set('test:key', { ok: true }, { ttl: 1000 });
    expect(cacheService.get('test:key')).toEqual({ ok: true });
  });

  it('expires values after TTL', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-02-06T00:00:00Z'));

    cacheService.set('ttl:key', 'value', { ttl: 10 });
    expect(cacheService.get('ttl:key')).toBe('value');

    vi.advanceTimersByTime(11);
    expect(cacheService.get('ttl:key')).toBeNull();
  });

  it('invalidates by visit tag', () => {
    cacheService.set('visit:key', 'value', {
      ttl: 1000,
      tags: [CACHE_TAGS.visit(123)],
    });
    expect(cacheService.get('visit:key')).toBe('value');

    cacheService.invalidateByVisit(123);
    expect(cacheService.get('visit:key')).toBeNull();
  });

  it('invalidates by patient tag', () => {
    cacheService.set('patient:key', 'value', {
      ttl: 1000,
      tags: [CACHE_TAGS.patient(456)],
    });
    expect(cacheService.get('patient:key')).toBe('value');

    cacheService.invalidateByPatient(456);
    expect(cacheService.get('patient:key')).toBeNull();
  });
});
